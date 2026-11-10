"""Custom widgets ("glass" style) painted with QPainter.

All the look of the program lives here: colours, glass cards, buttons, the animated ring,
icons. To change the colours or the style, edit this file.
"""
from __future__ import annotations

import math
import time
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QByteArray, QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QRadialGradient,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QLineEdit, QMenu, QSizePolicy, QWidget

# ------------------------------------------------------------------ colours
TEAL = QColor("#5eead4")
INDIGO = QColor("#818cf8")
PINK = QColor("#f472b6")
AMBER = QColor("#fbbf24")
ROSE = QColor("#fb7185")
INK_DARK = QColor("#06101f")
TEXT = QColor("#f4f6ff")


def white(alpha: float) -> QColor:
    return QColor(255, 255, 255, int(alpha * 255))


def with_alpha(color: QColor, alpha: float) -> QColor:
    c = QColor(color)
    c.setAlpha(int(alpha * 255))
    return c


def ui_font(px: float, weight: QFont.Weight = QFont.Weight.Normal, display: bool = False, spacing: float = 0) -> QFont:
    font = QFont()
    font.setFamilies(
        [
            "Segoe UI Variable Display" if display else "Segoe UI Variable Text",
            "Segoe UI",
            "Helvetica Neue",
            "Noto Sans",
            "DejaVu Sans",
            "Arial",
        ]
    )
    font.setPixelSize(int(round(px)))
    font.setWeight(weight)
    if spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font


def mono_font(px: float) -> QFont:
    font = QFont()
    font.setFamilies(["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier New"])
    font.setPixelSize(int(round(px)))
    return font


def new_painter(widget: QWidget) -> QPainter:
    p = QPainter(widget)
    p.setRenderHints(
        QPainter.RenderHint.Antialiasing
        | QPainter.RenderHint.TextAntialiasing
        | QPainter.RenderHint.SmoothPixmapTransform
    )
    return p


# ------------------------------------------------------------------ SVG icons
_STROKE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" fill="none" stroke="{c}" stroke-opacity="{o}" '
    'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
)
_FILL = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{c}" fill-opacity="{o}">{body}</svg>'

_ICON_BODIES: Dict[str, Tuple[str, str, str]] = {
    # name: (kind, viewBox, body)
    "folder_search": (
        "stroke",
        "0 0 24 24",
        '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
        '<circle cx="14.5" cy="13.5" r="2.6"/><path d="M16.4 15.4l2.1 2.1"/>',
    ),
    "drive": (
        "stroke",
        "0 0 24 24",
        '<rect x="3" y="6" width="18" height="12" rx="3"/><path d="M7 12h.01M11 12h6"/>',
    ),
    "folder_open": (
        "stroke",
        "0 0 24 24",
        '<path d="M3 8a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1H3z"/>'
        '<path d="M3 11h18l-1.6 7a2 2 0 0 1-2 1.5H6.6a2 2 0 0 1-2-1.5z"/>',
    ),
    "chevron": ("stroke", "0 0 24 24", '<path d="M6 9l6 6 6-6"/>'),
    "check": ("stroke", "0 0 24 24", '<path d="M5 12.5l4.5 4.5L19 7.5"/>'),
    "x": ("stroke", "0 0 24 24", '<path d="M5 5l14 14M19 5L5 19"/>'),
    "play": (
        "fill",
        "0 0 24 24",
        '<path d="M7 4.5v15a1 1 0 0 0 1.5.86l12-7.5a1 1 0 0 0 0-1.72l-12-7.5A1 1 0 0 0 7 4.5z"/>',
    ),
    "pause": (
        "fill",
        "0 0 24 24",
        '<rect x="6" y="4" width="4.5" height="16" rx="1.2"/><rect x="13.5" y="4" width="4.5" height="16" rx="1.2"/>',
    ),
    "info": ("stroke", "0 0 24 24", '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 7.8h.01"/>'),
    "alert": ("stroke", "0 0 24 24", '<path d="M12 4l9 16H3z"/><path d="M12 10v4"/><path d="M12 17.2h.01"/>'),
    "win_min": ("stroke", "0 0 12 12", '<path d="M1 6h10"/>'),
    "win_max": ("stroke", "0 0 12 12", '<rect x="1.5" y="1.5" width="9" height="9" rx="1.5"/>'),
    "win_restore": (
        "stroke",
        "0 0 12 12",
        '<rect x="1.5" y="3.5" width="7" height="7" rx="1.3"/><path d="M3.5 3.5V2.8A1.3 1.3 0 0 1 4.8 1.5h5A1.3 1.3 0 0 1 11 2.8v5a1.3 1.3 0 0 1-1.3 1.3H8.5"/>',
    ),
    "win_close": ("stroke", "0 0 12 12", '<path d="M1.5 1.5l9 9M10.5 1.5l-9 9"/>'),
}

