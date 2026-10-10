# 정본 model.json 생성기 — 용어사전을 먼저 확정하고, 모든 이름은 사전에서만 가져온다.
import json, datetime

SCHEMA = "acad"
AUD = lambda: [
    {"name": "created_at", "kor": "생성시각", "domain": "시각", "nullable": False, "default": "now()"},
    {"name": "updated_at", "kor": "수정시각", "domain": "시각", "nullable": False, "default": "now()"},
]

# ---------- 1. 단어 사전 (kor, abbr, full, is_class, description) ----------
WORDS = [
    ("학과", "dept", "department", False, "학생이 소속되는 학사 조직"),
    ("교수", "prof", "professor", False, "과목을 담당하는 교원"),
    ("학생", "stud", "student", False, "재학 중인 학습자"),
    ("과목", "course", "course", False, "개설된 교과목"),
    ("수강", "enroll", "enrollment", False, "학생이 과목을 듣는 사실"),
    ("성적", "grade", "grade", False, "수강 결과 평가 등급"),
    ("연락처", "contact", "contact", False, "학생과 연결된 연락 수단"),
    ("주체", "subject", "subject", False, "연락처의 소유 주체(본인·보호자)"),
    ("유형", "type", "type", False, "분류 유형"),
    ("비상", "emerg", "emergency", False, "비상 연락망"),
    ("값", "val", "value", False, "실제 내용 값"),
    ("학점", "credit", "credit", False, "이수 학점"),
    ("개인정보", "pi", "personal_information", False, "개인 식별·민감 정보 테이블 접두어"),
    ("코드표", "code", "code_table", False, "코드 테이블 접미어(코드값 분류어 cd 와 구분)"),
    ("생성", "created", "created", False, "행 생성"),
    ("수정", "updated", "updated", False, "행 최종 수정"),
    ("사용", "use", "use", False, "사용 중 여부"),
    ("순서", "sort", "sort", False, "표시 순서"),
    ("코드", "cd", "code", True, "분류어: 코드값"),
    ("번호", "no", "number", True, "분류어: 업무 식별 번호"),
    ("명", "nm", "name", True, "분류어: 명칭"),
    ("식별자", "id", "identifier", True, "분류어: 시스템 대리키"),
    ("여부", "yn", "yes_no", True, "분류어: 참/거짓"),
    ("시각", "at", "timestamp", True, "분류어: 일시"),
]

# ---------- 2. 도메인 ----------
DOMAINS = {
    "식별자":    {"type": "bigint",       "check": None, "example": "1001", "desc": "시스템 대리키"},
    "코드(10)":  {"type": "varchar(10)",  "check": None, "example": "SELF", "desc": "코드값"},
    "성적등급":  {"type": "varchar(2)",   "check": "IN ('A+','A0','B+','B0','C+','C0','D+','D0','F')", "example": "A0", "desc": "성적 등급 9종"},
    "번호(10)":  {"type": "varchar(10)",  "check": None, "example": "S001", "desc": "업무 식별 번호"},
    "명칭(50)":  {"type": "varchar(50)",  "check": None, "example": "김민준", "desc": "짧은 명칭"},
    "명칭(100)": {"type": "varchar(100)", "check": None, "example": "컴퓨터공학과", "desc": "긴 명칭"},
    "연락처값":  {"type": "varchar(200)", "check": None, "example": "010-1234-5678", "desc": "전화·이메일·주소 등 실제 값"},
    "학점":      {"type": "smallint",     "check": "BETWEEN 0 AND 10", "example": "3", "desc": "이수 학점"},
    "여부":      {"type": "boolean",      "check": None, "example": "true", "desc": "참/거짓"},
    "순서":      {"type": "integer",      "check": None, "example": "1", "desc": "표시 순서"},
    "시각":      {"type": "timestamptz",  "check": None, "example": "2026-03-01 09:00+09", "desc": "일시(시간대 포함)"},
}

def col(name, kor, domain, nullable=True, pk=False, unique=False, identity=False, default=None, fk=None, pi=False, check=None, desc=None):
    c = {"name": name, "kor": kor, "domain": domain, "nullable": nullable}
    if pk: c["pk"] = True
    if unique: c["unique"] = True
    if identity: c["identity"] = True
    if default is not None: c["default"] = default
    if fk: c["fk"] = fk
    if pi: c["pi"] = True
    if check: c["check"] = check
    if desc: c["description"] = desc
    return c

FK = lambda t, c, od="RESTRICT": {"table": t, "column": c, "on_delete": od}

