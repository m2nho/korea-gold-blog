import tkinter as tk
from tkinter import ttk
import datetime
import math
import weakref
import threading

# ── 색상 팔레트 (Catppuccin Mocha 확장) ──────────────────
BG = "#1e1e2e"
BG_SURFACE = "#22223a"
BG_CARD = "#292942"
BG_INPUT = "#313150"
BG_HOVER = "#3a3a58"
FG = "#cdd6f4"
FG_DIM = "#a6adc8"
FG_MUTED = "#585b70"
ACCENT = "#89b4fa"
ACCENT_HOVER = "#b4d0fb"
ACCENT_DIM = "#4a6a9f"
ACCENT_GLOW = "#89b4fa"
SUCCESS = "#a6e3a1"
SUCCESS_BG = "#1a2e1a"
ERROR = "#f38ba8"
ERROR_BG = "#2e1a22"
WARNING = "#fab387"
WARNING_BG = "#2e2518"
BORDER = "#3e3e5c"
BORDER_FOCUS = "#89b4fa"
SHADOW = "#11111b"
SURFACE_LIGHT = "#2f2f4a"
LAVENDER = "#b4befe"
PINK = "#f5c2e7"
TEAL = "#94e2d5"


# ── 글로벌 폰트 스케일 ─────────────────────────────────

_font_scale = 1.0
_scale_callbacks: list = []
_scalable_widgets: list = []  # (widget_ref, family, base_size, weight)


def get_font_scale() -> float:
    return _font_scale


def set_font_scale(scale: float):
    global _font_scale
    _font_scale = max(0.7, min(1.5, scale))
    _apply_all_scalable()
    for cb in _scale_callbacks:
        try:
            cb(_font_scale)
        except Exception:
            pass


def on_font_scale_change(cb):
    _scale_callbacks.append(cb)


def scaled(base_size: int) -> int:
    return max(7, round(base_size * _font_scale))


def register_scalable(widget, family: str, base_size: int, weight: str = ""):
    """콘텐츠 위젯을 스케일 대상으로 등록"""
    import weakref
    ref = weakref.ref(widget)
    _scalable_widgets.append((ref, family, base_size, weight))
    _apply_font(widget, family, base_size, weight)


def _apply_font(widget, family, base_size, weight):
    sz = max(7, round(base_size * _font_scale))
    font = (family, sz, weight) if weight else (family, sz)
    try:
        widget.configure(font=font)
    except Exception:
        pass


def _apply_all_scalable():
    alive = []
    for ref, family, base_size, weight in _scalable_widgets:
        w = ref()
        if w is not None:
            _apply_font(w, family, base_size, weight)
            alive.append((ref, family, base_size, weight))
    _scalable_widgets.clear()
    _scalable_widgets.extend(alive)


def apply_theme(root: tk.Tk):
    root.configure(bg=BG)
    style = ttk.Style()
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=FG, borderwidth=0)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
    style.configure("Title.TLabel", background=BG, font=("Segoe UI", 18, "bold"), foreground=FG)
    style.configure("Subtitle.TLabel", background=BG, font=("Segoe UI", 9), foreground=FG_MUTED)

    style.configure(
        "Accent.TButton", background=ACCENT, foreground="#11111b",
        font=("Segoe UI", 11, "bold"), padding=(20, 13), borderwidth=0,
    )
    style.map("Accent.TButton",
              background=[("active", ACCENT_HOVER), ("disabled", BORDER)],
              foreground=[("disabled", FG_MUTED)])

    style.configure(
        "Secondary.TButton", background=BG_INPUT, foreground=FG,
        font=("Segoe UI", 10, "bold"), padding=(12, 8), borderwidth=0,
    )
    style.map("Secondary.TButton",
              background=[("active", BG_HOVER), ("disabled", BORDER)],
              foreground=[("disabled", FG_MUTED)])

    style.configure(
        "Stop.TButton", background=ERROR_BG, foreground=ERROR,
        font=("Segoe UI", 10, "bold"), padding=(12, 8), borderwidth=0,
    )
    style.map("Stop.TButton",
              background=[("active", "#3e1a28"), ("disabled", BORDER)],
              foreground=[("disabled", FG_MUTED)])

    style.configure(
        "Quit.TButton", background=BG_SURFACE, foreground=FG_MUTED,
        font=("Segoe UI", 9), padding=(12, 8), borderwidth=0,
    )
    style.map("Quit.TButton",
              background=[("active", BG_HOVER)],
              foreground=[("active", FG_DIM)])

    style.configure("TCheckbutton", background=BG_CARD, foreground=FG_DIM, font=("Segoe UI", 9))
    style.map("TCheckbutton", background=[("active", BG_CARD)])


# ── 카드 ─────────────────────────────────────────────────

