"""운영체제 차이 흡수 — 특히 Windows(한글 cp949 콘솔·파이프) 인코딩.

- 자식 파이썬 프로세스는 항상 UTF-8 로 입출력하게 하고(PYTHONUTF8/PYTHONIOENCODING), 부모도 UTF-8 로 읽는다.
  Windows 에서 text=True 만 쓰면 부모는 cp949 로 디코딩해 한글 출력이 깨지거나 UnicodeDecodeError 가 난다.
- CLI 표준출력은 콘솔이 cp949 여도 죽지 않게 errors=replace 로 다시 설정한다.
- 경로를 DuckDB·SQL 문자열에 넣을 때는 슬래시 경로로 바꾼다.
"""
from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

UTF8_ENV = {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def child_env(extra: dict | None = None) -> dict:
    env = dict(os.environ)
    env.update(UTF8_ENV)
    if extra:
        env.update(extra)
    return env


def run_py(args: list, *, input_text: str | None = None, cwd: str | None = None, timeout: int | None = None) -> subprocess.CompletedProcess:
    """현재 파이썬으로 스크립트/모듈 실행. 입력·출력 모두 UTF-8."""
    return subprocess.run([sys.executable, *map(str, args)], input=input_text, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=cwd, env=child_env(), timeout=timeout)


def utf8_stdio() -> None:
    """CLI 진입점에서 호출: 콘솔 인코딩이 cp949 등이어도 출력 중 예외로 죽지 않게"""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def posix_path(p) -> str:
    """C:\\a\\b → C:/a/b (DuckDB glob·SQL 리터럴용). 작은따옴표는 SQL 이스케이프.
    Windows 형식 경로(드라이브 문자·역슬래시)는 어느 OS 에서 돌든 Windows 규칙으로 바꾼다."""
    import re
    from pathlib import PureWindowsPath
    s = str(p)
    if re.match(r"^[A-Za-z]:[\\/]", s) or "\\" in s:
        out = PureWindowsPath(s).as_posix()
    else:
        out = Path(s).resolve().as_posix()
    return out.replace("'", "''")