_renderers: Dict[Tuple, QSvgRenderer] = {}


def draw_icon(p: QPainter, name: str, rect: QRectF, color: QColor, stroke: float = 1.8) -> None:
    key = (name, color.rgba(), stroke)
    renderer = _renderers.get(key)
    if renderer is None:
        kind, viewbox, body = _ICON_BODIES[name]
        opacity = f"{color.alphaF():.3f}"
        rgb = f"#{color.red():02x}{color.green():02x}{color.blue():02x}"
        if kind == "fill":
            svg = _FILL.format(c=rgb, o=opacity, body=body)
        else:
            svg = _STROKE.format(vb=viewbox, c=rgb, o=opacity, w=stroke, body=body)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        _renderers[key] = renderer
    renderer.render(p, rect)


def centered(cx: float, cy: float, size: float) -> QRectF:
    return QRectF(cx - size / 2, cy - size / 2, size, size)


def paint_logo(p: QPainter, rect: QRectF) -> None:
    """Program logo: gradient rounded square with a folder and a magnifying glass."""
    radius = rect.width() * 0.31
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0, TEAL)
    grad.setColorAt(1, INDIGO)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(rect, radius, radius)
    inner = rect.width() * 0.625
    draw_icon(p, "folder_search", centered(rect.center().x(), rect.center().y(), inner), INK_DARK, stroke=2.0)


# ------------------------------------------------------------------ glass cards
class GlassCard(QWidget):
    """Semi-transparent panel with a glowing border, typical of the "glass" style."""

    def __init__(self, strong: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._strong = strong
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = 22.0
        top, bottom = (0.17, 0.05) if self._strong else (0.15, 0.05)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0, white(top))
        grad.setColorAt(1, white(bottom))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(white(0.20 if self._strong else 0.18), 1))
        p.drawRoundedRect(r, radius, radius)
        # highlight on the top edge
        hl = QLinearGradient(r.left(), 0, r.right(), 0)
        hl.setColorAt(0.0, white(0.0))
        hl.setColorAt(0.5, white(0.30))
        hl.setColorAt(1.0, white(0.0))
        p.setPen(QPen(QBrush(hl), 1))
        p.drawLine(QPointF(r.left() + radius, r.top() + 1.2), QPointF(r.right() - radius, r.top() + 1.2))


