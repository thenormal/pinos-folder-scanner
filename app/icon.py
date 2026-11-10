"""Program icon, drawn in code (no image files to carry around)."""
from __future__ import annotations

import struct

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap

from .widgets import paint_logo

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def make_image(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
    paint_logo(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def app_icon() -> QIcon:
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(QPixmap.fromImage(make_image(size)))
    return icon


def write_ico(path: str) -> None:
    """Create a .ico file (for the .exe icon) with several sizes."""
    images = []
    for size in ICON_SIZES:
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        make_image(size).save(buffer, "PNG")
        buffer.close()
        images.append((size, bytes(data)))
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    blob = b""
    for size, png in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(blob))
        blob += png
    with open(path, "wb") as fh:
        fh.write(header + entries + blob)
