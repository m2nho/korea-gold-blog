import time
import json
import logging
import re
from typing import Callable
import pyperclip
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from threading import Event
from core.google_sheets import BlogPostData

logger = logging.getLogger(__name__)

# 전역 stop event — 워커 스레드에서 참조
_stop_event: Event | None = None


def set_stop_event(event: Event | None):
    global _stop_event
    _stop_event = event


def _interruptible_sleep(seconds: float):
    """stop_event가 set되면 즉시 반환하는 sleep."""
    if _stop_event and _stop_event.wait(seconds):
        raise _StopRequested()


def _check_stop():
    if _stop_event and _stop_event.is_set():
        raise _StopRequested()


class _StopRequested(Exception):
    pass

StatusCallback = Callable[[str, str], None]
_noop: StatusCallback = lambda msg, lvl="info": None


def _switch_to_editor(driver: WebDriver):
    _check_stop()
    driver.switch_to.default_content()
    wait = WebDriverWait(driver, 10)
    iframe = wait.until(EC.presence_of_element_located((By.ID, "mainFrame")))
    driver.switch_to.frame(iframe)


def _collect_placeholder_keys(driver: WebDriver):
    """
    에디터에서 {xxx} 형태의 플레이스홀더 키 목록만 수집 (element 참조 없이).
    반환: ["{date}", "{section1_title}", ...]
    """
    return driver.execute_script("""
        var results = [];
        var article = document.querySelector('article.se-components-wrap');
        if (!article) return results;
        var spans = article.querySelectorAll('span.__se-node');
        var regex = /\\{[^}]+\\}/g;
        for (var i = 0; i < spans.length; i++) {
            var matches = spans[i].textContent.match(regex);
            if (matches) {
                for (var j = 0; j < matches.length; j++) {
                    results.push(matches[j]);
                }
            }
        }
        return results;
    """)


def _find_span_by_key(driver: WebDriver, key: str):
    """현재 DOM에서 {key}를 포함하는 span.__se-node를 fresh하게 찾아 반환"""
    return driver.execute_script("""
        var key = arguments[0];
        var article = document.querySelector('article.se-components-wrap');
        if (!article) return null;
        var spans = article.querySelectorAll('span.__se-node');
        for (var i = 0; i < spans.length; i++) {
            if (spans[i].textContent.indexOf(key) !== -1) {
                return spans[i];
            }
        }
        return null;
    """, key)


def _click_and_paste(driver: WebDriver, element, text: str):
    """요소 클릭 → 전체 선택 → 붙여넣기"""
    ActionChains(driver).click(element).perform()
    time.sleep(0.1)
    # Home + Shift+End로 해당 줄/셀 전체 선택
    ActionChains(driver)\
        .send_keys(Keys.HOME)\
        .key_down(Keys.SHIFT).send_keys(Keys.END).key_up(Keys.SHIFT)\
        .perform()
    time.sleep(0.05)
    pyperclip.copy(text)
    ActionChains(driver)\
        .key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL)\
        .perform()
    time.sleep(0.2)


def _copy_image_to_clipboard(image_path: str, size: tuple[int, int] = (400, 400)):
    """이미지를 지정 크기로 리사이즈한 후 BMP로 변환하여 Windows 클립보드에 복사한다."""
    import io
    import win32clipboard
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    img = img.resize(size, Image.LANCZOS)
    bmp_buf = io.BytesIO()
    img.save(bmp_buf, format="BMP")
    data = bmp_buf.getvalue()[14:]

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    finally:
        win32clipboard.CloseClipboard()


