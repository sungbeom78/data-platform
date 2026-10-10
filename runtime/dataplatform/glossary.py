"""용어 시스템 어댑터.

기본: bomiyang-glossary (https://github.com/sungbeom78/bomiyang-glossary)
  - 단어 = dictionary/words.json 의 id(영문 전체형) / lang.ko(한글) / abbreviation.short 또는 variants[type=abbreviation].short(약어)
  - 복합어 = dictionary/compounds.json (words 배열)
  - 쓰기는 반드시 core/writer.py 의 GlossaryWriter 경유 (JSON 직접 수정 금지 — 저장소 규칙)
대체: DB 공통 스키마 meta 의 word 테이블 (bomiyang 이 없을 때)

※ bomiyang 의 domain(trading/system…)은 '주제 분류'이고, 데이터 도메인(금액·일자·전화번호)은 아니다.
  데이터 도메인은 어느 모드든 model.json domains / meta.domain 에서 관리한다.
"""
from __future__ import annotations
import json, os, re, subprocess, sys
from dataclasses import dataclass, asdict

TOKEN = re.compile(r"^[a-z][a-z0-9]*$")


@dataclass
class Word:
    kor: str
    abbr: str
    full: str
    is_class: bool = False
    desc: str = ""
    source: str = ""

    def as_model(self) -> dict:
        return {"kor": self.kor, "abbr": self.abbr, "full": self.full, "is_class": self.is_class, "desc": self.desc}


# 분류어는 어느 사전이든 공통으로 쓴다 (data-modeling 명명 규칙)
CLASS_WORDS = [
    Word("코드", "cd", "code", True, "분류어: 코드값", "builtin"),
    Word("번호", "no", "number", True, "분류어: 업무 식별 번호", "builtin"),
    Word("명", "nm", "name", True, "분류어: 명칭", "builtin"),
    Word("식별자", "id", "identifier", True, "분류어: 시스템 대리키", "builtin"),
    Word("여부", "yn", "yes_no", True, "분류어: 참/거짓", "builtin"),
    Word("시각", "at", "timestamp", True, "분류어: 일시", "builtin"),
    Word("일자", "dt", "date", True, "분류어: 날짜", "builtin"),
    Word("금액", "amt", "amount", True, "분류어: 금액", "builtin"),
    Word("수", "cnt", "count", True, "분류어: 건수", "builtin"),
    Word("값", "val", "value", True, "분류어: 내용 값", "builtin"),
    Word("율", "rt", "rate", True, "분류어: 비율", "builtin"),
    Word("해시", "hash", "hash", True, "분류어: 단방향 해시", "builtin"),
    Word("암호문", "enc", "encrypted", True, "분류어: 양방향 암호문", "builtin"),
]
STRUCT_WORDS = [
    Word("생성", "created", "created", False, "행 생성", "builtin"),
    Word("수정", "updated", "updated", False, "행 최종 수정", "builtin"),
    Word("사용", "use", "use", False, "사용 중 여부", "builtin"),
    Word("순서", "sort", "sort", False, "표시 순서", "builtin"),
    Word("개인정보", "pi", "personal_information", False, "개인정보 테이블 접두어", "builtin"),
    Word("코드표", "code", "code_table", False, "코드 테이블 접미어", "builtin"),
    Word("행", "row", "row", False, "적재 행", "builtin"),
]


class Glossary:
    mode = "base"

    def __init__(self):
        self.by_tok: dict[str, Word] = {}
        self.by_kor: dict[str, Word] = {}
        for w in CLASS_WORDS + STRUCT_WORDS:
            self._add(w)

    def _add(self, w: Word, override: bool = False):
        for t in {w.abbr, w.full}:
            if override or t not in self.by_tok:
                self.by_tok[t] = w
        if w.kor and (override or w.kor not in self.by_kor):
            self.by_kor[w.kor] = w

    # ---- 조회 ----
    def lookup(self, token: str) -> Word | None:
        return self.by_tok.get(token)

    def lookup_kor(self, kor: str) -> Word | None:
        return self.by_kor.get(kor)

    def check_identifier(self, name: str) -> list[str]:
        """사전에 없는 토큰 목록 (빈 리스트면 통과)"""
        return [t for t in name.split("_") if t not in self.by_tok]

    def compose_kor(self, kor_label: str) -> tuple[list[Word], str]:
        """한글 항목명을 사전 단어로 최장일치 분해 → (단어들, 남은 미등록 부분)
        예) '사업장명' → [사업장, 명], ''"""
        s = re.sub(r"[\s()\[\]_\-/·.,]", "", kor_label)
        out, rest, i = [], "", 0
        keys = sorted(self.by_kor, key=len, reverse=True)
        while i < len(s):
            for k in keys:
                if s.startswith(k, i):
                    out.append(self.by_kor[k]); i += len(k); break
            else:
                rest += s[i]; i += 1
        return out, rest

    def model_words(self, names: list[str]) -> list[dict]:
        """물리명 목록에 쓰인 단어만 model.json words 형식으로"""
        seen, out = set(), []
        for n in names:
            for t in n.split("_"):
                w = self.by_tok.get(t)
                if w and (w.kor, w.abbr) not in seen:
                    seen.add((w.kor, w.abbr)); out.append(w.as_model())
        return out

    def register(self, words: list[Word]) -> list[str]:
        raise NotImplementedError

    def info(self) -> dict:
        return {"mode": self.mode, "words": len({id(w) for w in self.by_tok.values()})}


