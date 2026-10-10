"""데이터 프로파일 — 타입 추론, 결측·고유값, 개인정보 후보, 대용량(로그성) 판정."""
from __future__ import annotations
import re
from datetime import datetime
import pandas as pd

INT = re.compile(r"^[+-]?\d+$")
NUM = re.compile(r"^[+-]?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$")
DATE = [(re.compile(r"^\d{4}-\d{2}-\d{2}$"), "%Y-%m-%d"), (re.compile(r"^\d{4}\.\d{2}\.\d{2}\.?$"), "%Y.%m.%d"),
        (re.compile(r"^\d{4}/\d{2}/\d{2}$"), "%Y/%m/%d"), (re.compile(r"^\d{8}$"), "%Y%m%d")]
TS = re.compile(r"^\d{4}[-./]\d{2}[-./]\d{2}[ T]\d{1,2}:\d{2}(:\d{2})?(\.\d+)?([+-]\d{2}:?\d{2}|Z)?$")
BOOL = {"y", "n", "yes", "no", "true", "false", "t", "f"}

# 개인정보 판정 — (유형, 이름 패턴, 값 패턴, 권장 암호화, 민감)
PI_RULES = [
    ("주민등록번호", r"주민|rrn|resident", r"^\d{6}-?[1-8]\d{6}$", "aes+hmac", True),
    ("여권번호", r"여권|passport", r"^[A-Z]{1,2}\d{7,8}$", "aes+hmac", True),
    ("운전면허번호", r"면허번호|license_?no", r"^\d{2}-\d{2}-\d{6}-\d{2}$", "aes+hmac", True),
    ("계좌번호", r"계좌|account_?no|bank_?acc", None, "aes", False),
    ("카드번호", r"카드번호|card_?no", r"^\d{4}-?\d{4}-?\d{4}-?\d{4}$", "aes", False),
    ("전화번호", r"전화|휴대|핸드폰|연락처|phone|mobile|tel", r"^0\d{1,2}-?\d{3,4}-?\d{4}$", "aes+hmac", False),
    ("이메일", r"이메일|e-?mail", r"^[\w.+-]+@[\w-]+\.[\w.]+$", "aes+hmac", False),
    ("성명", r"성명|이름|대표자|담당자명|고객명|환자명|학생명|^name$|person", None, "aes", False),
    ("주소", r"상세주소|주소|address|addr", None, "aes", False),
    ("생년월일", r"생년월일|birth", None, "aes", False),
    ("건강정보", r"병명|진단|질병|처방|diagnos", None, "aes", True),
]
# 이름 패턴이 걸려도 개인정보가 아닌 경우 (사업장·기관·도로명 주소 등 공개 정보)
NOT_PI = re.compile(r"사업장|기관|시설|업체|회사|상호|법인|도로명주소|소재지|지번주소|대표전화|팩스|홈페이지")


def infer_type(values: pd.Series, name: str = "") -> tuple[str, str]:
    """(PostgreSQL 자료형, 근거)"""
    v = values.dropna().astype(str)
    if v.empty:
        return "text", "값 없음"
    s = v.head(20000)
    if s.map(lambda x: x.lower() in BOOL).all() and s.str.lower().nunique() <= 2:
        return "boolean", "Y/N·true/false"
    if s.map(lambda x: bool(INT.match(x))).all():
        if s.map(lambda x: len(x.lstrip("+-")) > 1 and x.lstrip("+-").startswith("0")).any():
            return f"varchar({_round_len(s.str.len().max())})", "앞자리 0 → 코드/번호(문자)"
        for rx, fmt in DATE[3:]:
            if s.map(lambda x: bool(rx.match(x))).all() and _all_dates(s, fmt) and re.search(r"일자|날짜|일$|date|dt$|ymd", name, re.I):
                return "date", "YYYYMMDD"
        mx = s.map(lambda x: abs(int(x))).max()
        if re.search(r"번호|코드|_no$|_cd$|code|id$", name, re.I):
            return f"varchar({_round_len(s.str.len().max())})", "숫자형 코드/번호 → 문자 권장"
        return ("integer" if mx < 2_000_000_000 else "bigint"), "정수"
    if s.map(lambda x: bool(NUM.match(x))).all():
        frac = s.map(lambda x: len(x.split(".")[1]) if "." in x else 0).max()
        intd = s.map(lambda x: len(x.split(".")[0].replace(",", "").lstrip("+-"))).max()
        return f"numeric({min(intd + frac + 2, 38)},{frac})", "소수"
    for rx, fmt in DATE[:3]:
        if s.map(lambda x: bool(rx.match(x))).all() and _all_dates(s, fmt):
            return "date", "날짜"
    if s.map(lambda x: bool(TS.match(x))).all():
        return "timestamptz", "일시"
    mx = s.str.len().max()
    return (f"varchar({_round_len(mx)})" if mx <= 2000 else "text"), "문자"