def insert_thumbnail(
    driver: WebDriver,
    image_path: str,
    on_status: StatusCallback = _noop,
) -> bool:
    """에디터 맨 앞에 썸네일 이미지를 클립보드 붙여넣기로 삽입한다."""
    try:
        on_status("🖼 썸네일 이미지를 삽입합니다", "info")
        _switch_to_editor(driver)
        _interruptible_sleep(1)

        # 기존 이미지 컴포넌트 수 기록
        before_count = len(driver.find_elements(
            By.CSS_SELECTOR, ".se-component.se-image"
        ))

        # 에디터 첫 번째 텍스트 영역 맨 앞으로 커서 이동
        driver.execute_script("""
            var first = document.querySelector('article.se-components-wrap .se-component');
            if (first) {
                var p = first.querySelector('p.se-text-paragraph, span.__se-node');
                if (p) p.click();
            }
        """)
        _interruptible_sleep(0.5)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys(Keys.HOME).key_up(Keys.CONTROL).perform()
        _interruptible_sleep(0.3)

        # Enter로 빈 줄 만들고 위로 이동
        ActionChains(driver).send_keys(Keys.HOME).send_keys(Keys.ENTER).send_keys(Keys.UP).perform()
        _interruptible_sleep(0.3)

        # 클립보드에 이미지 복사 후 Ctrl+V
        on_status("📋 클립보드에 이미지를 복사합니다", "info")
        _copy_image_to_clipboard(image_path)
        _interruptible_sleep(0.2)

        ActionChains(driver)\
            .key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL)\
            .perform()
        on_status("⏳ 이미지 업로드 대기 중...", "info")

        # 새 이미지 컴포넌트가 나타날 때까지 대기
        WebDriverWait(driver, 30).until(
            lambda d: len(d.find_elements(
                By.CSS_SELECTOR, ".se-component.se-image"
            )) > before_count
        )
        _interruptible_sleep(2)

        # 새로 삽입된 이미지의 인덱스 (기존 이미지 뒤에 추가됨)
        all_images = driver.find_elements(By.CSS_SELECTOR, ".se-component.se-image")
        total = len(all_images)
        new_img_idx = before_count  # 기존 개수 = 새 이미지의 인덱스
        logger.info(f"이미지 총 {total}개, 새 이미지 인덱스: {new_img_idx}")

        on_status(f"⚙️ 대표 사진 및 AI 활용 설정 중... (이미지 {new_img_idx+1}/{total})", "info")

        # iframe 컨텍스트 재확인
        _switch_to_editor(driver)
        _interruptible_sleep(1)

        # 이미지 선택 해제: 텍스트 영역 클릭
        driver.execute_script("""
            var text = document.querySelector('.se-component.se-text .se-text-paragraph');
            if (text) text.click();
        """)
        _interruptible_sleep(1)

        # N번째 이미지의 img 요소를 클릭하여 활성화
        img_el = driver.execute_script("""
            var comps = document.querySelectorAll('.se-component.se-image');
            var target = comps[arguments[0]];
            if (!target) return null;
            return target.querySelector('.se-image-resource');
        """, new_img_idx)

        if not img_el:
            on_status("❌ 새 이미지 요소를 찾지 못했습니다", "error")
            return False

        ActionChains(driver).move_to_element(img_el).click().perform()
        _interruptible_sleep(1)

        # N번째 이미지 섹션이 활성화될 때까지 대기 (최대 5초)
        activated = False
        for _ in range(10):
            _check_stop()
            activated = driver.execute_script("""
                var comps = document.querySelectorAll('.se-component.se-image');
                var target = comps[arguments[0]];
                if (!target) return false;
                var section = target.querySelector('.se-section-image');
                return section && section.classList.contains('se-is-activated');
            """, new_img_idx)
            if activated:
                break
            _interruptible_sleep(0.5)

        logger.info(f"이미지[{new_img_idx}] 활성화 상태: {activated}")

        if not activated:
            ActionChains(driver).move_to_element(img_el).click().perform()
            _interruptible_sleep(2)

        # N번째 이미지 섹션 내에서 대표 사진 등록
        rep_result = driver.execute_script("""
            var comps = document.querySelectorAll('.se-component.se-image');
            var target = comps[arguments[0]];
            if (!target) return 'COMP_NOT_FOUND';
            var section = target.querySelector('.se-section-image');
            if (!section || !section.classList.contains('se-is-activated'))
                return 'NOT_ACTIVATED';
            var btn = section.querySelector('button.se-set-rep-image-button');
            if (!btn) return 'BTN_NOT_FOUND';
            btn.click();
            return 'CLICKED';
        """, new_img_idx)
        logger.info(f"대표 사진[{new_img_idx}]: {rep_result}")
        _interruptible_sleep(1)

        # 대표 클릭 후 이미지 재클릭하여 활성화 보장
        ActionChains(driver).move_to_element(img_el).click().perform()
        _interruptible_sleep(1)

        # N번째 이미지 섹션 내 AI 버튼 DOM 상태 진단
        ai_debug = driver.execute_script("""
            var comps = document.querySelectorAll('.se-component.se-image');
            var target = comps[arguments[0]];
            if (!target) return {error: 'COMP_NOT_FOUND'};
            var section = target.querySelector('.se-section-image');
            if (!section) return {error: 'SECTION_NOT_FOUND'};
            var activated = section.classList.contains('se-is-activated');
            var wrapper = section.querySelector('.se-set-ai-mark-button');
            if (!wrapper) return {error: 'WRAPPER_NOT_FOUND', activated: activated};
            var wrapperClasses = wrapper.className;
            var isSelected = wrapper.classList.contains('se-is-selected');
            var toggle = wrapper.querySelector('button.se-set-ai-mark-button-toggle');
            var toggleExists = !!toggle;
            var toggleHTML = wrapper.outerHTML.substring(0, 500);
            return {
                activated: activated,
                wrapperClasses: wrapperClasses,
                isSelected: isSelected,
                toggleExists: toggleExists,
                html: toggleHTML
            };
        """, new_img_idx)
        logger.info(f"AI 버튼 진단: {ai_debug}")

        # AI 활용 설정 (버튼 자체의 se-is-selected로 판단)
        ai_result = driver.execute_script("""
            var comps = document.querySelectorAll('.se-component.se-image');
            var target = comps[arguments[0]];
            if (!target) return 'COMP_NOT_FOUND';
            var section = target.querySelector('.se-section-image');
            if (!section) return 'SECTION_NOT_FOUND';
            var toggle = section.querySelector('button.se-set-ai-mark-button-toggle');
            if (!toggle) return 'TOGGLE_NOT_FOUND';
            if (toggle.classList.contains('se-is-selected')) return 'ALREADY_ON';
            toggle.click();
            return 'CLICKED';
        """, new_img_idx)
        logger.info(f"AI 활용 설정: {ai_result}")
        _interruptible_sleep(0.5)

        # AI 클릭 후 실제 상태 재확인 (버튼 클래스로 판단)
        ai_verify = driver.execute_script("""
            var comps = document.querySelectorAll('.se-component.se-image');
            var target = comps[arguments[0]];
            if (!target) return 'COMP_NOT_FOUND';
            var section = target.querySelector('.se-section-image');
            if (!section) return 'SECTION_NOT_FOUND';
            var toggle = section.querySelector('button.se-set-ai-mark-button-toggle');
            if (!toggle) return 'TOGGLE_NOT_FOUND';
            return toggle.classList.contains('se-is-selected') ? 'ON' : 'OFF';
        """, new_img_idx)
        logger.info(f"AI 최종 상태: {ai_verify}")

        on_status(f"✅ 썸네일 삽입 완료 (대표:{rep_result}, AI:{ai_result})", "success")
        logger.info(f"썸네일 삽입 완료: {image_path}")
        return True

    except _StopRequested:
        raise
    except Exception as e:
        logger.exception("썸네일 이미지 삽입 실패")
        on_status(f"❌ 썸네일 삽입 실패: {e}", "error")
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        return False


