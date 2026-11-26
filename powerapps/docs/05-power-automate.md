# 05 - تدفقات Power Automate

كل التدفقات تُنشأ **داخل الـ Solution** (Solutions → New → Automation → Cloud flow) باستخدام
**Connection references** حتى تنتقل بين البيئات. استخدم حساب خدمة (service account) مرخّص للاتصال بـ Dataverse.

| # | التدفق | المشغّل | المتطلبات |
|---|---|---|---|
| F01 | استقبال نشاط TestFlair | HTTP request (webhook) | BR-03 |
| F02 | محرك فحص القواعد | Recurrence يومياً 07:00 | BR-04، BR-10 |
| F03 | استقبال نتائج مراجعة AI | HTTP request (webhook) | BR-04، BR-05 |
| F04 | إشعار المشرف (Teams Adaptive Card) | Dataverse: Flag added | BR-06، BO-06 |
| F05 | سجل قرارات التنبيهات | Dataverse: Flag modified (Flag Status) | BR-11، US-05 #3 |
| F06 | استيراد الحضور | Recurrence / بعد نهاية الجلسة | BR-12 |
| F07 | استيراد درجات Kahoot | ملف في SharePoint/OneDrive | BR-12، BR-14 |
| F08 | إصدار الشهادة وكشف الجلسات | Dataverse: Attendance modified (Confirmed) | BR-13، US-03 |
| F09 | حساب حالة المخاطر | Recurrence ليلياً | BR-16، BR-08 |
| F10 | تنبيه جاهزية أدوات التدريب | Recurrence يومياً | BR-15، US-17 #3 |
| F11 | ملكية السجلات وصلاحيات المدرب + حارس "سير العمل الكامل" | Dataverse: added (عدة جداول) | الأمان، US-13 #6 |
| F12 | قائمة حضور الجلسة + بوابة NDA | Dataverse: Session added | قيد NDA |
| F13 | ضبط اعتماد الكفاءة | Dataverse: Competency Approval added | US-07 #5، #8 |

---

## F01 — استقبال نشاط TestFlair (commits / builds / test runs)

**Trigger:** *When an HTTP request is received* (Premium). الـ JSON schema في
[`../integrations/testflair-webhook.schema.json`](../integrations/testflair-webhook.schema.json) (`activity`).
احمِ الـ URL: اطلب header `x-wbl-key` وقارنه بقيمة في **Environment variable** `wbl_TestFlairKey` (نوع Secret / Key Vault).

**Steps**
1. Condition: `triggerOutputs()?['headers']?['x-wbl-key']` = `wbl_TestFlairKey` — وإلا Response 401.
2. List rows — Engineers: Filter `wbl_email eq '@{triggerBody()?['engineerEmail']}'` Top 1.
3. List rows — Projects: Filter `wbl_name eq '@{triggerBody()?['projectName']}'`.
   * Condition: `wbl_clientpermitsdata` = true — وإلا Response 202 "ignored: client has not permitted" (قيد 3.3).
4. List rows — Sprints: `_wbl_projectid_value eq <project> and wbl_startdate le '@{utcNow('yyyy-MM-dd')}' and wbl_enddate ge '@{utcNow('yyyy-MM-dd')}'`.
5. List rows — Work Activities: `wbl_externalid eq '@{triggerBody()?['externalId']}'` → إن وُجد: تجاهل (منع التكرار).
6. Add a new row — Work Activities:
   * Owner = `systemusers(<engineer useraccount id>)`، Engineer، Sprint، Activity Type، Occurred On، Due Date، Result، Link، External ID، Source = TestFlair.
   * **لا تُخزن محتوى الكود** — فقط metadata ورابط.
7. Response 200.

> إن لم يدعم TestFlair الـ webhooks: اجعل التدفق Recurrence كل ساعة يستدعي TestFlair REST API عبر
> **Custom connector** (يُنشأ من OpenAPI لـ TestFlair) بنفس الخطوات 2-6.

## F02 — محرك فحص القواعد (Rule checks)

**Trigger:** Recurrence — يومياً 07:00 (Time zone: Arab Standard Time)، أيام العمل.

**Steps**
1. List rows — Flag Rules: `wbl_isactive eq true`.
2. List rows — Sprints: `wbl_sprintstatus eq <Active value>`.
3. Apply to each **Sprint** → List rows Project Assignments للمشروع → Apply to each **Engineer**:
   * Apply to each **Rule** (تخطّ القاعدة إن كان لها Track ≠ مسار المهندس):
   * **Switch** على `wbl_ruletype`:

