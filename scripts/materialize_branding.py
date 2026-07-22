from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from framejoin.brand_data import ASSET_HASHES, asset_bytes

assets = root / "framejoin" / "assets"
for name in ASSET_HASHES:
    target = assets / name
    target.write_bytes(asset_bytes(name))
    print(target)