def fill_post(
    driver: WebDriver,
    post: BlogPostData,
    on_status: StatusCallback = _noop,
) -> bool:
    try:
        on_status("📝 에디터에 데이터를 입력합니다", "info")
        _switch_to_editor(driver)
        _interruptible_sleep(1)

        # 플레이스홀더 → 값 매핑
        data_map = {
            "{date}": post.date,
            "{compareDate}": post.compare_date,
            "{section1_title}": post.section1_title,
            "{section1_introText}": post.section1_intro,
            "{section1_summaryText}": post.section1_summary,
            "{section2_title}": post.section2_title,
            "{section2_content}": post.section2_content,
        }

        # 1) 플레이스홀더 키 목록 수집 (element 참조 없이 키만)
        on_status("🔍 플레이스홀더를 검색합니다", "info")
        keys_queue = _collect_placeholder_keys(driver)
        logger.info(f"플레이스홀더 {len(keys_queue)}개 발견: {keys_queue}")

        if not keys_queue:
            on_status("⚠️ 플레이스홀더를 찾지 못했습니다", "warn")
        else:
            on_status(f"🔄 {len(keys_queue)}개 플레이스홀더를 치환합니다", "info")

        # 2) 큐에서 하나씩 — 매번 fresh하게 span을 찾아서 처리
        count = 0
        for key in keys_queue:
            value = data_map.get(key, "")
            if not value:
                logger.warning(f"값 없음: {key}")
                continue

            span = _find_span_by_key(driver, key)
            if not span:
                logger.warning(f"span 못 찾음: {key}")
                continue

            # span의 현재 전체 텍스트에서 {key}만 value로 치환
            full_text = driver.execute_script("return arguments[0].textContent;", span)
            new_text = full_text.replace(key, value)

            _click_and_paste(driver, span, new_text)
            count += 1
            logger.info(f"치환: {key} → {value[:30]}...")

        logger.info(f"텍스트 치환 완료: {count}개")
        on_status(f"✅ 텍스트 {count}개 항목 치환 완료", "success")

        # 3) 표 데이터 채우기
        if post.section1_table:
            on_status("📊 시세 표 데이터를 입력합니다", "info")
            table_data = post.section1_table
            filled = 0

            for i, item in enumerate(table_data):
                values = [
                    item.get("item", ""),
                    item.get("yesterday", ""),
                    item.get("today", ""),
                    item.get("diff", ""),
                ]
                for j, val in enumerate(values):
                    if not val:
                        continue
                    # 매번 fresh하게 셀 찾기
                    cell_el = driver.execute_script("""
                        var rowIdx = arguments[0];
                        var colIdx = arguments[1];
                        var table = document.querySelector('table.se-table-content');
                        if (!table) return null;
                        var rows = table.querySelectorAll('tr.se-tr');
                        if (rowIdx + 1 >= rows.length) return null;
                        var cells = rows[rowIdx + 1].querySelectorAll('td.se-cell');
                        if (colIdx >= cells.length) return null;
                        return cells[colIdx].querySelector('p.se-text-paragraph') 
                            || cells[colIdx].querySelector('span.__se-node') 
                            || cells[colIdx];
                    """, i, j)

                    if cell_el:
                        _click_and_paste(driver, cell_el, val)

                filled += 1

            logger.info(f"표 데이터 채우기 완료: {filled}행")
            on_status(f"✅ 시세 표 {filled}행 입력 완료", "success")

        _interruptible_sleep(0.5)
        on_status("🎉 블로그 글 데이터 입력 완료", "success")
        logger.info("블로그 글 데이터 입력 완료")
        return True

    except _StopRequested:
        raise
    except Exception as e:
        logger.exception("블로그 글 데이터 입력 실패")
        on_status("❌ 데이터 입력에 실패했습니다", "error")
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        return False


def publish_post(
    driver: WebDriver,
    on_status: StatusCallback = _noop,
) -> bool:
    try:
        _switch_to_editor(driver)
        _interruptible_sleep(1)

        on_status("📤 발행 버튼을 클릭합니다", "info")
        wait = WebDriverWait(driver, 10)
        publish_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.publish_btn__m9KHH")
        ))
        driver.execute_script("arguments[0].click()", publish_btn)
        logger.info("첫 번째 발행 버튼 클릭")
        _interruptible_sleep(2)

        on_status("📤 최종 발행을 확인합니다", "info")
        confirm_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.confirm_btn__WEaBq[data-testid='seOnePublishBtn']")
        ))
        driver.execute_script("arguments[0].click()", confirm_btn)
        logger.info("최종 발행 버튼 클릭")

        _interruptible_sleep(2)
        on_status("🎉 블로그 글이 발행되었습니다!", "success")
        logger.info("블로그 글 발행 완료")
        return True

    except _StopRequested:
        raise
    except Exception as e:
        logger.exception("블로그 글 발행 실패")
        on_status("❌ 발행에 실패했습니다", "error")
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        return False
