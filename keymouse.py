#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
键盘模拟鼠标工具
════════════════════════════════════════
  · 有鼠标模式/滚轮模式
  · 可视化 GUI：实时显示当前模式
  · 所有按键均可在界面内「录制」自定义
  · 移动步长、加速延迟、加速倍数、滚动行数均可调节
  · 配置自动保存到 km_config.json
依赖安装：
  pip install keyboard pyautogui
"""

import os
import sys
import json
import platform
import threading
import time
import tkinter as tk
from tkinter import ttk

import pyautogui
import keyboard

pyautogui.FAILSAFE = False
pyautogui.PAUSE    = 0

# ──────────────────────────── 常量 ────────────────────────────

CONFIG_FILE = "km_config.json"

DEFAULTS: dict = {
    "hotkey_mouse":  "ctrl+alt+m",
    "hotkey_scroll": "ctrl+alt+s",
    "move_up":       "up",
    "move_down":     "down",
    "move_left":     "left",
    "move_right":    "right",
    "click_l":       "enter",
    "click_r":       "space",
    "dbl_click":     "tab",
    "scroll_up":     "up",
    "scroll_down":   "down",
    "scroll_left":   "left",
    "scroll_right":  "right",
    "exit_mode":     "esc",
    "step_px":       20,
    "accel_delay":   0.3,
    "accel_factor":  3,
    "scroll_lines":  3,
}

LABELS: dict = {
    "hotkey_mouse":  "开启/关闭 鼠标模式",
    "hotkey_scroll": "开启/关闭 滚轮模式",
    "move_up":       "向上移动",
    "move_down":     "向下移动",
    "move_left":     "向左移动",
    "move_right":    "向右移动",
    "click_l":       "左键单击",
    "click_r":       "右键单击",
    "dbl_click":     "左键双击",
    "scroll_up":     "向上滚动",
    "scroll_down":   "向下滚动",
    "scroll_left":   "向左滚动",
    "scroll_right":  "向右滚动",
    "exit_mode":     "退出当前模式",
}

KEY_SECTIONS = [
    ("🌐  全局快捷键", ["hotkey_mouse", "hotkey_scroll"]),
    ("🖱  鼠标移动模式", ["move_up", "move_down", "move_left", "move_right",
                          "click_l", "click_r", "dbl_click"]),
    ("📜  滚轮模式",     ["scroll_up", "scroll_down", "scroll_left", "scroll_right"]),
    ("⚙  通用",         ["exit_mode"]),
]

MOD_MAP: dict = {
    "ctrl":        "ctrl",
    "left ctrl":   "ctrl",
    "right ctrl":  "ctrl",
    "alt":         "alt",
    "left alt":    "alt",
    "right alt":   "alt",
    "shift":       "shift",
    "left shift":  "shift",
    "right shift": "shift",
}

# ── 颜色主题 ──────────────────────────────────────────────────
BG     = "#0f0e17"
PANEL  = "#16213e"
CARD   = "#1a2744"
ACC    = "#4a3f6b"
BTN    = "#1e3a5f"
BTN_H  = "#2a4f7c"
C_MOUSE  = "#00d4aa"
C_SCROLL = "#f5a623"
C_INACT  = "#4a5568"
TEXT   = "#e8eaf6"
SUB    = "#8892a4"

_FONT = "Microsoft YaHei" if platform.system() == "Windows" else "Helvetica"

def _f(size: int, bold: bool = False) -> tuple:
    return (_FONT, size, "bold") if bold else (_FONT, size)


# ──────────────────────────── 主程序 ──────────────────────────

class App:
    INACTIVE = 0
    MOUSE    = 1
    SCROLL   = 2

    def __init__(self) -> None:
        self.cfg         = self._load_cfg()
        self.mode        = self.INACTIVE
        self._pressed    : set = set()   # 当前按下的方向键（内部名 up/down/left/right）
        self._mods       : set = set()   # 当前按下的修饰键
        self._hook               = None  # suppress=True 钩子
        self._passthru   : set = set()   # 防递归标记
        self._move_lock          = threading.Lock()
        self._move_thread        = None
        self._gh_handles : list = []     # 全局热键句柄

        self._build_gui()
        self._reg_hotkeys()

    # ═══════════════════════════ 配置 ═══════════════════════════

    def _load_cfg(self) -> dict:
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULTS.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            return dict(DEFAULTS)

    def _save_cfg(self) -> None:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ═══════════════════════════ GUI ════════════════════════════

    def _build_gui(self) -> None:
        root = tk.Tk()
        root.title("键盘鼠标工具 v3")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root = root

        # ── 顶栏 ──────────────────────────────────────────────
        hdr = tk.Frame(root, bg=ACC, pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⌨  键盘鼠标工具  v3",
                 font=_f(15, True), fg=TEXT, bg=ACC).pack()

        # ── 状态条 ────────────────────────────────────────────
        sf = tk.Frame(root, bg=PANEL, pady=10)
        sf.pack(fill="x")
        self._dot_cv = tk.Canvas(sf, width=18, height=18,
                                 bg=PANEL, highlightthickness=0)
        self._dot_cv.pack(side="left", padx=(18, 6))
        self._dot = self._dot_cv.create_oval(1, 1, 17, 17,
                                             fill=C_INACT, outline="")
        self._sv = tk.StringVar(value="  未激活 — 点击按钮或按快捷键启动")
        tk.Label(sf, textvariable=self._sv, font=_f(11, True),
                 fg=TEXT, bg=PANEL).pack(side="left")

        # ── 模式按钮 ──────────────────────────────────────────
        bf = tk.Frame(root, bg=BG, pady=10)
        bf.pack(fill="x", padx=16)
        self._mb = self._mode_btn(bf, "🖱  鼠标模式  Ctrl+Alt+M",
                                  lambda: self._toggle(self.MOUSE), C_MOUSE)
        self._mb.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self._sb = self._mode_btn(bf, "📜  滚轮模式  Ctrl+Alt+S",
                                  lambda: self._toggle(self.SCROLL), C_SCROLL)
        self._sb.pack(side="left", expand=True, fill="x")

        # ── Notebook ──────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook",       background=BG,    borderwidth=0)
        style.configure("TNotebook.Tab",   background=BTN,   foreground=SUB,
                        padding=[14, 6],   font=_f(10))
        style.map("TNotebook.Tab",
                  background=[("selected", ACC)],
                  foreground=[("selected", TEXT)])

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=12, pady=6)

        kf = tk.Frame(nb, bg=BG);     nb.add(kf, text="  按键设置  ")
        pf = tk.Frame(nb, bg=BG);     nb.add(pf, text="  参数设置  ")
        hf = tk.Frame(nb, bg=BG);     nb.add(hf, text="  帮助  ")

        self._build_keys_tab(kf)
        self._build_params_tab(pf)
        self._build_help_tab(hf)

        # ── 底栏 ──────────────────────────────────────────────
        ft = tk.Frame(root, bg=PANEL, pady=6)
        ft.pack(fill="x")
        tk.Label(ft, text="Ctrl+C 可在任意时刻退出程序 · 建议以管理员身份运行",
                 font=_f(9), fg=SUB, bg=PANEL).pack()

        root.update_idletasks()
        w = max(root.winfo_reqwidth(), 500)
        h = root.winfo_reqheight()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _mode_btn(self, parent, text, cmd, active_color) -> tk.Button:
        btn = tk.Button(parent, text=text, command=cmd,
                        font=_f(10, True), fg=TEXT, bg=BTN,
                        activebackground=active_color, activeforeground="#000",
                        relief="flat", cursor="hand2", pady=10, bd=0)
        btn.bind("<Enter>", lambda _: btn.configure(bg=BTN_H))
        btn.bind("<Leave>", lambda _: self._refresh_btn_color(btn))
        return btn

    # ── 按键设置 Tab ──────────────────────────────────────────

    def _build_keys_tab(self, parent) -> None:
        cv = tk.Canvas(parent, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=BG)
        inner.bind("<Configure>",
                   lambda _: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=inner, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        cv.bind_all("<MouseWheel>",
                    lambda e: cv.yview_scroll(-1*(e.delta//120), "units"))

        self._kv: dict = {}   # config_key → StringVar

        for sec_name, keys in KEY_SECTIONS:
            hdr = tk.Frame(inner, bg=ACC, pady=5)
            hdr.pack(fill="x", padx=8, pady=(10, 0))
            tk.Label(hdr, text=f"  {sec_name}",
                     font=_f(10, True), fg=TEXT, bg=ACC).pack(side="left")

            for key in keys:
                row = tk.Frame(inner, bg=CARD, pady=7)
                row.pack(fill="x", padx=8, pady=1)

                tk.Label(row, text=LABELS.get(key, key), font=_f(10),
                         fg=TEXT, bg=CARD, width=16, anchor="w"
                         ).pack(side="left", padx=(12, 6))

                var = tk.StringVar(value=self.cfg.get(key, DEFAULTS.get(key, "")))
                self._kv[key] = var

                tk.Label(row, textvariable=var, font=("Consolas", 10, "bold"),
                         fg=TEXT, bg=BTN, padx=10, pady=3
                         ).pack(side="left", padx=4)

                tk.Button(row, text="重置", font=_f(9), fg=SUB, bg=PANEL,
                          relief="flat", cursor="hand2", padx=6, pady=2,
                          command=lambda k=key, v=var: self._reset_key(k, v)
                          ).pack(side="right", padx=(2, 12))

                tk.Button(row, text="录制", font=_f(9), fg=TEXT, bg=ACC,
                          relief="flat", cursor="hand2", padx=6, pady=2,
                          command=lambda k=key, v=var: self._capture_key(k, v)
                          ).pack(side="right", padx=2)

    # ── 参数设置 Tab ──────────────────────────────────────────

    def _build_params_tab(self, parent) -> None:
        params = [
            ("移动步长 (像素)",    "step_px",     5,  100, lambda x: int(x),
             lambda v: str(int(v))),
            ("加速触发延迟 (秒)",  "accel_delay", 1,  20,
             lambda x: round(int(x) / 10, 1), lambda v: f"{v:.1f}"),
            ("加速倍数",           "accel_factor",1,  10,  lambda x: int(x),
             lambda v: str(int(v))),
            ("滚动行数",           "scroll_lines",1,  20,  lambda x: int(x),
             lambda v: str(int(v))),
        ]
        for i, (lbl, key, lo, hi, to_cfg, to_disp) in enumerate(params):
            row = tk.Frame(parent, bg=CARD, pady=14)
            row.pack(fill="x", padx=12, pady=(8 if i == 0 else 3, 0))

            tk.Label(row, text=lbl, font=_f(10), fg=TEXT, bg=CARD,
                     width=18, anchor="w").pack(side="left", padx=12)

            raw = self.cfg.get(key, DEFAULTS[key])
            vv = tk.StringVar(value=to_disp(raw))
            tk.Label(row, textvariable=vv, font=("Consolas", 11, "bold"),
                     fg=C_MOUSE, bg=CARD, width=5).pack(side="right", padx=12)

            init = int(raw * 10) if key == "accel_delay" else int(raw)
            slider = tk.Scale(row, from_=lo, to=hi, orient="horizontal",
                              bg=CARD, fg=SUB, troughcolor=ACC,
                              activebackground=C_MOUSE,
                              highlightthickness=0, bd=0, showvalue=False,
                              command=lambda v, k=key, sv=vv, c=to_cfg, d=to_disp:
                                  self._param_change(k, v, sv, c, d))
            slider.set(init)
            slider.pack(side="left", fill="x", expand=True, padx=8)

    # ── 帮助 Tab ──────────────────────────────────────────────

    def _build_help_tab(self, parent) -> None:
        content = (
            "快速上手\n\n"
            "1. 点击「鼠标模式」或按 Ctrl+Alt+M 激活鼠标控制\n"
            "2. 方向键移动光标，长按自动加速\n"
            "3. Enter = 左键单击，Space = 右键单击，Tab = 左键双击\n"
            "4. 按 Esc 或再次按快捷键退出当前模式\n\n"
            "滚轮模式\n\n"
            "1. 点击「滚轮模式」或按 Ctrl+Alt+S 激活\n"
            "2. ↑↓ 控制垂直滚动，←→ 控制水平滚动\n"
            "3. 长按方向键持续滚动\n\n"
            "自定义按键\n\n"
            "点击「按键设置」Tab，再点击对应行的「录制」按钮，\n"
            "然后按下你想要的按键（支持 Ctrl/Alt/Shift 组合键）。\n"
            "「重置」按钮恢复默认值。设置自动保存。\n\n"
            "注意事项\n\n"
            "· 建议以管理员身份运行，否则某些程序内快捷键无效\n"
            "· 不支持在 IDLE 中运行\n"
            "· Ctrl+C 或关闭窗口均可退出程序\n"
            "· 水平滚动需要应用程序支持"
        )
        t = tk.Text(parent, bg=PANEL, fg=TEXT, font=_f(10),
                    padx=18, pady=14, relief="flat", wrap="word",
                    state="disabled", height=16)
        t.pack(fill="both", expand=True, padx=8, pady=8)
        t.configure(state="normal")
        t.insert("1.0", content)
        t.configure(state="disabled")

    # ═══════════════════════════ 模式控制 ══════════════════════

    def _toggle(self, target: int) -> None:
        """切换到目标模式；若已在该模式则退出。"""
        if self.mode == target:
            self._deactivate()
        else:
            if self.mode != self.INACTIVE:
                self._deactivate()
            self._activate(target)

    def _activate(self, mode: int) -> None:
        self.mode = mode
        self._mods.clear()
        self._passthru.clear()
        self._hook = keyboard.hook(self._handler, suppress=True)
        self.root.after(0, self._refresh_ui)
        print(f"[激活] {'鼠标模式' if mode == self.MOUSE else '滚轮模式'}")

    def _deactivate(self) -> None:
        """
        ★ Bug 修复核心：
          1. 先 unhook 抑制钩子
          2. 对每一个被追踪的修饰键发送合成 release，消除按键粘连
          3. 清理所有临时状态
        """
        if self._hook:
            keyboard.unhook(self._hook)
            self._hook = None

        # ── 释放被追踪的修饰键，防止粘连 ─────────────────────
        for mod in list(self._mods):
            try:
                keyboard.release(mod)
            except Exception:
                pass
        self._mods.clear()
        self._passthru.clear()

        with self._move_lock:
            self._pressed.clear()

        self.mode = self.INACTIVE
        self.root.after(0, self._refresh_ui)
        print("[停用] 已退出模式")

    # ── UI 刷新 ───────────────────────────────────────────────

    def _refresh_ui(self) -> None:
        if self.mode == self.MOUSE:
            color, text = C_MOUSE, "🖱  鼠标模式  已激活"
        elif self.mode == self.SCROLL:
            color, text = C_SCROLL, "📜  滚轮模式  已激活"
        else:
            color, text = C_INACT,  "  未激活 — 点击按钮或按快捷键启动"
        self._dot_cv.itemconfig(self._dot, fill=color)
        self._sv.set(f"  {text}")
        self._refresh_btn_color(self._mb)
        self._refresh_btn_color(self._sb)

    def _refresh_btn_color(self, btn: tk.Button) -> None:
        if btn is self._mb:
            btn.configure(bg=C_MOUSE if self.mode == self.MOUSE else BTN,
                          fg="#000" if self.mode == self.MOUSE else TEXT)
        else:
            btn.configure(bg=C_SCROLL if self.mode == self.SCROLL else BTN,
                          fg="#000" if self.mode == self.SCROLL else TEXT)

    # ═══════════════════════════ 键盘钩子 ══════════════════════

    def _inject(self, ev: keyboard.KeyboardEvent) -> None:
        """把事件重新注入系统，同时用 _passthru 防止递归。"""
        sig = (ev.scan_code, ev.event_type)
        self._passthru.add(sig)
        try:
            if ev.event_type == keyboard.KEY_DOWN:
                keyboard.press(ev.scan_code)
            else:
                keyboard.release(ev.scan_code)
        except Exception:
            self._passthru.discard(sig)

    def _matches(self, hotkey_str: str, key: str) -> bool:
        """检查当前按键是否匹配热键字符串（含修饰键状态）。"""
        parts    = hotkey_str.lower().split("+")
        mods_req = set(p for p in parts if p in ("ctrl", "alt", "shift", "win"))
        non_mod  = [p for p in parts if p not in ("ctrl", "alt", "shift", "win")]
        return (mods_req == self._mods and
                len(non_mod) == 1 and non_mod[0] == key)

    def _handler(self, ev: keyboard.KeyboardEvent) -> None:
        sig   = (ev.scan_code, ev.event_type)
        if sig in self._passthru:
            self._passthru.discard(sig)
            return

        key   = (ev.name or "").lower()
        etype = ev.event_type

        # ── 追踪修饰键，透传给系统 ────────────────────────────
        if key in MOD_MAP:
            norm = MOD_MAP[key]
            if etype == keyboard.KEY_DOWN:
                self._mods.add(norm)
            else:
                self._mods.discard(norm)
            self._inject(ev)
            return

        # ── Ctrl+C：退出程序 ──────────────────────────────────
        if key == "c" and etype == keyboard.KEY_DOWN and "ctrl" in self._mods:
            self.root.after(0, self._on_close)
            return

        # ── 在钩子内检测全局热键（防止 suppress 阻断全局热键） ─
        if etype == keyboard.KEY_DOWN:
            if self._matches(self.cfg.get("hotkey_mouse",  "ctrl+alt+m"), key):
                self.root.after(0, lambda: self._toggle(self.MOUSE))
                return
            if self._matches(self.cfg.get("hotkey_scroll", "ctrl+alt+s"), key):
                self.root.after(0, lambda: self._toggle(self.SCROLL))
                return

        # ── 分发到对应模式处理器 ──────────────────────────────
        if self.mode == self.MOUSE:
            self._mouse_handler(ev, key, etype)
        elif self.mode == self.SCROLL:
            self._scroll_handler(ev, key, etype)
        else:
            self._inject(ev)

    # ── 鼠标模式处理 ──────────────────────────────────────────

    def _mouse_handler(self, ev, key: str, etype: str) -> None:
        c = self.cfg
        dir_map = {
            c["move_up"]:    "up",
            c["move_down"]:  "down",
            c["move_left"]:  "left",
            c["move_right"]: "right",
        }
        if key in dir_map:
            d = dir_map[key]
            if etype == keyboard.KEY_DOWN:
                with self._move_lock:
                    self._pressed.add(d)
                self._ensure_thread("move")
            else:
                with self._move_lock:
                    self._pressed.discard(d)
            return

        if etype == keyboard.KEY_DOWN:
            if key == c.get("exit_mode", "esc"):
                self.root.after(0, self._deactivate); return
            if key == c.get("click_l", "enter"):
                threading.Thread(target=pyautogui.click,
                                 kwargs={"button": "left"}, daemon=True).start(); return
            if key == c.get("click_r", "space"):
                threading.Thread(target=pyautogui.click,
                                 kwargs={"button": "right"}, daemon=True).start(); return
            if key == c.get("dbl_click", "tab"):
                threading.Thread(target=pyautogui.doubleClick,
                                 daemon=True).start(); return
        self._inject(ev)

    # ── 滚轮模式处理 ──────────────────────────────────────────

    def _scroll_handler(self, ev, key: str, etype: str) -> None:
        c = self.cfg
        dir_map = {
            c["scroll_up"]:    "up",
            c["scroll_down"]:  "down",
            c["scroll_left"]:  "left",
            c["scroll_right"]: "right",
        }
        if key in dir_map:
            d = dir_map[key]
            if etype == keyboard.KEY_DOWN:
                with self._move_lock:
                    self._pressed.add(d)
                self._ensure_thread("scroll")
            else:
                with self._move_lock:
                    self._pressed.discard(d)
            return

        if etype == keyboard.KEY_DOWN:
            if key == c.get("exit_mode", "esc"):
                self.root.after(0, self._deactivate); return
        self._inject(ev)

    # ── 动作线程 ──────────────────────────────────────────────

    def _ensure_thread(self, action: str) -> None:
        """如果没有活跃的动作线程，启动一个。"""
        if self._move_thread and self._move_thread.is_alive():
            return
        t = threading.Thread(target=self._action_loop,
                             args=(action,), daemon=True)
        self._move_thread = t
        t.start()

    def _action_loop(self, action: str) -> None:
        t0 = time.time()
        while True:
            with self._move_lock:
                keys = set(self._pressed)
            if not keys or self.mode == self.INACTIVE:
                break

            c      = self.cfg
            accel  = (time.time() - t0) > c.get("accel_delay", 0.3)

            if action == "move":
                step = int(c.get("step_px", 20) *
                           (c.get("accel_factor", 3) if accel else 1))
                dx = dy = 0
                if "up"    in keys: dy -= step
                if "down"  in keys: dy += step
                if "left"  in keys: dx -= step
                if "right" in keys: dx += step
                if dx or dy:
                    pyautogui.moveRel(dx, dy)
                time.sleep(0.025)

            elif action == "scroll":
                lines = int(c.get("scroll_lines", 3))
                if "up"    in keys: pyautogui.scroll(lines)
                if "down"  in keys: pyautogui.scroll(-lines)
                if "left"  in keys:
                    try: pyautogui.hscroll(-lines)
                    except Exception: pass
                if "right" in keys:
                    try: pyautogui.hscroll(lines)
                    except Exception: pass
                time.sleep(0.08)

    # ═══════════════════════════ 按键录制 ══════════════════════

    def _capture_key(self, cfg_key: str, var: tk.StringVar) -> None:
        if self.mode != self.INACTIVE:
            # 模式激活中不允许录制，避免冲突
            _toast(self.root, "请先退出当前模式再录制按键")
            return

        self._unreg_hotkeys()   # 录制期间暂时取消全局热键

        dlg = tk.Toplevel(self.root)
        dlg.title("录制按键")
        dlg.configure(bg=PANEL)
        dlg.resizable(False, False)
        dlg.grab_set()

        self.root.update_idletasks()
        px, py = self.root.winfo_x(), self.root.winfo_y()
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        dlg.geometry(f"320x148+{px+(pw-320)//2}+{py+(ph-148)//2}")

        tk.Label(dlg, text="请按下新的按键（支持组合键）",
                 font=_f(11, True), fg=TEXT, bg=PANEL).pack(pady=(20, 10))
        pv = tk.StringVar(value="等待按键...")
        tk.Label(dlg, textvariable=pv, font=("Consolas", 12, "bold"),
                 fg=C_MOUSE, bg=BTN, padx=14, pady=6).pack()
        tk.Label(dlg, text="按 Esc 取消",
                 font=_f(9), fg=SUB, bg=PANEL).pack(pady=8)

        cap_mods : set = set()
        hook_ref : list = [None]

        def _on_key(ev):
            k = (ev.name or "").lower()
            if ev.event_type == keyboard.KEY_DOWN:
                if k in MOD_MAP:
                    cap_mods.add(MOD_MAP[k])
                    preview = "+".join(m for m in ("ctrl","alt","shift") if m in cap_mods)
                    pv.set((preview + "+...") if preview else "...")
                    return
                if k == "esc" and not cap_mods:
                    _finish(None); return
                parts  = [m for m in ("ctrl", "alt", "shift") if m in cap_mods]
                parts.append(k)
                combo  = "+".join(parts)
                pv.set(combo)
                dlg.after(250, lambda: _finish(combo))
            elif ev.event_type == keyboard.KEY_UP:
                if k in MOD_MAP:
                    cap_mods.discard(MOD_MAP[k])

        def _finish(combo):
            if hook_ref[0]:
                try: keyboard.unhook(hook_ref[0])
                except Exception: pass
                hook_ref[0] = None
            if combo:
                self.cfg[cfg_key] = combo
                var.set(combo)
                self._save_cfg()
            try: dlg.destroy()
            except Exception: pass
            self._reg_hotkeys()

        hook_ref[0] = keyboard.hook(_on_key, suppress=False)
        dlg.protocol("WM_DELETE_WINDOW", lambda: _finish(None))

    def _reset_key(self, cfg_key: str, var: tk.StringVar) -> None:
        d = DEFAULTS.get(cfg_key, "")
        self.cfg[cfg_key] = d
        var.set(d)
        self._save_cfg()
        self._reg_hotkeys()

    # ═══════════════════════════ 参数回调 ══════════════════════

    def _param_change(self, key, raw_val, sv, to_cfg, to_disp) -> None:
        try:
            v = to_cfg(raw_val)
            self.cfg[key] = v
            sv.set(to_disp(v))
            self._save_cfg()
        except Exception:
            pass

    # ═══════════════════════════ 全局热键 ══════════════════════

    def _reg_hotkeys(self) -> None:
        self._unreg_hotkeys()
        def safe(hk, fn):
            try:
                h = keyboard.add_hotkey(hk, fn)
                self._gh_handles.append(h)
            except Exception as e:
                print(f"[警告] 热键注册失败 {hk}: {e}")
        safe(self.cfg.get("hotkey_mouse",  "ctrl+alt+m"),
             lambda: self.root.after(0, lambda: self._toggle(self.MOUSE)))
        safe(self.cfg.get("hotkey_scroll", "ctrl+alt+s"),
             lambda: self.root.after(0, lambda: self._toggle(self.SCROLL)))

    def _unreg_hotkeys(self) -> None:
        for h in self._gh_handles:
            try: keyboard.remove_hotkey(h)
            except Exception: pass
        self._gh_handles.clear()

    # ═══════════════════════════ 生命周期 ══════════════════════

    def _on_close(self) -> None:
        self._deactivate()
        self._unreg_hotkeys()
        try: self.root.destroy()
        except Exception: pass
        os._exit(0)

    def run(self) -> None:
        self.root.mainloop()


# ──────────────────────────── 工具函数 ────────────────────────

def _toast(root: tk.Tk, msg: str) -> None:
    dlg = tk.Toplevel(root)
    dlg.overrideredirect(True)
    dlg.attributes("-topmost", True)
    dlg.attributes("-alpha", 0.88)
    tk.Label(dlg, text=f"  {msg}  ", font=_f(12, True),
             fg=TEXT, bg=ACC, padx=16, pady=10).pack()
    dlg.update_idletasks()
    sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
    ww, wh = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
    dlg.geometry(f"+{(sw-ww)//2}+{(sh-wh)//2}")
    dlg.after(2000, dlg.destroy)


# ──────────────────────────── 入口 ────────────────────────────

if __name__ == "__main__":
    print("=" * 52)
    print("  键盘鼠标工具 v3  启动中...")
    print("  ⚠  建议以管理员身份运行")
    print("  ⚠  不支持在 IDLE 中运行")
    print("=" * 52)
    App().run()