| Rule Type | الاستعلام (List rows, Filter rows) | الشرط لإنشاء تنبيه | الدليل (Evidence) |
|---|---|---|---|
| Late commit | Work Activities: `_wbl_engineerid_value eq E and wbl_activitytype eq Commit and wbl_duedate ne null and wbl_occurredon ge <yesterday>` | أي سجل فيه `occurredon > duedate + threshold hours` (Filter array) | "Commit at {occurredon}, due {duedate}" + رابط الـ commit |
| Inactivity | Work Activities + Work Logs للمهندس في آخر N أيام عمل | العدد = 0 | "No activity since {last date}" |
| Failed build | Work Activities: Build + Result = Failed + آخر 24 ساعة | العدد ≥ threshold | قائمة الروابط |
| Failed tests | Work Activities: Test Run + Failed + Source = TestFlair + أمس | العدد ≥ threshold | قائمة الروابط |
| Missing work log | فقط إذا Tool Integration = None: Work Logs آخر N أيام عمل | العدد = 0 | "No work log for N days" |
| Absence / Late attendance | Session Attendances (فقط إن كانت القاعدة Active — معطلة افتراضياً) | ≥ threshold | الجلسات |

   * **منع التكرار:** قبل الإنشاء List rows — Flags:
     `_wbl_engineerid_value eq E and _wbl_ruleid_value eq R and _wbl_sprintid_value eq S and wbl_flagstatus ne <Dismissed> and wbl_flagstatus ne <Resolved>`
     → أنشئ فقط إن كان فارغاً.
   * Add a new row — Flags: Title = `{Rule name} - {Engineer}`، Source = Rule check، Category/Severity من القاعدة،
     Flag Status = New، Detected On = `utcNow()`، Evidence، Reason = Description القاعدة، Rule، Sprint، Engineer،
     **Owner = حساب المهندس**.

**أيام العمل:** احسب "N working days ago" بمتغير يتخطى الجمعة والسبت:
```text
// Do until counter = N: decrement date by 1 day; if dayOfWeek(date) in (5,6) don't count it
```

> لإضافة نوع قاعدة **جديد كلياً** (ليس تعديل حد): أضف خياراً إلى `Rule Type` وفرعاً في Switch — هذا هو التعديل الوحيد
> الذي يحتاج المسؤول. تعديل الحدود/التفعيل/المسار لا يحتاج أي تعديل (BR-10).

## F03 — استقبال نتائج مراجعة الذكاء الاصطناعي

وفق BRD 2.4، المراجعة في المرحلة 1 تتم **على TestFlair** (داخل NTG). TestFlair يرسل *النتيجة* فقط.

**Trigger:** HTTP request — schema `aiFinding` من ملف integrations.

**Steps**
1. تحقق من المفتاح (مثل F01).
2. ابحث عن المهندس والمشروع والسبرنت (مثل F01).
3. Add a new row — Flags:
   * Source = **AI review**، Category = Performance، Severity من الطلب (افتراضي Medium)
   * Evidence Link = `commitUrl`، Definition of Done Item = `dodItem`، Reason = `reason`، Evidence = `evidence`
   * Flag Status = New، Detected On = `utcNow()`، Owner = حساب المهندس.

**بديل داخل Power Platform (للمشاريع المحاكاة فقط):**
تدفق على *Work Activity added (Commit)* → إن كان `Project Type = Simulated` → جلب diff من Git → **AI Builder "Run a prompt"**:
```text
You are a code reviewer. Compare the commit with the Definition of Done.
Only report items of the Definition of Done that the commit does NOT meet. Do not score the engineer.
Return JSON: {"findings":[{"dodItem":"...","reason":"...","evidence":"file/line or quote"}]}
Definition of Done:
{DoD}
Commit message and diff:
{Diff}
```
ثم Apply to each finding → Add Flag (Source = AI review). **لا تستخدمه لمشاريع العملاء الحقيقية** إن كان
`Client Code Must Stay Inside NTG = Yes` (قيد 3.3 والمخاطرة "Unauthorized disclosure of code").

## F04 — إشعار المشرف في Teams

**Trigger:** Dataverse *When a row is added* — Flags.
1. Get row — Engineer (expand Supervisor) → Get user profile.
2. **Post adaptive card and wait for a response** (Teams, to the supervisor) — البطاقة تعرض العنوان، المهندس، السبب، الدليل،
   زر "Open commit"، و `Input.ChoiceSet` (Accept / Dismiss / Resolve / Escalate) و `Input.Text` للسبب
   (`isRequired` عند Dismiss يتم التحقق منه أيضاً في الخادم).
3. Condition: إن كان القرار Dismiss والسبب فارغ → أعد إرسال البطاقة برسالة خطأ.
4. Update a row — Flags: Flag Status، Decision Reason، Decided By، Decided On = `utcNow()`.

> لتقليل الإزعاج (BO-06): بدلاً من بطاقة لكل تنبيه، اجعل F04 **ملخصاً يومياً** (Recurrence 08:00) يجمع كل التنبيهات الجديدة لكل مشرف في بطاقة واحدة مع رابط للتطبيق.

