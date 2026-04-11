import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

logger = logging.getLogger(__name__)

_STEALTH_JS = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"

# 앱 전용 Chrome 프로필 경로 (로그인 정보 유지)
import os
_PROFILE_DIR = Path(os.environ.get("APPDATA", Path.home())) / "NaverBlogAutomation" / "ChromeProfile"


def create_driver() -> webdriver.Chrome:
    _PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--start-maximized")
    opts.add_argument(f"--user-data-dir={_PROFILE_DIR}")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=opts)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument", {"source": _STEALTH_JS}
    )
    logger.info("Chrome 드라이버 생성 완료 (전용 프로필)")
    return driver
