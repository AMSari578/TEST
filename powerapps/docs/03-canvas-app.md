# 03 - تطبيق Canvas: "WBL Tawwer"

تطبيق واحد للمستخدمين اليوميين: **المهندس، المشرف، المدرب**. يعمل على الجوال والويب وداخل Teams.
الخبير والإدارة والمسؤول يستخدمون تطبيق Model-driven (ملف 04) لأنه أسرع في البناء لشاشات الإعداد والاعتماد.

> أسماء الجداول والأعمدة أدناه هي **Display names** كما ينشئها السكربت من `schema.json`.
> إن غيّرت اسماً في الـ JSON، غيّره هنا أيضاً.

## 0. الإنشاء

1. make.powerapps.com → اختر البيئة → **Solutions** → افتح `WBL Training Management System (Tawwer)`.
2. New → App → **Canvas app** → Tablet format (يعمل جيداً على الجوال مع Responsive containers). الاسم: `WBL Tawwer`.
3. Settings → Display → أوقف *Scale to fit* واجعل التطبيق Responsive.
4. Settings → Updates → فعّل **Named formulas** و **Modern controls and themes**.
5. Data → Add data → Dataverse: أضف الجداول:
   `Engineers, Users, Projects, Project Assignments, Sprints, Work Logs, Flags, Training Sessions,
   Session Attendances, Assessment Results, Competency Approvals, Role Profile Items, Skills, Rubrics,
   Certificates, Toolkit Items, Training Calendars, UI Strings`.

## 1. الهوية والأدوار و اللغة

### App.Formulas (Named formulas)
```powerfx
// من أنا؟
MeUser = LookUp(Users, 'Primary Email' = User().Email);
MeEngineer = LookUp(Engineers, Email = User().Email);
IsEngineer = !IsBlank(MeEngineer);

// المشرف: المهندسون الذين أنا مشرفهم (الأمان الفعلي يأتي من Hierarchy Security)
MyTeam = Filter(Engineers, Supervisor.User = MeUser.User);
IsSupervisor = !IsEmpty(MyTeam);

// المدرب: الجلسات التي أنا مدربها
MySessions = Filter('Training Sessions', 'Instructor / Trainer'.User = MeUser.User);
IsInstructor = !IsEmpty(MySessions);

// اتجاه الواجهة
IsRTL = varLang = "ar";
TextAlign = If(IsRTL, Align.Right, Align.Left);
```

### App.OnStart
```powerfx
Set(varLang, If(StartsWith(Lower(Language()), "ar"), "ar", "en"));
ClearCollect(
    colStrings,
    ForAll('UI Strings', {Key: ThisRecord.Key, Txt: If(varLang = "ar", ThisRecord.Arabic, ThisRecord.English)})
);
Set(varEngineer, MeEngineer);   // الشاشة "التقدم" تعرض هذا المهندس (المشرف يغيره)
```

### النصوص بلغتين
كل Label/Button نصه:
```powerfx
LookUp(colStrings, Key = "nav.worklog", Txt)
```
و `Align` لكل نص = `TextAlign`.

### زر تبديل اللغة (في الهيدر)
```powerfx
// Text
LookUp(colStrings, Key = "lang.toggle", Txt)
// OnSelect
Set(varLang, If(varLang = "ar", "en", "ar"));
ClearCollect(
    colStrings,
    ForAll('UI Strings', {Key: ThisRecord.Key, Txt: If(varLang = "ar", ThisRecord.Arabic, ThisRecord.English)})
);
```
لعكس ترتيب العناصر في الحاويات الأفقية (RTL): اجعل ترتيب الأبناء يعتمد على `IsRTL`
(مثلاً أيقونة الرجوع `Icon = If(IsRTL, Icon.ChevronRight, Icon.ChevronLeft)`)، ولأسماء الجداول من Dataverse استخدم العمود العربي:
```powerfx
If(IsRTL, ThisItem.'Name (Arabic)', ThisItem.Name)
```

