# 04 - تطبيق Model-driven: "WBL Admin & SME"

تطبيق للمستخدمين الذين يعملون على **إعداد** النظام و**اعتماد** النتائج و**المتابعة**:
الخبير (SME)، الإدارة (Program Director)، والمسؤول (Administrator). يدعم العربية وRTL تلقائياً
عند اختيار المستخدم للغة العربية (Personalization settings → Languages).

## 1. الإنشاء
Solutions → `WBL Training Management System (Tawwer)` → New → App → **Model-driven app** → الاسم `WBL Admin & SME`.

## 2. خريطة التنقل (Site map)

| المنطقة | المجموعة | الصفحات | الدور الأساسي |
|---|---|---|---|
| **NTG Standard** | المعيار | Skills, Skill Level Descriptors, Role Profile Items, Rubrics | SME |
| | القواعد | Flag Rules, Risk Rules | SME (+ الإدارة لموافقة Risk Rules) |
| **Competency** | الاعتماد | Competency Approvals (view: *Pending my review*), Assessment Results | SME |
| **Programme** | الأشخاص | Engineers, Project Assignments | Admin / الإدارة |
| | المشاريع | Projects, Sprints | Admin |
| | التدريب | Training Calendars, Training Sessions (Calendar view), Session Attendances, Toolkit Items | الإدارة |
| | المخرجات | Certificates | الإدارة |
| **Insights** | اللوحات | Power BI dashboard (ملف 06)، Flags, Flag Decisions, Risk Snapshots | الإدارة |
| **Settings** | | Departments, Tracks, UI Strings | Admin |

## 3. النماذج (Forms) المهمة

### Engineer — Main form (BR-01: "سجل واحد")
تبويبات:
1. **Summary**: الاسم/بالعربي، البريد، الحساب، المشرف، المسار، الإدارة، التقويم (الدفعة)، حالة المخاطر وسببها.
2. **Compliance**: NDA Signed/On، Security Permissions Approved، Source Code Access Approved.
3. **Projects & Sprints**: Subgrid `Project Assignments`، Subgrid `Work Logs` (آخر 30 يوم).
4. **Competency**: Subgrid `Competency Approvals` (view: Current)، Subgrid `Assessment Results`.
5. **Learning**: Subgrid `Session Attendances`، Subgrid `Certificates`.
6. **Flags** (يظهر للمشرف/SME/الإدارة فقط — بالصلاحيات): Subgrid `Flags`.
7. **Risk history**: Subgrid `Risk Snapshots` + Chart.

### Competency Approval — Main form (US-07)
القسم الأعلى: Engineer, Skill, **Target Level** (للقراءة)، **Approved Level**، Decision، SME Comments.
القسم الأسفل **Evidence**: Subgrid `Assessment Results` مفلترة على نفس المهندس والمهارة
(استخدم *Related records filtering* أو subgrid على Engineer ثم View مخصص)، مع أعمدة النوع والدرجة والمُقيّم والتاريخ و*Supporting only*.

* AC #1: الخبير يرى الأدلة والمستوى المستهدف قبل الحفظ.
* AC #3: لا يوجد أي تدفق أو Business rule يضع `Approved Level` تلقائياً.
* AC #4: Decision = Approved أو Further review requested.
* AC #7: View للأدلة يُظهر عمود `Supporting Evidence Only` (الشهادات الخارجية).
* AC #8: **F13** يملأ `Approved By` و `Approved On` ويضع `Target Level` و `Gap`، ويجعل السجل السابق `Is Current = No`.

### Flag Rule — Main form (US-09، BR-10)
Rule Type، Category، Severity، Threshold + Unit، Track (فارغ = كل المسارات)، Active، Description.
إضافة قاعدة جديدة = سجل جديد هنا. **F02** يقرأ القواعد النشطة في كل تشغيل، فلا حاجة لتعديل أي تدفق.

### Training Session — Main form + Calendar view
فعّل **Calendar control** على View `Sessions - This year` (Start = Starts On، End = Ends On، Description = Topic)
لعرض **التقويم السنوي** بأسماء المدربين والمواضيع. Subgrid `Toolkit Items` على نموذج الجلسة.

## 4. Business Rules (تعمل على الخادم — Scope: **Entity**)

| الجدول | الاسم | الشرط | الإجراء | المتطلب |
|---|---|---|---|---|
| Flag | `Dismiss needs reason` | Flag Status = Dismissed **AND** Decision Reason does not contain data | Show error on Decision Reason: "A reason is required to dismiss a flag / يجب كتابة سبب لرفض التنبيه" | US-05 #1 |
| Session Attendance | `Confirm needs data` | Confirmed by Instructor = Yes **AND** (Attendance does not contain data **OR** Assessment Score % does not contain data) | Show error | US-11 #1 |
| Assessment Result | `Full workflow needs project` | Assessment Type = Full workflow **AND** (Simulated Project does not contain data **OR** Rubric does not contain data) | Show error | US-13 #2، #3 |
| Assessment Result | `External cert is supporting` | Assessment Type = External certification | Set Supporting Evidence Only = Yes | US-07 #7 |
| Competency Approval | `Approved needs level` | Decision = Approved **AND** Approved Level does not contain data | Show error | US-07 |
| Engineer | `NDA date` | NDA Signed = Yes | Set business required: NDA Signed On | قيد NDA |

> Business rules لا تستطيع قراءة أعمدة جدول مرتبط (مثل نوع المشروع). لذلك التحقق "المشروع يجب أن يكون محاكى"
> يتم في الواجهة (القائمة لا تعرض إلا المشاريع المحاكاة) + **F11** على الخادم.
> بديل أقوى: **Dataverse low-code plug-in** (Power Fx) على Create/Update للجدول `Assessment Results`:
> ```powerfx
> If(
>     ThisRecord.'Assessment Type' = 'Assessment Type'.'Full workflow' &&
>     LookUp(Projects, Project = ThisRecord.'Simulated Project'.Project).'Project Type' <> 'Project Type'.Simulated,
>     Error({Kind: ErrorKind.Validation, Message: "Full workflow assessments must use a simulated project"})
> )
> ```
> (يتطلب تثبيت Dataverse Accelerator — تحقق من توفره في منطقتك.)

## 5. Views مقترحة

| الجدول | View | الفلتر |
|---|---|---|
| Competency Approvals | Current levels | Is Current = Yes |
| Competency Approvals | Further review requested | Decision = Further review requested |
| Assessment Results | Awaiting SME review | Assessed On last 30 days، لا يوجد Competency Approval لاحق (استخدم عمود ترتيب) |
| Flags | Open flags | Flag Status in (New, Accepted, Escalated) |
| Flags | Escalated to management | Flag Status = Escalated |
| Training Sessions | This year | Starts On this year |
| Toolkit Items | **Not ready – next 14 days** (US-17 #3) | Readiness <> Ready AND Session.Starts On next 14 days |
| Engineers | High risk | Risk Status = High risk |
| Engineers | Not cleared to enrol | NDA Signed = No OR Security Permissions Approved = No |

## 6. إضافة حقول بدون برمجة (US-09 #1-2)
المسؤول (دور System Customizer) يضيف عموداً جديداً من: Solutions → الجدول → Columns → New، ثم يسحبه إلى النموذج.
لا يحتاج أي كود. التطبيقات تعرضه فوراً بعد Publish.
