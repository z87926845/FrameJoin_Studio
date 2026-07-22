from pathlib import Path
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from PIL import Image
from PySide6.QtCore import QByteArray, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from framejoin.brand_data import asset_bytes

assets = root / "framejoin" / "assets"
renderer = QSvgRenderer(QByteArray(asset_bytes("logo.svg")))
if not renderer.isValid():
    raise SystemExit("Invalid fixed logo.svg")
image = QImage(1024, 1024, QImage.Format.Format_ARGB32)
image.fill(0)
painter = QPainter(image)
renderer.render(painter, QRectF(0, 0, 1024, 1024))
painter.end()
png = assets / "logo.png"
if not image.save(str(png), "PNG"):
    raise SystemExit("Could not render logo.png")
icon = assets / "app.ico"
Image.open(png).convert("RGBA").save(icon, format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(png)
print(icon)