## F05 — سجل قرارات التنبيهات (BR-11)

**Trigger:** *When a row is added, modified* — Flags، Change type = Modified، **Select columns** = `wbl_flagstatus`.
1. Add a new row — Flag Decisions: Title = `{Flag title} → {new status}`، Flag، New Status، Reason = Decision Reason،
   Decided By، Decided On، Owner = owner التنبيه (المهندس).
2. إن كانت الحالة **Escalated**: أرسل بريداً لمجموعة WBL-Management + الخبير.

## F06 — استيراد الحضور من NTG Connect / Teams

**الخيار A (Teams):** Trigger Recurrence كل ساعة → Training Sessions التي `Ends On` بين الآن-2س والآن و Platform = Teams →
HTTP with Microsoft Entra ID (Graph) `GET /users/{organizer}/onlineMeetings/{id}/attendanceReports` →
لكل مشارك: List Engineers بالبريد → Update/Upsert row في Session Attendances:
* Join Time = أول دخول، Minutes Late = `div(sub(ticks(joinTime), ticks(startsOn)), 600000000)` (إن > 0)
* Attendance = `Late` إن Minutes Late > `Late After (minutes)` وإلا `Present`، Attendance Source = Conference platform.

**الخيار B (NTG Connect):** إن كان يصدّر CSV: ضع الملف في مكتبة SharePoint `WBL-Imports/Attendance` →
Trigger *When a file is created* → اقرأ الصفوف (Excel table أو Parse CSV) → نفس التحديث.

**الخيار C (يدوي):** المدرب يُدخل الحضور من `scrSessions` (Attendance Source = Manual).

بعد انتهاء الاستيراد: أي مهندس مسجّل في الجلسة بدون حضور → Attendance = Absent.

## F07 — استيراد درجات Kahoot

**Trigger:** SharePoint *When a file is created in a folder* `WBL-Imports/Kahoot/<Session Title>`.
1. المدرب يصدّر النتائج من Kahoot (Excel) ويرفعها (أو يحوّلها إلى Table اسمها `Results`).
2. List rows present in a table → لكل صف: ابحث عن المهندس بالبريد أو الاسم المستعار → Update Session Attendance:
   Assessment Score % = `mul(div(correct, total), 100)`، Score Source = External service.
3. Add row — Assessment Results: Assessment Type = Standardized، External Source = "Kahoot"، Session، Skill (من إعداد الجلسة)، Score.

## F08 — إصدار الشهادة وكشف الجلسات (BR-13، US-03)

**Trigger:** Session Attendances — Modified — Select columns `wbl_isconfirmed`، Filter `wbl_isconfirmed eq true`.