class Caption(QLabel):
    """Section label in capitals with wide letter spacing."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setFont(ui_font(11, QFont.Weight.ExtraBold, spacing=1.5))
        self.setStyleSheet("color: rgba(255,255,255,0.68); background: transparent;")


def make_label(text: str, px: float, weight: QFont.Weight, color: str, display: bool = False) -> QLabel:
    label = QLabel(text)
    label.setFont(ui_font(px, weight, display=display))
    label.setStyleSheet(f"color: {color}; background: transparent;")
    return label


class IconWidget(QWidget):
    def __init__(self, name: str, size: int, color: QColor, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._name, self._color = name, color
        self.setFixedSize(size, size)

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        if not self.isEnabled():
            p.setOpacity(0.5)
        draw_icon(p, self._name, QRectF(self.rect()), self._color)


def paint_field(p: QPainter, r: QRectF, highlight: bool = False, hover: bool = False) -> None:
    p.setBrush(QColor(8, 12, 28, 128))
    border = with_alpha(TEAL, 0.75) if highlight else white(0.28 if hover else 0.16)
    p.setPen(QPen(border, 1))
    p.drawRoundedRect(r, 14, 14)


class PathField(QWidget):
    """Path field: drive icon + editable text."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(54)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)
        layout.addWidget(IconWidget("drive", 20, TEAL))
        self.edit = QLineEdit()
        self.edit.setFont(ui_font(16, QFont.Weight.Bold))
        self.edit.setFrame(False)
        pal = self.edit.palette()
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(255, 255, 255, 105))
        self.edit.setPalette(pal)
        self.edit.setStyleSheet(
            "QLineEdit{background:transparent;border:none;color:#f4f6ff;selection-background-color:rgba(94,234,212,0.35);}"
            "QLineEdit:disabled{color:rgba(244,246,255,0.5);}"
        )
        self.edit.installEventFilter(self)
        layout.addWidget(self.edit, 1)

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.edit and event.type() in (event.Type.FocusIn, event.Type.FocusOut):
            self.update()
        return super().eventFilter(obj, event)

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        if not self.isEnabled():
            p.setOpacity(0.5)
        paint_field(p, QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), highlight=self.edit.hasFocus())


