from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

EXPECTED_SHA256 = "907c9771b5ce0582dc8d83e35ca3cdb9dd176552ef343842a1f7392118f178b7"
ARCHIVE_PREFIX = "FrameJoin_Studio_v0.19_Source.zip.part"
SOURCE_ROOT = "FrameJoin_Studio_v0.19_Source"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parent
    parts_dir = root / "source_parts"
    parts = sorted(parts_dir.glob(f"{ARCHIVE_PREFIX}*"))
    if not parts:
        print("未找到 source_parts 中的源码分卷。")
        return 1

    with tempfile.TemporaryDirectory(prefix="framejoin_source_") as temp_name:
        temp = Path(temp_name)
        archive = temp / "FrameJoin_Studio_v0.19_Source.zip"
        with archive.open("wb") as output:
            for part in parts:
                output.write(part.read_bytes())

        actual = sha256_file(archive)
        if actual != EXPECTED_SHA256:
            print("源码包校验失败。")
            print(f"预期：{EXPECTED_SHA256}")
            print(f"实际：{actual}")
            return 2

        unpack = temp / "unpack"
        with zipfile.ZipFile(archive) as source_zip:
            source_zip.extractall(unpack)
        source = unpack / SOURCE_ROOT
        if not (source / "main.py").is_file() or not (source / "framejoin" / "ui.py").is_file():
            print("源码包结构不完整。")
            return 3

        target_package = root / "framejoin"
        if target_package.exists():
            shutil.rmtree(target_package)
        shutil.copytree(source / "framejoin", target_package)

        for name in (
            "main.py",
            "sitecustomize.py",
            "requirements.txt",
            "THIRD_PARTY_NOTICES.txt",
            ".gitignore",
        ):
            shutil.copy2(source / name, root / name)

    print("FrameJoin Studio 0.19 完整源码已校验并展开到仓库根目录。")
    print("接下来可执行：pip install -r requirements.txt")
    print("然后执行：python main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
