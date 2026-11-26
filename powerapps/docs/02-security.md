# 02 - الأمان والصلاحيات / Security

قيد BRD 3.3: "Access to data depends on the role of the user". وعدة معايير قبول تعتمد على الأمان:

* US-02 #5، US-10 #3، US-14 #4: لا أحد يرى سجلات مهندسين ليسوا تحت مسؤوليته.
* US-02 #6، US-10 #4: المهندس والمدرب **لا يرون** نتائج مراجعة AI (التنبيهات).
* US-06 #3: فقط الخبير يغيّر المستويات المستهدفة. US-07 #3: فقط الخبير يعتمد مستوى الكفاءة.

**مبدأ مهم:** الفلترة في Canvas App ليست أماناً. الأمان الحقيقي في Dataverse، والتطبيقات تعرض فقط ما يسمح به.

## 1. نموذج الملكية (Ownership)

كل سجل يخص مهندساً (Work Log, Flag, Attendance, Assessment, Competency Approval, Certificate, Risk Snapshot)
**مملوك لحساب المهندس نفسه** (Owner = المهندس). التدفق **F11** يضمن ذلك حتى لو أنشأ السجلَ مدربٌ أو تدفق.

ثم:

| من | كيف يصل للسجل |
|---|---|
| المهندس | صلاحية **User** level → يرى ما يملكه فقط |
| المشرف | **Manager Hierarchy Security**: المشرف هو `Manager` للمهندس في جدول Users → يرى ويعدل سجلات مرؤوسيه المباشرين فقط |
| المدرب | **Access Team** على سجلات الحضور والتقييم الخاصة بجلساته (F11 يضيفه تلقائياً) |
| الخبير SME / الإدارة | صلاحية **Organization** level قراءة |

### تفعيل Hierarchy Security
1. Power Platform admin center → Environment → Settings → Users + permissions → **Hierarchy security**.
2. فعّل **Enable Hierarchy Modeling** واختر **Manager hierarchy**، Depth = **1**.
3. لكل مهندس: Settings → Users → افتح المستخدم → حقل **Manager** = المشرف.
   (يُنصح بأن يقوم F11 أيضاً بمزامنة `wbl_supervisorid` في جدول المهندس مع حقل Manager.)
4. استثنِ جداول الإعداد من الهرمية (Exclude) غير ضرورية لأنها Organization-owned.

### Access Team Templates
أنشئ Template باسم `Session Instructor` لكل من الجدولين `wbl_attendance` و `wbl_assessment` و `wbl_engineer`
(فعّل *Enable access teams* في إعدادات كل جدول أولاً):

| Template | الجدول | الصلاحيات |
|---|---|---|
| `Instructor - Attendance` | wbl_attendance | Read, Write |
| `Instructor - Assessment` | wbl_assessment | Read, Write |
| `Instructor - Engineer` | wbl_engineer | Read |

## 2. الأدوار الأمنية (Security Roles)

أنشئ الأدوار من: Environment → Settings → Security roles → New role (انسخ من **Basic User** ثم أضف ما يلي).

الرموز: **U** = User (ما يملكه)، **O** = Organization (الكل)، **—** = لا شيء، `C/R/W/D/A/AT` = Create/Read/Write/Delete/Append/Append To.

