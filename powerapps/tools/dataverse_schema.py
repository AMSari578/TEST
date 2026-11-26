#!/usr/bin/env python3
"""
WBL Training Management System - Dataverse schema tool.

Reads powerapps/dataverse/schema.json and can:

  doc     Generate a Markdown data dictionary (docs/01-data-model.md).
  deploy  Create the solution, global choices, tables, columns and lookups
          in a Dataverse environment through the Web API.
  seed    Load the CSV files in powerapps/data/ into the tables.

Examples
  python3 dataverse_schema.py doc
  python3 dataverse_schema.py deploy --env https://yourorg.crm4.dynamics.com --dry-run
  python3 dataverse_schema.py deploy --env https://yourorg.crm4.dynamics.com --arabic
  python3 dataverse_schema.py seed   --env https://yourorg.crm4.dynamics.com

Authentication (pick one)
  * Set DATAVERSE_TOKEN to a bearer token, e.g. from the Azure CLI:
      az account get-access-token --resource https://yourorg.crm4.dynamics.com --query accessToken -o tsv
  * Or `pip install msal` and the script signs you in with a device code.

The script is idempotent: anything that already exists is skipped.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "dataverse" / "schema.json"
DATA_DIR = ROOT / "data"
DOC_OUT = ROOT / "docs" / "01-data-model.md"

EN, AR = 1033, 1025
# Public client id used by Microsoft's Dataverse samples. Override with --client-id.
SAMPLE_CLIENT_ID = "51f81489-12ee-4a9e-aaae-a2591f45987d"

# Seed order respects lookups (parents first).
SEED_ORDER = [
    "wbl_department", "wbl_track", "wbl_skill", "wbl_trainingcalendar",
    "wbl_roleprofileitem", "wbl_flagrule", "wbl_riskrule", "wbl_uistring",
]


def load_schema() -> dict:
    with open(SCHEMA, encoding="utf-8") as f:
        return json.load(f)


def schema_name(logical: str) -> str:
    """wbl_engineerid -> wbl_EngineerId (schema names are case-sensitive in Dataverse)."""
    prefix, rest = logical.split("_", 1)
    if rest.endswith("id") and len(rest) > 2:
        return f"{prefix}_{rest[:-2].capitalize()}Id"
    return f"{prefix}_{rest.capitalize()}"


# --------------------------------------------------------------------------- doc

TYPE_LABEL = {
    "text": "Text", "memo": "Multiline text", "int": "Whole number", "decimal": "Decimal",
    "bool": "Yes/No", "date": "Date only", "datetime": "Date and time", "choice": "Choice",
    "lookup": "Lookup", "url": "URL", "email": "Email", "file": "File",
}


def cmd_doc(schema: dict, _args) -> None:
    choices = {c["name"]: c for c in schema["choices"]}
    out = [
        "# 01 - Data Model (Dataverse) / نموذج البيانات",
        "",
        "> Generated from `powerapps/dataverse/schema.json` by `tools/dataverse_schema.py doc`. "
        "Do not edit by hand; edit the JSON and run the command again.",
        "",
        f"Publisher prefix: `{schema['publisherPrefix']}_`  |  Solution: `{schema['solutionUniqueName']}`",
        "",
        "## Tables / الجداول",
        "",
        "| Table | الجدول | Logical name | Ownership | Audit | Requirements |",
        "|---|---|---|---|---|---|",
    ]
    for t in schema["tables"]:
        out.append(
            f"| {t['enPlural']} | {t['arPlural']} | `{t['name']}` | {t['ownership'].replace('Owned', '')} "
            f"| {'Yes' if t.get('audit') else '-'} | {', '.join(t.get('br', []))} |"
        )
    out += ["", "## Relationships / العلاقات", "", "```mermaid", "erDiagram"]
    for t in schema["tables"]:
        for c in t["columns"]:
            if c["type"] == "lookup":
                parent = c["target"].replace("wbl_", "").upper()
                child = t["name"].replace("wbl_", "").upper()
                out.append(f'    {parent} ||--o{{ {child} : "{c["name"]}"')
    out += ["```", ""]

    for t in schema["tables"]:
        out += [
            f"## {t['en']} / {t['ar']} (`{t['name']}`)",
            "",
            f"Ownership: **{t['ownership']}**. Audit: **{'on' if t.get('audit') else 'off'}**. "
            f"Covers: {', '.join(t.get('br', []))}.",
            "",
            "| Column | العمود | Logical name | Type | Required | Notes |",
            "|---|---|---|---|---|---|",
        ]
        auto = f"autonumber `{t['autonumber']}`" if t.get("autonumber") else "primary name"
        out.append(f"| {t['primary'][0]} | {t['primary'][1]} | `wbl_name` | Text | Yes | {auto} |")
        for c in t["columns"]:
            note = ""
            if c["type"] == "lookup":
                note = f"→ `{c['target']}`"
            elif c["type"] == "choice":
                note = f"global choice `{c['choice']}`"
            elif c["type"] in ("int", "decimal") and "min" in c:
                note = f"{c['min']} … {c['max']}"
            out.append(
                f"| {c['en']} | {c['ar']} | `{c['name']}` | {TYPE_LABEL[c['type']]} "
                f"| {'Yes' if c.get('required') else ''} | {note} |"
            )
        out.append("")

    out += ["## Global choices / الخيارات", "", "| Choice | الخيار | Name | Options (EN / AR) |", "|---|---|---|---|"]
    for c in choices.values():
        opts = "; ".join(f"{en} / {ar}" for en, ar in c["options"])
        out.append(f"| {c['en']} | {c['ar']} | `{c['name']}` | {opts} |")
    out.append("")

    DOC_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOC_OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {DOC_OUT.relative_to(ROOT.parent)}")


# ------------------------------------------------------------------- web api

class Dataverse:
    def __init__(self, env: str, token: str | None, dry_run: bool, solution: str):
        self.base = env.rstrip("/") + "/api/data/v9.2/"
        self.dry_run = dry_run
        self.solution = solution
        self.token = token
        self.session = None
        if not dry_run:
            import requests  # noqa: WPS433 (imported lazily so `doc` and dry-run need no deps)
            self.session = requests.Session()
            self.session.headers.update({
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
                "MSCRM.SolutionUniqueName": solution,
            })

    def get(self, path: str):
        if self.dry_run:
            return None
        r = self.session.get(self.base + path)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict, what: str):
        if self.dry_run:
            print(f"[dry-run] POST {path}  ({what})")
            if os.environ.get("WBL_VERBOSE"):
                print(json.dumps(body, ensure_ascii=False, indent=2))
            return None
        for attempt in range(5):
            r = self.session.post(self.base + path, data=json.dumps(body, ensure_ascii=False).encode("utf-8"))
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"{what}: HTTP {r.status_code} {r.text[:800]}")
            print(f"created  {what}")
            return r.headers.get("OData-EntityId")
        raise RuntimeError(f"{what}: gave up after retries")


def label(en: str, ar: str | None, arabic: bool) -> dict:
    labels = [{"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": en, "LanguageCode": EN}]
    if arabic and ar:
        labels.append({"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": ar, "LanguageCode": AR})
    return {"@odata.type": "Microsoft.Dynamics.CRM.Label", "LocalizedLabels": labels}


def required(flag: bool) -> dict:
    return {
        "Value": "ApplicationRequired" if flag else "None",
        "CanBeChanged": True,
        "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings",
    }


def column_body(c: dict, arabic: bool, choice_ids: dict) -> dict:
    base = {
        "SchemaName": schema_name(c["name"]),
        "DisplayName": label(c["en"], c.get("ar"), arabic),
        "RequiredLevel": required(c.get("required", False)),
    }
    t = c["type"]
    if t in ("text", "url", "email"):
        fmt = {"text": "Text", "url": "Url", "email": "Email"}[t]
        base.update({"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
                     "MaxLength": c.get("max", 200 if t == "text" else 500), "FormatName": {"Value": fmt}})
    elif t == "memo":
        base.update({"@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata",
                     "MaxLength": c.get("max", 4000), "Format": "TextArea"})
    elif t == "int":
        base.update({"@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata",
                     "MinValue": c.get("min", -2147483648), "MaxValue": c.get("max", 2147483647), "Format": "None"})
    elif t == "decimal":
        base.update({"@odata.type": "Microsoft.Dynamics.CRM.DecimalAttributeMetadata",
                     "MinValue": c.get("min", -100000), "MaxValue": c.get("max", 100000), "Precision": 2})
    elif t == "bool":
        base.update({
            "@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata",
            "DefaultValue": False,
            "OptionSet": {
                "@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                "TrueOption": {"Value": 1, "Label": label("Yes", "نعم", arabic)},
                "FalseOption": {"Value": 0, "Label": label("No", "لا", arabic)},
                "OptionSetType": "Boolean",
            },
        })
    elif t in ("date", "datetime"):
        base.update({"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
                     "Format": "DateOnly" if t == "date" else "DateAndTime",
                     "DateTimeBehavior": {"Value": "DateOnly" if t == "date" else "UserLocal"}})
    elif t == "choice":
        base.update({"@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata",
                     "GlobalOptionSet@odata.bind": f"/GlobalOptionSetDefinitions({choice_ids.get(c['choice'], c['choice'])})"})
    elif t == "file":
        base.update({"@odata.type": "Microsoft.Dynamics.CRM.FileAttributeMetadata", "MaxSizeInKB": 10240})
    else:
        raise ValueError(f"Unsupported column type {t} on {c['name']}")
    return base


def get_token(env: str, client_id: str) -> str:
    token = os.environ.get("DATAVERSE_TOKEN")
    if token:
        return token
    try:
        import msal
    except ImportError:
        sys.exit("Set DATAVERSE_TOKEN or run `pip install msal requests`.")
    app = msal.PublicClientApplication(client_id, authority="https://login.microsoftonline.com/organizations")
    flow = app.initiate_device_flow(scopes=[env.rstrip("/") + "/user_impersonation"])
    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        sys.exit(f"Sign-in failed: {result.get('error_description')}")
    return result["access_token"]


def ensure_solution(dv: Dataverse, schema: dict) -> None:
    prefix = schema["publisherPrefix"]
    pub = dv.get(f"publishers?$select=publisherid&$filter=customizationprefix eq '{prefix}'")
    pub_id = pub["value"][0]["publisherid"] if pub and pub["value"] else None
    if not pub_id and not dv.dry_run:
        dv.post("publishers", {
            "uniquename": "ntgwbl", "friendlyname": "NTG WBL", "customizationprefix": prefix,
            "customizationoptionvalueprefix": 18420,
        }, "publisher ntgwbl")
        pub_id = dv.get(f"publishers?$select=publisherid&$filter=customizationprefix eq '{prefix}'")["value"][0]["publisherid"]
    elif dv.dry_run:
        print(f"[dry-run] ensure publisher with prefix '{prefix}'")
    sol = dv.get(f"solutions?$select=solutionid&$filter=uniquename eq '{schema['solutionUniqueName']}'")
    if not (sol and sol["value"]):
        dv.post("solutions", {
            "uniquename": schema["solutionUniqueName"], "friendlyname": schema["solutionDisplayName"],
            "version": "1.0.0.0", "publisherid@odata.bind": f"/publishers({pub_id})",
        }, f"solution {schema['solutionUniqueName']}")


def cmd_deploy(schema: dict, args) -> None:
    token = None if args.dry_run else get_token(args.env, args.client_id)
    dv = Dataverse(args.env, token, args.dry_run, schema["solutionUniqueName"])
    ensure_solution(dv, schema)

    # 1. Global choices
    choice_ids: dict[str, str] = {}
    for c in schema["choices"]:
        existing = dv.get(f"GlobalOptionSetDefinitions(Name='{c['name']}')")
        if existing:
            choice_ids[c["name"]] = existing["MetadataId"]
            print(f"exists   choice {c['name']}")
            continue
        body = {
            "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
            "Name": c["name"], "DisplayName": label(c["en"], c["ar"], args.arabic),
            "OptionSetType": "Picklist", "IsGlobal": True,
            "Options": [{"Label": label(en, ar, args.arabic)} for en, ar in c["options"]],
        }
        dv.post("GlobalOptionSetDefinitions", body, f"choice {c['name']}")
        if not dv.dry_run:
            choice_ids[c["name"]] = dv.get(f"GlobalOptionSetDefinitions(Name='{c['name']}')")["MetadataId"]

    # 2. Tables with primary name column
    for t in schema["tables"]:
        if dv.get(f"EntityDefinitions(LogicalName='{t['name']}')?$select=LogicalName"):
            print(f"exists   table {t['name']}")
            continue
        primary = {
            "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
            "SchemaName": "wbl_Name", "IsPrimaryName": True, "MaxLength": 200,
            "FormatName": {"Value": "Text"},
            "RequiredLevel": required(not t.get("autonumber")),
            "DisplayName": label(t["primary"][0], t["primary"][1], args.arabic),
        }
        if t.get("autonumber"):
            primary["AutoNumberFormat"] = t["autonumber"]
        body = {
            "@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
            "SchemaName": schema_name(t["name"]),
            "DisplayName": label(t["en"], t["ar"], args.arabic),
            "DisplayCollectionName": label(t["enPlural"], t["arPlural"], args.arabic),
            "Description": label(f"WBL TMS - {t['en']}", None, False),
            "OwnershipType": t["ownership"],
            "IsActivity": False, "HasActivities": False, "HasNotes": True,
            "IsAuditEnabled": {"Value": bool(t.get("audit")), "CanBeChanged": True,
                               "ManagedPropertyLogicalName": "canmodifyauditsettings"},
            "Attributes": [primary],
        }
        dv.post("EntityDefinitions", body, f"table {t['name']}")

    # 3. Columns (non-lookup)
    for t in schema["tables"]:
        for c in t["columns"]:
            if c["type"] == "lookup":
                continue
            if dv.get(f"EntityDefinitions(LogicalName='{t['name']}')/Attributes(LogicalName='{c['name']}')?$select=LogicalName"):
                continue
            dv.post(f"EntityDefinitions(LogicalName='{t['name']}')/Attributes",
                    column_body(c, args.arabic, choice_ids), f"column {t['name']}.{c['name']}")

    # 4. Lookups (one-to-many relationships)
    for t in schema["tables"]:
        for c in t["columns"]:
            if c["type"] != "lookup":
                continue
            if dv.get(f"EntityDefinitions(LogicalName='{t['name']}')/Attributes(LogicalName='{c['name']}')?$select=LogicalName"):
                continue
            rel = f"wbl_{c['target'].replace('wbl_', '')}_{t['name'].replace('wbl_', '')}_{c['name'].replace('wbl_', '')}"
            body = {
                "@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
                "SchemaName": rel[:100],
                "ReferencedEntity": c["target"],
                "ReferencingEntity": t["name"],
                "CascadeConfiguration": {"Assign": "NoCascade", "Delete": "RemoveLink", "Merge": "NoCascade",
                                         "Reparent": "NoCascade", "Share": "NoCascade", "Unshare": "NoCascade"},
                "Lookup": {
                    "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
                    "SchemaName": schema_name(c["name"]),
                    "DisplayName": label(c["en"], c.get("ar"), args.arabic),
                    "RequiredLevel": required(c.get("required", False)),
                },
            }
            dv.post("RelationshipDefinitions", body, f"lookup {t['name']}.{c['name']} -> {c['target']}")

    dv.post("PublishAllXml", {}, "publish all customizations")
    print("Done.")


# ---------------------------------------------------------------------- seed

def cmd_seed(schema: dict, args) -> None:
    token = None if args.dry_run else get_token(args.env, args.client_id)
    dv = Dataverse(args.env, token, args.dry_run, schema["solutionUniqueName"])
    tables = {t["name"]: t for t in schema["tables"]}
    choice_values: dict[str, dict[str, int]] = {}

    def choice_value(choice: str, text: str) -> int | None:
        if dv.dry_run:
            return 0
        if choice not in choice_values:
            meta = dv.get(f"GlobalOptionSetDefinitions(Name='{choice}')")
            choice_values[choice] = {
                o["Label"]["LocalizedLabels"][0]["Label"]: o["Value"] for o in meta["Options"]
            }
        return choice_values[choice].get(text)

    entity_sets: dict[str, str] = {}

    def entity_set(table: str) -> str:
        # Dataverse pluralises collection names (e.g. ...activity -> ...activities), so ask it.
        if dv.dry_run:
            return table + "s"
        if table not in entity_sets:
            entity_sets[table] = dv.get(f"EntityDefinitions(LogicalName='{table}')?$select=EntitySetName")["EntitySetName"]
        return entity_sets[table]

    def lookup_id(target: str, name: str) -> str | None:
        if dv.dry_run:
            return None
        safe = name.replace("'", "''")
        res = dv.get(f"{entity_set(target)}?$select={target}id&$filter=wbl_name eq '{safe}'")
        return res["value"][0][f"{target}id"] if res and res["value"] else None

    for table in SEED_ORDER:
        path = DATA_DIR / f"{table}.csv"
        if not path.exists():
            continue
        cols = {c["name"]: c for c in tables[table]["columns"]}
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if lookup_id(table, row["wbl_name"]):
                    print(f"exists   {table}: {row['wbl_name']}")
                    continue
                body: dict = {"wbl_name": row["wbl_name"]}
                for key, raw in row.items():
                    if key == "wbl_name" or raw is None or raw.strip() == "":
                        continue
                    c = cols[key]
                    if c["type"] == "lookup":
                        ref = lookup_id(c["target"], raw) or ("<id of " + raw + ">" if dv.dry_run else None)
                        if not ref:
                            raise RuntimeError(f"{table}.{key}: no {c['target']} named '{raw}'")
                        body[f"{schema_name(key)}@odata.bind"] = f"/{entity_set(c['target'])}({ref})"
                    elif c["type"] == "choice":
                        v = choice_value(c["choice"], raw)
                        if v is None:
                            raise RuntimeError(f"{table}.{key}: '{raw}' is not an option of {c['choice']}")
                        body[key] = v
                    elif c["type"] == "bool":
                        body[key] = raw.strip().lower() in ("1", "true", "yes", "y")
                    elif c["type"] == "int":
                        body[key] = int(raw)
                    elif c["type"] == "decimal":
                        body[key] = float(raw)
                    else:
                        body[key] = raw
                dv.post(entity_set(table), body, f"row {table}: {row['wbl_name']}")
    print("Seed done.")


# ---------------------------------------------------------------------- main

def validate(schema: dict) -> None:
    """Basic consistency checks so mistakes surface before calling the API."""
    choices = {c["name"] for c in schema["choices"]}
    tables = {t["name"] for t in schema["tables"]} | {"systemuser"}
    errors = []
    for t in schema["tables"]:
        seen = set()
        for c in t["columns"]:
            if c["name"] in seen:
                errors.append(f"{t['name']}: duplicate column {c['name']}")
            seen.add(c["name"])
            if not c["name"].startswith("wbl_"):
                errors.append(f"{t['name']}.{c['name']}: missing prefix")
            if c["type"] == "choice" and c["choice"] not in choices:
                errors.append(f"{t['name']}.{c['name']}: unknown choice {c['choice']}")
            if c["type"] == "lookup" and c["target"] not in tables:
                errors.append(f"{t['name']}.{c['name']}: unknown table {c['target']}")
            if c["type"] == "lookup" and not c["name"].endswith("id"):
                errors.append(f"{t['name']}.{c['name']}: lookup names must end with 'id'")
    for table in SEED_ORDER:
        path = DATA_DIR / f"{table}.csv"
        if path.exists():
            t = next(x for x in schema["tables"] if x["name"] == table)
            allowed = {"wbl_name"} | {c["name"] for c in t["columns"]}
            with open(path, encoding="utf-8-sig", newline="") as f:
                header = next(csv.reader(f))
            for h in header:
                if h not in allowed:
                    errors.append(f"data/{table}.csv: unknown column {h}")
    if errors:
        sys.exit("Schema errors:\n  " + "\n  ".join(errors))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doc", help="generate docs/01-data-model.md")
    sub.add_parser("validate", help="check schema.json and data/*.csv")
    for name in ("deploy", "seed"):
        sp = sub.add_parser(name)
        sp.add_argument("--env", required=True, help="environment URL, e.g. https://yourorg.crm4.dynamics.com")
        sp.add_argument("--dry-run", action="store_true", help="print what would be created")
        sp.add_argument("--arabic", action="store_true",
                        help="also write Arabic (1025) labels; enable the Arabic language in the environment first")
        sp.add_argument("--client-id", default=SAMPLE_CLIENT_ID)
    args = p.parse_args()
    schema = load_schema()
    validate(schema)
    if args.cmd == "validate":
        print("Schema OK")
        return
    {"doc": cmd_doc, "deploy": cmd_deploy, "seed": cmd_seed}[args.cmd](schema, args)


if __name__ == "__main__":
    main()
