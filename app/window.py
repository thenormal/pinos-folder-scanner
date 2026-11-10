"""Main window: assembles the widgets and connects scanning and exporting."""
from __future__ import annotations

import math
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import QEvent, QPointF, QRectF, QStandardPaths, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizeGrip,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import i18n
from .dialogs import GlassDialog
from .exporters import FORMATS, PROGRAM_NAME, target_paths
from .i18n import LANGUAGES
from .icon import app_icon
from .scanner import normalize_root
from .settings import DEPTH_KEYS, Settings
from .widgets import (
    Caption,
    DepthSelector,
    FormatChip,
    GlassCard,
    GradientButton,
    PathField,
    PathTicker,
    ProgressRing,
    StatTile,
    StatusPill,
    TitleBar,
    ToggleSwitch,
    make_label,
    new_painter,
    white,
)
from .worker import ScanWorker

DEPTH_VALUE = {"0": 0, "1": 1, "2": 2, "3": 3, "all": None}

# Coloured glows in the background: (x, y, radius, colour, opacity, amplitude, speed, phase)
# x, y and radius are fractions of the window width/height.
BLOBS = [
    (0.10, 0.14, 0.22, "#6366f1", 0.80, 46.0, 0.050, 0.0),
    (0.97, 0.50, 0.25, "#2dd4bf", 0.42, 40.0, 0.040, 1.7),
    (0.50, 1.04, 0.27, "#ec4899", 0.34, 50.0, 0.030, 3.1),
]


def fmt_int(n: int) -> str:
    return f"{n:,}"


def fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class DimOverlay(QWidget):
    """Dark veil that dims the option cards while the scan is running."""

    def __init__(self, parent: QWidget, cards: List[QWidget]):
        super().__init__(parent)
        self._cards = cards
        self._alpha = 0.0
        self._target = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(240)
        self._anim.valueChanged.connect(self._on_value)
        self._anim.finished.connect(self._on_finished)
        self.hide()

    def set_active(self, active: bool) -> None:
        self._target = 1.0 if active else 0.0
        self._anim.stop()
        self._anim.setStartValue(self._alpha)
        self._anim.setEndValue(self._target)
        if active:
            self.show()
            self.raise_()
        self._anim.start()

    def _on_value(self, value) -> None:
        self._alpha = float(value)
        self.update()

    def _on_finished(self) -> None:
        if self._target == 0.0:
            self.hide()

    def paintEvent(self, _event):  # noqa: N802
        if self._alpha <= 0.001:
            return
        p = new_painter(self)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(8, 12, 28, int(125 * self._alpha)))
        for card in self._cards:
            p.drawRoundedRect(QRectF(card.geometry()), 22, 22)


