import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
import sys
from pathlib import Path
from threading import Event

from config.settings import save_credentials, load_credentials
from core.naver_auth import login, navigate_to_write, apply_template, LoginResult
from core.google_sheets import fetch_posts, BlogPostData
from core.blog_writer import fill_post, publish_post, insert_thumbnail, set_stop_event
from ui.theme import (
    apply_theme, Card, PlaceholderEntry, ToggleSwitch,
    StepTimeline, ProgressBar, StatusBanner, DetailPreview, LogPanel,
    BG, BG_CARD, BG_SURFACE, BG_INPUT, BG_HOVER, FG, FG_DIM, FG_MUTED,
    ACCENT, ACCENT_HOVER, SUCCESS, ERROR, WARNING, BORDER,
    get_font_scale, set_font_scale, on_font_scale_change,
)

logger = logging.getLogger(__name__)

LEVEL_TAGS = {"info": "info", "success": "success", "error": "error", "warn": "warn"}
TOTAL_STEPS = 6


# Windows 작업표시줄 아이콘 설정
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("naver.blog.automation.1.0")
except Exception:
    pass


class MainWindow:
    W, H = 960, 720

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("네이버 블로그 자동화")
        self.root.resizable(False, False)
        self._center()
        apply_theme(self.root)
        self._set_window_icon()

        self.driver = None
        self.posts: list[BlogPostData] = []
        self.selected_post: BlogPostData | None = None
        self._running = False
        self._stop_event = Event()
        self.use_thumbnail_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._load_saved()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center(self):
        x = (self.root.winfo_screenwidth() - self.W) // 2
        y = (self.root.winfo_screenheight() - self.H) // 2
        self.root.geometry(f"{self.W}x{self.H}+{x}+{y}")

    def _asset_path(self, filename: str) -> Path:
        if getattr(sys, 'frozen', False):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).resolve().parent.parent
        return base / 'assets' / filename

    def _set_window_icon(self):
        ico = self._asset_path('favicon.ico')
        if ico.exists():
            try:
                self.root.iconbitmap(str(ico))
            except Exception:
                pass

    def _load_logo(self):
        logo = self._asset_path('logo_가로-누끼.png')
        if not logo.exists():
            return None
        try:
            img = tk.PhotoImage(file=str(logo))
            # 로고를 헤더에 맞게 축소 (높이 ~36px 기준)
            w, h = img.width(), img.height()
            factor = max(1, h // 36)
            if factor > 1:
                img = img.subsample(factor)
            return img
        except Exception:
            return None

    # ── UI ────────────────────────────────────────────────

    def _build_ui(self):
        # 상단 프로그레스
        self.progress = ProgressBar(self.root)
        self.progress.pack(fill="x", side="top")

        # ── 하단 상태바 (body보다 먼저 pack해야 잘리지 않음)
        bar = tk.Frame(self.root, bg=BG_SURFACE, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.status_var = tk.StringVar(value="준비 완료")
        tk.Label(bar, textvariable=self.status_var, bg=BG_SURFACE,
                 fg=FG_MUTED, font=("Segoe UI", 8), anchor="w", padx=16).pack(
            side="left", fill="both", expand=True)

        zoom_frame = tk.Frame(bar, bg=BG_SURFACE)
        zoom_frame.pack(side="right", padx=(0, 6))
        for txt, delta in [("−", -0.1), ("+", 0.1)]:
            btn = tk.Label(zoom_frame, text=txt, bg=BG_INPUT, fg=FG_DIM,
                           font=("Consolas", 9, "bold"), padx=5, cursor="hand2")
            btn.pack(side="left", padx=1)
            btn.bind("<Button-1>", lambda _, d=delta: self._zoom(d))
        self._scale_label = tk.Label(zoom_frame, text="100%", bg=BG_SURFACE,
                                     fg=FG_MUTED, font=("Consolas", 8), width=4)
        self._scale_label.pack(side="left", padx=(4, 0))

        tk.Label(bar, text="v1.1.0", bg=BG_SURFACE, fg=FG_MUTED,
                 font=("Consolas", 8), padx=8).pack(side="right")

        # 2-패널 컨테이너
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)

        # ━━━ 좌측 패널 (설정) ━━━━━━━━━━━━━━━━━━━━━━━━━━━
        left = tk.Frame(body, bg=BG, width=420)
        left.pack(side="left", fill="both")
        left.pack_propagate(False)

        P = 12

        # 헤더
        hdr = tk.Frame(left, bg=BG)
        hdr.pack(fill="x", padx=P, pady=(10, 0))
        self._logo_img = self._load_logo()
        if self._logo_img:
            tk.Label(hdr, image=self._logo_img, bg=BG).pack(side="left")
        else:
            tk.Label(hdr, text="🚀", bg=BG, font=("Segoe UI", 18)).pack(side="left")
        hdr_text = tk.Frame(hdr, bg=BG)
        hdr_text.pack(side="left", padx=(8, 0))
        ttk.Label(hdr_text, text="블로그 자동화", style="Title.TLabel").pack(anchor="w")

        # ── 로그인 카드 ──────────────────────────────────
        lc = Card(left, title="네이버 계정", icon="🔐")
        lc.pack(fill="x", padx=P, pady=(8, 0))

        r1 = tk.Frame(lc.content, bg=BG_CARD)
        r1.pack(fill="x")
        self._field(r1, "아이디", "네이버 아이디", 0)
        self.id_entry = self._last_entry
        self._field(r1, "비밀번호", "비밀번호", 1, show_char="●")
        self.pw_entry = self._last_entry

        r2 = tk.Frame(lc.content, bg=BG_CARD)
        r2.pack(fill="x", pady=(6, 0))
        self._field(r2, "블로그 ID", "예: gold_exchange", 0)
        self.blog_entry = self._last_entry

        lc.add_separator()

        opt = tk.Frame(lc.content, bg=BG_CARD)
        opt.pack(fill="x")
        self.save_cred_var = tk.BooleanVar(value=True)
        self._toggle(opt, "정보 저장", self.save_cred_var, "left")
        self.auto_publish_var = tk.BooleanVar(value=False)
        self._toggle(opt, "자동 발행", self.auto_publish_var, "right")

        # ── 시트 카드 ────────────────────────────────────
        sc = Card(left, title="구글 시트", icon="📊")
        sc.pack(fill="x", padx=P, pady=(6, 0))

        url_row = tk.Frame(sc.content, bg=BG_CARD)
        url_row.pack(fill="x")
        self.sheet_url_entry = PlaceholderEntry(
            url_row, placeholder="https://docs.google.com/spreadsheets/d/..."
        )
        self.sheet_url_entry.pack(fill="x", ipady=4)

        self.fetch_btn = ttk.Button(
            sc.content, text="📥  데이터 불러오기",
            style="Secondary.TButton", command=self._on_fetch_sheet,
        )
        self.fetch_btn.pack(fill="x", pady=(6, 0))

        # ── 데이터 카드 ──────────────────────────────────
        dc = Card(left, title="데이터 선택", icon="📋")
        dc.pack(fill="x", padx=P, pady=(6, 0))

        lf = tk.Frame(dc.content, bg=BG_CARD)
        lf.pack(fill="x")
        self.post_listbox = tk.Listbox(
            lf, bg=BG_INPUT, fg=FG, font=("Consolas", 9),
            selectbackground=ACCENT, selectforeground="#11111b",
            relief="flat", highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT, height=5, activestyle="none",
        )
        self.post_listbox.pack(side="left", fill="x", expand=True)
        sb = tk.Scrollbar(lf, command=self.post_listbox.yview)
        sb.pack(side="right", fill="y")
        self.post_listbox.config(yscrollcommand=sb.set)
        self.post_listbox.bind("<<ListboxSelect>>", self._on_post_select)



        # ── 실행/중지 버튼 ──────────────────────────────
        btn_frame = tk.Frame(left, bg=BG)
        btn_frame.pack(fill="x", padx=P, pady=(10, 12), side="bottom")

        self.run_btn = ttk.Button(
            btn_frame, text="▶  자동화 시작",
            style="Accent.TButton", command=self._on_start,
        )
        self.run_btn.pack(fill="x")

        sub_row = tk.Frame(btn_frame, bg=BG)
        sub_row.pack(fill="x", pady=(6, 0))

        self.stop_btn = ttk.Button(
            sub_row, text="⏹  중지",
            style="Stop.TButton", command=self._on_stop,
        )
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.stop_btn.state(["disabled"])

        self.quit_btn = ttk.Button(
            sub_row, text="✕  종료",
            style="Quit.TButton", command=self._on_close,
        )
        self.quit_btn.pack(side="left", fill="x", expand=True, padx=(3, 0))

        # ━━━ 구분선 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        tk.Frame(body, bg=BORDER, width=1).pack(side="left", fill="y")

        # ━━━ 우측 패널 (진행 상황) ━━━━━━━━━━━━━━━━━━━━━━
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        RP = 16

        # 우측 상단: 상태 배너
        self.banner = StatusBanner(right)
        self.banner.pack(fill="x", padx=RP, pady=(16, 0))
        self.banner.set_state("idle", "준비 완료", "설정을 완료하고 자동화를 시작하세요")

        # 우측 중앙: 미리보기 / 진행 단계 전환 영역
        self._right_mid_wrap = tk.Frame(right, bg=BG)
        self._right_mid_wrap.pack(fill="both", expand=True, padx=RP, pady=(10, 0))

        # 전환 탭 바
        self._view_bar = tk.Frame(self._right_mid_wrap, bg=BG_SURFACE)
        self._view_bar.pack(fill="x")
        self._view_tabs: list[tk.Label] = []
        for i, name in enumerate(["📋 미리보기", "📍 진행 단계"]):
            btn = tk.Label(
                self._view_bar, text=name, bg=BG_SURFACE, fg=FG_MUTED,
                font=("Segoe UI", 9, "bold"), padx=14, pady=6, cursor="hand2",
            )
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda _, idx=i: (
                self._show_preview() if idx == 0 else self._show_progress()
            ))
            self._view_tabs.append(btn)

        self._right_mid = tk.Frame(self._right_mid_wrap, bg=BG)
        self._right_mid.pack(fill="both", expand=True)

        # 미리보기 패널
        self.detail_preview = DetailPreview(self._right_mid, thumbnail_var=self.use_thumbnail_var)

        # 진행 단계 패널
        self._progress_panel = tk.Frame(self._right_mid, bg=BG)
        tc = Card(self._progress_panel, title="진행 단계", icon="📍")
        tc.pack(fill="x")
        self.timeline = StepTimeline(tc.content)
        self.timeline.pack(fill="x")
        self.log_panel = LogPanel(self._progress_panel)
        self.log_panel.pack(fill="both", expand=True, pady=(10, 0))

        # 초기: 미리보기 표시
        self.detail_preview.pack(fill="both", expand=True)
        self._showing_progress = False
        self._update_view_tabs()

        self.root.bind("<Return>", lambda _: self._on_start())
        self.root.bind("<Control-MouseWheel>", self._on_ctrl_wheel)
        on_font_scale_change(lambda s: self.root.after(0, self._apply_scale))

    # ── 헬퍼 ─────────────────────────────────────────────

    def _field(self, parent, label, placeholder, col, show_char=""):
        f = tk.Frame(parent, bg=BG_CARD)
        f.pack(side="left", fill="x", expand=True, padx=(0 if col == 0 else 6, 0))
        tk.Label(f, text=label, bg=BG_CARD, fg=FG_MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w")
        entry = PlaceholderEntry(f, placeholder=placeholder, show_char=show_char)
        entry.pack(fill="x", ipady=5)
        self._last_entry = entry

    def _toggle(self, parent, label, var, side):
        f = tk.Frame(parent, bg=BG_CARD)
        f.pack(side=side)
        ToggleSwitch(f, variable=var).pack(side="left")
        lbl = tk.Label(f, text=label, bg=BG_CARD, fg=FG_DIM,
                       font=("Segoe UI", 9), cursor="hand2")
        lbl.pack(side="left", padx=(6, 14))
        lbl.bind("<Button-1>", lambda _: var.set(not var.get()))

    # ── 저장/로드 ────────────────────────────────────────

    def _load_saved(self):
        creds = load_credentials()
        if creds:
            self.id_entry.set_value(creds.get("id", ""))
            self.pw_entry.set_value(creds.get("pw", ""))
            if creds.get("blog_id"):
                self.blog_entry.set_value(creds["blog_id"])
            if creds.get("sheet_url"):
                self.sheet_url_entry.set_value(creds["sheet_url"])
            self._log("💾 저장된 설정을 불러왔습니다", "info")

    def _save_all(self):
        save_credentials(
            naver_id=self.id_entry.get_value().strip(),
            naver_pw=self.pw_entry.get_value().strip(),
            blog_id=self.blog_entry.get_value().strip(),
            sheet_url=self.sheet_url_entry.get_value().strip(),
        )

    # ── 상태/로그 ────────────────────────────────────────

    def _set_status(self, text: str):
        self.status_var.set(text)

    def _log(self, text: str, tag: str = "msg"):
        self.log_panel.append(text, tag)

    def _status_cb(self, text: str, level: str = "info"):
        tag = LEVEL_TAGS.get(level, "msg")
        self.root.after(0, lambda: (self._set_status(text), self._log(text, tag)))

    def _set_running(self, running: bool):
        self._running = running
        if running:
            self.run_btn.state(["disabled"])
            self.run_btn.configure(text="⏳  진행 중...")
            self.stop_btn.state(["!disabled"])
            self.fetch_btn.state(["disabled"])
            self.progress.pulse()
            self.banner.set_state("running", "자동화 진행 중", "브라우저를 조작하지 마세요")
        else:
            self.run_btn.configure(text="▶  자동화 시작")
            self.run_btn.state(["!disabled"])
            self.stop_btn.state(["disabled"])
            self.fetch_btn.state(["!disabled"])
            self.progress.stop_pulse()

    # ── 구글 시트 ────────────────────────────────────────

    def _on_fetch_sheet(self):
        url = self.sheet_url_entry.get_value().strip()
        if not url or "docs.google.com" not in url:
            messagebox.showwarning("입력 오류", "올바른 구글 시트 URL을 입력하세요.")
            return

        self.fetch_btn.state(["disabled"])
        self._log("📊 시트 데이터를 불러오는 중...", "info")
        self._set_status("시트 데이터 불러오는 중...")

        def worker():
            try:
                posts = fetch_posts(url)
                self.root.after(0, lambda: self._on_sheet_loaded(posts))
            except Exception as e:
                logger.exception("시트 로드 실패")
                self.root.after(0, lambda: (
                    self._log(f"❌ 시트 로드 실패: {e}", "error"),
                    self._set_status("시트 로드 실패"),
                    self.fetch_btn.state(["!disabled"]),
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _on_sheet_loaded(self, posts: list[BlogPostData]):
        self.posts = posts
        self.post_listbox.delete(0, "end")
        for p in posts:
            self.post_listbox.insert("end", p.display_label)

        self.fetch_btn.state(["!disabled"])
        self._log(f"✅ {len(posts)}개 데이터를 불러왔습니다", "success")
        self._set_status(f"시트 데이터 {len(posts)}개 로드 완료")

        if self.save_cred_var.get():
            self._save_all()

    def _on_post_select(self, _):
        sel = self.post_listbox.curselection()
        if not sel:
            return
        post = self.posts[sel[0]]
        self.selected_post = post
        self.detail_preview.set_post(post)
        self._show_preview()

    # ── 자동화 체인 ──────────────────────────────────────

    def _on_start(self):
        if self._running:
            return

        nid = self.id_entry.get_value().strip()
        npw = self.pw_entry.get_value().strip()
        bid = self.blog_entry.get_value().strip()

        if not nid or not npw or not bid:
            messagebox.showwarning("입력 오류", "아이디, 비밀번호, 블로그 ID를 모두 입력하세요.")
            return
        if not self.selected_post:
            messagebox.showwarning("입력 오류", "시트 데이터를 불러온 후 작성할 항목을 선택하세요.")
            return

        self._stop_event.clear()
        set_stop_event(self._stop_event)
        self._set_running(True)
        self._show_progress()
        self.log_panel.clear()
        self.timeline.set_step(0)
        self.progress.set_progress(0)
        self._log("🚀 자동화를 시작합니다", "info")
        self._log("⚠️ 작업이 완료될 때까지 브라우저를 조작하지 마세요!", "warn")

        if self.save_cred_var.get():
            self._save_all()

        def worker():
            result: LoginResult = login(nid, npw, self._status_cb)
            self.root.after(0, lambda: self._after_login(result, bid))

        threading.Thread(target=worker, daemon=True).start()

    def _is_stopped(self) -> bool:
        return self._stop_event.is_set()

    def _after_login(self, result: LoginResult, blog_id: str):
        if self._is_stopped():
            return
        if not result.success:
            self._fail(0)
            return
        self.driver = result.driver
        self._step(1)
        self._bring_to_front()

        def w():
            ok = navigate_to_write(self.driver, blog_id, self._status_cb)
            self.root.after(0, lambda: self._after_navigate(ok))
        threading.Thread(target=w, daemon=True).start()

    def _after_navigate(self, ok: bool):
        if self._is_stopped():
            return
        if not ok:
            self._fail(1)
            return
        self._step(2)

        def w():
            ok = apply_template(self.driver, self._status_cb)
            self.root.after(0, lambda: self._after_template(ok))
        threading.Thread(target=w, daemon=True).start()

    def _after_template(self, ok: bool):
        if self._is_stopped():
            return
        if not ok:
            self._fail(3)
            return
        self._step(4)

        # 썸네일 사용 ON이면 이미지 삽입 후 데이터 입력
        if self.use_thumbnail_var.get():
            def w():
                thumb_path = self._ensure_thumbnail()
                if thumb_path:
                    ok = insert_thumbnail(self.driver, str(thumb_path), self._status_cb)
                else:
                    self._status_cb("⚠️ 썸네일 생성 실패, 생략합니다", "warn")
                    ok = True  # 썸네일 실패해도 계속 진행
                self.root.after(0, lambda: self._after_thumbnail(ok))
            threading.Thread(target=w, daemon=True).start()
        else:
            self._after_thumbnail(True)

    def _ensure_thumbnail(self) -> Path | None:
        """output.png가 있으면 재사용, 없으면 자동 생성"""
        from core.thumbnail import create_thumbnail, _split_title, _pick_random_background, OUTPUT_DIR
        output = OUTPUT_DIR / "output.png"
        if output.exists():
            self._status_cb("🖼 기존 썸네일을 사용합니다", "info")
            return output
        try:
            self._status_cb("🖼 썸네일을 자동 생성합니다", "info")
            title = self.selected_post.section2_title or ""
            l1, l2 = _split_title(title)
            if not l1:
                l1 = self.selected_post.section1_title or "썸네일"
            bg = str(_pick_random_background())
            return create_thumbnail(bg, l1, l2, date_label=self.selected_post.date or "")
        except Exception as e:
            logger.exception("썸네일 자동 생성 실패")
            return None

    def _after_thumbnail(self, ok: bool):
        if self._is_stopped():
            return
        # 썸네일 실패해도 데이터 입력은 계속 진행
        def w():
            ok = fill_post(self.driver, self.selected_post, self._status_cb)
            self.root.after(0, lambda: self._after_fill(ok))
        threading.Thread(target=w, daemon=True).start()

    def _after_fill(self, ok: bool):
        if self._is_stopped():
            return
        if not ok:
            self._fail(4)
            return
        self._step(5)

        if self.auto_publish_var.get():
            def w():
                ok = publish_post(self.driver, self._status_cb)
                self.root.after(0, lambda: self._after_publish(ok))
            threading.Thread(target=w, daemon=True).start()
        else:
            self._set_running(False)
            self.progress.set_progress(5 / TOTAL_STEPS)
            self.banner.set_state("success", "작성 완료", "자동 발행이 꺼져 있어 직접 발행해주세요")
            self._log("✅ 블로그 글 작성 완료 — 직접 발행해주세요", "success")

    def _after_publish(self, ok: bool):
        if self._is_stopped():
            return
        if not ok:
            self._fail(5)
            return
        self._set_running(False)
        self.timeline.set_step(6)
        self.progress.set_progress(1.0)
        self.banner.set_state("success", "발행 완료! 🎉", "블로그 글이 성공적으로 발행되었습니다")
        self._log("🎉 블로그 글 발행 완료!", "success")

    # ── 공통 ─────────────────────────────────────────────

    def _step(self, idx: int):
        self.timeline.set_step(idx)
        self.progress.set_progress(idx / TOTAL_STEPS)

    def _fail(self, idx: int):
        self._set_running(False)
        self.timeline.set_step(idx, error=True)
        self.banner.set_state("error", "자동화 실패",
                              f"{StepTimeline.STEPS[idx][0]} 단계에서 오류가 발생했습니다")

    # ── 중지 / 종료 ──────────────────────────────────────

    def _on_stop(self):
        if not self._running:
            return
        self._stop_event.set()
        # 즉시 UI 상태 전환 (지연 없이)
        self._set_running(False)
        self.progress.set_progress(0)
        self.banner.set_state("warn", "중지 중...", "브라우저를 강제 종료하고 있습니다")
        self._log("⏹ 강제 중지 중...", "warn")

        def force():
            drv = self.driver
            self.driver = None
            if drv:
                try:
                    pid = drv.service.process.pid
                    drv.quit()
                except Exception:
                    pass
                try:
                    import subprocess
                    subprocess.run(
                        ['taskkill', '/F', '/T', '/PID', str(pid)],
                        capture_output=True, timeout=5,
                    )
                except Exception:
                    pass
            self.root.after(0, lambda: (
                self.banner.set_state("warn", "중지됨", "사용자에 의해 자동화가 강제 중지되었습니다"),
                self._log("⏹ 자동화가 강제 중지되었습니다", "warn"),
            ))

        threading.Thread(target=force, daemon=True).start()

    def _cleanup_driver(self):
        if self.driver:
            try:
                self.driver.quit()
                logger.info("브라우저 종료 완료")
            except Exception:
                logger.warning("브라우저 종료 중 오류", exc_info=True)
            finally:
                self.driver = None

    def _on_close(self):
        if self._running:
            if not messagebox.askokcancel(
                "종료 확인", "자동화가 진행 중입니다. 종료하시겠습니까?"
            ):
                return
            self._stop_event.set()
        self._cleanup_driver()
        self.root.destroy()

    def _bring_to_front(self):
        """\ubd0c\ub77c\uc6b0\uc800 \ub4a4\uc5d0 \uac00\ub824\uc9c4 \ud504\ub85c\uadf8\ub7a8 \ucc3d\uc744 \ub2e4\uc2dc \uc55e\uc73c\ub85c \ub744\uc6b0\uace0 \uacbd\uace0 \ud45c\uc2dc"""
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        self.banner.set_state("warn", "⚠️  작업 중 — 조작 금지",
                              "자동화가 완료될 때까지 브라우저를 건드리지 마세요!")
        self._log("⚠️ 브라우저가 실행되었습니다 — 작업 완료까지 조작하지 마세요!", "warn")

    def _show_preview(self):
        if self._showing_progress:
            self._progress_panel.pack_forget()
            self.detail_preview.pack(fill="both", expand=True)
            self._showing_progress = False
            self._update_view_tabs()

    def _show_progress(self):
        if not self._showing_progress:
            self.detail_preview.pack_forget()
            self._progress_panel.pack(fill="both", expand=True)
            self._showing_progress = True
            self._update_view_tabs()

    def _update_view_tabs(self):
        active = 1 if self._showing_progress else 0
        for i, btn in enumerate(self._view_tabs):
            if i == active:
                btn.configure(bg=BG_CARD, fg=ACCENT)
            else:
                btn.configure(bg=BG_SURFACE, fg=FG_MUTED)

    # ── 글자 크기 ────────────────────────────────────────

    def _zoom(self, delta: float):
        set_font_scale(get_font_scale() + delta)

    def _on_ctrl_wheel(self, e):
        self._zoom(0.05 if e.delta > 0 else -0.05)

    def _apply_scale(self):
        pct = round(get_font_scale() * 100)
        self._scale_label.configure(text=f"{pct}%")

    # ── 실행 ─────────────────────────────────────────────

    def run(self):
        self.root.mainloop()
