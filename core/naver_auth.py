import time
import logging
from typing import Callable
import pyperclip
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException

from core.browser import create_driver
from core.blog_writer import _interruptible_sleep, _check_stop, _StopRequested

logger = logging.getLogger(__name__)

LOGIN_URL = "https://nid.naver.com/nidlogin.login"
CAPTCHA_WAIT_SEC = 120

# 콜백 타입: (메시지, 레벨) → level: info, success, error, warn
StatusCallback = Callable[[str, str], None]
_noop: StatusCallback = lambda msg, lvl="info": None


class LoginResult:
    def __init__(self, success: bool, driver: WebDriver | None = None, message: str = ""):
        self.success = success
        self.driver = driver
        self.message = message


# ── 내부 유틸 ────────────────────────────────────────────

def _dismiss_all_alerts(driver: WebDriver):
    for _ in range(5):
        try:
            alert = driver.switch_to.alert
            logger.debug(f"Alert 닫기: {alert.text}")
            alert.accept()
            _interruptible_sleep(0.5)
        except _StopRequested:
            raise
        except (NoAlertPresentException, Exception):
            break


def _safe_get(driver: WebDriver, url: str):
    for attempt in range(3):
        try:
            _dismiss_all_alerts(driver)
            driver.get(url)
            return
        except _StopRequested:
            raise
        except UnexpectedAlertPresentException:
            logger.debug(f"URL 이동 중 alert, 재시도 ({attempt+1}/3)")
            _dismiss_all_alerts(driver)
            _interruptible_sleep(0.5)
    _dismiss_all_alerts(driver)
    driver.get(url)


def _clipboard_paste(element, text: str):
    pyperclip.copy(text)
    element.click()
    _interruptible_sleep(0.2)
    element.send_keys(Keys.CONTROL, "a")
    _interruptible_sleep(0.1)
    element.send_keys(Keys.CONTROL, "v")
    _interruptible_sleep(0.3)


def _switch_to_editor(driver: WebDriver):
    driver.switch_to.default_content()
    wait = WebDriverWait(driver, 10)
    iframe = wait.until(EC.presence_of_element_located((By.ID, "mainFrame")))
    driver.switch_to.frame(iframe)


def _dismiss_editor_popups(driver: WebDriver):
    for _ in range(5):
        try:
            found = driver.execute_script("""
                var cancel = document.querySelector('button.se-popup-button-cancel');
                if (cancel) { cancel.click(); return true; }
                return false;
            """)
            if not found:
                break
            _interruptible_sleep(1)
        except _StopRequested:
            raise
        except Exception:
            break
    try:
        driver.execute_script("""
            document.querySelectorAll('.se-popup-dim').forEach(el => el.remove());
            document.querySelectorAll('.se-popup-container').forEach(el => el.remove());
        """)
        _interruptible_sleep(0.5)
    except _StopRequested:
        raise
    except Exception:
        pass


def _close_help_panel(driver: WebDriver):
    try:
        driver.execute_script("""
            var btn = document.querySelector('button.se-help-panel-close-button');
            if (btn) btn.click();
            document.querySelectorAll('article.se-help-panel').forEach(p => {
                p.classList.remove('se-is-on');
                p.style.display = 'none';
            });
        """)
        _interruptible_sleep(1)
    except _StopRequested:
        raise
    except Exception:
        pass


def _is_logged_in(driver: WebDriver) -> bool:
    """네이버 메인에서 로그인 링크 존재 여부로 로그인 상태 확인"""
    try:
        driver.get("https://www.naver.com")
        _interruptible_sleep(2)
        login_link = driver.execute_script("""
            return document.querySelector('#account a.MyView-module__link_login___HpHMW');
        """)
        logged_in = login_link is None
        logger.info(f"로그인 상태: {'로그인됨' if logged_in else '미로그인'}")
        return logged_in
    except Exception as e:
        logger.warning(f"로그인 상태 확인 실패: {e}")
        return False


# ── 로그인 ───────────────────────────────────────────────

def login(
    naver_id: str,
    naver_pw: str,
    on_status: StatusCallback = _noop,
) -> LoginResult:
    driver = None
    try:
        on_status("🌐 Chrome 브라우저를 시작합니다", "info")
        driver = create_driver()

        # 이미 로그인된 상태면 바로 성공 반환
        on_status("🔍 로그인 상태를 확인합니다", "info")
        if _is_logged_in(driver):
            on_status("✅ 이미 로그인된 상태입니다", "success")
            return LoginResult(True, driver, "세션 재사용")

        on_status("🔗 네이버 로그인 페이지로 이동합니다", "info")
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 10)

        on_status("👤 아이디를 입력합니다", "info")
        id_el = wait.until(EC.presence_of_element_located((By.ID, "id")))
        _clipboard_paste(id_el, naver_id)

        on_status("🔒 비밀번호를 입력합니다", "info")
        pw_el = driver.find_element(By.ID, "pw")
        _clipboard_paste(pw_el, naver_pw)

        _interruptible_sleep(0.5)
        driver.find_element(By.ID, "log.login").click()
        on_status("⏳ 로그인 처리 중... (캡차 발생 시 직접 해결해주세요)", "warn")
        logger.info("로그인 버튼 클릭")

        for i in range(CAPTCHA_WAIT_SEC):
            _interruptible_sleep(1)
            try:
                current = driver.current_url
            except _StopRequested:
                raise
            except UnexpectedAlertPresentException:
                _dismiss_all_alerts(driver)
                continue
            if "nid.naver.com" not in current:
                _dismiss_all_alerts(driver)
                on_status("✅ 네이버 로그인에 성공했습니다", "success")
                logger.info("로그인 성공")
                return LoginResult(True, driver, "로그인 성공")
            if i > 0 and i % 10 == 0:
                on_status(f"⏳ 로그인 대기 중... ({i}초 경과)", "warn")

        on_status("❌ 로그인 시간이 초과되었습니다 (2분)", "error")
        logger.warning("로그인 시간 초과")
        driver.quit()
        return LoginResult(False, None, "로그인 시간 초과")

    except _StopRequested:
        logger.info("로그인 중 중지 요청")
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        return LoginResult(False, None, "중지됨")
    except Exception as e:
        logger.exception("로그인 실패")
        on_status("❌ 로그인 중 오류가 발생했습니다", "error")
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        return LoginResult(False, None, str(e))