TABLES = [
    {"name": "contact_subject_code", "kor": "연락처주체코드", "kind": "코드", "is_pi": False,
     "description": "연락처 주체 분류(본인·어머니·아버지·보호자·기타)",
     "columns": [
        col("subject_cd", "주체코드", "코드(10)", False, pk=True),
        col("subject_nm", "주체명", "명칭(50)", False),
        col("sort_no", "순서번호", "순서", False, default="0"),
        col("use_yn", "사용여부", "여부", False, default="true"),
     ] + AUD(),
     "seed": [["SELF","본인",1],["MOTHER","어머니",2],["FATHER","아버지",3],["GUARDIAN","보호자",4],["ETC","기타",9]]},
    {"name": "contact_type_code", "kor": "연락처유형코드", "kind": "코드", "is_pi": False,
     "description": "연락처 유형 분류(휴대전화·집전화·이메일·주소)",
     "columns": [
        col("type_cd", "유형코드", "코드(10)", False, pk=True),
        col("type_nm", "유형명", "명칭(50)", False),
        col("sort_no", "순서번호", "순서", False, default="0"),
        col("use_yn", "사용여부", "여부", False, default="true"),
     ] + AUD(),
     "seed": [["MOBILE","휴대전화",1],["HOME","집전화",2],["EMAIL","이메일",3],["ADDR","주소",4]]},
    {"name": "department", "kor": "학과", "kind": "기준", "is_pi": False,
     "description": "학생이 소속되는 학사 조직",
     "columns": [
        col("dept_id", "학과식별자", "식별자", False, pk=True, identity=True),
        col("dept_cd", "학과코드", "코드(10)", False, unique=True, desc="업무 자연키"),
        col("dept_nm", "학과명", "명칭(100)", False),
        col("use_yn", "사용여부", "여부", False, default="true"),
     ] + AUD()},
    {"name": "professor", "kor": "교수", "kind": "기준", "is_pi": False,
     "description": "과목을 담당하는 교원. 성명은 pi_professor",
     "columns": [
        col("prof_id", "교수식별자", "식별자", False, pk=True, identity=True),
        col("prof_no", "교수번호", "번호(10)", False, unique=True, desc="업무 자연키"),
     ] + AUD()},
    {"name": "pi_professor", "kor": "교수개인정보", "kind": "PI", "is_pi": True,
     "description": "교수 성명 등 개인정보. professor 와 1:1",
     "columns": [
        col("prof_id", "교수식별자", "식별자", False, pk=True, fk=FK("professor","prof_id","CASCADE")),
        col("prof_nm", "교수명", "명칭(50)", False, pi=True),
     ] + AUD()},
    {"name": "student", "kor": "학생", "kind": "기준", "is_pi": False,
     "description": "재학생. 성명은 pi_student",
     "columns": [
        col("stud_id", "학생식별자", "식별자", False, pk=True, identity=True),
        col("stud_no", "학생번호", "번호(10)", False, unique=True, desc="업무 자연키"),
        col("dept_id", "학과식별자", "식별자", False, fk=FK("department","dept_id")),
     ] + AUD()},
    {"name": "pi_student", "kor": "학생개인정보", "kind": "PI", "is_pi": True,
     "description": "학생 성명 등 개인정보. student 와 1:1",
     "columns": [
        col("stud_id", "학생식별자", "식별자", False, pk=True, fk=FK("student","stud_id","CASCADE")),
        col("stud_nm", "학생명", "명칭(50)", False, pi=True),
     ] + AUD()},
    {"name": "course", "kor": "과목", "kind": "기준", "is_pi": False,
     "description": "개설 과목. 이수학점과 담당 교수 1명",
     "columns": [
        col("course_id", "과목식별자", "식별자", False, pk=True, identity=True),
        col("course_cd", "과목코드", "코드(10)", False, unique=True, desc="업무 자연키"),
        col("course_nm", "과목명", "명칭(100)", False),
        col("credit", "학점", "학점", False),
        col("prof_id", "교수식별자", "식별자", False, fk=FK("professor","prof_id")),
     ] + AUD()},
    {"name": "enrollment", "kor": "수강성적", "kind": "거래", "is_pi": False,
     "description": "학생×과목 교차. 성적등급은 이 관계의 속성. PK=(학생,과목)이 중복 수강을 막음",
     "columns": [
        col("stud_id", "학생식별자", "식별자", False, pk=True, fk=FK("student","stud_id")),
        col("course_id", "과목식별자", "식별자", False, pk=True, fk=FK("course","course_id")),
        col("grade_cd", "성적등급코드", "성적등급", True, desc="미확정이면 NULL"),
     ] + AUD()},
    {"name": "contact", "kor": "연락처", "kind": "거래", "is_pi": False,
     "description": "학생 1명에 여러 개. 주체·유형·비상여부. 실제 값은 pi_contact",
     "columns": [
        col("contact_id", "연락처식별자", "식별자", False, pk=True, identity=True),
        col("stud_id", "학생식별자", "식별자", False, fk=FK("student","stud_id","CASCADE")),
        col("subject_cd", "주체코드", "코드(10)", False, fk=FK("contact_subject_code","subject_cd")),
        col("type_cd", "유형코드", "코드(10)", False, fk=FK("contact_type_code","type_cd")),
        col("emerg_yn", "비상여부", "여부", False, default="false"),
        col("use_yn", "사용여부", "여부", False, default="true"),
     ] + AUD()},
    {"name": "pi_contact", "kor": "연락처개인정보", "kind": "PI", "is_pi": True,
     "description": "전화번호·주소 등 연락처 실제 값. contact 와 1:1",
     "columns": [
        col("contact_id", "연락처식별자", "식별자", False, pk=True, fk=FK("contact","contact_id","CASCADE")),
        col("contact_val", "연락처값", "연락처값", False, pi=True),
     ] + AUD()},
]