## 2. الشاشات

| الشاشة | تظهر لـ | User stories |
|---|---|---|
| `scrHome` | الكل | — |
| `scrWorkLog` | المهندس | US-01 |
| `scrProgress` | المهندس (نفسه)، المشرف (مهندسيه) | US-02, US-14 |
| `scrCertificates` | المهندس | US-03 |
| `scrTeam` | المشرف | US-14 |
| `scrFlags` | المشرف | US-04, US-05 |
| `scrSessions` | المدرب | US-10, US-11, US-17 #4 |
| `scrAssess` | المدرب، المشرف | US-12, US-13 |
| `scrCalendar` | الكل | التقويم السنوي |

### 2.1 scrHome
بلاطات (Buttons) تظهر حسب الدور:
```powerfx
btnWorkLog.Visible     = IsEngineer
btnProgress.Visible    = IsEngineer
btnCerts.Visible       = IsEngineer
btnTeam.Visible        = IsSupervisor
btnFlags.Visible       = IsSupervisor
btnSessions.Visible    = IsInstructor
btnAssess.Visible      = IsInstructor || IsSupervisor
```
شارة عدد التنبيهات الجديدة على زر التنبيهات:
```powerfx
CountRows(Filter(Flags, 'Flag Status' = 'Flag Status'.New))
```

### 2.2 scrWorkLog — تسجيل العمل بأقل جهد (US-01)

**OnVisible**
```powerfx
With(
    {myProjects: Filter('Project Assignments', Engineer.Engineer = MeEngineer.Engineer)},
    ClearCollect(
        colMySprints,
        Filter(
            Sprints,
            'Sprint Status' = 'Sprint Status'.Active &&
            Project.Project in ForAll(myProjects, ThisRecord.Project.Project)
        )
    )
);
```