# ── 블로그 글쓰기 이동 ──────────────────────────────────

def navigate_to_write(
    driver: WebDriver,
    blog_id: str,
    on_status: StatusCallback = _noop,
) -> bool:
    try:
        _dismiss_all_alerts(driver)

        on_status(f"📝 블로그({blog_id})로 이동합니다", "info")
        _safe_get(driver, f"https://blog.naver.com/{blog_id}")
        _interruptible_sleep(2)
        _dismiss_all_alerts(driver)
        logger.info(f"블로그 진입: {driver.current_url}")

        # 블로그 진입 팝업 닫기 (mainFrame 안에 있음)
        try:
            wait_popup = WebDriverWait(driver, 5)
            iframe = wait_popup.until(EC.presence_of_element_located((By.ID, "mainFrame")))
            driver.switch_to.frame(iframe)
            try:
                close_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn_close._btn_close"))
                )
                close_btn.click()
                logger.info("팝업 닫기 완료")
                _interruptible_sleep(0.5)
            except Exception:
                pass
            driver.switch_to.default_content()
        except Exception:
            driver.switch_to.default_content()

        on_status("🔍 글쓰기 버튼을 찾고 있습니다", "info")
        wait = WebDriverWait(driver, 10)
        iframe = wait.until(EC.presence_of_element_located((By.ID, "mainFrame")))
        driver.switch_to.frame(iframe)

        write_link = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "a[href*='postwrite']")
        ))
        write_link.click()
        on_status("📄 글쓰기 페이지를 불러오고 있습니다", "info")
        logger.info("글쓰기 링크 클릭")

        driver.switch_to.default_content()
        _interruptible_sleep(3)
        _dismiss_all_alerts(driver)

        on_status("✅ 글쓰기 페이지에 진입했습니다", "success")
        logger.info(f"글쓰기 페이지: {driver.current_url}")
        return True

    except _StopRequested:
        raise
    except Exception as e:
        _dismiss_all_alerts(driver)
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        try:
            current = driver.current_url
        except Exception:
            current = ""
        if "PostWrite" in current or "postwrite" in current or "editor" in current:
            on_status("✅ 글쓰기 페이지에 진입했습니다", "success")
            return True
        logger.exception("글쓰기 페이지 이동 실패")
        on_status("❌ 글쓰기 페이지 이동에 실패했습니다", "error")
        return False


# ── 템플릿 적용 ──────────────────────────────────────────

def apply_template(
    driver: WebDriver,
    on_status: StatusCallback = _noop,
) -> bool:
    try:
        on_status("⏳ 에디터가 로드될 때까지 대기합니다", "info")
        _switch_to_editor(driver)
        wait = WebDriverWait(driver, 15)

        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".se-component, .se-toolbar")
        ))
        _interruptible_sleep(1)

        on_status("🧹 에디터 팝업을 정리합니다", "info")
        _dismiss_editor_popups(driver)
        _close_help_panel(driver)

        on_status("📋 템플릿 패널을 열고 있습니다", "info")
        tpl_btn = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "button[data-name='template']")
        ))
        driver.execute_script("arguments[0].click();", tpl_btn)
        _interruptible_sleep(1)

        on_status("📂 내 템플릿 목록을 불러옵니다", "info")
        my_tab = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.se-tab-button[value='my']")
        ))
        my_tab.click()
        _interruptible_sleep(1)

        on_status("🎨 첫 번째 템플릿을 적용합니다", "info")
        _interruptible_sleep(2)

        first_tpl = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".se-doc-template-item:first-child a.se-doc-template")
        ))
        tpl_name = ""
        try:
            tpl_name = driver.find_element(
                By.CSS_SELECTOR, ".se-doc-template-item:first-child .se-doc-template-title"
            ).text
        except Exception:
            pass

        driver.execute_script("arguments[0].click();", first_tpl)
        _interruptible_sleep(2)

        msg = f"✅ 템플릿 적용 완료" + (f" — {tpl_name}" if tpl_name else "")
        on_status(msg, "success")
        logger.info(f"템플릿 적용: {tpl_name}")
        return True

    except _StopRequested:
        raise
    except Exception as e:
        logger.exception("템플릿 적용 실패")
        on_status("❌ 템플릿 적용에 실패했습니다", "error")
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        return False
