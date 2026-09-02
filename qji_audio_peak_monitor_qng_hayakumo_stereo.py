#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qji Audio Peak Monitor — QNG Edition
====================================
ffmpeg の astats + ametadata=print が書き出すログを tail しながら、
Qji Next Generation (QNG) のホームページ／UIと調和する
ダーク・シネマティックなリアルタイム・ピークモニターです。

機能:
  * リアルタイム Peak Level (dBFS) グラフ
  * しきい値ライン／Threshold Hit 表示
  * 横型 LED ピークメーター
  * Current Peak / Peak Hold
  * 再生時間・監視ウィンドウ・更新間隔などのステータス
  * FFmpeg + CamillaDSP を意識した QNG インフォメーション
  * Qji / QNG のブランド表示

監視対象は従来どおり ffmpeg astats のログです。
--log-glob を変えれば任意の ffmpeg astats パイプラインにも使用できます。

例:
    python3 qji_audio_peak_monitor_qng.py
    python3 qji_audio_peak_monitor_qng.py \
        --log-glob "/tmp/myapp_*.log" --threshold -1.0

必要:
    pip install matplotlib numpy --break-system-packages
"""

import argparse
import bisect
import glob
import os
import time
import re
from collections import deque

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.font_manager as fm
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch


# ─────────────────────────────────────────────
# 日本語フォント
# ─────────────────────────────────────────────
_JP_FONT_CANDIDATES = [
    "Noto Sans CJK JP", "Noto Sans JP", "IPAexGothic", "IPAGothic",
    "IPAPGothic", "TakaoGothic", "TakaoPGothic", "VL PGothic", "VL Gothic",
]
_available = {f.name for f in fm.fontManager.ttflist}
_jp_font = next((name for name in _JP_FONT_CANDIDATES if name in _available), None)
JP_OK = _jp_font is not None

if JP_OK:
    matplotlib.rcParams["font.family"] = _jp_font
matplotlib.rcParams["axes.unicode_minus"] = False


# ─────────────────────────────────────────────
# QNG palette
# ─────────────────────────────────────────────
BG = "#03070d"
PANEL = "#07101a"
PANEL2 = "#091522"
GRID = "#142536"
BORDER = "#1d4058"
TEXT = "#dce8f2"
DIM = "#718596"

BLUE = "#32b9ff"
CYAN = "#63dcff"
GREEN = "#31df8a"
YELLOW = "#f5c84c"
ORANGE = "#ff9b38"
RED = "#ff4d5d"
GOLD = "#f1bf58"
WHITE = "#f4f8fb"

PEAK_RE = re.compile(r"lavfi\.astats\.Overall\.Peak_level=(-?[\d.]+|-inf)")
PEAK_CH_RE = re.compile(r"lavfi\.astats\.(1|2)\.Peak_level=(-?[\d.]+|-inf)")


def led_color(db, threshold_db):
    """QNG-style safety color."""
    if db >= threshold_db:
        return RED
    if db >= threshold_db - 3:
        return ORANGE
    if db >= threshold_db - 9:
        return YELLOW
    return GREEN


def add_panel(ax, face=PANEL, edge=BORDER, lw=0.9):
    ax.set_facecolor(face)
    for spine in ax.spines.values():
        spine.set_color(edge)
        spine.set_linewidth(lw)


def panel_title(ax, title, x=0.035, y=0.92, color=CYAN, size=9.5):
    ax.text(x, y, title, transform=ax.transAxes, color=color,
            fontsize=size, fontweight="medium", va="center", ha="left")


def main():
    ap = argparse.ArgumentParser(
        description="Qji QNG-style ffmpeg astats real-time peak monitor"
    )
    ap.add_argument(
        "--log-glob", default="/tmp/qji_declip_*.log",
        help="監視するログファイルのglobパターン"
    )
    ap.add_argument(
        "--title", default="Qji Audio Peak Monitor",
        help="ウィンドウ/表示タイトル"
    )
    ap.add_argument(
        "--threshold", type=float, default=-0.3,
        help="歪みトリガーのしきい値(dB)"
    )
    ap.add_argument(
        "--window", type=float, default=20.0,
        help="スクロール表示の時間幅(秒)"
    )
    ap.add_argument(
        "--floor", type=float, default=-60.0,
        help="表示する最低レベル(dB)"
    )
    ap.add_argument(
        "--refresh-ms", type=int, default=100,
        help="画面更新間隔(ms)"
    )
    ap.add_argument(
        "--width-scale", type=float, default=0.5,
        help="初期ウィンドウ横幅の倍率(デフォルト0.5 = 半分の幅)"
    )
    ap.add_argument(
        "--height-scale", type=float, default=1.0,
        help="初期ウィンドウ高さの倍率(デフォルト1.0 = 元の高さのまま)"
    )
    ap.add_argument(
        "--no-topmost", action="store_true",
        help="常に最前面表示を無効にする"
    )
    ap.add_argument(
        "--display-delay", type=float, default=0.0,
        help=(
            "実際にスピーカーから音が聞こえるタイミングに合わせて表示を"
            "遅らせる秒数。astatsはffmpegのフィルター処理段階の値を"
            "そのまま記録するため、DSPループバックやALSAバッファなど"
            "下流の遅延分だけ表示が実際の音より早く動いてしまう場合に"
            "指定する(例: 通常再生で1.0、DSP再生で2.5など)。0で無効。"
            "起動後も ← → キーで0.1秒刻み、↑ ↓ キーで0.5秒刻みに"
            "リアルタイム調整できるほか、数字キーを押すと直接入力モードに"
            "入り、続けて数値を入力してEnterで確定できる"
            "(Escでキャンセル、Backspaceで一文字削除、rキーでこの"
            "初期値にリセット)。"
        )
    )
    args = ap.parse_args()

    LOG_GLOB = args.log_glob
    THRESHOLD_DB = args.threshold
    WINDOW_SEC = args.window
    FLOOR_DB = args.floor
    # 矢印キーで実行中にリアルタイム微調整できるよう、単純な定数ではなく
    # ミュータブルな状態(辞書)として持たせる。
    delay_state = {"sec": max(0.0, args.display_delay)}
    CEIL_DB = 2.0
    REFRESH_MS = args.refresh_ms
    PEAK_HOLD_DECAY_DB_PER_SEC = 12.0

    if JP_OK:
        L = dict(
            waiting="信号待機中…  再生を開始してください",
            final="最終出力",
            threshold="しきい値",
            hits="しきい値超え",
            window="監視ウィンドウ",
            update="更新間隔",
            peakhold="ピーク保持",
            now="現在値",
            playing="PLAYING",
            safe="SAFE",
            nominal="NOMINAL",
            high="HIGH",
            critical="CRITICAL",
            source="SOURCE",
            engine="ENGINE",
            mode="MONITOR",
            status="STATUS",
        )
    else:
        L = dict(
            waiting="Waiting for signal... start playback",
            final="Final Output",
            threshold="Threshold",
            hits="Threshold Hits",
            window="Window",
            update="Update",
            peakhold="Peak Hold",
            now="NOW",
            playing="PLAYING",
            safe="SAFE",
            nominal="NOMINAL",
            high="HIGH",
            critical="CRITICAL",
            source="SOURCE",
            engine="ENGINE",
            mode="MONITOR",
            status="STATUS",
        )

    # ─────────────────────────────────────────
    # Data monitor
    # ─────────────────────────────────────────
    class Monitor:
        """Read astats peak metadata, preserving L/R when available."""
        def __init__(self):
            self.times = deque()
            self.values = deque()      # max(L,R), kept for existing panels
            self.values_l = deque()
            self.values_r = deque()
            self.start_time = time.time()
            self.current_log_path = None
            self.file_pos = 0
            self.hit_times = deque()
            self.peak_hold_db = FLOOR_DB
            self.peak_hold_ts = time.time()
            self.last_val = FLOOR_DB
            self.last_l = FLOOR_DB
            self.last_r = FLOOR_DB

        def _find_active_log(self):
            candidates = glob.glob(LOG_GLOB)
            if not candidates:
                return None
            candidates.sort(
                key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0,
                reverse=True
            )
            return candidates[0]

        def _switch_log_if_needed(self):
            latest = self._find_active_log()
            if latest is None:
                # glob が一瞬何もヒットしない(書き手がファイルを
                # リネーム/再作成する瞬間など)ことがあっても、
                # そのたびに表示を全消去してしまわないよう、
                # 前回のログパスを保持したまま様子を見る。
                # (該当ファイルが本当に消えていれば poll() 側の
                # os.path.exists チェックで安全に何もしない)
                return
            if latest != self.current_log_path:
                self.current_log_path = latest
                self.file_pos = 0
                self.times.clear()
                self.values.clear()
                self.values_l.clear()
                self.values_r.clear()
                self.hit_times.clear()
                self.peak_hold_db = FLOOR_DB
                self.start_time = time.time()
                self.last_l = FLOOR_DB
                self.last_r = FLOOR_DB

        @staticmethod
        def _db(raw):
            return FLOOR_DB if raw == "-inf" else max(FLOOR_DB, float(raw))

        def _append_sample(self, l, r, overall, t):
            # If channel metadata exists, use it. Otherwise fall back to Overall.
            if l is None and r is None:
                l = r = overall if overall is not None else FLOOR_DB
            elif l is None:
                l = overall if overall is not None else r
            elif r is None:
                r = overall if overall is not None else l

            l = max(FLOOR_DB, l)
            r = max(FLOOR_DB, r)
            val = max(l, r)

            self.times.append(t)
            self.values.append(val)
            self.values_l.append(l)
            self.values_r.append(r)
            self.last_l = l
            self.last_r = r
            self.last_val = val

            if val > self.peak_hold_db:
                self.peak_hold_db = val
            if val >= THRESHOLD_DB:
                self.hit_times.append(t)

        def delayed_reading(self):
            """--display-delay に応じて、実際にスピーカーから聞こえる
            タイミングに近い過去の読み取り値を返す (l, r, val)。
            astats は ffmpeg のフィルター処理段階の値をそのまま記録する
            ため、DSPループバックやALSAバッファなど下流の遅延がある分、
            最新値をそのまま表示すると音より早く針が動いてしまう。
            そこで履歴 (times/values_l/values_r) の中から
            「今から display_delay 秒前」に最も近いサンプルを探して使う。"""
            if not self.times or delay_state["sec"] <= 0:
                return self.last_l, self.last_r, self.last_val

            now = time.time()
            target_t = (now - self.start_time) - delay_state["sec"]

            if target_t <= self.times[0]:
                # 遅延分の履歴がまだ溜まっていない(再生直後など)。
                # 遅延前の最新値を暫定的に使う。
                return self.last_l, self.last_r, self.last_val

            # times は単調増加なので二分探索で target_t 以下の
            # 最後のインデックスを探す。
            idx = bisect.bisect_right(self.times, target_t) - 1
            idx = max(0, min(idx, len(self.times) - 1))
            return self.values_l[idx], self.values_r[idx], self.values[idx]

        def poll(self):
            self._switch_log_if_needed()
            now = time.time()

            elapsed = now - self.peak_hold_ts
            self.peak_hold_db = max(
                FLOOR_DB,
                self.peak_hold_db -
                PEAK_HOLD_DECAY_DB_PER_SEC * elapsed
            )
            self.peak_hold_ts = now

            if not self.current_log_path or not os.path.exists(self.current_log_path):
                return

            try:
                current_size = os.path.getsize(self.current_log_path)
            except OSError:
                return

            if current_size < self.file_pos:
                # ファイルが同じパスのまま途中で切り詰め/再作成された
                # (例: 書き手が同名ログを再オープンして上書きした場合)。
                # 古い file_pos は EOF より後ろを指してしまっており、
                # そのままだと f.read() が永遠に "" を返し続けて
                # メーターが完全に固まってしまう。先頭から読み直す。
                self.file_pos = 0

            try:
                with open(self.current_log_path, "r", errors="ignore") as f:
                    f.seek(self.file_pos)
                    new_data = f.read()
                    self.file_pos = f.tell()
            except Exception:
                return

            pending_l = None
            pending_r = None
            pending_overall = None
            got_channel = False

            for line in new_data.splitlines():
                cm = PEAK_CH_RE.search(line)
                if cm:
                    ch = cm.group(1)
                    val = self._db(cm.group(2))
                    if ch == "1":
                        pending_l = val
                    else:
                        pending_r = val
                    got_channel = True
                    continue

                om = PEAK_RE.search(line)
                if om:
                    pending_overall = self._db(om.group(1))
                    # astats normally emits channel 1/2 metadata followed by Overall.
                    t = now - self.start_time
                    self._append_sample(pending_l, pending_r, pending_overall, t)
                    pending_l = pending_r = pending_overall = None
                    got_channel = False

            # Some astats configurations may omit Overall; don't lose the last L/R pair.
            if got_channel and (pending_l is not None or pending_r is not None):
                t = now - self.start_time
                self._append_sample(pending_l, pending_r, pending_overall, t)

            cutoff = (now - self.start_time) - WINDOW_SEC - 2.0

            while self.times and self.times[0] < cutoff:
                self.times.popleft()
                self.values.popleft()
                self.values_l.popleft()
                self.values_r.popleft()

            while self.hit_times and self.hit_times[0] < cutoff:
                self.hit_times.popleft()

    mon = Monitor()

    # ─────────────────────────────────────────
    # Figure
    # ─────────────────────────────────────────
    plt.rcParams["figure.facecolor"] = BG
    plt.rcParams["axes.facecolor"] = PANEL
    plt.rcParams["savefig.facecolor"] = BG

    BASE_FIGSIZE = (15.2, 8.4)
    FIGSIZE = (
        BASE_FIGSIZE[0] * args.width_scale,
        BASE_FIGSIZE[1] * args.height_scale
    )
    fig = plt.figure(figsize=FIGSIZE, facecolor=BG)

    try:
        fig.canvas.manager.set_window_title(
            f"Qji — {args.title}"
        )
    except Exception:
        pass

    gs = GridSpec(
        7, 12,
        figure=fig,
        left=0.025, right=0.975,
        top=0.955, bottom=0.055,
        wspace=0.018, hspace=0.12,
        height_ratios=[0.85, 3.8, 0.22, 1.25, 1.55, 0.12, 0.45]
    )

    # Header
    ax_head = fig.add_subplot(gs[0, :])
    ax_head.set_facecolor(BG)
    ax_head.axis("off")

    ax_head.text(
        0.012, 0.63, "Qji",
        transform=ax_head.transAxes,
        color=WHITE, fontsize=31,
        fontweight="light", va="center"
    )
    ax_head.text(
        0.115, 0.70, "A U D I O   P E A K   M O N I T O R",
        transform=ax_head.transAxes,
        color=CYAN, fontsize=11,
        va="center"
    )
    ax_head.text(
        0.115, 0.34, "Real-time Peak Level Monitor for Final Output",
        transform=ax_head.transAxes,
        color=TEXT, fontsize=8.5,
        va="center"
    )

    ax_head.text(
        0.62, 0.68, "Qji Auto De-Clip",
        transform=ax_head.transAxes,
        color=BLUE, fontsize=10
    )
    ax_head.text(
        0.735, 0.68, "Qji Next Generation",
        transform=ax_head.transAxes,
        color=GOLD, fontsize=10
    )
    ax_head.text(
        0.985, 0.30, "POWERED BY  FFmpeg  +  CamillaDSP",
        transform=ax_head.transAxes,
        color=DIM, fontsize=7.5, ha="right"
    )
    delay_readout = ax_head.text(
        0.985, 0.06, "",
        transform=ax_head.transAxes,
        color=GOLD, fontsize=8, ha="right", fontweight="bold",
        animated=True
    )

    # Decorative sound curves
    xcurve = np.linspace(0.78, 0.99, 180)
    for k, alpha in enumerate([0.12, 0.18, 0.28]):
        ycurve = 0.50 + 0.08 * np.sin(
            np.linspace(0, 3.8*np.pi, xcurve.size) + k * 0.7
        ) * (1 - 1.7*(xcurve - 0.78))
        ax_head.plot(
            xcurve, ycurve,
            transform=ax_head.transAxes,
            color=BLUE if k < 2 else GOLD,
            alpha=alpha, lw=0.8
        )

    # Main graph — warm analog stereo VU-style display
    # Inspired by classic illuminated stereo VU meters such as HAYAKUMO FORENO,
    # but drawn as an original QNG interface rather than copying the hardware.
    ax_wave = fig.add_subplot(gs[1, :9])
    add_panel(ax_wave, face="#090b0e", edge="#35404a", lw=1.0)
    ax_wave.set_xticks([])
    ax_wave.set_yticks([])

    panel_title(ax_wave, "STEREO PEAK LEVEL  •  ANALOG VU STYLE")

    # Warm amber meter windows
    ax_l = ax_wave.inset_axes([0.035, 0.14, 0.455, 0.72])
    ax_r = ax_wave.inset_axes([0.510, 0.14, 0.455, 0.72])

    VU_MIN = -40.0
    VU_MAX = 2.0

    def setup_vu(ax, channel_label):
        ax.set_facecolor("#e9a13a")
        ax.set_xlim(-1.15, 1.15)
        ax.set_ylim(-0.18, 1.15)
        ax.set_aspect("equal")
        ax.axis("off")

        # Black inner bezel
        bezel = FancyBboxPatch(
            (-1.12, -0.12), 2.24, 1.20,
            boxstyle="round,pad=0.018,rounding_size=0.045",
            facecolor="#080a0c", edgecolor="#59616a", linewidth=1.0,
            zorder=0
        )
        ax.add_patch(bezel)

        # Illuminated face
        face = FancyBboxPatch(
            (-0.99, -0.015), 1.98, 1.02,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            facecolor="#f1a63d", edgecolor="#24180b", linewidth=1.0,
            zorder=1
        )
        ax.add_patch(face)

        # Soft inner glow bands
        for y, alpha in [(0.05, 0.08), (0.16, 0.045), (0.28, 0.025)]:
            ax.fill_between(
                np.linspace(-0.94, 0.94, 200), y, y + 0.16,
                color="#ffe3a0", alpha=alpha, zorder=2
            )

        # Main scale arc: -40 .. +2 dBFS
        theta = np.linspace(np.deg2rad(138), np.deg2rad(42), 320)
        x = 0.78 * np.cos(theta)
        y = 0.78 * np.sin(theta) + 0.02
        ax.plot(x, y, color="#17110b", linewidth=2.0, zorder=4)

        # Colored danger band near 0 dBFS
        danger = np.linspace(np.deg2rad(58), np.deg2rad(42), 70)
        ax.plot(0.79*np.cos(danger), 0.79*np.sin(danger)+0.02,
                color="#8e1715", linewidth=5.0, alpha=0.75, zorder=4)

        # Ticks and labels
        tick_values = [-40, -30, -20, -15, -10, -7, -5, -3, -2, -1, 0, 1, 2]
        for db in tick_values:
            frac = (db - VU_MIN) / (VU_MAX - VU_MIN)
            ang = np.deg2rad(138 - 96 * frac)
            r0 = 0.68
            r1 = 0.80
            lw = 2.0 if db in (-40, -20, -10, 0, 2) else 1.0
            ax.plot(
                [r0*np.cos(ang), r1*np.cos(ang)],
                [r0*np.sin(ang)+0.02, r1*np.sin(ang)+0.02],
                color="#17110b", linewidth=lw, zorder=5
            )
            ax.text(
                0.57*np.cos(ang), 0.57*np.sin(ang)+0.02,
                f"{db:g}", color="#24180b", fontsize=7.0,
                ha="center", va="center", zorder=6
            )

        ax.text(0, 0.34, channel_label, color="#25180a",
                fontsize=12, fontweight="bold", ha="center", va="center", zorder=7)
        ax.text(0, 0.21, "dBFS", color="#4b2d12",
                fontsize=6.5, ha="center", va="center", zorder=7)

        # Baseline / pivot
        ax.plot([-0.52, 0.52], [-0.08, -0.08], color="#1b120a", lw=1.0, zorder=5)
        ax.add_patch(plt.Circle((0, -0.04), 0.075, facecolor="#24272a",
                                edgecolor="#0b0c0d", linewidth=1.0, zorder=9))
        ax.add_patch(plt.Circle((0, -0.04), 0.025, facecolor="#b8a070",
                                edgecolor="none", zorder=10))

        needle, = ax.plot([0, 0], [-0.04, 0.62],
                          color="#171717", linewidth=2.0, zorder=8,
                          solid_capstyle="round", animated=True)
        needle_tip, = ax.plot([0], [0.62], marker="o", markersize=3.0,
                              color="#171717", zorder=9, animated=True)
        value_text = ax.text(
            0, -0.105, "--.-", color="#e9d7ad", fontsize=7.0,
            ha="center", va="center", zorder=11,
            bbox=dict(boxstyle="round,pad=0.18", facecolor="#111417",
                      edgecolor="#30343a", linewidth=0.6, alpha=0.92),
            animated=True
        )
        return needle, needle_tip, value_text

    needle_l, tip_l, value_l = setup_vu(ax_l, "LEFT")
    needle_r, tip_r, value_r = setup_vu(ax_r, "RIGHT")

    def set_needle(needle, tip, value_text, db):
        db = float(np.clip(db, VU_MIN, VU_MAX))
        frac = (db - VU_MIN) / (VU_MAX - VU_MIN)
        ang = np.deg2rad(138 - 96 * frac)
        x = 0.62 * np.cos(ang)
        y = 0.62 * np.sin(ang) + 0.02
        needle.set_data([0, x], [-0.04, y])
        tip.set_data([x], [y])
        value_text.set_text(f"{db:5.1f}")

    # A small digital safety strip remains inside the main panel.
    threshold_text = ax_wave.text(
        0.975, 0.055,
        f"THRESHOLD  {THRESHOLD_DB:g} dBFS",
        transform=ax_wave.transAxes,
        color=RED, fontsize=7.5,
        ha="right", va="center"
    )
    main_line = None
    glow_lines = []
    state = {"fill": None}
    hit_scatter = None
    # Current peak panel
    ax_now = fig.add_subplot(gs[1, 9:])
    add_panel(ax_now, face="#050b12")
    ax_now.set_xticks([])
    ax_now.set_yticks([])

    panel_title(ax_now, "CURRENT PEAK", y=0.90)

    now_readout = ax_now.text(
        0.07, 0.57, "--.-",
        transform=ax_now.transAxes,
        color=DIM, fontsize=36,
        fontweight="bold",
        va="center", ha="left",
        animated=True
    )
    ax_now.text(
        0.70, 0.57, "dBFS",
        transform=ax_now.transAxes,
        color=DIM, fontsize=10,
        va="center"
    )

    status_badge = FancyBboxPatch(
        (0.07, 0.27), 0.84, 0.105,
        boxstyle="round,pad=0.012,rounding_size=0.025",
        facecolor=BG, edgecolor=BORDER,
        linewidth=0.7
    )
    ax_now.add_patch(status_badge)

    status_dot = ax_now.scatter(
        [0.105], [0.327],
        s=32, color=DIM,
        transform=ax_now.transAxes,
        zorder=4, animated=True
    )
    status_text = ax_now.text(
        0.16, 0.327, "WAITING",
        transform=ax_now.transAxes,
        color=DIM, fontsize=8.5,
        va="center", animated=True
    )

    ax_now.text(
        0.07, 0.12, "THRESHOLD",
        transform=ax_now.transAxes,
        color=DIM, fontsize=7
    )
    threshold_value = ax_now.text(
        0.30, 0.12, f"{THRESHOLD_DB:.1f} dBFS",
        transform=ax_now.transAxes,
        color=TEXT, fontsize=8
    )

    ax_now.text(
        0.62, 0.12, "FLOOR",
        transform=ax_now.transAxes,
        color=DIM, fontsize=7
    )
    ax_now.text(
        0.80, 0.12, f"{FLOOR_DB:.1f} dBFS",
        transform=ax_now.transAxes,
        color=TEXT, fontsize=8
    )

    # Thin separator
    ax_sep = fig.add_subplot(gs[2, :])
    ax_sep.set_facecolor(BG)
    ax_sep.axis("off")

    # Horizontal peak meter
    ax_meter = fig.add_subplot(gs[3, :9])
    add_panel(ax_meter)
    panel_title(ax_meter, "PEAK LEVEL METER  (dBFS)")

    N_SEGMENTS = 34
    seg_edges = np.linspace(FLOOR_DB, CEIL_DB, N_SEGMENTS + 1)
    seg_width = 0.80 / N_SEGMENTS
    meter_patches = []

    for i in range(N_SEGMENTS):
        x = 0.08 + i * seg_width
        center_db = (seg_edges[i] + seg_edges[i+1]) / 2
        color = led_color(center_db, THRESHOLD_DB)

        patch = FancyBboxPatch(
            (x, 0.39), seg_width * 0.76, 0.28,
            boxstyle="round,pad=0.002,rounding_size=0.008",
            facecolor=color, edgecolor="none",
            alpha=0.10, animated=True
        )
        ax_meter.add_patch(patch)
        meter_patches.append((patch, color, center_db))

    ax_meter.set_xlim(0, 1)
    ax_meter.set_ylim(0, 1)
    ax_meter.axis("off")

    meter_scale = np.linspace(FLOOR_DB, CEIL_DB, 9)
    for db in meter_scale:
        xpos = 0.08 + 0.80 * ((db - FLOOR_DB) / (CEIL_DB - FLOOR_DB))
        ax_meter.text(
            xpos, 0.82, f"{db:g}",
            transform=ax_meter.transAxes,
            color=DIM, fontsize=6.8,
            ha="center"
        )

    ax_meter.text(
        0.18, 0.16, L["safe"],
        transform=ax_meter.transAxes,
        color=GREEN, fontsize=7.5, ha="center"
    )
    ax_meter.text(
        0.43, 0.16, L["nominal"],
        transform=ax_meter.transAxes,
        color=YELLOW, fontsize=7.5, ha="center"
    )
    ax_meter.text(
        0.65, 0.16, L["high"],
        transform=ax_meter.transAxes,
        color=ORANGE, fontsize=7.5, ha="center"
    )
    ax_meter.text(
        0.86, 0.16, L["critical"],
        transform=ax_meter.transAxes,
        color=RED, fontsize=7.5, ha="center"
    )

    meter_marker = ax_meter.axvline(
        0.08, color=DIM, linewidth=1.2, alpha=0.9, animated=True
    )

    # Stats panel
    ax_stats = fig.add_subplot(gs[3:5, 9:])
    add_panel(ax_stats, face="#050b12")
    ax_stats.axis("off")
    panel_title(ax_stats, "STATS")

    stat_hits = ax_stats.text(
        0.07, 0.72, "THRESHOLD HITS", color=DIM,
        fontsize=7.5, transform=ax_stats.transAxes
    )
    hits_readout = ax_stats.text(
        0.92, 0.70, "0", color=RED,
        fontsize=20, ha="right",
        transform=ax_stats.transAxes, animated=True
    )

    ax_stats.text(
        0.07, 0.49, "TOTAL TIME",
        color=DIM, fontsize=7.5,
        transform=ax_stats.transAxes
    )
    time_readout = ax_stats.text(
        0.92, 0.47, "00:00:00",
        color=TEXT, fontsize=10,
        ha="right", transform=ax_stats.transAxes, animated=True
    )

    ax_stats.text(
        0.07, 0.27, "WINDOW",
        color=DIM, fontsize=7.5,
        transform=ax_stats.transAxes
    )
    window_readout = ax_stats.text(
        0.92, 0.25, f"{WINDOW_SEC:.1f} sec",
        color=TEXT, fontsize=9,
        ha="right", transform=ax_stats.transAxes
    )

    ax_stats.text(
        0.07, 0.09, "UPDATE",
        color=DIM, fontsize=7.5,
        transform=ax_stats.transAxes
    )
    update_readout = ax_stats.text(
        0.92, 0.07, f"{REFRESH_MS} ms",
        color=TEXT, fontsize=9,
        ha="right", transform=ax_stats.transAxes
    )

    # Lower panels
    ax_hold = fig.add_subplot(gs[4, :2])
    add_panel(ax_hold)
    panel_title(ax_hold, "PEAK HOLD")
    hold_readout = ax_hold.text(
        0.10, 0.52, "--.-",
        transform=ax_hold.transAxes,
        color=GOLD, fontsize=22,
        va="center", animated=True
    )
    ax_hold.text(
        0.72, 0.52, "dBFS",
        transform=ax_hold.transAxes,
        color=DIM, fontsize=8,
        va="center"
    )
    ax_hold.text(
        0.10, 0.16, "DECAY  12 dB/sec",
        transform=ax_hold.transAxes,
        color=DIM, fontsize=6.5
    )

    # Signal profile: derived from actual peak history, NOT a frequency spectrum.
    ax_profile = fig.add_subplot(gs[4, 2:7])
    add_panel(ax_profile)
    panel_title(ax_profile, "SIGNAL PROFILE  •  PEAK HISTORY")

    profile_line, = ax_profile.plot(
        [], [], color=BLUE, linewidth=1.0, animated=True
    )
    profile_glow, = ax_profile.plot(
        [], [], color=CYAN, linewidth=4.0, alpha=0.06, animated=True
    )
    # 以前は毎フレーム fill_between() で PolyCollection を作り直して
    # いたが(remove()+再生成はオブジェクト生成コストが高くCPU負荷の
    # 主因だった)、常設の Polygon を1つだけ作っておき、頂点座標
    # (set_xy)だけを毎フレーム更新する方式に変更。見た目は同じまま
    # 描画コストを大幅に削減できる。
    from matplotlib.patches import Polygon as _Polygon
    profile_fill_patch = _Polygon(
        [[0, FLOOR_DB], [0, FLOOR_DB]], closed=True,
        facecolor=BLUE, edgecolor="none", alpha=0.055, animated=True
    )
    ax_profile.add_patch(profile_fill_patch)

    def _update_profile_fill(relx, ys):
        """profile_fill_patch の頂点を更新する(新規オブジェクトは作らない)。"""
        if len(relx) == 0:
            profile_fill_patch.set_xy([[0, FLOOR_DB], [0, FLOOR_DB]])
            return
        verts = np.empty((len(relx) + 2, 2))
        verts[0] = (relx[0], FLOOR_DB)
        verts[1:-1, 0] = relx
        verts[1:-1, 1] = ys
        verts[-1] = (relx[-1], FLOOR_DB)
        profile_fill_patch.set_xy(verts)

    # "NOW" マーカー: display-delay分だけ右端(=ffmpegが処理を終えて
    # 次段に渡した瞬間)から左に戻った位置が、実際にスピーカーで
    # 聞こえている音におおよそ対応する。
    now_marker = ax_profile.axvline(
        WINDOW_SEC, color=GOLD, linewidth=1.1,
        alpha=0.85, linestyle=(0, (3, 2)), zorder=5, animated=True
    )
    now_marker_label = ax_profile.text(
        WINDOW_SEC, CEIL_DB, "",
        color=GOLD, fontsize=6.3, fontweight="bold",
        ha="right", va="bottom", zorder=5, animated=True
    )
    now_marker.set_visible(False)
    now_marker_label.set_visible(False)

    ax_profile.set_ylim(FLOOR_DB, CEIL_DB)
    ax_profile.set_xlim(0, WINDOW_SEC)
    ax_profile.tick_params(
        colors=DIM, labelsize=6,
        left=False, labelleft=False,
        bottom=True, labelbottom=False
    )
    ax_profile.grid(True, color=GRID, linewidth=0.4, alpha=0.6)

    # Information panel
    ax_info = fig.add_subplot(gs[4, 7:9])
    add_panel(ax_info)
    ax_info.axis("off")
    panel_title(ax_info, "INFORMATION")

    info_y = [0.70, 0.48, 0.26, 0.10]
    info_labels = [
        ("♪", L["source"], "FFmpeg astats"),
        ("◆", L["engine"], "FFmpeg + CamillaDSP"),
        ("~", L["mode"], "Final Output Peak"),
        ("◎", L["status"], "Realtime Monitor"),
    ]

    info_values = []
    for (symbol, label, value), y in zip(info_labels, info_y):
        ax_info.text(
            0.06, y, symbol,
            transform=ax_info.transAxes,
            color=CYAN, fontsize=10,
            va="center"
        )
        ax_info.text(
            0.19, y, label,
            transform=ax_info.transAxes,
            color=DIM, fontsize=6.5,
            va="center"
        )
        tv = ax_info.text(
            0.19, y - 0.10, value,
            transform=ax_info.transAxes,
            color=TEXT, fontsize=7.2,
            va="center", animated=True
        )
        info_values.append(tv)

    # Footer
    ax_footer = fig.add_subplot(gs[6, :])
    ax_footer.set_facecolor(BG)
    ax_footer.axis("off")

    playing_text = ax_footer.text(
        0.012, 0.50, "●  " + L["playing"],
        transform=ax_footer.transAxes,
        color=CYAN, fontsize=8.5,
        va="center"
    )
    ax_footer.text(
        0.25, 0.50,
        "A L L   F O R   T H E   M U S I C ,   A L L   F O R   T H E   E M O T I O N .",
        transform=ax_footer.transAxes,
        color=GOLD, fontsize=7.2,
        va="center"
    )
    ax_footer.text(
        0.985, 0.50,
        "Bring the Concert Hall to Your Home.",
        transform=ax_footer.transAxes,
        color=BLUE, fontsize=7.2,
        ha="right", va="center"
    )

    # ─────────────────────────────────────────
    # Update
    # ─────────────────────────────────────────
    # blit=True では、update() は「毎フレーム同じアーティストの集合」を
    # 返す必要がある(表示/非表示はset_visible()で切り替え、集合自体は
    # 固定)。ここで一度だけ定義しておく。
    _ANIM_ARTISTS = (
        needle_l, tip_l, value_l, needle_r, tip_r, value_r,
        now_readout, hold_readout, status_text, status_dot,
        meter_marker, profile_line, profile_glow, profile_fill_patch,
        now_marker, now_marker_label,
        hits_readout, time_readout, delay_readout, info_values[0],
    ) + tuple(patch for patch, _color, _center in meter_patches)

    def update(_frame):
        mon.poll()

        if input_state["active"]:
            delay_readout.set_text(f"SET DELAY ▶ {input_state['buffer']}_")
            delay_readout.set_color(ORANGE)
        elif delay_state["sec"] > 0:
            delay_readout.set_text(f"DISPLAY DELAY  {delay_state['sec']:.1f}s")
            delay_readout.set_color(GOLD)
        else:
            delay_readout.set_text("DISPLAY DELAY  OFF")
            delay_readout.set_color(GOLD)

        if not mon.times:
            status_text.set_text("WAITING FOR SIGNAL")
            status_text.set_color(DIM)
            status_dot.set_color(DIM)
            now_readout.set_text("--.-")
            now_readout.set_color(DIM)
            hold_readout.set_text("--.-")

            set_needle(needle_l, tip_l, value_l, FLOOR_DB)
            set_needle(needle_r, tip_r, value_r, FLOOR_DB)

            for patch, color, _ in meter_patches:
                patch.set_alpha(0.08)

            meter_marker.set_xdata([0.08, 0.08])
            now_marker.set_visible(False)
            now_marker_label.set_visible(False)

            profile_line.set_data([], [])
            profile_glow.set_data([], [])
            _update_profile_fill(np.array([]), np.array([]))

            hits_readout.set_text("0")
            time_readout.set_text("00:00:00")
            return _ANIM_ARTISTS

        xs = np.asarray(mon.times)
        ys = np.asarray(mon.values)
        t_last = xs[-1]

        # The main display is now a warm analog stereo meter.
        disp_l, disp_r, disp_val = mon.delayed_reading()
        set_needle(needle_l, tip_l, value_l, disp_l)
        set_needle(needle_r, tip_r, value_r, disp_r)

        latest_db = disp_val
        current_color = led_color(latest_db, THRESHOLD_DB)

        now_readout.set_text(f"{latest_db:5.1f}")
        now_readout.set_color(current_color)

        hold_readout.set_text(f"{mon.peak_hold_db:5.1f}")

        if latest_db >= THRESHOLD_DB:
            status_text.set_text("THRESHOLD EXCEEDED")
            status_text.set_color(RED)
            status_dot.set_color(RED)
        elif latest_db >= THRESHOLD_DB - 3:
            status_text.set_text("HIGH LEVEL")
            status_text.set_color(ORANGE)
            status_dot.set_color(ORANGE)
        else:
            status_text.set_text("SIGNAL NOMINAL")
            status_text.set_color(GREEN)
            status_dot.set_color(GREEN)

        # Horizontal meter
        norm = np.clip(
            (latest_db - FLOOR_DB) / (CEIL_DB - FLOOR_DB),
            0, 1
        )
        meter_x = 0.08 + 0.80 * norm
        meter_marker.set_xdata([meter_x, meter_x])

        for patch, color, center_db in meter_patches:
            patch.set_alpha(
                0.88 if center_db <= latest_db else 0.07
            )

        # Signal profile based on actual peak history.
        relx = xs - max(0, t_last - WINDOW_SEC)
        profile_line.set_data(relx, ys)
        profile_glow.set_data(relx, ys)
        # blit=True では軸の表示範囲(xlim)を毎フレーム変えると、
        # 背景としてキャッシュ済みのグリッド線とズレてしまうため、
        # 起動時に設定した固定 xlim (0, WINDOW_SEC) のまま変更しない。

        _update_profile_fill(relx, ys)

        # "NOW" マーカー: 実際に耳に聞こえているであろう位置。
        # display-delay が 0 の場合は「右端 = 今」なので表示しない。
        if delay_state["sec"] > 0:
            now_x = relx[-1] - delay_state["sec"]
            if now_x >= 0:
                now_marker.set_xdata([now_x, now_x])
                now_marker_label.set_position((now_x, CEIL_DB))
                now_marker_label.set_text(f"NOW  −{delay_state['sec']:.1f}s")
                now_marker.set_visible(True)
                now_marker_label.set_visible(True)
            else:
                # 再生直後などまだ履歴が足りない場合は非表示。
                now_marker.set_visible(False)
                now_marker_label.set_visible(False)
        else:
            now_marker.set_visible(False)
            now_marker_label.set_visible(False)

        # Stats
        elapsed_total = max(0, int(time.time() - mon.start_time))
        hh = elapsed_total // 3600
        mm = (elapsed_total % 3600) // 60
        ss = elapsed_total % 60

        hits_readout.set_text(str(len(mon.hit_times)))
        time_readout.set_text(f"{hh:02d}:{mm:02d}:{ss:02d}")

        # Dynamic source/log name
        if mon.current_log_path:
            base = os.path.basename(mon.current_log_path)
            info_values[0].set_text(base[:25])

        return _ANIM_ARTISTS

    # delayの数値直接入力用の状態。数字キーを押すと入力モードに入り、
    # Enterで確定、Escでキャンセル、Backspaceで一文字削除できる。
    # ※ blit=True の場合、FuncAnimation はコンストラクタの中で即座に
    #   1回目の update() を呼ぶため、update() が参照する input_state は
    #   必ず FuncAnimation の生成より前に定義しておく必要がある。
    input_state = {"active": False, "buffer": ""}

    ani = animation.FuncAnimation(
        fig, update,
        interval=REFRESH_MS,
        blit=True,
        cache_frame_data=False
    )

    # 矢印キーや一部の文字キーは matplotlib 標準で「ズーム履歴の戻る/進む」
    # 等に割り当てられており、独自のキー操作(delay微調整・数値直接入力)
    # と衝突するため、ここで解除しておく。
    for _keymap_name in (
        "keymap.home", "keymap.back", "keymap.forward",
        "keymap.pan", "keymap.zoom",
    ):
        plt.rcParams[_keymap_name] = []

    def on_key(event):
        key = event.key

        if input_state["active"]:
            if key in ("enter", "return"):
                buf = input_state["buffer"]
                input_state["active"] = False
                input_state["buffer"] = ""
                if buf:
                    try:
                        delay_state["sec"] = max(0.0, round(float(buf), 2))
                    except ValueError:
                        pass
                return
            if key == "escape":
                input_state["active"] = False
                input_state["buffer"] = ""
                return
            if key == "backspace":
                input_state["buffer"] = input_state["buffer"][:-1]
                return
            if key is not None and len(key) == 1 and (key.isdigit() or key == "."):
                if key == "." and "." in input_state["buffer"]:
                    return
                if len(input_state["buffer"]) < 6:
                    input_state["buffer"] += key
                return
            # 入力モード中は他のキーは無視する。
            return

        # ← → : 0.1秒刻みの微調整 / ↑ ↓ : 0.5秒刻みの大まかな調整
        # r : 起動時に --display-delay で指定した値へリセット
        # 数字キー / . : 数値直接入力モードを開始(Enterで確定)
        step = None
        if key == "right":
            step = 0.1
        elif key == "left":
            step = -0.1
        elif key == "up":
            step = 0.5
        elif key == "down":
            step = -0.5
        elif key == "r":
            delay_state["sec"] = max(0.0, args.display_delay)
            return
        elif key is not None and len(key) == 1 and (key.isdigit() or key == "."):
            input_state["active"] = True
            input_state["buffer"] = "0." if key == "." else key
            return
        if step is not None:
            delay_state["sec"] = max(0.0, round(delay_state["sec"] + step, 2))

    fig.canvas.mpl_connect("key_press_event", on_key)

    if not args.no_topmost:
        # 常に最前面表示。TkAgg バックエンドの Tk ウィンドウに直接
        # 'topmost' 属性を立てる。ウィンドウがまだ OS のウィンドウ
        # マネージャーにマップされていない生成直後の段階で設定すると
        # 一部の環境(特に Linux/X11 系 WM)では無視されてしまうため、
        # ここ(plt.show() 直前、ウィンドウが実体化した後)で設定する。
        # さらに WM が表示直後に一度 topmost を解除してくることがある
        # ため、少し遅延させて再度押し直す保険もかけておく。
        try:
            tk_window = fig.canvas.manager.window
            tk_window.update_idletasks()
            tk_window.attributes("-topmost", 1)
            tk_window.lift()
            tk_window.after(
                250,
                lambda: tk_window.attributes("-topmost", 1)
            )
        except Exception:
            pass

    plt.show()


if __name__ == "__main__":
    main()