# ------------------------------------------------------------------ buttons
class GradientButton(QAbstractButton):
    """Gradient button. Variants: primary, amber, rose, ghost."""

    def __init__(self, text: str = "", variant: str = "primary", icon: str = "", height: int = 54, font_px: int = 15, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setText(text)
        self.variant = variant
        self.icon_name = icon
        self._font_px = font_px
        self._hover = False
        self.setFixedHeight(height)
        self.setFont(ui_font(font_px, QFont.Weight.ExtraBold))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def set_look(self, variant: str, icon: Optional[str] = None, text: Optional[str] = None) -> None:
        self.variant = variant
        if icon is not None:
            self.icon_name = icon
        if text is not None:
            self.setText(text)
        self.update()

    def sizeHint(self):  # noqa: N802
        from PySide6.QtCore import QSize

        w = QFontMetrics(self.font()).horizontalAdvance(self.text()) + 48
        if self.icon_name:
            w += 28
        return QSize(w, self.height())

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def _look(self):
        enabled = self.isEnabled()
        v = self.variant
        if enabled and v == "primary":
            return dict(grad=(TEAL, INDIGO), text=INK_DARK, border=None, fill=None)
        if enabled and v == "amber":
            return dict(grad=(QColor("#fde68a"), AMBER), text=QColor("#1c1100"), border=None, fill=None)
        if enabled and v == "rose":
            return dict(grad=None, text=QColor("#fecdd3"), border=QColor(251, 113, 133, 166), fill=QColor(251, 113, 133, 41))
        if enabled and v == "ghost":
            return dict(grad=None, text=white(0.92), border=white(0.28), fill=white(0.07))
        if v == "primary":
            return dict(grad=None, text=white(0.55), border=white(0.16), fill=white(0.07))
        return dict(grad=None, text=white(0.40), border=white(0.14), fill=white(0.05))

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        look = self._look()
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = min(16.0, r.height() / 3)
        enabled = self.isEnabled()
        if look["grad"]:
            g = QLinearGradient(r.topLeft(), r.topRight())
            c1, c2 = look["grad"]
            if self._hover or self.hasFocus():
                c1, c2 = c1.lighter(108), c2.lighter(108)
            if self.isDown():
                c1, c2 = c1.darker(110), c2.darker(110)
            g.setColorAt(0, c1)
            g.setColorAt(1, c2)
            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, radius, radius)
            hl = QLinearGradient(0, r.top(), 0, r.top() + r.height() * 0.55)
            hl.setColorAt(0, white(0.28))
            hl.setColorAt(1, white(0.0))
            p.setBrush(QBrush(hl))
            p.drawRoundedRect(r, radius, radius)
        else:
            fill = QColor(look["fill"])
            if enabled and self._hover:
                fill.setAlpha(min(255, fill.alpha() + 30))
            p.setBrush(fill)
            p.setPen(QPen(look["border"], 1))
            p.drawRoundedRect(r, radius, radius)
        if self.hasFocus() and enabled:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(white(0.85), 1.5))
            p.drawRoundedRect(r.adjusted(2.5, 2.5, -2.5, -2.5), radius - 2, radius - 2)

        text_color = look["text"]
        fm = QFontMetrics(self.font())
        text_w = fm.horizontalAdvance(self.text())
        icon_size = 18 if self._font_px >= 15 else 16
        gap = 9
        total = text_w + (icon_size + gap if self.icon_name else 0)
        x = r.center().x() - total / 2
        if self.icon_name:
            draw_icon(p, self.icon_name, QRectF(x, r.center().y() - icon_size / 2, icon_size, icon_size), text_color, stroke=2.0)
            x += icon_size + gap
        p.setFont(self.font())
        p.setPen(text_color)
        p.drawText(QRectF(x, r.top(), text_w + 4, r.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())


class FormatChip(QAbstractButton):
    """Selectable card for an export format (with a coloured badge)."""

    BADGES = {
        "pdf": (QColor(251, 113, 133, 64), QColor("#fecdd3")),
        "txt": (QColor(148, 163, 184, 64), QColor("#e2e8f0")),
        "csv": (QColor(251, 191, 36, 56), QColor("#fde68a")),
        "xlsx": (QColor(74, 222, 128, 64), QColor("#bbf7d0")),
        "html": (QColor(56, 189, 248, 56), QColor("#bae6fd")),
        "json": (QColor(192, 132, 252, 61), QColor("#e9d5ff")),
    }

    def __init__(self, fmt: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.fmt = fmt
        self.subtitle = ""
        self._hover = False
        self.setCheckable(True)
        self.setFixedHeight(62)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_subtitle(self, text: str) -> None:
        self.subtitle = text
        self.update()

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        if not self.isEnabled():
            p.setOpacity(0.5)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        checked = self.isChecked()
        if checked:
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, with_alpha(TEAL, 0.26))
            g.setColorAt(1, with_alpha(INDIGO, 0.26))
            p.setBrush(QBrush(g))
            p.setPen(QPen(QColor(165, 243, 252, 190), 1.2))
        else:
            p.setBrush(white(0.10 if self._hover else 0.06))
            p.setPen(QPen(white(0.25 if self._hover else 0.15), 1))
        p.drawRoundedRect(r, 16, 16)
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(white(0.8), 1.5))
            p.drawRoundedRect(r.adjusted(2.5, 2.5, -2.5, -2.5), 14, 14)

        bg, fg = self.BADGES.get(self.fmt, self.BADGES["txt"])
        badge = QRectF(14, (self.height() - 34) / 2, 42, 34)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(badge, 10, 10)
        label = self.fmt.upper()
        p.setFont(ui_font(11 if len(label) <= 3 else 10, QFont.Weight.ExtraBold))
        p.setPen(fg)
        p.drawText(badge, int(Qt.AlignmentFlag.AlignCenter), label)

        text_x = 68
        p.setFont(ui_font(14, QFont.Weight.ExtraBold))
        p.setPen(TEXT)
        p.drawText(QRectF(text_x, self.height() / 2 - 19, self.width() - text_x - 30, 20), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), label)
        p.setFont(ui_font(11.5))
        p.setPen(white(0.70 if checked else 0.65))
        sub = QFontMetrics(p.font()).elidedText(self.subtitle, Qt.TextElideMode.ElideRight, int(self.width() - text_x - 12))
        p.drawText(QRectF(text_x, self.height() / 2 + 1, self.width() - text_x - 8, 18), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), sub)

        if checked:
            c = QPointF(self.width() - 19, 19)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(TEAL)
            p.drawEllipse(c, 9, 9)
            draw_icon(p, "check", centered(c.x(), c.y(), 11), INK_DARK, stroke=3.4)