# ---------- 3. 용어 = 물리명 전수 (테이블명 + 컬럼명). 모든 이름은 단어 abbr 조합이어야 한다 ----------
# 규칙: 테이블명은 단어의 영문 전체형(full), 컬럼명은 약어(abbr)를 쓴다. 둘 다 사전에 있어야 한다.
tok2kor = {}
for w in WORDS:
    tok2kor[w[1]] = w[0]; tok2kor[w[2]] = w[0]
def word_path(phys):
    toks = phys.split("_")
    bad = [t for t in toks if t not in tok2kor]
    if bad: raise SystemExit(f"사전에 없는 단어: {bad} in {phys}")
    return ">".join(tok2kor[t] for t in toks)

terms = {}
for t in TABLES:
    terms.setdefault(t["name"], {"kor": t["kor"], "phys": t["name"], "word_path": word_path(t["name"]), "domain": None, "desc": t["description"]})
    for c in t["columns"]:
        terms.setdefault(c["name"], {"kor": c["kor"], "phys": c["name"], "word_path": word_path(c["name"]), "domain": c["domain"], "desc": c.get("description")})

# ---------- 4. 관계 요약 ----------
rels = []
for t in TABLES:
    for c in t["columns"]:
        if c.get("fk"):
            one_to_one = c.get("pk") and len([x for x in t["columns"] if x.get("pk")]) == 1
            rels.append({"from": t["name"], "from_col": c["name"], "to": c["fk"]["table"], "to_col": c["fk"]["column"],
                         "type": "1:1" if one_to_one else "N:1", "optional": c["nullable"], "on_delete": c["fk"]["on_delete"],
                         "meaning": f"{t['kor']}.{c['kor']} → {c['fk']['table']}"})

model = {
    "project": "학사관리(수강·성적·연락처) 입문 모델", "version": "1.0", "generated_at": datetime.date.today().isoformat(),
    "db": "postgresql", "db_version": "16", "schema": SCHEMA, "meta_schema": "meta",
    "modeling_tool": "pgModeler 1.1",
    "assumptions": ["한 학기 기준(학기 엔터티 없음)", "분반 없음", "과목당 담당 교수 1명", "연락처는 현재값만 관리(이력 없음)", "성적등급 9종 고정 → CHECK"],
    "open_questions": ["교수의 학과 소속 필요 여부", "학생 상태(재학·휴학·졸업) 필요 여부", "학기 구분 선반영 여부"],
    "words": [{"kor": w[0], "abbr": w[1], "full": w[2], "is_class": w[3], "desc": w[4]} for w in WORDS],
    "domains": [{"name": k, **v} for k, v in DOMAINS.items()],
    "terms": list(terms.values()),
    "tables": TABLES,
    "relationships": rels,
    "pi_suggestions": [
        "pi_* 테이블을 별도 스키마(pi)로 옮기고 전용 ROLE에만 SELECT 부여",
        "pi_contact.contact_val, pi_student.stud_nm 에 pgcrypto(pgp_sym_encrypt) 컬럼 암호화 적용 검토",
        "일반 조회용 마스킹 뷰(v_student_masked: 김*준, 010-****-2222) 제공",
        "졸업·탈퇴 후 보존 기간(예: 5년) 경과 시 pi_* 파기 배치",
        "행 수준 보안(RLS)으로 담당 학과 외 접근 차단",
    ],
    "dq_notes": [
        "모든 테이블 PK 보유, 업무 자연키(학과코드·교수번호·학생번호·과목코드) UNIQUE",
        "enrollment PK=(stud_id, course_id)로 같은 과목 중복 수강 행 차단",
        "성적등급 CHECK 9종, 학점 CHECK 0~10",
        "모든 FK 삭제규칙 명시: 기준 참조는 RESTRICT, 종속(학생→연락처, 본체→PI)은 CASCADE",
        "FK 컬럼마다 인덱스",
        "시각은 timestamptz, 이름·코드는 varchar 길이 제한",
    ],
}
json.dump(model, open("model.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("model.json  tables:", len(TABLES), "terms:", len(terms), "words:", len(WORDS), "rels:", len(rels))
