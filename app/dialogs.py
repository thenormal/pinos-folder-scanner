"""Message boxes in "glass" style (instead of the grey Windows boxes)."""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QKeyEvent, QLinearGradient, QPen
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .widgets import (
    AMBER,
    INDIGO,
    INK_DARK,
    ROSE,
    TEAL,
    GradientButton,
    centered,
    draw_icon,
    new_painter,
    ui_font,
    white,
)

# tone -> (icon, colour)
TONES = {
    "success": ("check", TEAL),
    "info": ("info", INDIGO),
    "warn": ("alert", AMBER),
    "error": ("x", ROSE),
}


class _Bubble(QWidget):
    def __init__(self, tone: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icon, self._color = TONES.get(tone, TONES["info"])
        self.setFixedSize(40, 40)

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        c = QPointF(20, 20)
        p.setPen(Qt.PenStyle.NoPen)
        fill = QColor(self._color)
        fill.setAlpha(46)
        p.setBrush(fill)
        p.drawEllipse(c, 20, 20)
        ring = QColor(self._color)
        ring.setAlpha(150)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(ring, 1.2))
        p.drawEllipse(c, 19.4, 19.4)
        draw_icon(p, self._icon, centered(20, 20, 22), self._color, stroke=2.0)


class GlassDialog(QDialog):
    """Modal message. `buttons` = [(text, variant, returned_value), ...]."""

    SHADOW = 14

    def __init__(
        self,
        parent: Optional[QWidget],
        title: str,
        text: str,
        buttons: List[Tuple[str, str, int]],
        tone: str = "info",
        extra: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setWindowTitle(title)
        self._default_value = buttons[-1][2] if buttons else 0

        m = self.SHADOW
        outer = QVBoxLayout(self)
        outer.setContentsMargins(m + 26, m + 22, m + 26, m + 24)
        outer.setSpacing(16)

        head = QHBoxLayout()
        head.setSpacing(14)
        head.addWidget(_Bubble(tone))
        title_label = QLabel(title)
        title_label.setFont(ui_font(19, QFont.Weight.Bold, display=True))
        title_label.setStyleSheet("color:#f4f6ff;background:transparent;")
        title_label.setWordWrap(True)
        head.addWidget(title_label, 1)
        outer.addLayout(head)

        body = QLabel(text)
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setWordWrap(True)
        body.setMinimumWidth(430)
        body.setMaximumWidth(560)
        body.setFont(ui_font(14))
        body.setStyleSheet("color:rgba(255,255,255,0.86);background:transparent;")
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(body)
        if extra is not None:  # more content (for example the link buttons of the info window)
            outer.addWidget(extra)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        for label, variant, value in buttons:
            button = GradientButton(label, variant, "", 46, 14)
            # wide enough for the whole text (long texts, like in German, must not be cut)
            button.setMinimumWidth(max(110, button.fontMetrics().horizontalAdvance(label) + 56))
            button.clicked.connect(lambda _checked=False, v=value: self.done(v))
            row.addWidget(button)
        outer.addLayout(row)

    def keyPressEvent(self, event: QKeyEvent):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.done(self._default_value)
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        m = self.SHADOW
        r = QRectF(self.rect()).adjusted(m, m, -m, -m)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(1, 7):
            p.setBrush(QColor(0, 0, 0, 15))
            p.drawRoundedRect(r.adjusted(-i * 2, -i * 2 + 6, i * 2, i * 2 + 6), 20 + i * 2, 20 + i * 2)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0, QColor("#1f1a5e"))
        grad.setColorAt(1, QColor("#0d2848"))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(white(0.24), 1))
        p.drawRoundedRect(r, 20, 20)
        hl = QLinearGradient(r.left(), 0, r.right(), 0)
        hl.setColorAt(0.0, white(0.0))
        hl.setColorAt(0.5, white(0.34))
        hl.setColorAt(1.0, white(0.0))
        p.setPen(QPen(QBrush(hl), 1))
        p.drawLine(QPointF(r.left() + 22, r.top() + 1.2), QPointF(r.right() - 22, r.top() + 1.2))

    # ------------------------------------------------------------ shortcuts
    @staticmethod
    def message(parent: Optional[QWidget], title: str, text: str, ok_text: str, tone: str = "info") -> None:
        GlassDialog(parent, title, text, [(ok_text, "primary", 1)], tone).exec()

    @staticmethod
    def choose(
        parent: Optional[QWidget], title: str, text: str, buttons: List[Tuple[str, str, int]], tone: str = "info"
    ) -> int:
        """A message with several buttons; returns the value of the one pressed (0 if closed)."""
        return GlassDialog(parent, title, text, buttons, tone).exec()

    @staticmethod
    def info_window(
        parent: Optional[QWidget],
        title: str,
        text: str,
        links: List[Tuple[str, Callable[[], object]]],
        actions: List[Tuple[str, Callable[[], object]]],
        close_text: str,
    ) -> None:
        """The information window: a row of link buttons, a row of action buttons and Close.

        The buttons do their job and leave the window open.
        """
        extra = QWidget()
        extra.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(extra)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(10)
        for group in (links, actions):
            row = QHBoxLayout()
            row.setSpacing(8)
            for label, callback in group:
                button = GradientButton(label, "ghost", "", 40, 13)
                button.clicked.connect(lambda _checked=False, cb=callback: cb())
                row.addWidget(button)
            lay.addLayout(row)
        GlassDialog(parent, title, text, [(close_text, "primary", 1)], "info", extra).exec()

    @staticmethod
    def ask(
        parent: Optional[QWidget], title: str, text: str, yes_text: str, no_text: str, tone: str = "warn"
    ) -> bool:
        dlg = GlassDialog(parent, title, text, [(no_text, "ghost", 0), (yes_text, "primary", 1)], tone)
        return dlg.exec() == 1
