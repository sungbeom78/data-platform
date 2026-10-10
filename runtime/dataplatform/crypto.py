"""개인정보 암호화 — 성격에 따라 양방향/단방향을 구분한다. 모든 키는 128비트.

| 방식   | 용도                                   | 저장                         |
|--------|----------------------------------------|------------------------------|
| aes    | 복원이 필요한 값(성명·연락처·주소·계좌) | bytea = ver(1)+nonce(12)+ct+tag |
| hmac   | 일치 검색만 필요한 값(주민번호·전화 검색키), API 키 | bytea 32바이트          |
| argon2 | 인증용 비밀번호                         | text ($argon2id$…)          |

AES 암호문 맨 앞 1바이트에 키 번호를 넣어 키 교체(rotation) 후에도 옛 데이터를 읽을 수 있다.
"""
from __future__ import annotations
import hmac as _hmac, hashlib, os, re, secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

KEY_BYTES = 16  # 128bit
_ph = PasswordHasher()


class CryptoError(Exception):
    pass


def new_key_hex() -> str:
    """임의 128비트 키(16진수 32자리)"""
    return secrets.token_hex(KEY_BYTES)


def _key(hexstr: str, what: str) -> bytes:
    if not hexstr:
        raise CryptoError(f"{what} 키가 설정 파일에 없습니다 — `python -m dataplatform keygen --write <system.yaml>`")
    try:
        k = bytes.fromhex(hexstr)
    except ValueError as e:
        raise CryptoError(f"{what} 키는 16진수여야 합니다") from e
    if len(k) != KEY_BYTES:
        raise CryptoError(f"{what} 키는 128비트(16진수 32자리)여야 합니다 — 현재 {len(k) * 8}비트")
    return k


class Crypto:
    def __init__(self, crypto_cfg: dict):
        self.active = int(crypto_cfg.get("active_key", 1))
        self.keys = {int(k): v for k, v in (crypto_cfg.get("keys") or {}).items() if v}
        self.hmac_hex = crypto_cfg.get("hmac_key") or ""

    # ---- 양방향 AES-128-GCM ----
    def encrypt(self, value) -> bytes | None:
        if value is None:
            return None
        if self.active not in self.keys:
            raise CryptoError(f"active_key={self.active} 에 해당하는 키가 없습니다")
        if not 0 < self.active < 256:
            raise CryptoError("키 번호는 1~255")
        aes = AESGCM(_key(self.keys[self.active], f"keys.{self.active}"))
        nonce = os.urandom(12)
        return bytes([self.active]) + nonce + aes.encrypt(nonce, str(value).encode("utf-8"), None)

    def decrypt(self, blob) -> str | None:
        if blob is None:
            return None
        blob = bytes(blob)
        ver, nonce, ct = blob[0], blob[1:13], blob[13:]
        if ver not in self.keys:
            raise CryptoError(f"키 번호 {ver} 가 설정 파일에 없습니다(교체 전 키를 지우지 마세요)")
        return AESGCM(_key(self.keys[ver], f"keys.{ver}")).decrypt(nonce, ct, None).decode("utf-8")

    def key_version(self, blob) -> int | None:
        return None if blob is None else bytes(blob)[0]

    # ---- 단방향 HMAC-SHA256 (검색키) ----
    def hmac(self, value, normalize: bool = True) -> bytes | None:
        if value is None:
            return None
        s = str(value)
        if normalize:
            s = normalize_value(s)
        return _hmac.new(_key(self.hmac_hex, "hmac_key"), s.encode("utf-8"), hashlib.sha256).digest()

    def hmac_eq(self, value, digest) -> bool:
        return digest is not None and _hmac.compare_digest(self.hmac(value), bytes(digest))

    # ---- 단방향 argon2id (비밀번호) ----
    @staticmethod
    def hash_password(pw: str) -> str:
        return _ph.hash(pw)

    @staticmethod
    def verify_password(stored: str | None, pw: str) -> bool:
        if not stored:
            return False
        try:
            return _ph.verify(stored, pw)
        except (VerifyMismatchError, InvalidHashError):
            return False

    def apply(self, method: str, value):
        """model.json column.crypto 값으로 암호화"""
        if method == "aes":
            return self.encrypt(value)
        if method == "hmac":
            return self.hmac(value)
        if method == "argon2":
            return None if value is None else self.hash_password(str(value))
        raise CryptoError(f"알 수 없는 crypto 방식: {method}")


def normalize_value(s: str) -> str:
    """검색 해시용 정규화 — 공백·하이픈 제거, 소문자"""
    return re.sub(r"[\s\-]", "", s.strip()).lower()


# ---- 마스킹 (화면·로그 표시용) ----
def mask(value, kind: str = "auto") -> str | None:
    if value is None:
        return None
    s = str(value)
    if kind == "auto":
        if "@" in s:
            kind = "email"
        elif re.fullmatch(r"\d{6}-?\d{7}", s):
            kind = "rrn"
        elif re.fullmatch(r"0\d{1,2}-?\d{3,4}-?\d{4}", s):
            kind = "phone"
        elif re.fullmatch(r"[가-힣]{2,5}", s):
            kind = "name"
        else:
            kind = "generic"
    if kind == "name":
        return s[0] + "*" * (len(s) - 2) + s[-1] if len(s) > 2 else s[0] + "*"
    if kind == "phone":
        d = re.sub(r"\D", "", s)
        return f"{d[:3]}-****-{d[-4:]}"
    if kind == "email":
        u, _, dom = s.partition("@")
        return (u[:1] + "***@" + dom) if u else s
    if kind == "rrn":
        d = re.sub(r"\D", "", s)
        return f"{d[:6]}-{d[6]}******"
    keep = max(1, len(s) // 4)
    return s[:keep] + "*" * (len(s) - keep)
