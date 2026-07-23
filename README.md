<img width="720" height="405" alt="FrameJoin Studio" src="https://github.com/user-attachments/assets/3523e618-e5b2-43bb-a284-999b5f289174" />

# FrameJoin Studio 0.24

[中文](#中文) · [English](#english)

## 中文

FrameJoin Studio 是一款 Windows/macOS 视频原码拼接与序列帧转视频工具，重点提供无损处理、真实帧率组合预览和可选显卡编码。

### 主要功能

- 视频参数兼容时使用 FFmpeg `-c copy` 极速无损拼接，不解码、不重新编码。
- 多段视频或多组序列帧可按素材列表顺序整体预览；也可切换为仅预览所选片段。
- 预览按每段素材的实际时间轴运行，支持 `24000/1001`、`30000/1001`、`60000/1001` 等分数帧率。
- 视频预览优先使用 Qt/系统媒体后端的硬件解码，不可用时自动回退软件解码。
- 序列帧预览使用高精度计时、缩放读取和 32 帧缓存；电脑来不及显示所有帧时会跳过预览帧以保持真实播放速度。
- 支持上一帧、下一帧、拖动定位和按排序后的组合时间线预览。
- 序列帧输出帧率使用可编辑下拉框，内置常用整数和分数帧率，也可手动输入。
- 支持 H.264 RGB 真无损、H.265 真无损和 FFV1 数学无损输出。
- 支持 H.264/H.265 1–1000 Mbps 目标码流有损输出。
- 有损设置始终显示但默认置灰；勾选“启用有损输出”后才能编辑码流和显卡编码。
- 有损输出支持 NVIDIA NVENC、Intel Quick Sync、AMD AMF 和 Apple VideoToolbox；只显示或启用通过本机实际试编码检测的后端，失败自动回退 CPU。
- 支持 MP4、MOV、MKV；视频原码拼接还可跟随兼容源容器。
- FFmpeg、ffprobe 在 Windows 后台运行时不弹黑色控制台窗口。
- 中文/English 双语界面，可保存和打开 `.fjproj` 工程。
- 固定启动界面和 Logo 进行 SHA-256 完整性校验，软件内不提供替换入口。

### CPU、GPU 与无损模式

- **视频原码拼接**：使用 `-c copy`，不进行编码，因此既不是 CPU 编码，也不是 GPU 编码。
- **序列帧真无损输出**：H.264 RGB、H.265 Lossless、FFV1 当前使用 CPU，以保证像素和颜色路径可靠。
- **目标码流有损输出**：可使用 NVENC、Quick Sync、AMF 或 VideoToolbox；不可用或执行失败时回退 CPU。
- **视频预览**：系统媒体后端会自动尝试硬件解码；这与导出设置中的“显卡编码”是两套独立路径。
- **序列帧预览**：瓶颈通常是图片读取、解码和缩放，主要依靠缓存与预读，而不是显卡编码。

### 预览规则

1. 组合预览严格遵循左侧素材从上到下的顺序。
2. 上移或下移素材后，组合时间线同步更新。
3. 每一段按自身实际帧率或时间戳播放，不强制转换为统一 30 fps。
4. 24/25/30/50/60 fps 以及 NTSC 分数帧率都会保持正确时间速度。
5. 120 fps 或高分辨率素材超出显示/解码能力时，预览允许丢帧，但不会把整段播放成慢动作。

### 安装包

推送到 `main` 会自动运行 **Build Installers**，生成：

- Windows x64 便携 ZIP。
- Windows x64 双语 EXE 安装程序。
- macOS Apple Silicon DMG/PKG。
- macOS Intel DMG/PKG。

构建成功后，安装文件先出现在 Actions Artifacts；发布工作流会创建或更新对应版本的 GitHub Release。

> macOS 当前采用临时签名，未配置 Apple Developer ID 公证。首次打开可能需要在“系统设置 → 隐私与安全性”中确认。

### 基本使用

1. 添加视频或序列帧；两类素材不能在同一任务中混合。
2. 拖动排序，使用“按列表顺序整体预览”检查最终顺序。
3. 序列帧可选择或输入 `24`、`24000/1001`、`30000/1001`、`60` 等帧率。
4. 默认执行真无损输出；需要控制文件大小时，主动勾选有损输出并填写 1–1000 Mbps。
5. 选择输出文件并开始输出。

## English

FrameJoin Studio is a Windows/macOS stream-copy video joiner and image-sequence-to-video tool focused on lossless processing, real-frame-rate combined preview, and optional GPU encoding.

### Main Features

- Losslessly joins compatible video streams with FFmpeg `-c copy`, without decoding or re-encoding.
- Previews multiple videos or image sequences in the exact order shown in the media list, with an optional selected-clip-only mode.
- Preserves each clip's real timeline, including fractional rates such as `24000/1001`, `30000/1001`, and `60000/1001`.
- Video preview uses Qt/system media backends, which automatically attempt hardware decoding and fall back to software decoding.
- Image-sequence preview uses a precise elapsed-time clock, scaled image reads, and a 32-frame cache. It may skip preview frames to preserve real-time speed when the computer cannot display every frame.
- Previous-frame, next-frame, scrubbing, and ordered combined-timeline preview.
- Editable output-FPS combo box with common integer/fractional presets and custom input.
- H.264 RGB true lossless, H.265 true lossless, and FFV1 mathematically lossless output.
- H.264/H.265 target-bitrate lossy export from 1 to 1000 Mbps.
- Lossy controls remain visible but disabled by default. Bitrate and GPU encoding become editable only after enabling lossy export.
- NVIDIA NVENC, Intel Quick Sync, AMD AMF, and Apple VideoToolbox for lossy export. Backends are enabled only after a real local encoding probe; failures fall back to CPU.
- MP4, MOV, and MKV output.
- Silent FFmpeg/ffprobe background processes on Windows.
- Chinese/English UI and `.fjproj` project files.
- Fixed splash screen and logo protected by SHA-256 integrity verification, with no in-app replacement option.

### CPU, GPU, and Lossless Modes

- **Video stream-copy join** uses `-c copy`; it is neither CPU encoding nor GPU encoding.
- **True-lossless image-sequence export** currently uses CPU encoders for reliable pixel and colour handling.
- **Target-bitrate lossy export** may use NVENC, Quick Sync, AMF, or VideoToolbox and falls back to CPU when needed.
- **Video preview** may use hardware decoding through the operating-system media backend. Preview decoding and export encoding are separate paths.
- **Image-sequence preview** is normally limited by storage, image decoding, and scaling, so caching and prefetching matter more than GPU encoding.

### Preview Behaviour

1. Combined preview follows the media list from top to bottom.
2. Moving clips up or down immediately changes the combined timeline.
3. Every segment keeps its own frame rate or timestamps; preview is not forced to 30 fps.
4. Integer and NTSC fractional rates retain correct playback speed.
5. For 120 fps or very large media, preview may drop display frames while keeping the timeline in real time rather than slowing down.

### Installers

Every push to `main` runs **Build Installers** and produces:

- Windows x64 portable ZIP.
- Windows x64 bilingual EXE installer.
- macOS Apple Silicon DMG/PKG.
- macOS Intel DMG/PKG.

Successful builds first appear as Actions Artifacts. The publishing workflow creates or updates the matching GitHub Release.

> macOS builds are currently ad-hoc signed and not notarized with an Apple Developer ID. First launch may require approval in System Settings → Privacy & Security.

### Run from Source

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Place `ffmpeg` and `ffprobe` in `tools/` or on the system `PATH`. See [BUILD.md](BUILD.md) and [TESTING.md](TESTING.md).
