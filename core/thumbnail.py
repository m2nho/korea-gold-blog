from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import sys

def _base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent

def _output_dir() -> Path:
    """생성된 파일 저장 경로 (APPDATA 하위)."""
    import os
    d = Path(os.environ.get("APPDATA", ".")) / "NaverBlogAutomation" / "thumbnail"
    d.mkdir(parents=True, exist_ok=True)
    return d

ASSETS_DIR = _base_dir() / "assets" / "thumbnail"
OUTPUT_DIR = _output_dir()
LOGO_PATH = _base_dir() / "assets" / "logo_가로-누끼.png"
FONT_PATH = _base_dir() / "assets" / "fonts" / "malgunbd.ttf"
THUMBNAIL_SIZE = 1080  # 1:1 정사각형


def _find_max_font_size(draw, text, font_path, max_width, max_size=200, min_size=30):
    """주어진 너비에 맞는 최대 폰트 크기를 찾는다."""
    for size in range(max_size, min_size - 1, -2):
        font = ImageFont.truetype(font_path, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return font
    return ImageFont.truetype(font_path, min_size)


def _draw_outlined_text(draw, pos, text, font, fill, outline_color=(0, 0, 0), outline_width=4):
    """검정 외곽선 + 본문 텍스트를 그린다."""
    x, y = pos
    # 외곽선 (8방향)
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    # 본문
    draw.text((x, y), text, font=font, fill=fill)


def create_thumbnail(
    image_path: str | Path,
    line1: str,
    line2: str,
    output_path: str | Path = None,
    accent_color: tuple = (255, 60, 60),
) -> Path:
    """
    유튜브 경제 뉴스 스타일 1:1 썸네일을 생성한다.

    Args:
        image_path: 배경 이미지 경로
        line1: 첫 줄 (강조 문구, 자극적 핵심)
        line2: 둘째 줄 (보조 설명)
        output_path: 저장 경로 (None이면 thumbnail 폴더에 저장)
        accent_color: 첫 줄 강조색 (기본: 빨강)

    Returns:
        저장된 이미지 경로
    """
    # 1) 배경 이미지 → 1:1 크롭 & 리사이즈
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size
    crop_size = min(w, h)
    left = (w - crop_size) // 2
    top = (h - crop_size) // 2
    img = img.crop((left, top, left + crop_size, top + crop_size))
    img = img.resize((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.LANCZOS)

    # 2) 하단 40% 그라데이션 오버레이 (위: 투명 → 아래: 검정)
    overlay = Image.new("RGBA", (THUMBNAIL_SIZE, THUMBNAIL_SIZE), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    gradient_start = int(THUMBNAIL_SIZE * 0.55)  # 상위 55%부터 그라데이션 시작
    for y in range(gradient_start, THUMBNAIL_SIZE):
        progress = (y - gradient_start) / (THUMBNAIL_SIZE - gradient_start)
        alpha = int(230 * (progress ** 1.5))  # 비선형으로 아래쪽이 더 진하게
        overlay_draw.line([(0, y), (THUMBNAIL_SIZE, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, overlay)

    # 3) 텍스트 렌더링
    draw = ImageDraw.Draw(img)
    margin_x = int(THUMBNAIL_SIZE * 0.06)
    margin_bottom = int(THUMBNAIL_SIZE * 0.07)
    max_text_width = THUMBNAIL_SIZE - margin_x * 2

    # 폰트 크기 자동 계산 (화면에 꽉 차게)
    font1 = _find_max_font_size(draw, line1, FONT_PATH, max_text_width, max_size=160, min_size=50)
    font2 = _find_max_font_size(draw, line2, FONT_PATH, max_text_width, max_size=120, min_size=36)

    # 텍스트 높이 계산
    bbox1 = draw.textbbox((0, 0), line1, font=font1)
    bbox2 = draw.textbbox((0, 0), line2, font=font2)
    h1 = bbox1[3] - bbox1[1]
    h2 = bbox2[3] - bbox2[1]
    line_gap = int(h1 * 0.2)  # 줄 간격: 첫 줄 높이의 20%

    total_text_height = h1 + line_gap + h2

    # 하단 중앙 배치
    y2 = THUMBNAIL_SIZE - margin_bottom - h2
    y1 = y2 - line_gap - h1

    w1 = bbox1[2] - bbox1[0]
    w2 = bbox2[2] - bbox2[0]
    x1 = (THUMBNAIL_SIZE - w1) // 2
    x2 = (THUMBNAIL_SIZE - w2) // 2

    # 외곽선 두께 (폰트 크기에 비례)
    outline1 = max(3, font1.size // 25)
    outline2 = max(3, font2.size // 25)

    # 그림자 (은은하게)
    shadow_offset = max(2, font1.size // 40)
    _draw_outlined_text(draw, (x1 + shadow_offset, y1 + shadow_offset), line1, font1,
                        fill=(0, 0, 0, 120), outline_color=(0, 0, 0, 80), outline_width=outline1 + 2)
    _draw_outlined_text(draw, (x2 + shadow_offset, y2 + shadow_offset), line2, font2,
                        fill=(0, 0, 0, 120), outline_color=(0, 0, 0, 80), outline_width=outline2 + 2)

    # 본문 텍스트
    _draw_outlined_text(draw, (x1, y1), line1, font1,
                        fill=accent_color, outline_color=(0, 0, 0), outline_width=outline1)
    _draw_outlined_text(draw, (x2, y2), line2, font2,
                        fill=(255, 255, 255), outline_color=(0, 0, 0), outline_width=outline2)

    # 4) 우측 상단 로고 오버레이
    if LOGO_PATH.exists():
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo_h = int(THUMBNAIL_SIZE * 0.07)
            logo_w = int(logo.width * (logo_h / logo.height))
            logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
            logo_margin = int(THUMBNAIL_SIZE * 0.03)
            logo_x = THUMBNAIL_SIZE - logo_w - logo_margin
            logo_y = logo_margin
            img.paste(logo, (logo_x, logo_y), logo)
        except Exception:
            pass

    # 5) 저장
    if output_path is None:
        output_path = OUTPUT_DIR / "output.png"
    output_path = Path(output_path)
    img.convert("RGB").save(output_path, quality=95)
    return output_path


def _pick_random_background() -> Path:
    """thumbnail 폴더에서 base.png를 제외한 랜덤 이미지를 선택한다."""
    import random
    candidates = [
        f for f in ASSETS_DIR.glob("*.png")
        if f.name not in ("base.png", "test_output.png", "output.png")
    ]
    if not candidates:
        raise FileNotFoundError(f"배경 이미지가 없습니다: {ASSETS_DIR}")
    return random.choice(candidates)


def _split_title(text: str) -> tuple[str, str]:
    """입력 문장을 line1(강조), line2(보조)로 자동 분리한다."""
    import re
    # 접속 조사/키워드 기준으로 분리 시도
    splitters = r'(?:과\s|와\s|및\s|,\s)'
    parts = re.split(splitters, text, maxsplit=1)
    if len(parts) == 2 and len(parts[0].strip()) >= 4 and len(parts[1].strip()) >= 4:
        return parts[0].strip(), parts[1].strip()
    # 분리 실패 시 중간 공백 기준으로 반으로 나눔
    mid = len(text) // 2
    space_idx = text.find(' ', mid)
    space_idx_before = text.rfind(' ', 0, mid)
    # 중간에서 가장 가까운 공백 선택
    if space_idx == -1:
        split_at = space_idx_before
    elif space_idx_before == -1:
        split_at = space_idx
    else:
        split_at = space_idx if (space_idx - mid) <= (mid - space_idx_before) else space_idx_before
    if split_at <= 0:
        return text, ""
    return text[:split_at].strip(), text[split_at:].strip()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("[USAGE] python -m core.thumbnail \"제목 문장\"")
        sys.exit(1)
    title = " ".join(sys.argv[1:])
    line1, line2 = _split_title(title)
    print(f"[INFO] 1줄: {line1}")
    print(f"[INFO] 2줄: {line2}")
    bg = _pick_random_background()
    print(f"[INFO] 배경: {bg.name}")
    result = create_thumbnail(
        bg,
        line1=line1,
        line2=line2,
        output_path=OUTPUT_DIR / "output.png",
    )
    print(f"[OK] 썸네일 생성 완료: {result}")