class Card(tk.Frame):
    def __init__(self, master, title="", icon="", collapsible=False, **kw):
        kw.setdefault("bg", BG_CARD)
        super().__init__(master, **kw)
        self.configure(highlightbackground=BORDER, highlightthickness=1)

        self._body = tk.Frame(self, bg=BG_CARD, padx=14, pady=10)
        self._body.pack(fill="x")

        if title:
            hdr = tk.Frame(self._body, bg=BG_CARD)
            hdr.pack(fill="x", pady=(0, 6))
            tk.Label(hdr, text=f"{icon}  {title}" if icon else title,
                     bg=BG_CARD, fg=ACCENT, font=("Segoe UI", 10, "bold")).pack(side="left")

        self.content = tk.Frame(self._body, bg=BG_CARD)
        self.content.pack(fill="both", expand=True)

    def add_separator(self):
        tk.Frame(self.content, bg=BORDER, height=1).pack(fill="x", pady=(6, 6))


# ── 플레이스홀더 입력 ────────────────────────────────────

class PlaceholderEntry(tk.Entry):
    def __init__(self, master, placeholder="", show_char="", **kw):
        self._ph = placeholder
        self._show_char = show_char
        self._showing_ph = False
        kw.setdefault("bg", BG_INPUT)
        kw.setdefault("fg", FG)
        kw.setdefault("insertbackground", ACCENT)
        kw.setdefault("relief", "flat")
        kw.setdefault("font", ("Segoe UI", 11))
        kw.setdefault("highlightthickness", 2)
        kw.setdefault("highlightbackground", BORDER)
        kw.setdefault("highlightcolor", BORDER_FOCUS)
        kw.setdefault("selectbackground", ACCENT)
        kw.setdefault("selectforeground", "#11111b")
        super().__init__(master, **kw)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self._show_placeholder()

    def _show_placeholder(self):
        if not self.get():
            self._showing_ph = True
            self.configure(show="", fg=FG_MUTED)
            self.insert(0, self._ph)

    def _on_focus_in(self, _):
        if self._showing_ph:
            self.delete(0, "end")
            self.configure(show=self._show_char, fg=FG)
            self._showing_ph = False

    def _on_focus_out(self, _):
        if not self.get():
            self._show_placeholder()

    def get_value(self) -> str:
        return "" if self._showing_ph else self.get()

    def set_value(self, text: str):
        self._showing_ph = False
        self.configure(show=self._show_char, fg=FG)
        self.delete(0, "end")
        self.insert(0, text)


# ── 토글 스위치 ──────────────────────────────────────────

class ToggleSwitch(tk.Canvas):
    W, H = 38, 20

    def __init__(self, master, variable: tk.BooleanVar, **kw):
        kw.setdefault("bg", BG_CARD)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("width", self.W)
        kw.setdefault("height", self.H)
        super().__init__(master, **kw)
        self._var = variable
        self.bind("<Button-1>", lambda _: self._var.set(not self._var.get()))
        self._var.trace_add("write", lambda *_: self._draw())
        self._draw()

    def _draw(self):
        self.delete("all")
        on = self._var.get()
        r = self.H // 2
        bg = ACCENT if on else FG_MUTED
        self.create_oval(0, 0, self.H, self.H, fill=bg, outline="")
        self.create_oval(self.W - self.H, 0, self.W, self.H, fill=bg, outline="")
        self.create_rectangle(r, 0, self.W - r, self.H, fill=bg, outline="")
        pad = 3
        cx = (self.W - self.H + pad * 2) if on else pad
        d = self.H - pad * 2
        self.create_oval(cx, pad, cx + d, pad + d, fill="#fff", outline="")


# ── 라이브 스텝 타임라인 ─────────────────────────────────

