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

from core.google_sheets import BlogPostData

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str, str], None]
_noop: StatusCallback = lambda msg, lvl="info": None


def _switch_to_editor(driver: WebDriver):
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


def fill_post(
    driver: WebDriver,
    post: BlogPostData,
    on_status: StatusCallback = _noop,
) -> bool:
    try:
        on_status("📝 에디터에 데이터를 입력합니다", "info")
        _switch_to_editor(driver)
        time.sleep(1)

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

        time.sleep(0.5)
        on_status("🎉 블로그 글 데이터 입력 완료", "success")
        logger.info("블로그 글 데이터 입력 완료")
        return True

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
        time.sleep(1)

        on_status("📤 발행 버튼을 클릭합니다", "info")
        wait = WebDriverWait(driver, 10)
        publish_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.publish_btn__m9KHH")
        ))
        driver.execute_script("arguments[0].click()", publish_btn)
        logger.info("첫 번째 발행 버튼 클릭")
        time.sleep(2)

        on_status("📤 최종 발행을 확인합니다", "info")
        confirm_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.confirm_btn__WEaBq[data-testid='seOnePublishBtn']")
        ))
        driver.execute_script("arguments[0].click()", confirm_btn)
        logger.info("최종 발행 버튼 클릭")

        time.sleep(2)
        on_status("🎉 블로그 글이 발행되었습니다!", "success")
        logger.info("블로그 글 발행 완료")
        return True

    except Exception as e:
        logger.exception("블로그 글 발행 실패")
        on_status("❌ 발행에 실패했습니다", "error")
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        return False
