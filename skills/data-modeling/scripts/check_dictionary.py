#!/usr/bin/env python3
"""model.json 정합성 검사 — 이름은 사전에서만, FK는 실제 컬럼으로, PI는 pi_ 테이블에만.
(v2: pi_schema·crypto·uniques·seed_cols 선택 키가 있으면 함께 검사)
사용: python check_dictionary.py model.json   (문제 있으면 종료코드 1)
"""
import json, sys, re

M = json.load(open(sys.argv[1], encoding="utf-8"))
abbr = {w["abbr"]: w["kor"] for w in M["words"]}
full = {w["full"]: w["kor"] for w in M["words"]}
TBL = {t["name"]: t for t in M["tables"]}
DOM = {d["name"] for d in M["domains"]}
terms = {t["phys"] for t in M["terms"]}
errors, warns = [], []
PIS = M.get("pi_schema")
CRYPTO = ("aes", "hmac", "argon2")
DOMT = {d["name"]: d["type"] for d in M["domains"]}

for t in M["tables"]:
    # 테이블명: 영문 전체형 토큰
    for tok in t["name"].split("_"):
        if tok not in full and tok not in abbr:
            errors.append(f"[사전] 테이블 {t['name']}: 토큰 '{tok}' 없음")
    if t["name"] not in terms: errors.append(f"[용어] 테이블 {t['name']} 이 terms 에 없음")
    pk = [c["name"] for c in t["columns"] if c.get("pk")]
    if not pk: errors.append(f"[PK] {t['name']}: PK 없음")
    cols = {c["name"] for c in t["columns"]}
    for c in t["columns"]:
        for tok in c["name"].split("_"):
            if tok not in abbr and tok not in full:
                errors.append(f"[사전] {t['name']}.{c['name']}: 토큰 '{tok}' 없음")
        if c["name"] not in terms: errors.append(f"[용어] {t['name']}.{c['name']} 이 terms 에 없음")
        if c["domain"] not in DOM: errors.append(f"[도메인] {t['name']}.{c['name']}: 도메인 '{c['domain']}' 없음")
        if c.get("pi") and not t["name"].startswith("pi_"):
            errors.append(f"[PI] {t['name']}.{c['name']} 는 PI 인데 pi_ 테이블 밖에 있음")
        if c.get("fk"):
            f = c["fk"]
            if f["table"] not in TBL: errors.append(f"[FK] {t['name']}.{c['name']} → 없는 테이블 {f['table']}"); continue
            tgt = {x["name"]: x for x in TBL[f["table"]]["columns"]}
            if f["column"] not in tgt: errors.append(f"[FK] {t['name']}.{c['name']} → {f['table']}.{f['column']} 없음"); continue
            if tgt[f["column"]]["domain"] != c["domain"]:
                warns.append(f"[FK 타입] {t['name']}.{c['name']}({c['domain']}) ≠ {f['table']}.{f['column']}({tgt[f['column']]['domain']})")
            if f.get("on_delete") not in ("RESTRICT", "CASCADE", "SET NULL", "NO ACTION"):
                errors.append(f"[FK] {t['name']}.{c['name']}: on_delete 미지정")
    if "created_at" not in cols or "updated_at" not in cols:
        warns.append(f"[감사] {t['name']}: created_at/updated_at 없음")
    if t.get("is_pi") and not t["name"].startswith("pi_"):
        errors.append(f"[PI] {t['name']} is_pi=true 인데 이름이 pi_ 로 시작하지 않음")
    # ---- v2 확장 (선택 키가 있을 때만 검사) ----
    if PIS and t["name"].startswith("pi_") and t.get("schema") and t["schema"] != PIS:
        errors.append(f"[PI] {t['name']}: 개인정보 테이블은 {PIS} 스키마에만 둘 수 있음 (schema={t['schema']})")
    for c in t["columns"]:
        cr = c.get("crypto")
        if cr:
            if cr not in CRYPTO:
                errors.append(f"[암호화] {t['name']}.{c['name']}: crypto '{cr}' 는 aes|hmac|argon2 중 하나여야 함"); continue
            ty = DOMT.get(c["domain"], "")
            if cr in ("aes", "hmac") and ty != "bytea":
                errors.append(f"[암호화] {t['name']}.{c['name']}: {cr} 컬럼의 도메인 자료형은 bytea 여야 함 (현재 {ty})")
            if cr == "argon2" and not (ty == "text" or ty.startswith("varchar")):
                errors.append(f"[암호화] {t['name']}.{c['name']}: argon2 해시는 text/varchar 도메인이어야 함 (현재 {ty})")
        elif M.get("pi_crypto_required") and c.get("pi"):
            errors.append(f"[암호화] {t['name']}.{c['name']}: 개인정보 컬럼에 crypto 지정 필요 (pi_crypto_required)")
    for u in t.get("uniques", []):
        for cn in u:
            if cn not in cols: errors.append(f"[UNIQUE] {t['name']}: 복합 UNIQUE 컬럼 '{cn}' 없음")
    for cn in t.get("seed_cols", []):
        if cn not in cols: errors.append(f"[SEED] {t['name']}: seed_cols 컬럼 '{cn}' 없음")

for w in warns: print("WARN ", w)
for e in errors: print("ERROR", e)
print(f"tables={len(M['tables'])} columns={sum(len(t['columns']) for t in M['tables'])} terms={len(terms)} words={len(M['words'])}  errors={len(errors)} warns={len(warns)}")
sys.exit(1 if errors else 0)
