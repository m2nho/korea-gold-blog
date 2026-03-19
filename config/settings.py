import json
import os
import base64
import logging
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "NaverBlogAutomation"
CREDENTIALS_FILE = APP_DIR / "credentials.enc"
SETTINGS_FILE = APP_DIR / "settings.json"
KEY_FILE = APP_DIR / ".key"


def _ensure_app_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)


def _get_or_create_key() -> bytes:
    _ensure_app_dir()
    if KEY_FILE.exists():
        return base64.b64decode(KEY_FILE.read_text())
    key = AESGCM.generate_key(bit_length=256)
    KEY_FILE.write_text(base64.b64encode(key).decode())
    return key


def save_credentials(naver_id: str, naver_pw: str, blog_id: str = "",
                     sheet_url: str = "", gsheet_creds: str = ""):
    key = _get_or_create_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    payload = json.dumps({
        "id": naver_id, "pw": naver_pw, "blog_id": blog_id,
        "sheet_url": sheet_url, "gsheet_creds": gsheet_creds,
    }).encode()
    encrypted = aesgcm.encrypt(nonce, payload, None)
    _ensure_app_dir()
    CREDENTIALS_FILE.write_bytes(nonce + encrypted)
    logger.info("자격증명 저장 완료")


def load_credentials() -> dict | None:
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        key = _get_or_create_key()
        aesgcm = AESGCM(key)
        raw = CREDENTIALS_FILE.read_bytes()
        nonce, encrypted = raw[:12], raw[12:]
        payload = aesgcm.decrypt(nonce, encrypted, None)
        return json.loads(payload)
    except Exception:
        logger.warning("저장된 자격증명 복호화 실패")
        return None


def save_settings(settings: dict):
    _ensure_app_dir()
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2))


def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except Exception:
        return {}