class BomiyangGlossary(Glossary):
    mode = "bomiyang"

    def __init__(self, path: str):
        super().__init__()
        self.path = os.path.abspath(path)
        words = json.load(open(os.path.join(self.path, "dictionary", "words.json"), encoding="utf-8"))["words"]
        n = 0
        for w in words:
            if w.get("status", "active") != "active":
                continue
            wid = (w.get("id") or "").strip()
            if not TOKEN.match(wid):
                continue  # 'accumulation (또는 …)' 같은 비표준 id 는 토큰으로 쓰지 않음
            ab = None
            if isinstance(w.get("abbreviation"), dict):
                ab = w["abbreviation"].get("short")
            for v in w.get("variants") or []:
                if not ab and (v.get("type") == "abbreviation" or "abbreviation" in (v.get("types") or [])):
                    ab = v.get("short") or v.get("value")
            ab = (ab or "").strip().lower()
            if not TOKEN.match(ab):
                ab = wid
            kor = re.sub(r"\s*\(.*?\)\s*", "", (w.get("lang") or {}).get("ko", "")).strip()
            desc = ((w.get("description_i18n") or {}).get("ko") or "")[:200]
            self._add(Word(kor, ab, wid, False, desc, "bomiyang"))
            n += 1
        self.loaded = n

    def register(self, words: list[Word]) -> list[str]:
        """GlossaryWriter 로 단어·약어 등록 (bomiyang 규칙: 직접 JSON 수정 금지)"""
        payload = json.dumps([asdict(w) for w in words], ensure_ascii=False)
        code = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from core.writer import GlossaryWriter
ws = json.loads(sys.stdin.read()); done = []
with GlossaryWriter() as gw:
    for w in ws:
        added = gw.add_word({"id": w["full"], "lang": {"en": w["full"], "ko": w["kor"]}, "canonical_pos": "noun",
                             "domain": ["general"], "status": "active",
                             "description_i18n": {"ko": w["desc"] or w["kor"]}}, skip_duplicate=True)
        if w["abbr"] != w["full"]:
            gw.add_word_abbreviation(w["full"], w["abbr"])
        done.append(w["full"] + ("" if added else "(기존)"))
    errs = gw.validate()
    if errs:
        gw.rollback(); print(json.dumps({"errors": errs}, ensure_ascii=False)); sys.exit(1)
print(json.dumps({"done": done}, ensure_ascii=False))
'''
        from .compat import run_py
        # 단어 목록은 표준입력(UTF-8)으로 넘긴다 — 명령줄 길이·Windows 코드페이지 문제 회피
        r = run_py(["-c", code, self.path], input_text=payload, cwd=self.path)
        if r.returncode != 0:
            raise RuntimeError("bomiyang 등록 실패: " + (r.stdout + r.stderr)[-800:])
        for w in words:
            self._add(Word(w.kor, w.abbr, w.full, w.is_class, w.desc, "bomiyang"))
        return json.loads(r.stdout.strip().splitlines()[-1]).get("done", [])


class MetaGlossary(Glossary):
    """DB 공통 스키마(meta.word) 기반 용어 관리"""
    mode = "meta"

    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        if conn is not None and conn.execute("SELECT to_regclass('meta.word') IS NOT NULL AS ok").fetchone()["ok"]:
            for r in conn.execute("SELECT kor_name, eng_abbr, eng_full, coalesce(description,'') d, is_class FROM meta.word"):
                self._add(Word(r["kor_name"], r["eng_abbr"], r["eng_full"], r["is_class"], r["d"], "meta"), override=True)

    def register(self, words: list[Word]) -> list[str]:
        done = []
        for w in words:
            cur = self.conn.execute(
                "INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING RETURNING word_id", (w.kor, w.abbr, w.full, w.desc, w.is_class))
            done.append(w.full + ("" if cur.fetchone() else "(기존/충돌)"))
            self._add(w)
        self.conn.commit()
        return done


def open_glossary(cfg, conn=None) -> Glossary:
    g = cfg["glossary"]
    mode, path = g.get("mode", "auto"), g.get("bomiyang_path") or ""
    has_bomi = bool(path) and os.path.exists(os.path.join(path, "dictionary", "words.json"))
    if mode == "bomiyang" and not has_bomi:
        print(f"[glossary] bomiyang 경로({path})에 dictionary/words.json 이 없어 meta 모드로 전환합니다", file=sys.stderr)
    if mode in ("auto", "bomiyang") and has_bomi:
        gl = BomiyangGlossary(path)
        # meta 에 이미 등록된 조직 단어도 함께 인식(bomiyang 우선)
        if conn is not None:
            try:
                for w in MetaGlossary(conn).by_tok.values():
                    gl._add(w)
            except Exception:
                pass
        return gl
    return MetaGlossary(conn)