**عناصر الشاشة** (3 حقول إلزامية فقط لتحقيق AC #4):

| Control | خاصية | القيمة |
|---|---|---|
| `drpSprint` | Items | `colMySprints` |
|  | Default | `First(colMySprints)` |
| `dpDate` | DefaultDate | `Today()` |
| `txtHours` | Default | `"8"` |
| `txtSummary` | Mode | Multiline |
| `txtLink` | (اختياري) | |
| `lblAuto` | Visible | `varAutoProject` |
|  | Text | `LookUp(colStrings, Key = "worklog.auto", Txt)` |
| `conForm` | Visible | `!varAutoProject` |

**drpSprint.OnChange** و أيضاً في آخر OnVisible — AC #3 (لا يعيد إدخال بيانات تأتي من الأداة):
```powerfx
With(
    {p: LookUp(Projects, Project = drpSprint.Selected.Project.Project)},
    Set(
        varAutoProject,
        p.'Client Permits Tool Data Use' &&
        p.'Tool Integration' <> 'Tool Integration'.'None (manual logs)'
    )
)
```

**btnSave.DisplayMode**
```powerfx
If(
    IsBlank(drpSprint.Selected) || IsBlank(Trim(txtSummary.Text)) || !IsNumeric(txtHours.Text),
    DisplayMode.Disabled, DisplayMode.Edit
)
```

**btnSave.OnSelect** (AC #1, #2)
```powerfx
Patch(
    'Work Logs',
    Defaults('Work Logs'),
    {
        Title: MeEngineer.'Full Name' & " - " & Text(dpDate.SelectedDate, "yyyy-mm-dd"),
        Engineer: MeEngineer,
        Sprint: drpSprint.Selected,
        'Log Date': dpDate.SelectedDate,
        Hours: Value(txtHours.Text),
        'What I did': txtSummary.Text,
        'Link (commit / PR / document)': txtLink.Text,
        Source: 'Work Data Source'.Manual
    }
);
If(
    IsEmpty(Errors('Work Logs')),
    Notify(LookUp(colStrings, Key = "worklog.saved", Txt), NotificationType.Success);
    Reset(txtSummary); Reset(txtLink),
    Notify(First(Errors('Work Logs')).Message, NotificationType.Error)
)
```
أسفل النموذج: Gallery بآخر سجلاتي:
```powerfx
FirstN(Sort(Filter('Work Logs', Engineer.Engineer = MeEngineer.Engineer), 'Log Date', SortOrder.Descending), 10)
```

### 2.3 scrProgress — التقدم مقابل المستوى المستهدف (US-02 و US-14)

`varEngineer` = المهندس المعروض (المهندس نفسه أو أحد مهندسي المشرف).

**رأس السجل** (US-02 #4): المسار، المشرف، المشاريع.
```powerfx
lblTrack.Text      = If(IsRTL, varEngineer.Track.'Name (Arabic)', varEngineer.Track.Name)
lblSupervisor.Text = varEngineer.Supervisor.'Full Name'
lblProjects.Text   = Concat(Filter('Project Assignments', Engineer.Engineer = varEngineer.Engineer), Project.Name, ", ")
```

**حالة المخاطر** — للمشرف فقط (US-14 #5):
```powerfx
lblRisk.Visible = varEngineer.Engineer <> MeEngineer.Engineer
lblRisk.Text    = Text(varEngineer.'Risk Status')
lblRisk.Fill    = Switch(varEngineer.'Risk Status',
                    'Risk Status'.'On track', ColorValue("#2E7D32"),
                    'Risk Status'.'At risk',  ColorValue("#F9A825"),
                    'Risk Status'.'High risk',ColorValue("#C62828"),
                    Color.LightGray)
```

**galSkills.Items** — المستهدف، المعتمد، الفجوة (US-02 #1-2، US-14 #1-3):
```powerfx
ForAll(
    Filter('Role Profile Items', Track.Track = varEngineer.Track.Track) As p,
    With(
        {
            approved: LookUp(
                'Competency Approvals' As a,
                a.Engineer.Engineer = varEngineer.Engineer &&
                a.Skill.Skill = p.Skill.Skill &&
                a.'Is Current' &&
                a.Decision = 'Approval Decision'.Approved,
                a.'Approved Level'
            )
        },
        {
            SkillName: If(IsRTL, p.Skill.'Name (Arabic)', p.Skill.Name),
            Target: p.'Target Level',
            Approved: approved,
            Gap: p.'Target Level' - Coalesce(approved, 0)
        }
    )
)
```
داخل الـ Gallery: شريط تقدم = Rectangle عرضه `Parent.TemplateWidth * Coalesce(ThisItem.Approved,0) / 7`
وعلامة للمستهدف عند `Parent.TemplateWidth * ThisItem.Target / 7`. لون الفجوة: أخضر إذا `Gap <= 0`.

**التقدم عبر السبرنتات** (US-02 #3): Line chart أو Gallery على:
```powerfx
Sort(Filter('Competency Approvals', Engineer.Engineer = varEngineer.Engineer), 'Approved On', SortOrder.Ascending)
```
و قائمة التقييمات (US-02 #4):
```powerfx
Sort(Filter('Assessment Results', Engineer.Engineer = varEngineer.Engineer), 'Assessed On', SortOrder.Descending)
```
> **المهندس لا يرى التنبيهات/نتائج AI** (US-02 #6): لا يوجد أي عنصر يقرأ من `Flags` في هذه الشاشة،
> ودور Engineer ليس لديه صلاحية قراءة على جدول Flags أصلاً.

### 2.4 scrCertificates (US-03 #5، #7)
```powerfx
galCerts.Items = Filter(Certificates, Engineer.Engineer = MeEngineer.Engineer &&
                        Status = 'Certificate Status'.Issued)
btnDownloadCert.OnSelect       = Download(ThisItem.'Certificate (PDF)'.Value)
btnDownloadTranscript.OnSelect = Download(ThisItem.'Transcript (PDF)'.Value)
```
كشف حيّ (قبل إصدار الشهادة) — كل جلسة، تاريخها ونتيجتها:
```powerfx
Sort(
    Filter('Session Attendances', Engineer.Engineer = MeEngineer.Engineer),
    Session.'Starts On', SortOrder.Ascending
)
// داخل الـ Gallery
ThisItem.Session.Title & " | " & Text(ThisItem.Session.'Starts On', "dd/mm/yyyy") & " | " &
If(ThisItem.Passed, "✔", "✖") & " " & Text(ThisItem.'Assessment Score %') & "%"
```

### 2.5 scrTeam — مهندسيّ (US-14)
```powerfx
galTeam.Items = SortByColumns(MyTeam, "wbl_riskstatus", SortOrder.Descending)
// عدد التنبيهات المفتوحة لكل مهندس
lblOpen.Text = CountRows(Filter(Flags, Engineer.Engineer = ThisItem.Engineer &&
                 'Flag Status' <> 'Flag Status'.Dismissed && 'Flag Status' <> 'Flag Status'.Resolved))
galTeam.OnSelect = Set(varEngineer, ThisItem); Navigate(scrProgress)
```

### 2.6 scrFlags — صندوق التنبيهات للمشرف (US-04، US-05)

**galFlags.Items** (US-04 #1-2: الأمان يقصرها على مهندسيه تلقائياً)
```powerfx
SortByColumns(
    Filter(
        Flags,
        (tglShowClosed.Checked ||
            ('Flag Status' <> 'Flag Status'.Dismissed && 'Flag Status' <> 'Flag Status'.Resolved)) &&
        (IsBlank(drpEngineer.Selected) || Engineer.Engineer = drpEngineer.Selected.Engineer)
    ),
    "wbl_detectedon", SortOrder.Descending
)
```

**بطاقة التنبيه** (US-04 #4 — الدليل):
```powerfx
lblTitle.Text    = ThisItem.Title
lblWho.Text      = ThisItem.Engineer.'Full Name' & " • " & ThisItem.Sprint.Name
lblSource.Text   = Text(ThisItem.Source) & " • " & Text(ThisItem.Severity)
lblEvidence.Text = ThisItem.Evidence
lblDoD.Text      = ThisItem.'Definition of Done Item'      // لنتائج AI
lblReason.Text   = ThisItem.'Reason (from rule / AI)'
lnkCommit.OnSelect = Launch(ThisItem.'Evidence Link (commit)')
lnkCommit.Visible  = !IsBlank(ThisItem.'Evidence Link (commit)')
```

**أزرار القرار** (US-04 #5): أربعة أزرار تفتح لوحة تأكيد:
```powerfx
btnAccept.OnSelect   = Set(varAction, 'Flag Status'.Accepted);  Set(varFlag, ThisItem); Set(varShowDecision, true)
btnDismiss.OnSelect  = Set(varAction, 'Flag Status'.Dismissed); Set(varFlag, ThisItem); Set(varShowDecision, true)
btnResolve.OnSelect  = Set(varAction, 'Flag Status'.Resolved);  Set(varFlag, ThisItem); Set(varShowDecision, true)
btnEscalate.OnSelect = Set(varAction, 'Flag Status'.Escalated); Set(varFlag, ThisItem); Set(varShowDecision, true)
```

**لوحة التأكيد** `conDecision` (Visible = `varShowDecision`):
```powerfx
// تحذير السبب الإلزامي (US-05 #1)
lblReasonRequired.Visible = varAction = 'Flag Status'.Dismissed && IsBlank(Trim(txtReason.Text))

btnConfirm.DisplayMode =
    If(varAction = 'Flag Status'.Dismissed && IsBlank(Trim(txtReason.Text)),
       DisplayMode.Disabled, DisplayMode.Edit)

btnConfirm.OnSelect =
    Patch(
        Flags, varFlag,
        {
            'Flag Status': varAction,
            'Decision Reason': txtReason.Text,
            'Decided By': MeUser,
            'Decided On': Now()
        }
    );
    If(
        IsEmpty(Errors(Flags)),
        Notify(LookUp(colStrings, Key = "common.saved", Txt), NotificationType.Success);
        Set(varShowDecision, false); Reset(txtReason),
        Notify(First(Errors(Flags)).Message, NotificationType.Error)
    )
```
> سجل القرار (US-05 #3، BR-11) يُنشأ على الخادم بواسطة **F05** عند تغيّر الحالة — يعمل أيضاً عند القرار من بطاقة Teams.
> وقاعدة "لا رفض بدون سبب" مفروضة على الخادم بـ Business Rule (ملف 04)، فلا يمكن تجاوزها من أي قناة.

### 2.7 scrSessions — جلساتي كمدرب (US-10، US-11، US-17 #4)
```powerfx
galSessions.Items = Sort(MySessions, 'Starts On', SortOrder.Descending)

galAttendees.Items = Filter('Session Attendances',
                       Session.'Training Session' = galSessions.Selected.'Training Session')
```
داخل `galAttendees` — حضور، تأخير، درجة (US-10 #1):
```powerfx
lblName.Text  = ThisItem.Engineer.'Full Name'
drpStatus.Items = Choices('Attendance Status')          // إدخال يدوي إن لم يأت من المنصة
drpStatus.Default = ThisItem.Attendance
drpStatus.OnChange = Patch('Session Attendances', ThisItem,
                        {Attendance: drpStatus.Selected.Value, 'Attendance Source': 'Data Source'.Manual})
txtScore.Default  = ThisItem.'Assessment Score %'
txtScore.OnChange = Patch('Session Attendances', ThisItem,
                        {'Assessment Score %': Value(txtScore.Text), 'Score Source': 'Data Source'.Manual})
lblLate.Text = If(ThisItem.'Minutes Late' > 0, Text(ThisItem.'Minutes Late') & " min", "")
```
**زر التأكيد** (US-11 #1، #2):
```powerfx
btnConfirm.DisplayMode =
    If(
        IsBlank(ThisItem.Attendance) || IsBlank(ThisItem.'Assessment Score %') || ThisItem.'Confirmed by Instructor',
        DisplayMode.Disabled, DisplayMode.Edit
    )
btnConfirm.OnSelect =
    Patch(
        'Session Attendances', ThisItem,
        {
            'Confirmed by Instructor': true,
            'Confirmed By': MeUser,
            'Confirmed On': Now(),
            Passed: ThisItem.Attendance <> 'Attendance Status'.Absent &&
                    ThisItem.'Assessment Score %' >= Coalesce(galSessions.Selected.'Pass Mark %', 60)
        }
    )
```
(التأكيد لا يغيّر أي مستوى كفاءة — US-11 #4؛ إنما يطلق F08 للتحقق من أهلية الشهادة.)

أدوات الجلسة (US-17 #4):
```powerfx
galToolkit.Items = Filter('Toolkit Items', Session.'Training Session' = galSessions.Selected.'Training Session')
```

### 2.8 scrAssess — تسجيل نتيجة تقييم (US-12، US-13)

```powerfx
// نوع التقييم المسموح حسب الدور
rdoType.Items = Filter(
    Choices('Assessment Type'),
    (IsInstructor && (Value = 'Assessment Type'.Observed || Value = 'Assessment Type'.Standardized)) ||
    (IsSupervisor && Value = 'Assessment Type'.'Full workflow')
)

// المهندسون: مهندسي جلساتي (مدرب) أو فريقي (مشرف)
drpEngineer.Items =
    If(
        rdoType.Selected.Value = 'Assessment Type'.'Full workflow',
        MyTeam,
        Filter(
            Engineers,
            Engineer in ForAll(
                Filter('Session Attendances', Session.'Instructor / Trainer'.User = MeUser.User),
                ThisRecord.Engineer.Engineer
            )
        )
    )
// المدرب يرى سجلات هؤلاء المهندسين فقط بفضل Access Team التي يضيفه إليها F11.

drpSkill.Items = ForAll(
    Filter('Role Profile Items', Track.Track = drpEngineer.Selected.Track.Track),
    ThisRecord.Skill
)

// US-13 #6: لا يقبل عمل مشروع حقيقي كتقييم سير عمل كامل
drpProject.Visible = rdoType.Selected.Value = 'Assessment Type'.'Full workflow'
drpProject.Items   = Filter(Projects, 'Project Type' = 'Project Type'.Simulated)

drpRubric.Visible = rdoType.Selected.Value = 'Assessment Type'.'Full workflow'
drpRubric.Items   = Filter(Rubrics, Skill.Skill = drpSkill.Selected.Skill)
```
**btnSave.DisplayMode**
```powerfx
If(
    IsBlank(drpEngineer.Selected) || IsBlank(drpSkill.Selected) || IsBlank(Trim(txtObservation.Text)) ||
    (rdoType.Selected.Value = 'Assessment Type'.'Full workflow' &&
        (IsBlank(drpProject.Selected) || IsBlank(drpRubric.Selected) || IsBlank(txtDeliverable.Text))),
    DisplayMode.Disabled, DisplayMode.Edit
)
```
**btnSave.OnSelect**
```powerfx
Patch(
    'Assessment Results',
    Defaults('Assessment Results'),
    {
        Title: Text(rdoType.Selected.Value) & " - " & drpSkill.Selected.Name,
        Engineer: drpEngineer.Selected,
        Skill: drpSkill.Selected,
        'Assessment Type': rdoType.Selected.Value,
        'Simulated Project': If(rdoType.Selected.Value = 'Assessment Type'.'Full workflow', drpProject.Selected),
        Rubric: If(rdoType.Selected.Value = 'Assessment Type'.'Full workflow', drpRubric.Selected),
        Session: drpSession.Selected,
        Task: txtTask.Text,                                    // US-12 #2
        'What was observed / engineer actions': txtObservation.Text,
        Score: Value(txtScore.Text),
        'Max Score': Value(txtMax.Text),
        'Deliverable Link': txtDeliverable.Text,               // US-13 #3
        'Assessed By': MeUser,                                 // US-12 #3, US-13 #4
        'Assessed On': Now()
    }
);
If(IsEmpty(Errors('Assessment Results')),
   Notify(LookUp(colStrings, Key = "common.saved", Txt), NotificationType.Success); Back(),
   Notify(First(Errors('Assessment Results')).Message, NotificationType.Error))
```
> بعد الحفظ، **F11** ينقل الملكية للمهندس ويضيف المُقيّم إلى Access Team، ويرفض (يحذف ويبلّغ)
> أي تقييم "Full workflow" مرتبط بمشروع ليس Simulated حتى لو أُنشئ من خارج التطبيق.

### 2.9 scrCalendar — التقويم السنوي
```powerfx
// varYear في OnVisible: Set(varYear, Year(Today()))
galCalendar.Items =
    GroupBy(
        AddColumns(
            Filter('Training Sessions',
                   'Starts On' >= Date(varYear, 1, 1) && 'Starts On' < Date(varYear + 1, 1, 1)),
            MonthLabel, Text('Starts On', "mmmm yyyy", If(IsRTL, "ar-SA", "en-US"))
        ),
        MonthLabel, Sessions
    )
// gallery داخلية: ThisItem.Sessions — العنوان، المدرب، الموضوع، المسار
lblTrainer.Text = ThisItem.'Instructor / Trainer'.'Full Name'
```

## 3. نصائح الأداء والتفويض (Delegation)
* كل الفلاتر أعلاه بمقارنات `=`/`<>` على أعمدة Dataverse قابلة للتفويض. استخدامات `in` و `ForAll`
  على مجموعات صغيرة (مشاريع المهندس) لا تتجاوز حدود 500 سجل.
* اجعل *Data row limit* = 2000 احتياطاً.
* للاستخدام في Teams: Publish ثم **Add to Teams** من قائمة التطبيق.
