# 학사 예제(acad/model.json)를 data-platform 설치 DB 용으로 변환하는 예:
#  - meta 사전 공유(meta_mode=shared) · 개인정보 pi 스키마 분리 · 개인정보 AES-128 암호화 · 성적은 '성적' 분류 정책
# 원본 acad/model.json 은 바꾸지 않는다.
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(HERE, "..", "acad", "model.json"), encoding="utf-8"))
M["project"] += " (data-platform)"
M["meta_mode"] = "shared"
M["pi_schema"] = "pi"
M["pi_crypto_required"] = True
M["domains"].append({"name": "암호문", "type": "bytea", "check": None, "example": "\\x01…", "desc": "AES-128-GCM 암호문"})
for t in M["tables"]:
    for c in t["columns"]:
        if c.get("pi"):
            c["domain"] = "암호문"; c["crypto"] = "aes"
for term in M["terms"]:
    if term["phys"] in ("stud_nm", "prof_nm", "contact_val"):
        term["domain"] = "암호문"
M["access_policies"] = [
    {"schema": "acad", "table": "enrollment", "min_grade": "c", "category": "SCORE", "meaning": "성적 — 성적 분류 + C 이상"},
]
M["pi_suggestions"] = ["pi 스키마는 개인정보(PI) 분류 보유 계정만 조회", "화면 표시는 마스킹 함수 사용"]
json.dump(M, open(os.path.join(HERE, "model.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("acad_platform/model.json 생성")
