<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/a34e9bee-35db-453e-957b-fc9273e5d679" />
# FrameJoin Studio 0.21

[中文](#中文) · [English](#english)

## 中文

FrameJoin Studio 是一款 Windows/macOS 视频原码拼接与序列帧转视频工具。

### 功能

- 视频参数兼容时使用 FFmpeg `-c copy` 极速无损拼接，不重新编码。
- 序列帧支持自定义帧率，并可将多组序列按列表顺序转为视频。
- 支持 H.264 RGB 真无损、H.265 RGB 真无损、FFV1 数学无损。
- 支持 H.264/H.265 1–1000 Mbps 目标码流输出。
- 目标码流模式支持 NVIDIA NVENC、Intel Quick Sync、AMD AMF、Apple VideoToolbox；硬件失败自动回退 CPU。
- MP4、MOV、MKV 输出；视频原码拼接还可跟随兼容源容器。
- 预览不弹后台黑框，支持播放、上一帧、下一帧和拖动定位。
- 中文/English 界面，可保存和打开 `.fjproj` 工程。
- 固定内置 `splash_screen.svg` 与 `logo.svg`，运行时进行 SHA-256 校验，软件内没有替换入口。

### 安装包

推送到 `main` 会自动运行 **Build Installers**，生成：

- Windows x64 便携 ZIP。
- Windows x64 双语 EXE 安装程序。
- macOS Apple Silicon DMG/PKG。
- macOS Intel DMG/PKG。

在仓库 **Actions** 页面下载最新构建产物。推送 `v*` 标签时会自动创建 GitHub Release。

> macOS 当前采用临时签名，未配置 Apple Developer ID 公证。首次打开可能需要在“系统设置 → 隐私与安全性”中确认。

### 使用

1. 添加视频或序列帧；两类素材不能在同一任务中混合。
2. 序列帧载入时设置帧率，例如 `24`、`24000/1001`、`30000/1001`、`60`。
3. 不勾选目标码流时执行真无损输出；勾选后填写 1–1000 Mbps 并选择可用硬件编码器。
4. 选择输出文件并开始输出。

视频 `-c copy` 本身不重新编码，因此不会使用显卡。显卡只用于有损目标码流模式。

## English

FrameJoin Studio is a Windows/macOS stream-copy video joiner and image-sequence-to-video tool.

### Features

- Losslessly joins compatible video streams with FFmpeg `-c copy` and no re-encoding.
- Imports numbered image sequences with a custom FPS and joins multiple sequences in list order.
- H.264 RGB true lossless, H.265 RGB true lossless, and FFV1 mathematically lossless output.
- H.264/H.265 target-bitrate export from 1 to 1000 Mbps.
- NVIDIA NVENC, Intel Quick Sync, AMD AMF, and Apple VideoToolbox in target-bitrate mode, with automatic CPU fallback.
- MP4, MOV, and MKV output.
- Silent preview with play, previous-frame, next-frame, and scrub controls.
- Chinese/English UI and `.fjproj` project files.
- Fixed `splash_screen.svg` and `logo.svg` resources with runtime SHA-256 verification and no in-app replacement option.

### Installers

Every push to `main` runs **Build Installers** and produces:

- Windows x64 portable ZIP.
- Windows x64 bilingual EXE installer.
- macOS Apple Silicon DMG/PKG.
- macOS Intel DMG/PKG.

Download artifacts from the latest workflow run on the **Actions** page. Pushing a `v*` tag publishes the installers to a GitHub Release.

> macOS builds are currently ad-hoc signed and not notarized with an Apple Developer ID. First launch may require approval in System Settings → Privacy & Security.

### Run from source

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Place `ffmpeg` and `ffprobe` in `tools/` or on the system `PATH`. See [BUILD.md](BUILD.md) and [TESTING.md](TESTING.md).