| الجدول | Engineer | Supervisor | Instructor | SME | Management | Administrator |
|---|---|---|---|---|---|---|
| Department, Track, Training Calendar | R:O | R:O | R:O | R:O | R:O | CRWD:O |
| Skill, Skill Level Descriptor | R:O | R:O | R:O | CRWD:O | R:O | R:O |
| Role Profile Item (المستهدف) | R:O | R:O | — | **CRWD:O** | R:O | R:O |
| Rubric | — | R:O | R:O | CRWD:O | R:O | R:O |
| Flag Rule, Risk Rule | — | R:O | — | CRWD:O | R:O (+W على Risk Rule للموافقة) | R:O |
| Engineer | R:U | RW:U ¹ | R ² | R:O | R:O | CRWD:O |
| Project, Sprint | R:O | CRW:O | — | R:O | R:O | CRWD:O |
| Project Assignment | R:U | CRW:U ¹ | — | R:O | R:O | CRWD:O |
| Work Log | CRW:U | R:U ¹ | — | — | R:O | R:O |
| Work Activity | R:U | R:U ¹ | — | R:O | R:O | R:O |
| **Flag** | **—** | RW:U ¹ | **—** | R:O | R:O | R:O |
| Flag Decision | — | C R:U ¹ | — | R:O | R:O | R:O |
| Training Session | R:O | R:O | RW:O ³ | R:O | CRWD:O | CRWD:O |
| Attendance | R:U | R:U ¹ | RW ² | R:O | R:O | CRW:O |
| Assessment Result | R:U | CRW:U ¹ | C RW ² | R:O | R:O | R:O |
| **Competency Approval** | R:U | R:U ¹ | — | **CRW:O** | R:O | R:O |
| Certificate | R:U | R:U ¹ | — | R:O | CRW:O | CRW:O |
| Toolkit Item | — | — | R:O | R:O | CRWD:O | CRWD:O |
| Risk Snapshot | — | R:U ¹ | — | R:O | R:O | R:O |
| UI String | R:O | R:O | R:O | R:O | R:O | CRWD:O |

¹ مستوى U + Hierarchy Security = سجلات المرؤوسين المباشرين فقط.
² عبر Access Team (لا يحتاج الدور صلاحية مستوى أعلى من U).
³ يمكن تقييدها لاحقاً بحيث يعدل المدرب جلساته فقط (Instructor = Owner).

أضف أيضاً لكل الأدوار: `Append`/`Append To` على الجداول المرتبطة بما يكتبونه، وصلاحية **Read** على `User`.

**صلاحيات الأعمدة (Column security) المقترحة:**
* `wbl_engineer.wbl_riskreason` — اقرأها فقط للمشرف/SME/الإدارة (المهندس يرى الحالة دون التفاصيل إن رغبت الإدارة).
* `wbl_assessment.wbl_indicativelevel` — كتابة للمُقيِّم، قراءة للخبير.

## 3. الفرق (Teams) والتعيين

أنشئ **Microsoft Entra security groups** واربطها بـ Dataverse Group Teams، كل فريق يحمل دوراً:

| Entra group | Dataverse team | Role |
|---|---|---|
| `WBL-Engineers` | WBL Engineers | Engineer |
| `WBL-Supervisors` | WBL Supervisors | Supervisor |
| `WBL-Instructors` | WBL Instructors | Instructor |
| `WBL-SME` | WBL SME | SME |
| `WBL-Management` | WBL Management | Management |
| `WBL-Admins` | WBL Admins | Administrator + System Customizer |

> تنبيه: أدوار الفريق لا تكفي للملكية بمستوى User إلا إذا كان الفريق من نوع **Group team** مع
> *Membership type* مناسب، أو أُسند الدور مباشرة للمستخدم. الأبسط للمهندسين: أسند دور Engineer للمستخدم مباشرة.

## 4. Auditing (BR-11 و US-07 #8)

1. Environment → Settings → Auditing → **Start auditing** + **Log access**.
2. الجداول المعلَّمة `audit: true` في schema.json مفعّل عليها التدقيق مسبقاً.
3. فترة الاحتفاظ: اقترح 7 سنوات أو حسب سياسة NTG.

## 5. حماية البيانات (Data policies)

* أنشئ **DLP policy** للبيئة: ضع Dataverse, Teams, Office 365 Outlook, Word Online, OneDrive, HTTP (لـ TestFlair) في *Business*،
  وامنع (Block) الموصلات الاجتماعية والتخزين الخارجي.
* لا تخزن كود العميل في أي جدول: عمود `wbl_evidence` يحمل **وصف** المشكلة ورابط الـ commit فقط.