class MainWindow(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.lang = settings.language()
        self.state = "idle"
        self.worker: Optional[ScanWorker] = None
        self._count = 0
        self._skipped = 0
        self._last_path = ""
        self._error_text = ""
        self._last_duration = 0.0
        self._base = ""
        self._t = 0.0
        self._last_tick = time.monotonic()
        self._scan_started = 0.0
        self._paused_acc = 0.0
        self._pause_started: Optional[float] = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowSystemMenuHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(PROGRAM_NAME)
        self.setWindowIcon(app_icon())

        self._build()
        self._restore_settings()
        self.retranslate()

        self._bg_timer = QTimer(self)
        self._bg_timer.setInterval(33)
        self._bg_timer.timeout.connect(self._tick_background)
        self._bg_timer.start()
        self._clock = QTimer(self)
        self._clock.setInterval(250)
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start()

        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        width, height = 1100, 720
        if avail is not None:
            width = min(width, int(avail.width() * 0.96))
            height = min(height, int(avail.height() * 0.96))
        hint = self.minimumSizeHint()
        self.resize(max(width, hint.width()), max(height, hint.height()))
        if avail is not None:
            self.move(avail.center().x() - self.width() // 2, avail.center().y() - self.height() // 2)

    # ------------------------------------------------------------------ construction
    def _tr(self, key: str, **kw) -> str:
        return i18n.tr(self.lang, key, **kw)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.titlebar = TitleBar(self, LANGUAGES)
        self.titlebar.lang.changed.connect(self.set_language)
        root.addWidget(self.titlebar)

        body = QWidget()
        body_l = QHBoxLayout(body)
        body_l.setContentsMargins(32, 26, 32, 28)
        body_l.setSpacing(24)
        root.addWidget(body, 1)

        # ---- left column: options
        self.left = QWidget()
        left_l = QVBoxLayout(self.left)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(20)

        self.card_folder = GlassCard()
        fl = QVBoxLayout(self.card_folder)
        fl.setContentsMargins(24, 22, 24, 22)
        fl.setSpacing(12)
        self.cap_folder = Caption()
        fl.addWidget(self.cap_folder)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.path_field = PathField()
        self.path_field.edit.returnPressed.connect(self._on_start)
        row.addWidget(self.path_field, 1)
        self.btn_browse = GradientButton("", "primary", "folder_open", 54, 15)
        self.btn_browse.clicked.connect(self._browse)
        row.addWidget(self.btn_browse)
        fl.addLayout(row)
        fl.addSpacing(4)
        self.cap_depth = Caption()
        fl.addWidget(self.cap_depth)
        self.depth = DepthSelector()
        self.depth.changed.connect(lambda _k: self._refresh_tiles())
        fl.addWidget(self.depth)
        fl.addSpacing(4)
        trow = QHBoxLayout()
        tcol = QVBoxLayout()
        tcol.setSpacing(2)
        self.lbl_hidden_t = make_label("", 14, QFont.Weight.Bold, "#f4f6ff")
        self.lbl_hidden_s = make_label("", 12.5, QFont.Weight.Normal, "rgba(255,255,255,0.62)")
        tcol.addWidget(self.lbl_hidden_t)
        tcol.addWidget(self.lbl_hidden_s)
        trow.addLayout(tcol, 1)
        self.toggle = ToggleSwitch()
        trow.addWidget(self.toggle)
        fl.addLayout(trow)
        left_l.addWidget(self.card_folder)

        self.card_formats = GlassCard()
        gl = QVBoxLayout(self.card_formats)
        gl.setContentsMargins(24, 22, 24, 20)
        gl.setSpacing(12)
        self.cap_formats = Caption()
        gl.addWidget(self.cap_formats)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        self.chips: Dict[str, FormatChip] = {}
        for i, fmt in enumerate(FORMATS):
            chip = FormatChip(fmt)
            self.chips[fmt] = chip
            grid.addWidget(chip, i // 3, i % 3)
        for c in range(3):
            grid.setColumnStretch(c, 1)
        gl.addLayout(grid)
        gl.addStretch(1)
        self.lbl_hint = make_label("", 12.5, QFont.Weight.Normal, "rgba(255,255,255,0.62)")
        self.lbl_hint.setWordWrap(True)
        gl.addWidget(self.lbl_hint)
        left_l.addWidget(self.card_formats, 1)

        self.dim = DimOverlay(self.left, [self.card_folder, self.card_formats])
        self.left.installEventFilter(self)
        body_l.addWidget(self.left, 14)

        # ---- right column: status
        self.card_status = GlassCard(strong=True)
        rl = QVBoxLayout(self.card_status)
        rl.setContentsMargins(26, 24, 26, 24)
        rl.setSpacing(12)
        top = QHBoxLayout()
        self.cap_status = Caption()
        top.addWidget(self.cap_status)
        top.addStretch(1)
        self.pill = StatusPill()
        top.addWidget(self.pill)
        rl.addLayout(top)

        self.ring = ProgressRing()
        rl.addWidget(self.ring, 1, Qt.AlignmentFlag.AlignCenter)

        self.stack = QStackedWidget()
        self.stack.setFixedHeight(80)
        page_ready = QWidget()
        pr = QVBoxLayout(page_ready)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.setSpacing(6)
        self.lbl_title = make_label("", 22, QFont.Weight.Bold, "#f4f6ff", display=True)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setWordWrap(True)
        self.lbl_sub = make_label("", 13.5, QFont.Weight.Normal, "rgba(255,255,255,0.68)")
        self.lbl_sub.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.lbl_sub.setWordWrap(True)
        pr.addWidget(self.lbl_title)
        pr.addWidget(self.lbl_sub, 1)
        page_scan = QWidget()
        ps = QVBoxLayout(page_scan)
        ps.setContentsMargins(0, 8, 0, 0)
        ps.setSpacing(8)
        self.cap_last = Caption()
        self.ticker = PathTicker()
        ps.addWidget(self.cap_last)
        ps.addWidget(self.ticker)
        ps.addStretch(1)
        self.stack.addWidget(page_ready)
        self.stack.addWidget(page_scan)
        rl.addWidget(self.stack)

        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.tile_time, self.tile_skipped, self.tile_depth = StatTile(), StatTile(), StatTile()
        for tile in (self.tile_time, self.tile_skipped, self.tile_depth):
            tiles.addWidget(tile)
        rl.addLayout(tiles)

        self.btn_start = GradientButton("", "primary", "play", 56, 17)
        self.btn_start.clicked.connect(self._on_start)
        rl.addWidget(self.btn_start)
        brow = QHBoxLayout()
        brow.setSpacing(10)
        self.btn_pause = GradientButton("", "amber", "pause", 48, 15)
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_cancel = GradientButton("", "rose", "x", 48, 15)
        self.btn_cancel.clicked.connect(self._on_cancel)
        brow.addWidget(self.btn_pause, 1)
        brow.addWidget(self.btn_cancel, 1)
        rl.addLayout(brow)
        body_l.addWidget(self.card_status, 10)

        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        self.grip.setStyleSheet("QSizeGrip{background:transparent;image:none;}")

    # ------------------------------------------------------------------ settings
    def _restore_settings(self) -> None:
        self.titlebar.lang.set_current(self.lang)
        self.depth.set_current(self.settings.depth_key())
        self.toggle.setChecked(self.settings.include_hidden())
        chosen = self.settings.formats(FORMATS)
        for fmt, chip in self.chips.items():
            chip.setChecked(fmt in chosen)
        last = self.settings.last_folder()
        if last:
            self.path_field.edit.setText(last)

    def _save_settings(self) -> None:
        self.settings.set_language(self.lang)
        self.settings.set_depth_key(self.depth.current() or "2")
        self.settings.set_include_hidden(self.toggle.isChecked())
        self.settings.set_formats([f for f in FORMATS if self.chips[f].isChecked()])
        text = self.path_field.edit.text().strip()
        if text and os.path.isdir(text):
            self.settings.set_last_folder(text)

    # ------------------------------------------------------------------ language
    def set_language(self, lang: str) -> None:
        if lang == self.lang:
            return
        self.lang = lang
        self.settings.set_language(lang)
        self.titlebar.lang.set_current(lang)
        self.retranslate()

    def retranslate(self) -> None:
        t = self._tr
        self.titlebar.title.setText(PROGRAM_NAME)
        self.cap_folder.setText(t("section_folder"))
        self.path_field.edit.setPlaceholderText(t("path_placeholder"))
        self.btn_browse.set_look("primary", text=t("browse"))
        self.btn_browse.updateGeometry()
        self.cap_depth.setText(t("section_depth"))
        self.depth.set_options([(k, t(f"depth_{k}_title"), t(f"depth_{k}_sub")) for k in DEPTH_KEYS])
        self.lbl_hidden_t.setText(t("hidden_title"))
        self.lbl_hidden_s.setText(t("hidden_sub"))
        self.cap_formats.setText(t("section_formats"))
        for fmt, chip in self.chips.items():
            chip.set_subtitle(t(f"fmt_{fmt}_sub"))
        self.lbl_hint.setText(t("formats_hint"))
        self.cap_status.setText(t("section_status"))
        self.cap_last.setText(t("last_folder"))
        self._apply_state()
        self._refresh_tiles()

    # ------------------------------------------------------------------ animated background
    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.left and event.type() == QEvent.Type.Resize:
            self.dim.setGeometry(self.left.rect())
        return super().eventFilter(obj, event)

    def _tick_background(self) -> None:
        now = time.monotonic()
        dt, self._last_tick = now - self._last_tick, now
        if self.isMinimized() or not self.isVisible():
            return
        self._t += dt
        self.update()

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        w, h = self.width(), self.height()
        radius = 0.0 if self.isMaximized() else 14.0
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
        p.setClipPath(clip)
        base = QLinearGradient(0, 0, w, h)
        base.setColorAt(0.0, QColor("#080c1c"))
        base.setColorAt(0.55, QColor("#161040"))
        base.setColorAt(1.0, QColor("#08203a"))
        p.fillRect(self.rect(), QBrush(base))
        for fx, fy, fr, color, alpha, amp, speed, phase in BLOBS:
            cx = fx * w + amp * math.sin(self._t * speed * 2 * math.pi + phase)
            cy = fy * h + amp * math.cos(self._t * speed * 1.6 * math.pi + phase)
            glow = QRadialGradient(QPointF(cx, cy), fr * w)
            c0, c1 = QColor(color), QColor(color)
            c0.setAlphaF(alpha)
            c1.setAlphaF(0.0)
            glow.setColorAt(0.0, c0)
            glow.setColorAt(0.68, c1)
            glow.setColorAt(1.0, c1)
            p.fillRect(self.rect(), QBrush(glow))
        p.setClipping(False)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(white(0.14), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), radius, radius)

    def resizeEvent(self, event):  # noqa: N802
        self.grip.move(self.width() - 18, self.height() - 18)
        self.grip.raise_()
        super().resizeEvent(event)

    def changeEvent(self, event):  # noqa: N802
        if event.type() == QEvent.Type.WindowStateChange:
            self.titlebar.btn_max.set_kind("win_restore" if self.isMaximized() else "win_max")
            self.grip.setVisible(not self.isMaximized())
            self.update()
        super().changeEvent(event)

    # ------------------------------------------------------------------ state
    def _running(self) -> bool:
        return self.state in ("scanning", "paused", "exporting")

    def _set_state(self, state: str) -> None:
        self.state = state
        self._apply_state()

    def _apply_state(self) -> None:
        t = self._tr
        s = self.state
        running = self._running()

        pill = {
            "idle": ("idle", "st_ready"),
            "scanning": ("scanning", "st_scanning"),
            "paused": ("paused", "st_paused"),
            "exporting": ("exporting", "st_exporting"),
            "done": ("done", "st_done"),
            "cancelled": ("cancelled", "st_cancelled"),
            "error": ("error", "st_error"),
        }[s]
        self.pill.set_state(pill[0], t(pill[1]))

        count_text = fmt_int(self._count)
        if s in ("scanning", "paused"):
            self.ring.set_mode(s, count_text, t("count_caption"))
        elif s == "exporting":
            self.ring.set_mode("exporting", count_text, t("exporting_caption"))
        elif s == "done":
            self.ring.set_mode("done")
        elif s in ("cancelled", "error"):
            self.ring.set_mode("cancelled")
        else:
            self.ring.set_mode("idle")

        if running:
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)
            if s == "done":
                self.lbl_title.setText(t("done_title"))
                self.lbl_sub.setText(t("done_sub", n=fmt_int(self._count), s=fmt_int(self._skipped)))
            elif s == "cancelled":
                self.lbl_title.setText(t("cancelled_title"))
                self.lbl_sub.setText(t("cancelled_sub"))
            elif s == "error":
                self.lbl_title.setText(t("error_title"))
                self.lbl_sub.setText(self._error_text)
            else:
                self.lbl_title.setText(t("ready_title"))
                self.lbl_sub.setText(t("ready_sub"))

        if s == "exporting":
            self.btn_start.set_look("primary", "play", t("btn_exporting"))
        elif running:
            self.btn_start.set_look("primary", "play", t("btn_running"))
        else:
            self.btn_start.set_look("primary", "play", t("btn_start"))
        self.btn_start.setEnabled(not running)
        can_control = s in ("scanning", "paused")
        if s == "paused":
            self.btn_pause.set_look("amber", "play", t("btn_resume"))
        else:
            self.btn_pause.set_look("amber", "pause", t("btn_pause"))
        self.btn_pause.setEnabled(can_control)
        self.btn_cancel.set_look("rose", "x", t("btn_cancel"))
        self.btn_cancel.setEnabled(can_control)

        self.left.setEnabled(not running)
        self.dim.set_active(running)
        self.titlebar.lang.setEnabled(True)
        self._refresh_tiles()

    def _elapsed(self) -> float:
        if self.state == "scanning":
            return time.monotonic() - self._scan_started - self._paused_acc
        if self.state == "paused" and self._pause_started is not None:
            return self._pause_started - self._scan_started - self._paused_acc
        if self.state in ("done", "cancelled"):
            return self._last_duration
        if self.state == "exporting":
            return self._last_duration
        return 0.0

    def _refresh_tiles(self) -> None:
        t = self._tr
        self.tile_time.set_texts(fmt_time(self._elapsed()), t("tile_time"))
        self.tile_skipped.set_texts(fmt_int(self._skipped), t("tile_skipped"))
        key = self.depth.current() or "2"
        self.tile_depth.set_texts(t(f"depth_short_{key}"), t("tile_depth"))

    def _tick_clock(self) -> None:
        if self.state in ("scanning",):
            self.tile_time.set_texts(fmt_time(self._elapsed()))

    # ------------------------------------------------------------------ actions
    def _browse(self) -> None:
        home = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)
        start = self.path_field.edit.text().strip()
        if not start or not os.path.isdir(start):
            start = self.settings.last_folder() or home
        path = QFileDialog.getExistingDirectory(self, self._tr("dlg_choose_folder"), start)
        if path:
            self.path_field.edit.setText(os.path.normpath(path))

    def _message(self, key_title: str, text: str, tone: str = "warn") -> None:
        GlassDialog.message(self, self._tr(key_title), text, self._tr("btn_ok"), tone)

    def _default_stem(self, root: str) -> str:
        drive, _rest = os.path.splitdrive(root)
        name = os.path.basename(root.rstrip("\\/")) or drive
        name = re.sub(r"[^\w\-]+", "_", name).strip("_") or "root"
        prefix = "Folder_list"
        return f"{prefix}_{name}_{datetime.now():%Y%m%d_%H%M}"

    def _ask_base(self, formats: List[str], root: str) -> str:
        t = self._tr
        default_dir = (
            self.settings.last_save_dir()
            or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
            or os.path.expanduser("~")
        )
        stem = self._default_stem(root)
        if len(formats) == 1:
            path, _ = QFileDialog.getSaveFileName(
                self,
                t("dlg_save_single"),
                os.path.join(default_dir, f"{stem}.{formats[0]}"),
                t("dlg_filter_file", ext=formats[0]),
            )
        else:
            path, _ = QFileDialog.getSaveFileName(
                self,
                t("dlg_save_multi", formats=", ".join(f.upper() for f in formats)),
                os.path.join(default_dir, stem),
                t("dlg_filter_any"),
            )
        if not path:
            return ""
        return re.sub(r"\.(pdf|txt|csv|xlsx|html|json)$", "", path, flags=re.IGNORECASE)

    def _on_start(self) -> None:
        if self._running():
            return
        t = self._tr
        raw = self.path_field.edit.text().strip()
        if not raw:
            self._message("warn_title", t("warn_no_path"))
            return
        root = normalize_root(raw)
        if not os.path.isdir(root):
            self._message("warn_title", t("warn_bad_path", p=root))
            return
        formats = [f for f in FORMATS if self.chips[f].isChecked()]
        if not formats:
            self._message("warn_title", t("warn_no_format"))
            return
        base = self._ask_base(formats, root)
        if not base:
            return
        existing = [p for p in target_paths(base, formats) if os.path.exists(p)]
        if existing and not GlassDialog.ask(
            self,
            t("overwrite_title"),
            t("warn_overwrite", files="\n".join(os.path.basename(p) for p in existing)),
            t("btn_continue"),
            t("btn_cancel"),
        ):
            return

        self.path_field.edit.setText(root)
        self.settings.set_last_save_dir(os.path.dirname(base))
        self._save_settings()

        key = self.depth.current() or "2"
        depth_label = f"{t(f'depth_{key}_title')} ({t(f'depth_{key}_sub')})"
        self._base = base
        self._count = 0
        self._skipped = 0
        self._last_path = ""
        self._last_duration = 0.0
        self._paused_acc = 0.0
        self._pause_started = None
        self._scan_started = time.monotonic()
        self.ticker.set_text("")

        self.worker = ScanWorker(root, DEPTH_VALUE[key], self.toggle.isChecked(), formats, base, self.lang, depth_label, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.exporting.connect(self._on_exporting)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self._set_state("scanning")
        self.worker.start()

    def _on_pause(self) -> None:
        if self.worker is None:
            return
        if self.state == "scanning":
            self.worker.pause()
            self._pause_started = time.monotonic()
            self._set_state("paused")
        elif self.state == "paused":
            if self._pause_started is not None:
                self._paused_acc += time.monotonic() - self._pause_started
            self._pause_started = None
            self.worker.resume()
            self._set_state("scanning")

    def _on_cancel(self) -> None:
        if self.worker is not None and self.state in ("scanning", "paused"):
            self.btn_cancel.setEnabled(False)
            self.btn_pause.setEnabled(False)
            self.worker.cancel()

    # ------------------------------------------------------------------ replies from the thread
    def _on_progress(self, count: int, path: str, skipped: int) -> None:
        self._count, self._skipped = count, skipped
        if path:
            self._last_path = path
            self.ticker.set_text(path)
        self.ring.set_count(fmt_int(count))
        self.tile_skipped.set_texts(fmt_int(skipped))

    def _on_exporting(self) -> None:
        if self.worker is not None and self._pause_started is None:
            self._last_duration = time.monotonic() - self._scan_started - self._paused_acc
        self._set_state("exporting")

    def _release_worker(self) -> None:
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.wait()
            worker.deleteLater()

    def _on_finished(self, result, files: list, errors: list) -> None:
        self._release_worker()
        self._last_duration = result.duration
        self._count = len(result.folders)
        self._skipped = len(result.skipped)
        t = self._tr
        if result.cancelled:
            self._set_state("cancelled")
            GlassDialog.message(self, t("cancel_msg_title"), t("cancel_msg"), t("btn_ok"), "info")
            return
        self._set_state("done")
        folder = os.path.dirname(files[0]) if files else os.path.dirname(self._base)
        text = t("done_msg") + "\n\n" + t(
            "done_msg_info",
            n=fmt_int(self._count),
            s=fmt_int(self._skipped),
            t=fmt_time(result.duration),
            folder=folder,
            files="\n".join("• " + os.path.basename(f) for f in files) or "–",
        )
        if errors:
            text += t("done_msg_errors", errors="\n".join(f"• {fmt}: {msg}" for fmt, msg in errors))
        GlassDialog.message(self, t("done_msg_title"), text, t("btn_ok"), "warn" if errors else "success")

    def _on_failed(self, message: str) -> None:
        self._release_worker()
        self._error_text = message
        self._set_state("error")
        t = self._tr
        GlassDialog.message(self, t("err_title"), t("fail_msg", e=message), t("btn_ok"), "error")

    # ------------------------------------------------------------------ closing
    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker is not None and self.worker.isRunning():
            t = self._tr
            if not GlassDialog.ask(self, t("quit_title"), t("quit_msg"), t("btn_quit"), t("btn_keep")):
                event.ignore()
                return
            if self.worker is not None:
                self.worker.blockSignals(True)
                self.worker.cancel()
                if not self.worker.wait(5000):
                    self.worker.terminate()
                    self.worker.wait(1000)
        self._save_settings()
        event.accept()