class ToggleSwitch(QAbstractButton):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(48, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._pos = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.toggled.connect(self._on_toggled)

    def _on_anim(self, value):
        self._pos = float(value)
        self.update()

    def _on_toggled(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setChecked(self, checked: bool):  # noqa: N802
        super().setChecked(checked)
        self._anim.stop()
        self._pos = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        if not self.isEnabled():
            p.setOpacity(0.5)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.topLeft(), r.topRight())
        a = self._pos
        g.setColorAt(0, QColor(255, 255, 255, int(36 + a * 0)) if a == 0 else TEAL)
        g.setColorAt(1, QColor(255, 255, 255, 36) if a == 0 else INDIGO)
        p.setBrush(QBrush(g))
        p.setPen(QPen(white(0.22) if a < 0.5 else QColor(165, 243, 252, 150), 1))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        knob_x = 4 + 20 * self._pos
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawEllipse(QRectF(knob_x, 5, 20, 20))
        p.setBrush(QColor("#e8ecff"))
        p.drawEllipse(QRectF(knob_x, 4, 20, 20))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(white(0.8), 1.5))
            p.drawRoundedRect(r.adjusted(-1, -1, 1, 1), 14, 14)


# ------------------------------------------------------------------ depth selector
class DepthSelector(QWidget):
    """Drop-down menu with descriptive entries (title + subtitle)."""

    changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(62)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._options: List[Tuple[str, str, str]] = []  # (key, title, subtitle)
        self._current = ""
        self._hover = False

    def set_options(self, options: List[Tuple[str, str, str]]) -> None:
        self._options = options
        self.update()

    def current(self) -> str:
        return self._current

    def set_current(self, key: str) -> None:
        self._current = key
        self.update()

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.open_menu()

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_Down):
            self.open_menu()
        else:
            super().keyPressEvent(event)

    def open_menu(self) -> None:
        if not self.isEnabled() or not self._options:
            return
        menu = QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        menu.setMinimumWidth(self.width())
        menu.setFont(ui_font(14))
        menu.setStyleSheet(
            "QMenu{background:#17164a;border:1px solid rgba(255,255,255,60);border-radius:14px;padding:6px;color:#f4f6ff;}"
            "QMenu::item{padding:10px 18px 10px 12px;border-radius:9px;}"
            "QMenu::item:selected{background:rgba(94,234,212,60);}"
            "QMenu::indicator{width:16px;height:16px;}"
        )
        for key, title, sub in self._options:
            action = menu.addAction(f"{title}   ·   {sub}")
            action.setCheckable(True)
            action.setChecked(key == self._current)
            action.setData(key)
        chosen = menu.exec(self.mapToGlobal(self.rect().bottomLeft() + QPointF(0, 6).toPoint()))
        if chosen is not None:
            key = chosen.data()
            if key != self._current:
                self._current = key
                self.update()
                self.changed.emit(key)

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        if not self.isEnabled():
            p.setOpacity(0.5)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        paint_field(p, r, highlight=self.hasFocus(), hover=self._hover)
        title = sub = ""
        for key, t, s in self._options:
            if key == self._current:
                title, sub = t, s
        w = self.width() - 16 - 52
        p.setFont(ui_font(15, QFont.Weight.Bold))
        p.setPen(TEXT)
        p.drawText(QRectF(16, 10, w, 22), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), title)
        p.setFont(ui_font(12.5))
        p.setPen(white(0.65))
        p.drawText(QRectF(16, 33, w, 18), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), sub)
        draw_icon(p, "chevron", centered(self.width() - 28, self.height() / 2, 20), white(0.8), stroke=2.0)


