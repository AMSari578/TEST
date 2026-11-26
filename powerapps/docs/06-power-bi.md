# 06 - لوحات الإدارة (Power BI)

Power BI Desktop → Get data → **Dataverse** → اختر البيئة → حمّل الجداول:
Engineers, Departments, Tracks, Skills, Role Profile Items, Competency Approvals, Assessment Results, Flags, Flag Decisions,
Flag Rules, Training Sessions, Session Attendances, Risk Snapshots, Sprints, Toolkit Items, systemuser (للمشرفين).

**الأمان:** استخدم الاتصال بوضع DirectQuery مع *Use end user identity* أو Import مع **RLS** دور `Management`
(الإدارة ترى الكل). لا تنشر للمهندسين.

## 1. العلاقات
* Engineers[wbl_engineerid] 1→* على Flags، Competency Approvals، Assessment Results، Session Attendances، Risk Snapshots.
* Engineers[_wbl_supervisorid_value] *→1 systemuser (باسم **Supervisor**).
* Engineers[_wbl_departmentid_value] *→1 Departments؛ Engineers[_wbl_trackid_value] *→1 Tracks.
* جدول **Date** (CALENDAR) مرتبط بـ Flags[wbl_detectedon]، Session Attendances→Sessions[wbl_startson]، Competency Approvals[wbl_approvedon].

## 2. مقاييس DAX
```dax
Engineers Count = DISTINCTCOUNT ( Engineers[wbl_engineerid] )

Open Flags =
CALCULATE ( COUNTROWS ( Flags ),
    Flags[wbl_flagstatus_label] IN { "New", "Accepted", "Escalated" } )

Flags per Engineer = DIVIDE ( [Open Flags], [Engineers Count] )

Attendance Rate % =
VAR att = FILTER ( 'Session Attendances', 'Session Attendances'[wbl_attendancestatus_label] <> "Excused" )
RETURN DIVIDE (
    COUNTROWS ( FILTER ( att, 'Session Attendances'[wbl_attendancestatus_label] IN { "Present", "Late" } ) ),
    COUNTROWS ( att ) ) * 100

Punctuality Rate % =
DIVIDE (
    CALCULATE ( COUNTROWS ( 'Session Attendances' ), 'Session Attendances'[wbl_attendancestatus_label] = "Present" ),
    CALCULATE ( COUNTROWS ( 'Session Attendances' ), 'Session Attendances'[wbl_attendancestatus_label] IN { "Present", "Late" } )
) * 100

Avg Assessment Score % =
CALCULATE ( AVERAGE ( 'Session Attendances'[wbl_score] ), 'Session Attendances'[wbl_isconfirmed] = TRUE () )

Current Gap =
CALCULATE ( AVERAGE ( 'Competency Approvals'[wbl_gap] ), 'Competency Approvals'[wbl_iscurrent] = TRUE () )

Engineers per Supervisor = DIVIDE ( [Engineers Count], DISTINCTCOUNT ( Engineers[_wbl_supervisorid_value] ) )

Supervisor Load (open flags) = [Open Flags]   -- يوضع في Visual مقسّم على Supervisor

Dismiss Rate % (false flags) =
DIVIDE (
    CALCULATE ( COUNTROWS ( Flags ), Flags[wbl_flagstatus_label] = "Dismissed" ),
    CALCULATE ( COUNTROWS ( Flags ), Flags[wbl_flagstatus_label] <> "New" ) ) * 100
```
> أعمدة الـ Choice تأتي من Dataverse كرقم + عمود `..._label` (حسب الموصل؛ إن لم يظهر، استخدم جدول `OptionSetMetadata` أو اربط القيم يدوياً).

## 3. الصفحات

| الصفحة | المحتوى | المتطلب |
|---|---|---|
| **Overview** | بطاقات: عدد المهندسين، On track / At risk / High risk، Open flags، Attendance %، Punctuality %، Avg score. جدول المهندسين: المسار، المشرف، المستوى المعتمد، الفجوة، حالة المخاطر، المؤشرات الثلاثة | US-08 #1-5، BR-09 |
| **Supervisor load** | لكل مشرف: عدد المهندسين (هدف 5-8)، Open flags، متوسط زمن القرار (Decided On - Detected On)، Escalated | US-08 #1، BO-05 |
| **Department report** | Slicers: الإدارة (أو الكل) + الفترة. قسمان منفصلان بوضوح: **Competency results** (المستويات والفجوات) و **Performance indicators** (حضور، التزام، درجات، تنبيهات) | US-15 #1-3 |
| **Friction points** | أكثر أنواع التنبيهات لكل إدارة (Bar)، أكبر فجوات المهارات (Bar: Target - Approved)، جلسات بحضور أو درجات منخفضة (Table مع تنسيق شرطي) | US-16 #1-3 |
| **Drill-through** | صفحة "Engineer detail" و "Session detail" (Drill-through) تفتح السجلات خلف كل رقم، مع زر رابط لفتح السجل في تطبيق Model-driven | US-16 #4 |
| **Trend** | حالة المخاطر عبر السبرنتات (من Risk Snapshots)، تطور المستويات المعتمدة | BR-08 |
| **Toolkit readiness** | عناصر غير جاهزة قبل الجلسات القادمة | US-17 #3 |

**رابط فتح السجل** (عمود محسوب):
```dax
Engineer Link = "https://<org>.crm4.dynamics.com/main.aspx?appid=<APP-ID>&pagetype=entityrecord&etn=wbl_engineer&id=" & Engineers[wbl_engineerid]
```
(Data category = Web URL)

## 4. النشر والتصدير
1. Publish إلى Workspace `WBL TMS`، فعّل **Scheduled refresh** (كل ساعة إن كان Import).
2. **التصدير (US-15 #4):** Export → PDF / PowerPoint، أو Export data → Excel من أي Visual.
   للتقارير الدورية: **Paginated report** + اشتراك بريدي شهري.
3. تضمين في تطبيق Model-driven: Settings → Features → *Power BI visualization embedding* = On، ثم أضف
   **Dashboard → Power BI dashboard** إلى Site map منطقة Insights.
4. اللغة: كرّر عناوين الـ Visuals بالعربية باستخدام **Field parameters** أو نسختين من الصفحات (عربي/إنجليزي) مع Bookmarks وزر تبديل.