**Steps**
1. Get Engineer (المسار، الدفعة/التقويم). إن كان المسار `Issues Certificate = No` → إنهاء (General Skills لا تمنح شهادة — US-03 #6).
2. List rows — Training Sessions: `_wbl_trackid_value eq <track> and _wbl_calendarid_value eq <calendar>`
   و `wbl_sessiontype ne <General Skills>` → **RequiredCount**.
   تأكد أن بينها جلسة واحدة على الأقل `Final Assessment` وإلا إنهاء.
3. List rows — Session Attendances للمهندس على هذه الجلسات بشرط `wbl_isconfirmed eq true and wbl_passed eq true` → **PassedCount**.
4. Condition: `PassedCount = RequiredCount` **و** جلسة Final Assessment ضمن الناجحة **و** لا توجد شهادة Issued لنفس المسار.
5. Add a new row — Certificates (الرقم Autonumber)، Issued On = `utcNow()` (الختم الزمني)، Status = Draft.
6. **Populate a Microsoft Word template** (Word Online Business) — قالب `Certificate.docx` بحقول:
   `EngineerName`, `EngineerNameAr`, `TrackName`, `TrackNameAr`, `CertificateNo`, `IssuedOn`
   (**بدون** أي مستوى كفاءة — US-03 #4).
7. قالب `Transcript.docx` بقسم متكرر (Repeating section) `Sessions`: Title، Date، Score، Result.
8. Convert file → PDF (OneDrive *Convert file*) لكل منهما.
9. **Upload a file or an image** (Dataverse) → `wbl_certificatefile` و `wbl_transcriptfile`؛ Status = Issued؛ Issued By.
10. Owner = المهندس؛ إرسال بريد للمهندس مع المرفقين.

## F09 — حساب حالة المخاطر (BR-16)

**Trigger:** Recurrence — يومياً 02:00.
1. List rows — Risk Rules: `wbl_isactive eq true`، Sort by `wbl_priority asc`.
2. لكل مهندس نشط احسب المؤشرات:

| المؤشر | الحساب |
|---|---|
| Open flags | Count Flags حالتها New/Accepted |
| Escalated flags | Count Flags = Escalated |
| Attendance rate % | `(Present + Late) / (كل الحضور غير Excused) * 100` للجلسات المنتهية |
| Punctuality rate % | `Present / (Present + Late) * 100` |
| Average assessment score | متوسط `Assessment Score %` للجلسات المؤكدة |
| Max skill gap | أكبر `Gap` في Competency Approvals الحالية؛ إن لم يوجد اعتماد = لا يُقيَّم |

3. أول قاعدة تتحقق (حسب الأولوية) تحدد الحالة؛ إن لم تتحقق أي قاعدة → **On track**. Reason = أسماء القواعد المتحققة.
4. Update Engineer: Risk Status، Risk Reason، Risk Updated On.
5. Add row — Risk Snapshots (مع المؤشرات والسبرنت الحالي) **فقط إذا تغيّرت الحالة أو في آخر يوم من السبرنت** (حفظ التاريخ — BR-08).

> القيم الافتراضية في `data/wbl_riskrule.csv` مسودة. تُعتمد من الخبير والإدارة (عمود Agreed by Management).

## F10 — جاهزية أدوات التدريب (BR-15)

**Trigger:** Recurrence يومياً 09:00.
1. List Training Sessions التي تبدأ خلال 14 يوماً.
2. لكل جلسة: List Toolkit Items (للجلسة أو لمسارها بدون جلسة) `wbl_readiness ne <Ready>`.
3. إن وُجدت → بريد/رسالة Teams لمجموعة الإدارة والمدرب بجدول HTML (Create HTML table): العنصر، النوع، المسؤول، مطلوب قبل.

## F11 — ملكية السجلات وصلاحيات المدرب

**Triggers:** نسخة لكل جدول (أو تدفق واحد بفرع لكل جدول): *When a row is added* على
Work Logs، Session Attendances، Assessment Results، Competency Approvals، Certificates.

1. Get row — Engineer → `UserAccountId`.
2. إن كان Owner ≠ حساب المهندس → Update a row: `Owner` = `systemusers(<id>)` (Assign).
3. إن كان المُنشئ (`_createdby_value`) مدرباً (ليس المهندس وليس مشرفه):
   **Perform an unbound action** `AddUserToRecordTeam` مع:
   `Record` = السجل، `TeamTemplate` = `Instructor - Attendance` أو `Instructor - Assessment`، `SystemUser` = المنشئ.
   وكذلك على سجل **Engineer** بقالب `Instructor - Engineer` (قراءة فقط).
4. **Assessment Results فقط — حارس US-13 #6:** إن كان Assessment Type = Full workflow:
   Get Project → إن لم يكن `Simulated` → Delete row + بريد للمُنشئ: "Work from a real project is not accepted as a full workflow assessment".
5. **Engineers (عند الإضافة/تغيير المشرف):** Update a row — Users: `Manager` = Supervisor (لتفعيل Hierarchy Security).

## F12 — قائمة حضور الجلسة وبوابة NDA

**Trigger:** Training Sessions — added.
1. List Engineers: إن كانت الجلسة General Skills → كل المهندسين النشطين في نفس التقويم؛ وإلا → مهندسو المسار.
2. لكل مهندس:
   * إن كان `NDA Signed = Yes` **و** `Security Permissions Approved = Yes` → Add row Session Attendances (بدون حضور بعد)، Owner = المهندس، وأضف المدرب إلى Access Team.
   * وإلا → لا يُسجَّل، وأرسل للإدارة قائمة "Not cleared to enrol" (قيد 3.3).

## F13 — ضبط اعتماد الكفاءة (US-07)

**Trigger:** Competency Approvals — added.
1. Update الصف: `Approved By` = `_createdby_value` (الخبير)، `Approved On` = `utcNow()`،
   `Target Level` = من Role Profile Items (المسار + المهارة)، `Gap` = `sub(target, approved)`، `Is Current` = Yes.
2. List Competency Approvals السابقة لنفس المهندس+المهارة و Is Current = Yes (عدا الحالي) → Update `Is Current` = No.
   (التاريخ يبقى محفوظاً — US-07 #5.)
3. إن كان Decision = Further review requested → إشعار للمشرف والمدرب.

---

## إعدادات عامة
* **Environment variables** في الـ Solution: `wbl_TestFlairKey` (Secret)، `wbl_AppUrl`، `wbl_ManagementGroupEmail`، `wbl_CertificateTemplatePath`.
* **Run-only users** للتدفقات الآلية: حساب الخدمة فقط.
* فعّل **Retry policy** (Exponential، 4 مرات) على استدعاءات HTTP.
* راقب الأخطاء: أضف Scope "Try / Catch" في كل تدفق يرسل بريداً للمسؤول عند الفشل.