# ------------------------------------------------------------------ title bar
class LangSwitch(QWidget):
    changed = Signal(str)

    def __init__(self, languages: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._langs = languages
        self._current = languages[0]
        self.setFixedSize(34 * len(languages) + 38, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_current(self, lang: str) -> None:
        self._current = lang
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        seg = self.width() / len(self._langs)
        idx = max(0, min(len(self._langs) - 1, int(event.position().x() // seg)))
        lang = self._langs[idx]
        if lang != self._current:
            self._current = lang
            self.update()
            self.changed.emit(lang)

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(white(0.08))
        p.setPen(QPen(white(0.12), 1))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        seg = (r.width() - 6) / len(self._langs)
        for i, lang in enumerate(self._langs):
            sr = QRectF(r.left() + 3 + i * seg, r.top() + 3, seg, r.height() - 6)
            if lang == self._current:
                g = QLinearGradient(sr.topLeft(), sr.topRight())
                g.setColorAt(0, TEAL)
                g.setColorAt(1, INDIGO)
                p.setBrush(QBrush(g))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(sr, sr.height() / 2, sr.height() / 2)
                p.setPen(INK_DARK)
            else:
                p.setPen(white(0.70))
            p.setFont(ui_font(12, QFont.Weight.ExtraBold, spacing=0.7))
            p.drawText(sr, int(Qt.AlignmentFlag.AlignCenter), lang.upper())


class WinButton(QAbstractButton):
    def __init__(self, kind: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.kind = kind
        self._hover = False
        self.setFixedSize(40, 32)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def set_kind(self, kind: str) -> None:
        self.kind = kind
        self.update()

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        r = QRectF(self.rect()).adjusted(2, 0, -2, 0)
        color = white(0.80)
        if self._hover:
            closing = self.kind == "win_close"
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(232, 17, 35, 230) if closing else white(0.12))
            p.drawRoundedRect(r, 8, 8)
            if closing:
                color = QColor("white")
        draw_icon(p, self.kind, centered(self.width() / 2, self.height() / 2, 12), color, stroke=1.4)


class TitleBar(QWidget):
    def __init__(self, window: QWidget, languages: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._window = window
        self.setFixedHeight(52)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 0, 12, 0)
        lay.setSpacing(12)
        self.logo = QWidget()
        self.logo.setFixedSize(32, 32)
        self.logo.paintEvent = lambda _e: self._paint_logo()  # type: ignore[assignment]
        lay.addWidget(self.logo)
        self.title = make_label("", 15, QFont.Weight.DemiBold, "#f4f6ff", display=True)
        lay.addWidget(self.title)
        self.version = QLabel("v1.0")
        self.version.setFont(ui_font(11, QFont.Weight.Bold))
        self.version.setStyleSheet(
            "color: rgba(255,255,255,0.75); background: rgba(255,255,255,0.10); border-radius: 10px; padding: 3px 9px;"
        )
        self.version.setFixedHeight(22)
        lay.addWidget(self.version, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)
        self.lang = LangSwitch(languages)
        if len(languages) > 1:  # the switch only appears when there is more than one language
            lay.addWidget(self.lang)
            lay.addSpacing(10)
        else:
            self.lang.hide()
        self.btn_min = WinButton("win_min")
        self.btn_max = WinButton("win_max")
        self.btn_close = WinButton("win_close")
        for b, tip in ((self.btn_min, "–"), (self.btn_max, "□"), (self.btn_close, "✕")):
            lay.addWidget(b)
        self.btn_min.clicked.connect(window.showMinimized)
        self.btn_max.clicked.connect(self._toggle_max)
        self.btn_close.clicked.connect(window.close)

    def _paint_logo(self):
        p = new_painter(self.logo)
        paint_logo(p, QRectF(self.logo.rect()))

    def _toggle_max(self):
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and not self._window.isMaximized():
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemMove()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_max()

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        p.fillRect(self.rect(), white(0.05))
        p.setPen(QPen(white(0.10), 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


# ------------------------------------------------------------------ status and ring
class StatTile(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.value = ""
        self.label = ""
        self.setFixedHeight(62)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_texts(self, value: Optional[str] = None, label: Optional[str] = None) -> None:
        if value is not None:
            self.value = value
        if label is not None:
            self.label = label
        self.update()

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(QColor(8, 12, 28, 97))
        p.setPen(QPen(white(0.10), 1))
        p.drawRoundedRect(r, 14, 14)
        p.setFont(ui_font(18, QFont.Weight.Bold, display=True))
        p.setPen(TEXT)
        p.drawText(QRectF(0, 8, self.width(), 28), int(Qt.AlignmentFlag.AlignCenter), self.value)
        p.setFont(ui_font(11))
        p.setPen(white(0.62))
        p.drawText(QRectF(0, 36, self.width(), 18), int(Qt.AlignmentFlag.AlignCenter), self.label)


class PathTicker(QWidget):
    """Shows the last folder found (monospaced text, shortened in the middle)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.text = ""
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_text(self, text: str) -> None:
        if text != self.text:
            self.text = text
            self.update()

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(QColor(8, 12, 28, 128))
        p.setPen(QPen(white(0.12), 1))
        p.drawRoundedRect(r, 12, 12)
        font = mono_font(12.5)
        p.setFont(font)
        p.setPen(QColor("#99f6e4"))
        shown = QFontMetrics(font).elidedText(self.text, Qt.TextElideMode.ElideMiddle, int(self.width() - 28))
        p.drawText(QRectF(14, 0, self.width() - 28, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), shown)


class StatusPill(QWidget):
    """Coloured dot + status text; the dot pulses while the program is working."""

    COLORS = {
        "idle": TEAL,
        "scanning": AMBER,
        "paused": AMBER,
        "exporting": INDIGO,
        "done": TEAL,
        "cancelled": ROSE,
        "error": ROSE,
    }
    PULSING = {"idle", "scanning", "exporting"}

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mode = "idle"
        self.text = ""
        self.setFixedHeight(22)
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self.update)

    def set_state(self, mode: str, text: str) -> None:
        self.mode, self.text = mode, text
        fm = QFontMetrics(ui_font(12.5, QFont.Weight.Bold))
        self.setFixedWidth(fm.horizontalAdvance(text) + 34)
        self.update()

    def showEvent(self, event):  # noqa: N802
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        color = self.COLORS.get(self.mode, TEAL)
        cy = self.height() / 2
        if self.mode in self.PULSING:
            phase = (time.monotonic() % 1.8) / 1.8
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(with_alpha(color, 0.45 * (1 - phase)))
            p.drawEllipse(QPointF(7.5, cy), 4.5 + 3.5 * phase, 4.5 + 3.5 * phase)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(QPointF(7.5, cy), 4.5, 4.5)
        p.setFont(ui_font(12.5, QFont.Weight.Bold))
        p.setPen(color.lighter(120) if color == AMBER else color)
        p.drawText(QRectF(22, 0, self.width() - 22, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text)


class ProgressRing(QWidget):
    """Animated ring: breathes at rest, spins while scanning, stops when paused."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(130, 130)
        self.setMaximumSize(210, 210)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.mode = "idle"  # idle | scanning | paused | exporting | done | cancelled
        self.count_text = ""
        self.caption = ""
        self._angle = 0.0
        self._last = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def sizeHint(self):  # noqa: N802
        return QSize(200, 200)

    def set_mode(self, mode: str, count_text: str = "", caption: str = "") -> None:
        self.mode, self.count_text, self.caption = mode, count_text, caption
        self.update()

    def set_count(self, count_text: str) -> None:
        if count_text != self.count_text:
            self.count_text = count_text
            self.update()

    def showEvent(self, event):  # noqa: N802
        self._last = time.monotonic()
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self):
        now = time.monotonic()
        dt, self._last = now - self._last, now
        if self.mode in ("scanning", "exporting"):
            self._angle = (self._angle + 360.0 * dt / 2.2) % 360.0
        self.update()

    def paintEvent(self, _event):  # noqa: N802
        p = new_painter(self)
        side = min(self.width(), self.height())
        p.translate((self.width() - side) / 2, (self.height() - side) / 2)
        p.scale(side / 200.0, side / 200.0)
        c = QPointF(100, 100)
        t = time.monotonic()
        active = self.mode in ("scanning", "exporting", "paused")

        glow = QRadialGradient(c, 100)
        glow_alpha = 0.30 if self.mode != "paused" else 0.12
        if self.mode == "idle":
            glow_alpha = 0.22 + 0.10 * math.sin(t * 1.6)
        glow.setColorAt(0.55, with_alpha(INDIGO, glow_alpha))
        glow.setColorAt(1.0, with_alpha(INDIGO, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(c, 100, 100)

        ring_rect = QRectF(c.x() - 89, c.y() - 89, 178, 178)
        p.save()
        if self.mode in ("idle", "done", "cancelled"):
            s = 1.0 + 0.018 * math.sin(t * 1.6) if self.mode == "idle" else 1.0
            p.translate(c)
            p.scale(s, s)
            p.translate(-c)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(white(0.10), 6))
        p.drawEllipse(ring_rect)
        if active:
            g = QConicalGradient(c, -self._angle)
            g.setColorAt(0.0, with_alpha(TEAL, 0))
            g.setColorAt(0.36, TEAL)
            g.setColorAt(0.69, INDIGO)
            g.setColorAt(0.93, PINK)
            g.setColorAt(1.0, with_alpha(PINK, 0))
            if self.mode == "paused":
                p.setOpacity(0.55)
        else:
            g = QConicalGradient(c, 200)
            base = ROSE if self.mode == "cancelled" else TEAL
            g.setColorAt(0.0, base)
            g.setColorAt(0.33, INDIGO)
            g.setColorAt(0.66, PINK)
            g.setColorAt(1.0, base)
        p.setPen(QPen(QBrush(g), 6))
        p.drawEllipse(ring_rect)
        p.restore()

        disc = QRadialGradient(QPointF(c.x(), c.y() - 30), 115)
        disc.setColorAt(0, QColor("#1b1f4d"))
        disc.setColorAt(1, QColor("#0b0f26"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(disc))
        p.drawEllipse(c, 83, 83)

        if self.mode == "done":
            draw_icon(p, "check", centered(c.x(), c.y(), 70), TEAL, stroke=1.6)
        elif active:
            size = 38
            fm = QFontMetrics(ui_font(size, QFont.Weight.Bold, display=True))
            while size > 18 and fm.horizontalAdvance(self.count_text) > 138:
                size -= 2
                fm = QFontMetrics(ui_font(size, QFont.Weight.Bold, display=True))
            p.setFont(ui_font(size, QFont.Weight.Bold, display=True))
            p.setPen(TEXT)
            p.drawText(QRectF(c.x() - 80, c.y() - 36, 160, 46), int(Qt.AlignmentFlag.AlignCenter), self.count_text)
            p.setFont(ui_font(12.5, QFont.Weight.DemiBold))
            p.setPen(white(0.70))
            p.drawText(QRectF(c.x() - 80, c.y() + 12, 160, 22), int(Qt.AlignmentFlag.AlignCenter), self.caption)
        else:
            draw_icon(p, "folder_search", centered(c.x(), c.y(), 76), QColor("#c7d2fe"), stroke=1.4)
