"""Translated text for imported locations (NYC Open Data rows only have English names).

Every imported row gets a `program_type` key. The importer copies the matching
summary / services / status text below into the row's multilingual JSONB fields,
so imported locations read naturally in every supported language even though the
source data is English-only. Organization names themselves stay in English
(proper nouns); where a source name is not descriptive on its own (e.g. a NYCHA
development name), `name_suffix` adds a translated description.

Languages: en, es, vi, zh, ar (same as the rest of the app).
"""

LANGS = ("en", "es", "vi", "zh", "ar")

# Shown as the "open status" line for rows that have no verified hours.
CALL_AHEAD = {
    "en": "Call ahead to confirm hours",
    "es": "Llame antes para confirmar el horario",
    "vi": "Vui lòng gọi trước để xác nhận giờ mở cửa",
    "zh": "请提前致电确认开放时间",
    "ar": "يرجى الاتصال مسبقًا للتأكد من المواعيد",
}

PROGRAM_TYPES = {
    "food_pantry": {
        "category": "food",
        "summary": {
            "en": "Food pantry in the Food Bank For New York City network. Offers free groceries to neighbors in need. Call ahead to confirm distribution days and what to bring.",
            "es": "Despensa de alimentos de la red de Food Bank For New York City. Ofrece alimentos gratuitos a vecinos que los necesitan. Llame antes para confirmar los días de distribución y qué debe traer.",
            "vi": "Kho thực phẩm thuộc mạng lưới Food Bank For New York City. Cung cấp thực phẩm miễn phí cho người cần giúp đỡ. Vui lòng gọi trước để xác nhận ngày phát và giấy tờ cần mang.",
            "zh": "Food Bank For New York City 网络中的食品分发站，为有需要的居民免费提供食品。请提前致电确认发放日期及需携带的物品。",
            "ar": "بنك طعام ضمن شبكة Food Bank For New York City يقدم مواد غذائية مجانية للمحتاجين. يرجى الاتصال مسبقًا لمعرفة أيام التوزيع وما يجب إحضاره.",
        },
        "services": {
            "en": ["Free groceries", "Emergency food"],
            "es": ["Alimentos gratuitos", "Comida de emergencia"],
            "vi": ["Thực phẩm miễn phí", "Thực phẩm khẩn cấp"],
            "zh": ["免费食品", "紧急食品援助"],
            "ar": ["مواد غذائية مجانية", "طعام للطوارئ"],
        },
    },
    "soup_kitchen": {
        "category": "food",
        "summary": {
            "en": "Soup kitchen in the Food Bank For New York City network serving free hot meals. Call ahead to confirm meal times.",
            "es": "Comedor comunitario de la red de Food Bank For New York City que sirve comidas calientes gratuitas. Llame antes para confirmar el horario de comidas.",
            "vi": "Bếp ăn từ thiện thuộc mạng lưới Food Bank For New York City, phục vụ bữa ăn nóng miễn phí. Vui lòng gọi trước để xác nhận giờ phục vụ.",
            "zh": "Food Bank For New York City 网络中的施食处，免费提供热餐。请提前致电确认供餐时间。",
            "ar": "مطبخ خيري ضمن شبكة Food Bank For New York City يقدم وجبات ساخنة مجانية. يرجى الاتصال مسبقًا لمعرفة مواعيد الوجبات.",
        },
        "services": {
            "en": ["Free hot meals"],
            "es": ["Comidas calientes gratuitas"],
            "vi": ["Bữa ăn nóng miễn phí"],
            "zh": ["免费热餐"],
            "ar": ["وجبات ساخنة مجانية"],
        },
    },
    "hospital": {
        "category": "health",
        "summary": {
            "en": "Hospital licensed by New York State. Emergency rooms are open 24/7 and must treat everyone, regardless of insurance or immigration status.",
            "es": "Hospital autorizado por el Estado de Nueva York. Las salas de emergencia están abiertas 24/7 y deben atender a todos, sin importar su seguro o estatus migratorio.",
            "vi": "Bệnh viện được Tiểu bang New York cấp phép. Phòng cấp cứu mở cửa 24/7 và phải điều trị cho mọi người, bất kể bảo hiểm hay tình trạng di trú.",
            "zh": "纽约州许可的医院。急诊室全天候开放，无论保险或移民身份，都必须为所有人提供治疗。",
            "ar": "مستشفى مرخّص من ولاية نيويورك. أقسام الطوارئ مفتوحة على مدار الساعة ويجب أن تعالج الجميع بغض النظر عن التأمين أو وضع الهجرة.",
        },
        "services": {
            "en": ["Emergency care", "Primary & specialty care"],
            "es": ["Atención de emergencia", "Atención primaria y especializada"],
            "vi": ["Cấp cứu", "Chăm sóc ban đầu & chuyên khoa"],
            "zh": ["急诊", "初级与专科医疗"],
            "ar": ["رعاية طارئة", "رعاية أولية وتخصصية"],
        },
    },
    "health_center": {
        "category": "health",
        "summary": {
            "en": "Community health center licensed by New York State (diagnostic and treatment center). Many offer sliding-scale fees and help with insurance enrollment. Call to make an appointment.",
            "es": "Centro de salud comunitario autorizado por el Estado de Nueva York. Muchos ofrecen tarifas según ingresos y ayuda para inscribirse en un seguro. Llame para hacer una cita.",
            "vi": "Trung tâm y tế cộng đồng được Tiểu bang New York cấp phép. Nhiều nơi có mức phí theo thu nhập và hỗ trợ đăng ký bảo hiểm. Vui lòng gọi để đặt lịch hẹn.",
            "zh": "纽约州许可的社区健康中心（诊断与治疗中心）。许多中心按收入收费并协助办理保险。请致电预约。",
            "ar": "مركز صحي مجتمعي مرخّص من ولاية نيويورك. كثير منها يقدم رسومًا حسب الدخل ومساعدة في التسجيل في التأمين. اتصل لتحديد موعد.",
        },
        "services": {
            "en": ["Primary care", "Insurance enrollment help"],
            "es": ["Atención primaria", "Ayuda para inscribirse en un seguro"],
            "vi": ["Chăm sóc sức khỏe ban đầu", "Hỗ trợ đăng ký bảo hiểm"],
            "zh": ["初级医疗", "保险登记协助"],
            "ar": ["رعاية أولية", "مساعدة في التسجيل في التأمين"],
        },
    },
    "child_health": {
        "category": "health",
        "summary": {
            "en": "NYC Health + Hospitals community site with care for children and families, including checkups and vaccines. NYC Health + Hospitals serves everyone, regardless of ability to pay or immigration status.",
            "es": "Sitio comunitario de NYC Health + Hospitals con atención para niños y familias, incluidos chequeos y vacunas. Atiende a todos, sin importar su capacidad de pago o estatus migratorio.",
            "vi": "Cơ sở cộng đồng của NYC Health + Hospitals chăm sóc trẻ em và gia đình, gồm khám sức khỏe và tiêm chủng. Phục vụ mọi người, bất kể khả năng chi trả hay tình trạng di trú.",
            "zh": "NYC Health + Hospitals 社区站点，为儿童和家庭提供体检和疫苗等服务。无论支付能力或移民身份，均为所有人服务。",
            "ar": "موقع مجتمعي تابع لـ NYC Health + Hospitals يقدم رعاية للأطفال والعائلات تشمل الفحوصات واللقاحات. يخدم الجميع بغض النظر عن القدرة على الدفع أو وضع الهجرة.",
        },
        "services": {
            "en": ["Child checkups", "Vaccines", "Family care"],
            "es": ["Chequeos infantiles", "Vacunas", "Atención familiar"],
            "vi": ["Khám sức khỏe trẻ em", "Tiêm chủng", "Chăm sóc gia đình"],
            "zh": ["儿童体检", "疫苗接种", "家庭医疗"],
            "ar": ["فحوصات الأطفال", "اللقاحات", "رعاية الأسرة"],
        },
    },
    "opioid_treatment": {
        "category": "rehab",
        "summary": {
            "en": "Opioid treatment program (methadone / medication for addiction treatment) certified by New York State OASAS. Call for intake hours. The NY HOPEline (1-877-846-7369) is free and open 24/7.",
            "es": "Programa de tratamiento de opioides (metadona / medicamentos para la adicción) certificado por OASAS del Estado de Nueva York. Llame para conocer el horario de admisión. NY HOPEline (1-877-846-7369) es gratis y está abierta 24/7.",
            "vi": "Chương trình điều trị nghiện opioid (methadone / thuốc điều trị nghiện) được OASAS Tiểu bang New York chứng nhận. Gọi để biết giờ tiếp nhận. Đường dây NY HOPEline (1-877-846-7369) miễn phí và hoạt động 24/7.",
            "zh": "经纽约州 OASAS 认证的阿片类药物治疗项目（美沙酮/成瘾药物治疗）。请致电了解接诊时间。NY HOPEline（1-877-846-7369）免费且全天候开放。",
            "ar": "برنامج علاج إدمان المواد الأفيونية (الميثادون / الأدوية لعلاج الإدمان) معتمد من OASAS بولاية نيويورك. اتصل لمعرفة مواعيد الاستقبال. خط NY HOPEline (1-877-846-7369) مجاني ومتاح على مدار الساعة.",
        },
        "services": {
            "en": ["Opioid treatment", "Counseling"],
            "es": ["Tratamiento de opioides", "Consejería"],
            "vi": ["Điều trị nghiện opioid", "Tư vấn"],
            "zh": ["阿片类药物治疗", "心理辅导"],
            "ar": ["علاج إدمان الأفيونات", "استشارات"],
        },
        "name_suffix": {
            "en": "Opioid Treatment Program",
            "es": "Programa de Tratamiento de Opioides",
            "vi": "Chương trình Điều trị Nghiện Opioid",
            "zh": "阿片类药物治疗项目",
            "ar": "برنامج علاج إدمان الأفيونات",
        },
    },
    "library": {
        "category": "education",
        "summary": {
            "en": "New York Public Library branch. Free computers and Wi-Fi, books, homework help, ESOL and job-search programs. A library card is free for anyone who lives, works or studies in New York State.",
            "es": "Sucursal de la Biblioteca Pública de Nueva York. Computadoras y Wi-Fi gratis, libros, ayuda con tareas, clases de inglés y programas de búsqueda de empleo. La tarjeta es gratis para quien vive, trabaja o estudia en el Estado de Nueva York.",
            "vi": "Chi nhánh Thư viện Công cộng New York. Máy tính và Wi-Fi miễn phí, sách, hỗ trợ bài tập, lớp tiếng Anh và chương trình tìm việc. Thẻ thư viện miễn phí cho người sống, làm việc hoặc học tập tại Tiểu bang New York.",
            "zh": "纽约公共图书馆分馆。提供免费电脑和 Wi-Fi、图书、作业辅导、英语课程和求职项目。在纽约州居住、工作或学习的人均可免费办理借书证。",
            "ar": "فرع مكتبة نيويورك العامة. حواسيب وإنترنت لاسلكي مجانًا، كتب، مساعدة في الواجبات، دروس لغة إنجليزية وبرامج للبحث عن عمل. بطاقة المكتبة مجانية لكل من يعيش أو يعمل أو يدرس في ولاية نيويورك.",
        },
        "services": {
            "en": ["Free computers & Wi-Fi", "Homework help", "ESOL classes"],
            "es": ["Computadoras y Wi-Fi gratis", "Ayuda con tareas", "Clases de inglés"],
            "vi": ["Máy tính & Wi-Fi miễn phí", "Hỗ trợ bài tập", "Lớp tiếng Anh"],
            "zh": ["免费电脑和 Wi-Fi", "作业辅导", "英语课程"],
            "ar": ["حواسيب وإنترنت مجانًا", "مساعدة في الواجبات", "دروس اللغة الإنجليزية"],
        },
    },
    "adult_education": {
        "category": "education",
        "summary": {
            "en": "City-funded adult education program: basic reading, writing and math, and preparation for the high school equivalency (HSE) exam. Classes are free. Call to ask about enrollment.",
            "es": "Programa de educación para adultos financiado por la ciudad: lectura, escritura y matemáticas básicas, y preparación para el examen de equivalencia de secundaria (HSE). Las clases son gratuitas. Llame para inscribirse.",
            "vi": "Chương trình giáo dục người lớn do thành phố tài trợ: đọc, viết, toán cơ bản và luyện thi tương đương trung học (HSE). Lớp học miễn phí. Gọi để hỏi về đăng ký.",
            "zh": "市政府资助的成人教育项目：基础阅读、写作和数学，以及高中同等学力（HSE）考试准备。课程免费，请致电咨询报名。",
            "ar": "برنامج تعليم كبار ممول من المدينة: القراءة والكتابة والرياضيات الأساسية والتحضير لامتحان معادلة الثانوية (HSE). الدروس مجانية. اتصل للاستفسار عن التسجيل.",
        },
        "services": {
            "en": ["Adult basic education", "HSE exam prep"],
            "es": ["Educación básica para adultos", "Preparación para el examen HSE"],
            "vi": ["Giáo dục cơ bản cho người lớn", "Luyện thi HSE"],
            "zh": ["成人基础教育", "HSE 考试准备"],
            "ar": ["تعليم أساسي للكبار", "التحضير لامتحان HSE"],
        },
        "name_suffix": {
            "en": "Adult Education",
            "es": "Educación para Adultos",
            "vi": "Giáo dục Người lớn",
            "zh": "成人教育",
            "ar": "تعليم الكبار",
        },
    },
    "esl": {
        "category": "education",
        "summary": {
            "en": "City-funded English classes for adults who speak other languages (ESOL). Classes are free. Call to ask about enrollment and class times.",
            "es": "Clases de inglés financiadas por la ciudad para adultos que hablan otros idiomas (ESOL). Las clases son gratuitas. Llame para preguntar por la inscripción y los horarios.",
            "vi": "Lớp tiếng Anh do thành phố tài trợ dành cho người lớn nói ngôn ngữ khác (ESOL). Lớp học miễn phí. Gọi để hỏi về đăng ký và giờ học.",
            "zh": "市政府资助的成人英语课程（ESOL），面向母语非英语的成年人。课程免费，请致电咨询报名和上课时间。",
            "ar": "دروس لغة إنجليزية ممولة من المدينة للبالغين الناطقين بلغات أخرى (ESOL). الدروس مجانية. اتصل للاستفسار عن التسجيل والمواعيد.",
        },
        "services": {
            "en": ["English classes (ESOL)"],
            "es": ["Clases de inglés (ESOL)"],
            "vi": ["Lớp tiếng Anh (ESOL)"],
            "zh": ["英语课程 (ESOL)"],
            "ar": ["دروس اللغة الإنجليزية (ESOL)"],
        },
        "name_suffix": {
            "en": "English Classes",
            "es": "Clases de Inglés",
            "vi": "Lớp Tiếng Anh",
            "zh": "英语课程",
            "ar": "دروس اللغة الإنجليزية",
        },
    },
    "hse_prep": {
        "category": "education",
        "summary": {
            "en": "NYC Public Schools Pathways to Graduation site: free classes to prepare for the high school equivalency (HSE) diploma, for ages 18-24. Call to ask about enrollment.",
            "es": "Sitio de Pathways to Graduation de las Escuelas Públicas de NYC: clases gratuitas para obtener el diploma de equivalencia de secundaria (HSE), para jóvenes de 18 a 24 años. Llame para inscribirse.",
            "vi": "Cơ sở Pathways to Graduation của Trường Công lập NYC: lớp học miễn phí chuẩn bị bằng tương đương trung học (HSE) cho người 18-24 tuổi. Gọi để hỏi về đăng ký.",
            "zh": "纽约市公立学校 Pathways to Graduation 站点：为 18-24 岁青年免费提供高中同等学力（HSE）文凭备考课程。请致电咨询报名。",
            "ar": "موقع برنامج Pathways to Graduation التابع لمدارس مدينة نيويورك العامة: دروس مجانية للحصول على شهادة معادلة الثانوية (HSE) للأعمار 18-24. اتصل للاستفسار عن التسجيل.",
        },
        "services": {
            "en": ["HSE / GED classes", "Ages 18-24"],
            "es": ["Clases HSE / GED", "De 18 a 24 años"],
            "vi": ["Lớp HSE / GED", "Từ 18-24 tuổi"],
            "zh": ["HSE / GED 课程", "18-24 岁"],
            "ar": ["دروس HSE / GED", "الأعمار 18-24"],
        },
        "name_suffix": {
            "en": "HSE Prep (Pathways to Graduation)",
            "es": "Preparación HSE (Pathways to Graduation)",
            "vi": "Luyện thi HSE (Pathways to Graduation)",
            "zh": "HSE 备考（Pathways to Graduation）",
            "ar": "التحضير لـ HSE (Pathways to Graduation)",
        },
    },
    "workforce1": {
        "category": "jobs",
        "summary": {
            "en": "NYC Workforce1 Career Center: free job-search help, job listings, resume help and training referrals for New Yorkers.",
            "es": "Centro de Carreras Workforce1 de NYC: ayuda gratuita para buscar empleo, ofertas de trabajo, ayuda con el currículum y referidos a capacitación.",
            "vi": "Trung tâm Nghề nghiệp Workforce1 của NYC: hỗ trợ tìm việc miễn phí, danh sách việc làm, hỗ trợ viết hồ sơ xin việc và giới thiệu khóa đào tạo.",
            "zh": "纽约市 Workforce1 职业中心：免费提供求职帮助、职位信息、简历指导和培训推荐。",
            "ar": "مركز Workforce1 للتوظيف في مدينة نيويورك: مساعدة مجانية في البحث عن عمل، قوائم وظائف، مساعدة في السيرة الذاتية وإحالات للتدريب.",
        },
        "services": {
            "en": ["Job search help", "Resume help", "Training referrals"],
            "es": ["Ayuda para buscar empleo", "Ayuda con el currículum", "Referidos a capacitación"],
            "vi": ["Hỗ trợ tìm việc", "Hỗ trợ hồ sơ xin việc", "Giới thiệu đào tạo"],
            "zh": ["求职帮助", "简历指导", "培训推荐"],
            "ar": ["مساعدة في البحث عن عمل", "مساعدة في السيرة الذاتية", "إحالات للتدريب"],
        },
    },
    "job_program": {
        "category": "jobs",
        "summary": {
            "en": "City-funded employment program offering job training, job placement and career coaching. Call to check eligibility.",
            "es": "Programa de empleo financiado por la ciudad que ofrece capacitación, colocación laboral y orientación profesional. Llame para verificar si califica.",
            "vi": "Chương trình việc làm do thành phố tài trợ, cung cấp đào tạo nghề, giới thiệu việc làm và tư vấn nghề nghiệp. Gọi để kiểm tra điều kiện tham gia.",
            "zh": "市政府资助的就业项目，提供职业培训、工作安置和职业辅导。请致电确认资格。",
            "ar": "برنامج توظيف ممول من المدينة يقدم التدريب المهني والتوظيف والإرشاد المهني. اتصل للتحقق من الأهلية.",
        },
        "services": {
            "en": ["Job training", "Job placement", "Career coaching"],
            "es": ["Capacitación laboral", "Colocación laboral", "Orientación profesional"],
            "vi": ["Đào tạo nghề", "Giới thiệu việc làm", "Tư vấn nghề nghiệp"],
            "zh": ["职业培训", "工作安置", "职业辅导"],
            "ar": ["تدريب مهني", "توظيف", "إرشاد مهني"],
        },
        "name_suffix": {
            "en": "Employment Program",
            "es": "Programa de Empleo",
            "vi": "Chương trình Việc làm",
            "zh": "就业项目",
            "ar": "برنامج التوظيف",
        },
    },
    "benefits_center": {
        "category": "community",
        "summary": {
            "en": "NYC Human Resources Administration (HRA) office. Apply for or get help with SNAP (food stamps), Cash Assistance or Medicaid. Many services are also available online through ACCESS HRA.",
            "es": "Oficina de la Administración de Recursos Humanos de NYC (HRA). Solicite o reciba ayuda con SNAP (cupones de alimentos), Asistencia en Efectivo o Medicaid. Muchos servicios también están en línea en ACCESS HRA.",
            "vi": "Văn phòng Sở Quản lý Nguồn nhân lực NYC (HRA). Nộp đơn hoặc được hỗ trợ về SNAP (phiếu thực phẩm), Trợ cấp Tiền mặt hoặc Medicaid. Nhiều dịch vụ cũng có trực tuyến qua ACCESS HRA.",
            "zh": "纽约市人力资源管理局（HRA）办公室。可申请或咨询 SNAP（食品券）、现金援助或 Medicaid。许多服务也可通过 ACCESS HRA 在线办理。",
            "ar": "مكتب إدارة الموارد البشرية في مدينة نيويورك (HRA). قدّم طلبًا أو احصل على مساعدة بخصوص SNAP (قسائم الطعام) أو المساعدة النقدية أو Medicaid. كثير من الخدمات متاحة أيضًا عبر الإنترنت من خلال ACCESS HRA.",
        },
        "services": {
            "en": ["SNAP (food stamps)", "Cash Assistance", "Medicaid"],
            "es": ["SNAP (cupones de alimentos)", "Asistencia en Efectivo", "Medicaid"],
            "vi": ["SNAP (phiếu thực phẩm)", "Trợ cấp Tiền mặt", "Medicaid"],
            "zh": ["SNAP（食品券）", "现金援助", "Medicaid"],
            "ar": ["SNAP (قسائم الطعام)", "المساعدة النقدية", "Medicaid"],
        },
    },
    "community_center": {
        "category": "community",
        "summary": {
            "en": "NYCHA community center with free programs for youth, adults and seniors (programs vary by site, e.g. after-school, Cornerstone, senior activities). Open to the surrounding neighborhood.",
            "es": "Centro comunitario de NYCHA con programas gratuitos para jóvenes, adultos y personas mayores (varían según el sitio, p. ej. después de la escuela, Cornerstone, actividades para mayores). Abierto al vecindario.",
            "vi": "Trung tâm cộng đồng NYCHA với các chương trình miễn phí cho thanh thiếu niên, người lớn và người cao tuổi (tùy cơ sở, ví dụ sau giờ học, Cornerstone, hoạt động cho người cao tuổi). Mở cửa cho khu dân cư xung quanh.",
            "zh": "纽约市房屋局（NYCHA）社区中心，为青少年、成人和长者提供免费项目（因站点而异，例如课后班、Cornerstone、长者活动），向周边社区开放。",
            "ar": "مركز مجتمعي تابع لهيئة الإسكان (NYCHA) يقدم برامج مجانية للشباب والبالغين وكبار السن (تختلف حسب الموقع، مثل برامج ما بعد المدرسة وCornerstone وأنشطة كبار السن). مفتوح لسكان الحي.",
        },
        "services": {
            "en": ["Youth programs", "Adult & senior programs"],
            "es": ["Programas para jóvenes", "Programas para adultos y mayores"],
            "vi": ["Chương trình thanh thiếu niên", "Chương trình người lớn & cao tuổi"],
            "zh": ["青少年项目", "成人及长者项目"],
            "ar": ["برامج للشباب", "برامج للبالغين وكبار السن"],
        },
        "name_suffix": {
            "en": "Community Center (NYCHA)",
            "es": "Centro Comunitario (NYCHA)",
            "vi": "Trung tâm Cộng đồng (NYCHA)",
            "zh": "社区中心（NYCHA）",
            "ar": "مركز مجتمعي (NYCHA)",
        },
    },
    "immigrant_services": {
        "category": "community",
        "summary": {
            "en": "City-funded immigrant services: help with legal questions, applications and connecting to benefits. Services are confidential. Call to make an appointment.",
            "es": "Servicios para inmigrantes financiados por la ciudad: ayuda con preguntas legales, solicitudes y acceso a beneficios. Los servicios son confidenciales. Llame para hacer una cita.",
            "vi": "Dịch vụ cho người nhập cư do thành phố tài trợ: hỗ trợ câu hỏi pháp lý, hồ sơ và tiếp cận phúc lợi. Dịch vụ được bảo mật. Gọi để đặt lịch hẹn.",
            "zh": "市政府资助的移民服务：协助解答法律问题、填写申请及获取福利。服务保密，请致电预约。",
            "ar": "خدمات للمهاجرين ممولة من المدينة: مساعدة في الأسئلة القانونية والطلبات والوصول إلى المزايا. الخدمات سرية. اتصل لتحديد موعد.",
        },
        "services": {
            "en": ["Immigration help", "Benefits help"],
            "es": ["Ayuda de inmigración", "Ayuda con beneficios"],
            "vi": ["Hỗ trợ di trú", "Hỗ trợ phúc lợi"],
            "zh": ["移民协助", "福利协助"],
            "ar": ["مساعدة في الهجرة", "مساعدة في المزايا"],
        },
        "name_suffix": {
            "en": "Immigrant Services",
            "es": "Servicios para Inmigrantes",
            "vi": "Dịch vụ Người nhập cư",
            "zh": "移民服务",
            "ar": "خدمات المهاجرين",
        },
    },
    "civics_classes": {
        "category": "community",
        "summary": {
            "en": "Free civics and citizenship classes to help immigrants prepare for the U.S. naturalization interview. Call to ask about enrollment.",
            "es": "Clases gratuitas de educación cívica y ciudadanía para ayudar a los inmigrantes a prepararse para la entrevista de naturalización. Llame para inscribirse.",
            "vi": "Lớp học công dân miễn phí giúp người nhập cư chuẩn bị cho buổi phỏng vấn nhập tịch Hoa Kỳ. Gọi để hỏi về đăng ký.",
            "zh": "免费公民课程，帮助移民准备美国入籍面试。请致电咨询报名。",
            "ar": "دروس مجانية في التربية المدنية والجنسية لمساعدة المهاجرين على الاستعداد لمقابلة التجنس الأمريكية. اتصل للاستفسار عن التسجيل.",
        },
        "services": {
            "en": ["Citizenship classes"],
            "es": ["Clases de ciudadanía"],
            "vi": ["Lớp học quốc tịch"],
            "zh": ["入籍课程"],
            "ar": ["دروس الجنسية"],
        },
        "name_suffix": {
            "en": "Citizenship Classes",
            "es": "Clases de Ciudadanía",
            "vi": "Lớp học Quốc tịch",
            "zh": "入籍课程",
            "ar": "دروس الجنسية",
        },
    },
    "drop_in_center": {
        "category": "clothing",
        "summary": {
            "en": "Drop-in center for people experiencing homelessness: clothing, showers, meals, laundry and case management. Open to adults; no appointment needed.",
            "es": "Centro de acogida para personas sin hogar: ropa, duchas, comidas, lavandería y gestión de casos. Para adultos; no se necesita cita.",
            "vi": "Trung tâm tiếp nhận cho người vô gia cư: quần áo, tắm rửa, bữa ăn, giặt giũ và hỗ trợ hồ sơ. Dành cho người lớn; không cần hẹn trước.",
            "zh": "为无家可归者服务的日间中心：提供衣物、淋浴、餐食、洗衣和个案管理。面向成人，无需预约。",
            "ar": "مركز استقبال للأشخاص بلا مأوى: ملابس، استحمام، وجبات، غسيل ملابس وإدارة حالات. للبالغين؛ لا حاجة لموعد.",
        },
        "services": {
            "en": ["Clothing", "Showers & laundry", "Meals", "Case management"],
            "es": ["Ropa", "Duchas y lavandería", "Comidas", "Gestión de casos"],
            "vi": ["Quần áo", "Tắm & giặt giũ", "Bữa ăn", "Hỗ trợ hồ sơ"],
            "zh": ["衣物", "淋浴与洗衣", "餐食", "个案管理"],
            "ar": ["ملابس", "استحمام وغسيل", "وجبات", "إدارة الحالات"],
        },
        "name_suffix": {
            "en": "Drop-In Center",
            "es": "Centro de Acogida",
            "vi": "Trung tâm Tiếp nhận",
            "zh": "日间援助中心",
            "ar": "مركز استقبال",
        },
    },
}
