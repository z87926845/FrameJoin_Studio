from __future__ import annotations

from PySide6.QtGui import QIcon, QPixmap

from .brand_data import BrandingIntegrityError, asset_bytes, verify_branding


def pixmap(name: str) -> QPixmap:
    image = QPixmap()
    if not image.loadFromData(asset_bytes(name)):
        raise BrandingIntegrityError(f"Cannot decode fixed branding asset: {name}")
    return image


def application_icon() -> QIcon:
    return QIcon(pixmap("logo.png"))
