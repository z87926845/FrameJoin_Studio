from __future__ import annotations

import hashlib
from importlib import resources


class BrandingIntegrityError(RuntimeError):
    """Raised when a fixed branding asset was altered or is missing."""


ASSET_HASHES = {
    "splash_screen.svg": "0fe8d6c3eb2c02117f0c0ab73efdb3f20824cf8315d961b4e25e565dee7f652a",
    "logo.svg": "49960d1b37390b08cac19f1bccf4e0d04c4ad3bdd99622f903776fe76c87b08d",
}


def asset_bytes(name: str) -> bytes:
    expected = ASSET_HASHES.get(name)
    if expected is None:
        raise BrandingIntegrityError(f"Unknown branding asset: {name}")
    try:
        data = resources.files("framejoin.assets").joinpath(name).read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise BrandingIntegrityError(f"Fixed branding asset is missing: {name}") from exc
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise BrandingIntegrityError(f"Branding integrity check failed: {name}\nExpected: {expected}\nActual: {actual}")
    return data


def verify_branding() -> None:
    for name in ASSET_HASHES:
        asset_bytes(name)