def _round_len(n: int) -> int:
    for b in (1, 2, 5, 10, 20, 30, 50, 100, 200, 300, 500, 1000, 2000):
        if n <= b:
            return b
    return 4000


def _all_dates(s: pd.Series, fmt: str) -> bool:
    try:
        s.head(2000).map(lambda x: datetime.strptime(x.rstrip("."), fmt.rstrip(".")))
        return True
    except ValueError:
        return False


def detect_pi(name: str, values: pd.Series) -> dict | None:
    v = values.dropna().astype(str).head(2000)
    for typ, npat, vpat, crypto, sens in PI_RULES:
        by_name = re.search(npat, name, re.I) and not NOT_PI.search(name)
        by_val = vpat and len(v) > 0 and (v.map(lambda x: bool(re.match(vpat, x))).mean() >= 0.8)
        if by_name or by_val:
            if typ == "성명" and len(v) and v.str.len().max() > 20:
                continue
            return {"pi_type": typ, "crypto": crypto, "sensitive": sens, "by": "name" if by_name else "value"}
    return None


def profile(df: pd.DataFrame, total_rows: int | None = None, file_bytes: int | None = None, cfg=None) -> dict:
    cols = []
    n = len(df)
    for c in df.columns:
        s = df[c]
        typ, why = infer_type(s, c)
        nn = int(s.notna().sum())
        cols.append({"src": c, "type": typ, "type_reason": why, "null_ratio": round(1 - nn / n, 4) if n else 1.0,
                     "distinct": int(s.nunique(dropna=True)), "max_len": int(s.dropna().astype(str).str.len().max() or 0) if nn else 0,
                     "samples": [str(x) for x in s.dropna().head(3)], "pi": detect_pi(c, s)})
    rows = total_rows if total_rows is not None else n
    ing = (cfg or {}).get("ingest", {}) if cfg else {}
    large_rows, large_bytes = ing.get("large_rows", 10_000_000), ing.get("large_bytes", 2 * 1024 ** 3)
    ts_cols = [x["src"] for x in cols if x["type"] in ("timestamptz", "date")]
    reasons = []
    if rows >= large_rows:
        reasons.append(f"행 수 {rows:,} ≥ {large_rows:,}")
    if file_bytes and file_bytes >= large_bytes:
        reasons.append(f"파일 크기 {file_bytes / 1024 ** 3:.1f}GB ≥ {large_bytes / 1024 ** 3:.1f}GB")
    is_log = bool(ts_cols) and rows >= large_rows // 10 and len(cols) <= 40
    if is_log and not reasons:
        reasons.append(f"시각 컬럼({ts_cols[0]})이 있는 대량 이력형(append-only) 데이터")
    return {"rows": rows, "sample_rows": n, "file_bytes": file_bytes, "columns": cols,
            "pi_columns": [x["src"] for x in cols if x["pi"]],
            "store_recommendation": "LAKE" if reasons else "DB", "store_reasons": reasons, "time_columns": ts_cols}
