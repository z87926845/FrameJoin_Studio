# 构建说明 / Build Guide

## 自动构建 / Automated builds

`.github/workflows/build-installers.yml` runs on pushes to `main`, manual dispatch, and `v*` tags.

输出 / Outputs:

- `FrameJoin_Studio_v0.21_Windows_x64_Portable.zip`
- `FrameJoin_Studio_v0.21_Windows_x64_Setup.exe`
- `FrameJoin_Studio_v0.21_macOS_arm64.dmg` / `.pkg`
- `FrameJoin_Studio_v0.21_macOS_Intel.dmg` / `.pkg`
- SHA-256 files

Windows 使用 PyInstaller + Inno Setup。macOS 分别在 `macos-15` 与 `macos-15-intel` 上构建，并将对应架构的 FFmpeg/ffprobe 与依赖库装入 `.app`。

Windows uses PyInstaller and Inno Setup. macOS builds run natively on `macos-15` and `macos-15-intel`, bundling the matching FFmpeg/ffprobe binaries and libraries inside the app.

## 品牌资源 / Branding

`splash_screen.svg` and `logo.svg` are fixed source resources. Runtime hashes are stored in `framejoin/brand_data.py`. `scripts/build_icon.py` renders the fixed logo into Windows ICO and macOS icon source PNG.

## 本地运行 / Local run

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python main.py
```

FFmpeg and ffprobe must be in `tools/` or `PATH`.

## macOS 签名 / macOS signing

CI uses ad-hoc signing. For public distribution, replace it with Apple Developer ID signing and notarization. CI cannot create a notarized package without the owner's Apple credentials.
