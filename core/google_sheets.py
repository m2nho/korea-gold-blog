import csv
import io
import json
import re
import logging
from dataclasses import dataclass, field
from urllib.request import urlopen, Request

logger = logging.getLogger(__name__)


@dataclass
class BlogPostData:
    date: str = ""
    generated_at: str = ""
    section1_title: str = ""
    section1_intro: str = ""
    section1_summary: str = ""
    section1_table: list = field(default_factory=list)
    section2_title: str = ""
    section2_content: str = ""
    section2_articles: list = field(default_factory=list)
    news_count: int = 0
    price_row_count: int = 0
    compare_date: str = ""

    @property
    def display_label(self) -> str:
        return f"[{self.date}] {self.section1_title}"

    @property
    def price_summary(self) -> str:
        if not self.section1_table:
            return ""
        first = self.section1_table[0]
        return f"{first.get('item', '')}: {first.get('today', '')} ({first.get('diff', '')})"


def _parse_json_field(raw: str) -> list:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def _extract_sheet_id(url: str) -> str:
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return url.strip()


def _row_to_post(headers: list[str], row: list[str]) -> BlogPostData:
    def get(name: str) -> str:
        try:
            idx = headers.index(name)
            return row[idx] if idx < len(row) else ""
        except ValueError:
            return ""

    return BlogPostData(
        date=get("date"),
        generated_at=get("generatedAt"),
        section1_title=get("section1_title"),
        section1_intro=get("section1_introText"),
        section1_summary=get("section1_summaryText"),
        section1_table=_parse_json_field(get("section1_table_json")),
        section2_title=get("section2_title"),
        section2_content=get("section2_content"),
        section2_articles=_parse_json_field(get("section2_articles_json")),
        news_count=int(get("newsArticleCount") or 0),
        price_row_count=int(get("priceRowCount") or 0),
        compare_date=get("compareDate"),
    )


def fetch_posts(sheet_url: str, gid: str = "0") -> list[BlogPostData]:
    sheet_id = _extract_sheet_id(sheet_url)
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

    req = Request(csv_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=15) as resp:
        text = resp.read().decode("utf-8")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if len(rows) < 2:
        return []

    headers = rows[0]
    posts = []
    for row in rows[1:]:
        if not any(row):
            continue
        posts.append(_row_to_post(headers, row))

    posts.sort(key=lambda p: p.date, reverse=True)
    logger.info(f"시트에서 {len(posts)}개 포스트 로드")
    return posts