class StepTimeline(tk.Frame):
    STEPS = [
        ("로그인", "🔐"),
        ("블로그 이동", "🌐"),
        ("글쓰기", "✏️"),
        ("템플릿", "📄"),
        ("데이터 입력", "📝"),
        ("발행", "🚀"),
    ]

    def __init__(self, master, **kw):
        kw.setdefault("bg", BG_CARD)
        super().__init__(master, **kw)
        self._current = -1
        self._error = False
        self._step_times: dict[int, float] = {}
        self._step_start: float | None = None
        self._rows: list[dict] = []

        for i, (name, icon) in enumerate(self.STEPS):
            row = tk.Frame(self, bg=BG_CARD)
            row.pack(fill="x", pady=1)

            # 인디케이터 (원)
            cvs = tk.Canvas(row, width=28, height=28, bg=BG_CARD, highlightthickness=0)
            cvs.pack(side="left", padx=(0, 10))

            # 텍스트
            lbl = tk.Label(row, text=f"{icon}  {name}", bg=BG_CARD, fg=FG_MUTED,
                           font=("Segoe UI", 10), anchor="w")
            lbl.pack(side="left", fill="x", expand=True)

            # 소요시간
            time_lbl = tk.Label(row, text="", bg=BG_CARD, fg=FG_MUTED,
                                font=("Consolas", 8), anchor="e")
            time_lbl.pack(side="right", padx=(0, 4))

            # 상태 뱃지
            badge = tk.Label(row, text="", bg=BG_CARD, fg=FG_MUTED,
                             font=("Segoe UI", 8), anchor="e")
            badge.pack(side="right")

            self._rows.append({"canvas": cvs, "label": lbl, "time": time_lbl, "badge": badge})

        self._draw_all()

    def set_step(self, index: int, error: bool = False):
        now = datetime.datetime.now().timestamp()

        # 이전 스텝 소요시간 기록
        if self._step_start is not None and self._current >= 0:
            self._step_times[self._current] = now - self._step_start

        self._current = index
        self._error = error
        self._step_start = now
        self._draw_all()

    def _draw_all(self):
        for i, row in enumerate(self._rows):
            cvs = row["canvas"]
            lbl = row["label"]
            time_lbl = row["time"]
            badge = row["badge"]

            cvs.delete("all")
            r = 10
            cx, cy = 14, 14

            if self._error and i == self._current:
                cvs.create_oval(cx - r, cy - r, cx + r, cy + r, fill=ERROR, outline="")
                cvs.create_text(cx, cy, text="✕", fill="#fff", font=("Segoe UI", 8, "bold"))
                lbl.configure(fg=ERROR)
                badge.configure(text="실패", fg=ERROR)
            elif i < self._current:
                cvs.create_oval(cx - r, cy - r, cx + r, cy + r, fill=SUCCESS, outline="")
                cvs.create_text(cx, cy, text="✓", fill="#11111b", font=("Segoe UI", 9, "bold"))
                lbl.configure(fg=SUCCESS)
                badge.configure(text="완료", fg=SUCCESS)
                if i in self._step_times:
                    t = self._step_times[i]
                    time_lbl.configure(text=f"{t:.1f}s", fg=FG_MUTED)
            elif i == self._current:
                # 글로우 효과
                cvs.create_oval(cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2,
                                fill="", outline=ACCENT_DIM, width=2)
                cvs.create_oval(cx - r, cy - r, cx + r, cy + r, fill=ACCENT, outline="")
                cvs.create_text(cx, cy, text="●", fill="#fff", font=("Segoe UI", 6))
                lbl.configure(fg=FG)
                badge.configure(text="진행 중", fg=ACCENT)
                time_lbl.configure(text="")
            else:
                cvs.create_oval(cx - r, cy - r, cx + r, cy + r, fill=BG_INPUT, outline=BORDER)
                cvs.create_text(cx, cy, text=str(i + 1), fill=FG_MUTED, font=("Segoe UI", 8))
                lbl.configure(fg=FG_MUTED)
                badge.configure(text="대기", fg=FG_MUTED)
                time_lbl.configure(text="")


# ── 프로그레스 바 ────────────────────────────────────────

class ProgressBar(tk.Canvas):
    H = 3

    def __init__(self, master, **kw):
        kw.setdefault("bg", BORDER)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("height", self.H)
        super().__init__(master, **kw)
        self._progress = 0.0
        self._animating = False
        self.bind("<Configure>", lambda _: self._draw())

    def set_progress(self, value: float):
        self._progress = max(0.0, min(1.0, value))
        self._animating = False
        self._draw()

    def pulse(self):
        if self._animating:
            return
        self._animating = True
        self._pulse_pos = 0.0
        self._do_pulse()

    def stop_pulse(self):
        self._animating = False

    def _do_pulse(self):
        if not self._animating:
            self._draw()
            return
        self._pulse_pos = (self._pulse_pos + 0.015) % 1.0
        self.delete("all")
        w = self.winfo_width()
        pw = w * 0.25
        x = self._pulse_pos * (w + pw) - pw
        self.create_rectangle(max(0, x), 0, min(w, x + pw), self.H, fill=ACCENT, outline="")
        self.after(25, self._do_pulse)

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        if self._progress > 0:
            self.create_rectangle(0, 0, w * self._progress, self.H, fill=ACCENT, outline="")


# ── 상태 배너 ────────────────────────────────────────────

