"""시스템 설정(system.yaml) 로딩. 경로: --config 인자 > 환경변수 DP_CONFIG > ./config/system.yaml"""
from __future__ import annotations
import os, copy
import yaml

DEFAULTS = {
    "database": {"dsn": "postgresql://postgres@localhost:5432/postgres"},
    "crypto": {"active_key": 1, "keys": {}, "hmac_key": ""},
    "glossary": {"mode": "auto", "bomiyang_path": "./bomiyang-glossary"},
    "access": {"managed_schemas": [], "exclude_schemas": ["pg_catalog", "information_schema", "pg_toast"]},
    "api": {"jwt_secret": "", "token_ttl_min": 60, "default_max_rows": 10000, "default_timeout_ms": 15000,
            "host": "0.0.0.0", "port": 8800},
    "ingest": {"work_dir": "./work/ingest", "lake_dir": "./data_lake", "large_rows": 10_000_000,
               "large_bytes": 2 * 1024 ** 3, "lake_pi_policy": "hmac"},
    "public_data": {"service_key": ""},
}


def _merge(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class Config(dict):
    path: str | None = None

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e


def load(path: str | None = None) -> Config:
    path = path or os.environ.get("DP_CONFIG") or os.path.join(os.getcwd(), "config", "system.yaml")
    data = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    cfg = Config(_merge(DEFAULTS, data))
    cfg.path = path if os.path.exists(path) else None
    # 키 번호는 문자열/정수 모두 허용
    cfg["crypto"]["keys"] = {int(k): (v or "") for k, v in (cfg["crypto"].get("keys") or {}).items()}
    if os.environ.get("DP_DSN"):
        cfg["database"]["dsn"] = os.environ["DP_DSN"]
    return cfg
