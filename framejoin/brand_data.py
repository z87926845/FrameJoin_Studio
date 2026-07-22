from __future__ import annotations

import hashlib
from importlib import resources


class BrandingIntegrityError(RuntimeError):
    """Raised when a fixed branding asset was altered or is missing."""


ASSET_HASHES = {
    "splash_screen.svg": "4f3a6ec9424c991a82307ef21ae6815d3ac8b17606a584f1b1d586d9d163212c",
    "logo.svg": "6a4cea791502a953b01e50aec34e9ec098f027d581514ca8b591186b5b639f12",
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
        raise BrandingIntegrityError(
            f"Branding integrity check failed: {name}\nExpected: {expected}\nActual: {actual}"
        )
    return data


def verify_branding() -> None:
    for name in ASSET_HASHES:
        asset_bytes(name)