class StatusBanner(tk.Frame):
    def __init__(self, master, **kw):
        kw.setdefault("bg", BG_CARD)
        super().__init__(master, **kw)
        self.configure(highlightbackground=BORDER, highlightthickness=1)

        inner = tk.Frame(self, bg=BG_CARD, padx=18, pady=14)
        inner.pack(fill="x")

        self._icon = tk.Label(inner, text="⏸", bg=BG_CARD, font=("Segoe UI", 22))
        self._icon.pack(side="left", padx=(0, 14))

        text_frame = tk.Frame(inner, bg=BG_CARD)
        text_frame.pack(side="left", fill="x", expand=True)

        self._title = tk.Label(text_frame, text="준비 완료", bg=BG_CARD, fg=FG,
                               font=("Segoe UI", 12, "bold"), anchor="w")
        self._title.pack(fill="x")

        self._subtitle = tk.Label(text_frame, text="자동화를 시작하려면 설정을 완료하세요",
                                  bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 9), anchor="w")
        self._subtitle.pack(fill="x")

        self._inner = inner

    def set_state(self, state: str, title: str = "", subtitle: str = ""):
        configs = {
            "idle":    ("⏸", FG_MUTED, BG_CARD, BORDER),
            "running": ("⚡", ACCENT, BG_CARD, ACCENT_DIM),
            "success": ("✅", SUCCESS, SUCCESS_BG, SUCCESS),
            "error":   ("❌", ERROR, ERROR_BG, ERROR),
            "warn":    ("⚠️", WARNING, WARNING_BG, WARNING),
        }
        icon, fg, bg, border = configs.get(state, configs["idle"])
        self._icon.configure(text=icon, bg=bg)
        self._title.configure(text=title, fg=fg, bg=bg)
        self._subtitle.configure(text=subtitle, bg=bg)
        self._inner.configure(bg=bg)
        self.configure(highlightbackground=border)


# ── 미리보기 카드 (간소 — 좌측 패널용) ───────────────────

class PreviewCard(tk.Frame):
    def __init__(self, master, **kw):
        kw.setdefault("bg", BG_SURFACE)
        super().__init__(master, **kw)
        self.configure(highlightbackground=BORDER, highlightthickness=1)
        self._empty = True
        self._labels = {}

        self._empty_label = tk.Label(
            self, text="📋  항목을 선택하세요",
            bg=BG_SURFACE, fg=FG_MUTED, font=("Segoe UI", 9),
        )
        self._empty_label.pack(pady=10)

        self._detail = tk.Frame(self, bg=BG_SURFACE, padx=12, pady=8)
        for key, label, color in [("date", "📅", TEAL), ("title", "📰", FG)]:
            row = tk.Frame(self._detail, bg=BG_SURFACE)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, bg=BG_SURFACE, fg=FG_MUTED,
                     font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
            val = tk.Label(row, text="", bg=BG_SURFACE, fg=color,
                           font=("Segoe UI", 9), anchor="w")
            val.pack(side="left", fill="x", expand=True)
            self._labels[key] = val

    def set_data(self, date="", compare="", title="", **_):
        if self._empty:
            self._empty_label.pack_forget()
            self._detail.pack(fill="x")
            self._empty = False
        self._labels["date"].configure(text=f"{date}  ↔  {compare}")
        self._labels["title"].configure(text=title)

    def clear(self):
        if not self._empty:
            self._detail.pack_forget()
            self._empty_label.pack(pady=10)
            self._empty = True


# ── 상세 미리보기 패널 (우측 패널용 — 탭) ────────────────

