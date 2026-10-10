"""원천 가져오기 — 로컬 파일 / URL(파일·zip) / 공공데이터포털 Open API(JSON) → 로컬 파일 → DataFrame."""
from __future__ import annotations
import csv, io, json, os, re, zipfile
from urllib.parse import urlparse, unquote
import pandas as pd

TABLE_EXT = (".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls", ".json")


def fetch(src: str, work_dir: str) -> list[str]:
    """src(경로 또는 URL) → 로컬 파일 경로 목록 (zip 은 풀어서 표 파일만)"""
    os.makedirs(work_dir, exist_ok=True)
    if re.match(r"^https?://", src):
        import httpx
        with httpx.stream("GET", src, follow_redirects=True, timeout=120) as r:
            r.raise_for_status()
            name = None
            cd = r.headers.get("content-disposition", "")
            m = re.search(r"filename\*=UTF-8''([^;]+)", cd) or re.search(r'filename="?([^";]+)"?', cd)
            if m:
                name = unquote(m.group(1))
            if not name:
                name = os.path.basename(urlparse(src).path) or "download"
            ctype = r.headers.get("content-type", "")
            if "." not in name:
                name += ".json" if "json" in ctype else ".csv" if "csv" in ctype else ".bin"
            path = os.path.join(work_dir, re.sub(r"[\\/:*?\"<>|]", "_", name))
            with open(path, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
    else:
        path = src
        if not os.path.exists(path):
            raise FileNotFoundError(path)
    if zipfile.is_zipfile(path) and not path.lower().endswith((".xlsx", ".xlsm")):
        out = os.path.join(work_dir, os.path.splitext(os.path.basename(path))[0])
        with zipfile.ZipFile(path) as z:
            files = []
            for info in z.infolist():
                n = info.filename
                try:  # 한글 파일명(cp949) 복원
                    n = n.encode("cp437").decode("cp949")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
                if n.lower().endswith(TABLE_EXT) and not info.is_dir():
                    dst = os.path.join(out, n); os.makedirs(os.path.dirname(dst), exist_ok=True)
                    with z.open(info) as s, open(dst, "wb") as d:
                        d.write(s.read())
                    files.append(dst)
        return files
    return [path]


def detect_encoding(path: str) -> str:
    raw = open(path, "rb").read(1 << 20)
    for enc in ("utf-8-sig", "cp949"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            # 잘린 멀티바이트 끝부분 허용
            try:
                raw[:-4].decode(enc); return enc
            except UnicodeDecodeError:
                continue
    from charset_normalizer import from_bytes
    best = from_bytes(raw).best()
    return best.encoding if best else "utf-8"


def detect_delimiter(path: str, enc: str) -> str:
    if path.lower().endswith(".tsv"):
        return "\t"
    sample = open(path, encoding=enc, errors="replace").read(65536)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t|;").delimiter
    except csv.Error:
        return ","


def read(path: str, sheet=None, nrows: int | None = None) -> dict[str, pd.DataFrame]:
    """표 파일 → {이름: DataFrame}. 모든 값은 문자열로 읽고(앞자리 0 보존) 타입은 profile 에서 추론"""
    low = path.lower()
    if low.endswith((".xlsx", ".xlsm", ".xls")):
        dfs = pd.read_excel(path, sheet_name=sheet if sheet is not None else None, dtype=str, nrows=nrows)
        if isinstance(dfs, pd.DataFrame):
            dfs = {str(sheet): dfs}
        return {k: _clean(v) for k, v in dfs.items()}
    if low.endswith(".json"):
        data = json.load(open(path, encoding=detect_encoding(path)))
        items = _find_records(data)
        df = pd.json_normalize(items).astype(str).replace({"None": None, "nan": None})
        return {os.path.splitext(os.path.basename(path))[0]: _clean(df.head(nrows) if nrows else df)}
    enc = detect_encoding(path)
    df = pd.read_csv(path, encoding=enc, sep=detect_delimiter(path, enc), dtype=str, nrows=nrows,
                     keep_default_na=False, na_values=[""], engine="python" if nrows is None else "c")
    return {os.path.splitext(os.path.basename(path))[0]: _clean(df)}


def iter_csv(path: str, chunksize: int = 50000):
    enc = detect_encoding(path)
    for ch in pd.read_csv(path, encoding=enc, sep=detect_delimiter(path, enc), dtype=str, chunksize=chunksize,
                          keep_default_na=False, na_values=[""]):
        yield _clean(ch)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().replace("\n", " ") for c in df.columns]
    df = df.loc[:, [not str(c).startswith("Unnamed:") or df[c].notna().any() for c in df.columns]]
    for c in df.columns:
        df[c] = df[c].map(lambda v: None if v is None or (isinstance(v, float) and v != v) or (isinstance(v, str) and v.strip() == "") else str(v).strip())
    return df.dropna(how="all")


def _find_records(data):
    """공공데이터 API 응답에서 레코드 배열 찾기 (response.body.items.item / data / items …)"""
    if isinstance(data, list):
        return data
    for path in (("response", "body", "items", "item"), ("response", "body", "items"), ("data",), ("items",), ("records",)):
        cur = data
        for k in path:
            cur = cur.get(k) if isinstance(cur, dict) else None
        if isinstance(cur, list):
            return cur
        if isinstance(cur, dict):
            return [cur]
    raise ValueError("JSON 에서 레코드 배열을 찾지 못했습니다")


def estimate_rows(path: str) -> int | None:
    """큰 CSV 의 전체 행 수 추정(앞 4MB 평균 줄 길이로)"""
    low = path.lower()
    if not low.endswith((".csv", ".tsv", ".txt")):
        return None
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(4 << 20)
    lines = head.count(b"\n")
    if size <= len(head):
        return max(lines - 1, 0)
    return int(size / (len(head) / max(lines, 1)))


def datago_api(url: str, service_key: str, params: dict | None = None, out_path: str = "api.json",
               max_pages: int = 1000, rows: int = 1000) -> str:
    """공공데이터포털 Open API 페이징 수집 → JSON 배열 파일 (resultType=json 지원 API 기준)"""
    import httpx
    items, page = [], 1
    while page <= max_pages:
        p = {"serviceKey": service_key, "pageNo": page, "numOfRows": rows, "resultType": "json", "type": "json", **(params or {})}
        r = httpx.get(url, params=p, timeout=60)
        r.raise_for_status()
        data = r.json()
        batch = _find_records(data)
        items += batch
        total = None
        try:
            total = int(data["response"]["body"]["totalCount"])
        except Exception:
            total = data.get("totalCount") if isinstance(data, dict) else None
        if not batch or (total is not None and len(items) >= int(total)) or len(batch) < rows:
            break
        page += 1
    json.dump(items, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
    return out_path