class DetailPreview(tk.Frame):
    """탭 기반 상세 미리보기: 요약 / 시세표 / 뉴스"""

    TAB_NAMES = ["🖼 썸네일", "📄 요약", "📊 시세표", "📰 뉴스"]

    def __init__(self, master, thumbnail_var: "tk.BooleanVar | None" = None, **kw):
        kw.setdefault("bg", BG_CARD)
        super().__init__(master, **kw)
        self.configure(highlightbackground=BORDER, highlightthickness=1)

        self._current_tab = 0
        self._post = None
        self._thumbnail_var = thumbnail_var

        # 탭 바
        self._tab_bar = tk.Frame(self, bg=BG_SURFACE)
        self._tab_bar.pack(fill="x")
        self._tab_btns: list[tk.Label] = []
        for i, name in enumerate(self.TAB_NAMES):
            btn = tk.Label(
                self._tab_bar, text=name, bg=BG_SURFACE, fg=FG_MUTED,
                font=("Segoe UI", 9, "bold"), padx=14, pady=8, cursor="hand2",
            )
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda _, idx=i: self._switch_tab(idx))
            self._tab_btns.append(btn)

        # 콘텐츠 영역
        self._content = tk.Frame(self, bg=BG_CARD)
        self._content.pack(fill="both", expand=True)

        # 빈 상태
        self._empty_frame = tk.Frame(self._content, bg=BG_CARD)
        self._empty_frame.pack(fill="both", expand=True)
        tk.Label(self._empty_frame, text="📋", bg=BG_CARD,
                 font=("Segoe UI", 24)).pack(pady=(30, 6))
        tk.Label(self._empty_frame, text="시트 데이터를 불러온 후\n항목을 선택하면 미리보기가 표시됩니다",
                 bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 9),
                 justify="center").pack()

        # 탭별 프레임 (lazy)
        self._tab_frames: list[tk.Frame | None] = [None, None, None, None]

        self._switch_tab(0)

    def _switch_tab(self, idx: int):
        self._current_tab = idx
        for i, btn in enumerate(self._tab_btns):
            if i == idx:
                btn.configure(bg=BG_CARD, fg=ACCENT)
            else:
                btn.configure(bg=BG_SURFACE, fg=FG_MUTED)
        self._render()

    def set_post(self, post):
        self._post = post
        self._tab_frames = [None, None, None, None]  # 캐시 초기화
        self._render()

    def _render(self):
        for w in self._content.winfo_children():
            w.pack_forget()

        if not self._post:
            self._empty_frame.pack(fill="both", expand=True)
            return

        idx = self._current_tab
        if self._tab_frames[idx] is None:
            builders = [self._build_thumbnail, self._build_summary,
                        self._build_table, self._build_news]
            self._tab_frames[idx] = builders[idx]()

        self._tab_frames[idx].pack(fill="both", expand=True)

    # ── 요약 탭 ──────────────────────────────────────────

    def _build_summary(self) -> tk.Frame:
        p = self._post
        f = tk.Frame(self._content, bg=BG_CARD, padx=16, pady=12)

        # 날짜 뱃지
        date_row = tk.Frame(f, bg=BG_CARD)
        date_row.pack(fill="x", pady=(0, 8))
        self._badge(date_row, p.date, TEAL)
        tk.Label(date_row, text="  ↔  ", bg=BG_CARD, fg=FG_MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        self._badge(date_row, p.compare_date, LAVENDER)

        # 제목
        lbl_title = tk.Label(f, text=p.section1_title, bg=BG_CARD, fg=FG,
                             font=("Segoe UI", 11, "bold"), anchor="w",
                             wraplength=400)
        lbl_title.pack(fill="x", pady=(0, 6))
        register_scalable(lbl_title, "Segoe UI", 11, "bold")

        tk.Frame(f, bg=BORDER, height=1).pack(fill="x", pady=4)

        # 소개글
        self._section_label(f, "소개글")
        lbl_intro = tk.Label(f, text=p.section1_intro or "(없음)", bg=BG_CARD, fg=FG_DIM,
                             font=("Segoe UI", 9), anchor="w", justify="left",
                             wraplength=400)
        lbl_intro.pack(fill="x", pady=(0, 6))
        register_scalable(lbl_intro, "Segoe UI", 9)

        # 요약
        self._section_label(f, "요약")
        lbl_summary = tk.Label(f, text=p.section1_summary or "(없음)", bg=BG_CARD, fg=FG_DIM,
                               font=("Segoe UI", 9), anchor="w", justify="left",
                               wraplength=400)
        lbl_summary.pack(fill="x", pady=(0, 6))
        register_scalable(lbl_summary, "Segoe UI", 9)

        # 통계
        tk.Frame(f, bg=BORDER, height=1).pack(fill="x", pady=4)
        stat_row = tk.Frame(f, bg=BG_CARD)
        stat_row.pack(fill="x")
        self._stat(stat_row, "시세 항목", str(p.price_row_count), WARNING)
        self._stat(stat_row, "뉴스 기사", str(p.news_count), PINK)

        return f

    # ── 시세표 탭 ────────────────────────────────────────

    def _build_table(self) -> tk.Frame:
        p = self._post
        f = tk.Frame(self._content, bg=BG_CARD, padx=4, pady=8)

        if not p.section1_table:
            tk.Label(f, text="시세 데이터가 없습니다", bg=BG_CARD, fg=FG_MUTED,
                     font=("Segoe UI", 9)).pack(pady=20)
            return f

        # 스크롤 가능 영역
        canvas = tk.Canvas(f, bg=BG_CARD, highlightthickness=0)
        scrollbar = tk.Scrollbar(f, orient="vertical", command=canvas.yview)
        table_frame = tk.Frame(canvas, bg=BG_CARD)
        table_frame.bind("<Configure>",
                         lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=table_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 헤더
        headers = ["상품(고객기준)", p.compare_date or "전일", p.date or "오늘", "변동"]
        hdr_colors = [FG_MUTED, LAVENDER, TEAL, WARNING]
        hdr_row = tk.Frame(table_frame, bg=BG_SURFACE)
        hdr_row.pack(fill="x")
        for j, (h, c) in enumerate(zip(headers, hdr_colors)):
            w = 14 if j == 0 else 10
            lbl = tk.Label(hdr_row, text=h, bg=BG_SURFACE, fg=c,
                           font=("Consolas", 9, "bold"), width=w,
                           anchor="center", pady=4)
            lbl.pack(side="left", padx=1)
            register_scalable(lbl, "Consolas", 9, "bold")

        # 데이터 행
        for i, item in enumerate(p.section1_table):
            bg = BG_INPUT if i % 2 == 0 else BG_CARD
            row = tk.Frame(table_frame, bg=bg)
            row.pack(fill="x")

            vals = [
                (item.get("item", ""), FG, 14),
                (item.get("yesterday", ""), FG_DIM, 10),
                (item.get("today", ""), FG, 10),
                (item.get("diff", ""), self._diff_color(item.get("diff", "")), 10),
            ]
            for val, color, w in vals:
                lbl = tk.Label(row, text=val, bg=bg, fg=color,
                               font=("Consolas", 9), width=w,
                               anchor="center", pady=3)
                lbl.pack(side="left", padx=1)
                register_scalable(lbl, "Consolas", 9)

        return f

    # ── 뉴스 탭 ──────────────────────────────────────────

    def _build_news(self) -> tk.Frame:
        p = self._post
        f = tk.Frame(self._content, bg=BG_CARD, padx=16, pady=12)

        # 뉴스 제목
        lbl_title = tk.Label(f, text=p.section2_title or "(제목 없음)", bg=BG_CARD, fg=FG,
                             font=("Segoe UI", 11, "bold"), anchor="w",
                             wraplength=400)
        lbl_title.pack(fill="x", pady=(0, 6))
        register_scalable(lbl_title, "Segoe UI", 11, "bold")

        tk.Frame(f, bg=BORDER, height=1).pack(fill="x", pady=4)

        # 본문
        self._section_label(f, "본문")
        content_text = tk.Text(
            f, bg=BG_INPUT, fg=FG_DIM, font=("Segoe UI", 9),
            relief="flat", highlightthickness=1, highlightbackground=BORDER,
            wrap="word", height=8, padx=8, pady=6,
        )
        content_text.insert("1.0", p.section2_content or "(없음)")
        content_text.configure(state="disabled")
        content_text.pack(fill="both", expand=True)
        register_scalable(content_text, "Segoe UI", 9)

        return f

    # ── 유틸 ─────────────────────────────────────────────

    def _badge(self, parent, text, color):
        lbl = tk.Label(parent, text=f" {text} ", bg=BG_INPUT, fg=color,
                       font=("Consolas", 9, "bold"), padx=6, pady=1)
        lbl.pack(side="left")

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, bg=BG_CARD, fg=FG_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 2))

    def _stat(self, parent, label, value, color):
        f = tk.Frame(parent, bg=BG_CARD)
        f.pack(side="left", padx=(0, 20))
        tk.Label(f, text=value, bg=BG_CARD, fg=color,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(f, text=f"  {label}", bg=BG_CARD, fg=FG_MUTED,
                 font=("Segoe UI", 9)).pack(side="left")

    @staticmethod
    def _diff_color(diff_str: str) -> str:
        if not diff_str:
            return FG_DIM
        if diff_str.startswith("+") or diff_str.startswith("▲"):
            return ERROR
        if diff_str.startswith("-") or diff_str.startswith("▼"):
            return TEAL
        return FG_DIM

    # ── 썸네일 탭 ────────────────────────────────────────

    def _build_thumbnail(self) -> tk.Frame:
        from core.thumbnail import create_thumbnail, _split_title, _pick_random_background, ASSETS_DIR
        from tkinter import filedialog, colorchooser
        from pathlib import Path

        p = self._post
        f = tk.Frame(self._content, bg=BG_CARD, padx=16, pady=10)

        # ── 썸네일 사용 토글 ─────────────────────────────
        if self._thumbnail_var is not None:
            toggle_row = tk.Frame(f, bg=BG_CARD)
            toggle_row.pack(fill="x", pady=(0, 8))
            ToggleSwitch(toggle_row, variable=self._thumbnail_var).pack(side="left")
            toggle_lbl = tk.Label(toggle_row, text="썸네일 사용", bg=BG_CARD, fg=FG_DIM,
                                  font=("Segoe UI", 9), cursor="hand2")
            toggle_lbl.pack(side="left", padx=(6, 0))
            toggle_lbl.bind("<Button-1>", lambda _: self._thumbnail_var.set(not self._thumbnail_var.get()))
            tk.Frame(f, bg=BORDER, height=1).pack(fill="x", pady=(0, 8))

        # section2_title → 자동 분리
        title_text = p.section2_title or ""
        l1, l2 = _split_title(title_text)

        # 1줄 입력
        tk.Label(f, text="1줄 (강조)", bg=BG_CARD, fg=FG_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        line1_entry = PlaceholderEntry(f, placeholder="강조 문구")
        line1_entry.pack(fill="x", ipady=3)
        line1_entry.set_value(l1)

        # 2줄 입력
        tk.Label(f, text="2줄 (보조)", bg=BG_CARD, fg=FG_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(6, 0))
        line2_entry = PlaceholderEntry(f, placeholder="보조 설명")
        line2_entry.pack(fill="x", ipady=3)
        line2_entry.set_value(l2)

        # 옵션 행: 강조색 + 배경
        opt_row = tk.Frame(f, bg=BG_CARD)
        opt_row.pack(fill="x", pady=(8, 0))

        # 강조색
        accent_var = [(255, 60, 60)]  # mutable default
        color_box = tk.Label(opt_row, text="  ", bg="#ff3c3c", width=3,
                             relief="solid", borderwidth=1, cursor="hand2")
        color_box.pack(side="left")
        tk.Label(opt_row, text=" 강조색", bg=BG_CARD, fg=FG_DIM,
                 font=("Segoe UI", 8)).pack(side="left", padx=(2, 12))

        def pick_color(_=None):
            if self._thumbnail_var and not self._thumbnail_var.get():
                return
            c = colorchooser.askcolor(color=color_box.cget("bg"), title="강조색 선택")
            if c and c[0]:
                accent_var[0] = tuple(int(v) for v in c[0])
                color_box.configure(bg=c[1])
        color_box.bind("<Button-1>", pick_color)

        # 배경 이미지 선택
        bg_path_var = [None]  # None = 랜덤
        bg_label = tk.Label(opt_row, text="🎲 랜덤 배경", bg=BG_CARD, fg=TEAL,
                            font=("Segoe UI", 8), cursor="hand2")
        bg_label.pack(side="right")

        def pick_bg(_=None):
            if self._thumbnail_var and not self._thumbnail_var.get():
                return
            path = filedialog.askopenfilename(
                title="배경 이미지 선택",
                initialdir=str(ASSETS_DIR),
                filetypes=[("이미지", "*.png *.jpg *.jpeg *.webp")],
            )
            if path:
                bg_path_var[0] = path
                name = Path(path).name
                bg_label.configure(text=f"📁 {name[:20]}", fg=ACCENT)
            else:
                bg_path_var[0] = None
                bg_label.configure(text="🎲 랜덤 배경", fg=TEAL)
        bg_label.bind("<Button-1>", pick_bg)

        # 하단 버튼 (먼저 pack해서 하단 고정)
        btn_row = tk.Frame(f, bg=BG_CARD)
        btn_row.pack(fill="x", side="bottom", pady=(8, 0))

        status_lbl = tk.Label(btn_row, text="", bg=BG_CARD, fg=FG_MUTED,
                              font=("Segoe UI", 8))
        status_lbl.pack(side="left")

        # 미리보기 영역 (나머지 공간 채움)
        preview_frame = tk.Frame(f, bg=BG_INPUT, highlightbackground=BORDER,
                                 highlightthickness=1)
        preview_frame.pack(fill="both", expand=True, pady=(8, 0))
        preview_frame.pack_propagate(False)
        preview_label = tk.Label(preview_frame, text="🖼  생성 버튼을 눌러 미리보기",
                                 bg=BG_INPUT, fg=FG_MUTED, font=("Segoe UI", 9))
        preview_label.pack(expand=True)

        # 비활성 오버레이
        overlay_lbl = tk.Label(preview_frame, text="썸네일 사용이 꺼져 있습니다",
                               bg=BG_INPUT, fg=FG_MUTED, font=("Segoe UI", 10))
        self._thumb_photo = None  # GC 방지

        def do_generate():
            l1_val = line1_entry.get_value().strip()
            l2_val = line2_entry.get_value().strip()
            if not l1_val:
                status_lbl.configure(text="1줄을 입력하세요", fg=ERROR)
                return
            gen_btn.configure(state="disabled")
            status_lbl.configure(text="생성 중...", fg=WARNING)

            def worker():
                try:
                    bg_img = bg_path_var[0] or str(_pick_random_background())
                    out = create_thumbnail(
                        bg_img, l1_val, l2_val,
                        accent_color=tuple(accent_var[0]),
                    )
                    self.winfo_toplevel().after(0, lambda: on_done(out))
                except Exception as e:
                    self.winfo_toplevel().after(0, lambda: on_error(str(e)))

            def on_done(path):
                try:
                    from PIL import Image, ImageTk
                    pil_img = Image.open(path)
                    preview_frame.update_idletasks()
                    pw = max(preview_frame.winfo_width() - 4, 200)
                    ph = max(preview_frame.winfo_height() - 4, 200)
                    fit = min(pw / pil_img.width, ph / pil_img.height)
                    new_w = int(pil_img.width * fit)
                    new_h = int(pil_img.height * fit)
                    pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
                    self._thumb_photo = ImageTk.PhotoImage(pil_img)
                    preview_label.configure(image=self._thumb_photo, text="")
                    self._last_thumb_path = str(path)
                    save_btn.configure(state="normal")
                    status_lbl.configure(text="✅ 생성 완료", fg=SUCCESS)
                except Exception as e:
                    status_lbl.configure(text=f"미리보기 실패: {e}", fg=ERROR)
                gen_btn.configure(state="normal")

            def on_error(msg):
                status_lbl.configure(text=f"❌ {msg}", fg=ERROR)
                gen_btn.configure(state="normal")

            threading.Thread(target=worker, daemon=True).start()

        def do_save():
            from tkinter import filedialog as fd
            import shutil
            src = getattr(self, '_last_thumb_path', None)
            if not src:
                return
            dst = fd.asksaveasfilename(
                title="썸네일 저장",
                defaultextension=".png",
                initialfile="thumbnail.png",
                filetypes=[("PNG", "*.png"), ("모든 파일", "*.*")],
            )
            if dst:
                shutil.copy2(src, dst)
                status_lbl.configure(text="✅ 저장 완료", fg=SUCCESS)

        save_btn = ttk.Button(btn_row, text="💾 저장",
                              style="Secondary.TButton", command=do_save)
        save_btn.pack(side="right", padx=(4, 0))
        save_btn.configure(state="disabled")

        gen_btn = ttk.Button(btn_row, text="🖼  썸네일 생성",
                             style="Secondary.TButton", command=do_generate)
        gen_btn.pack(side="right")

        # 토글 상태에 따라 위젯 활성/비활성
        if self._thumbnail_var is not None:
            def _update_state(*_):
                on = self._thumbnail_var.get()
                state = "normal" if on else "disabled"
                for entry in (line1_entry, line2_entry):
                    entry.configure(state=state)
                gen_btn.configure(state=state)
                color_box.configure(cursor="hand2" if on else "")
                bg_label.configure(cursor="hand2" if on else "")
                if not on:
                    overlay_lbl.place(relx=0.5, rely=0.5, anchor="center")
                else:
                    overlay_lbl.place_forget()

            self._thumbnail_var.trace_add("write", _update_state)
            _update_state()  # 초기 상태 적용

        return f


# ── 로그 패널 ────────────────────────────────────────────

class LogPanel(tk.Frame):
    MAX_LINES = 120

    def __init__(self, master, **kw):
        super().__init__(master, bg=BG_SURFACE, **kw)
        self.configure(highlightbackground=BORDER, highlightthickness=1)
        self._start_time = None

        hdr = tk.Frame(self, bg=BG_SURFACE)
        hdr.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(hdr, text="📋  진행 로그", bg=BG_SURFACE, fg=FG_MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self._elapsed = tk.Label(hdr, text="", bg=BG_SURFACE, fg=FG_MUTED,
                                 font=("Consolas", 8))
        self._elapsed.pack(side="right")

        self._text = tk.Text(
            self, bg=BG_SURFACE, fg=FG_DIM, font=("Consolas", 9),
            relief="flat", highlightthickness=0, wrap="word",
            state="disabled", cursor="arrow", padx=14, pady=6,
            selectbackground=ACCENT, selectforeground="#11111b",
            spacing1=1, spacing3=1,
        )
        self._text.pack(fill="both", expand=True)
        self._text.tag_configure("time", foreground=FG_MUTED, font=("Consolas", 8))
        self._text.tag_configure("info", foreground=FG)
        self._text.tag_configure("msg", foreground=FG_DIM)
        self._text.tag_configure("success", foreground=SUCCESS)
        self._text.tag_configure("error", foreground=ERROR)
        self._text.tag_configure("warn", foreground=WARNING)

    def append(self, text: str, tag: str = "msg"):
        if self._start_time is None:
            self._start_time = datetime.datetime.now()
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        elapsed = datetime.datetime.now() - self._start_time
        s = int(elapsed.total_seconds())
        self._elapsed.configure(text=f"⏱ {s // 60:02d}:{s % 60:02d}")

        self._text.configure(state="normal")
        self._text.insert("end", f" {ts} ", "time")
        self._text.insert("end", f" {text}\n", tag)
        lines = int(self._text.index("end-1c").split(".")[0])
        if lines > self.MAX_LINES:
            self._text.delete("1.0", f"{lines - self.MAX_LINES}.0")
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self):
        self._start_time = None
        self._elapsed.configure(text="")
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")


# ── 하위 호환 (StepIndicator alias) ─────────────────────
StepIndicator = StepTimeline
