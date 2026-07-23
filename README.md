<img width="720" height="405" alt="FrameJoin Studio" src="https://github.com/user-attachments/assets/3523e618-e5b2-43bb-a284-999b5f289174" />

# FrameJoin Studio 0.25

[中文](#中文) · [English](#english)

## 中文

FrameJoin Studio 是一款 Windows/macOS 视频拼接与序列帧处理工具，提供原码无损拼接、视频转码拼接、序列帧转视频和连续序列帧输出。

### 0.25 主要变化

- 修复两段或多段视频组合预览在片段边界反复停留下一段首帧的问题。
- 视频切段使用一次性异步加载事务，忽略上一段延迟到达的 `EndOfMedia` 与位置事件。
- 两段、三段及更多视频按左侧列表顺序连续预览。
- 多组序列帧继续使用独立的高精度时间线，按实际帧率跨段播放。
- 视频默认仍使用 FFmpeg `-c copy` 极速原码拼接，不解码、不重新编码。
- 可主动勾选“启用视频转码输出”，使用 H.264/H.265、1–1000 Mbps、CPU 或 GPU 编码。
- 视频转码可跟随第1段帧率或输入自定义整数/分数帧率。
- 视频转码音频支持 AAC 320 kbps、原音频复制（仅参数一致）或无音频。
- 序列帧新增“输出为连续序列帧”：不修改源文件、不重新编码图像，按素材列表顺序复制到新目录并连续编号。
- 连续序列帧可设置文件名前缀、起始编号和编号位数。
- 连续序列帧先写入同级临时目录，全部成功后再整体切换为最终目录，取消或失败不会留下半套正式编号文件。

### 输出模式

#### 视频

1. **极速原码拼接（默认）**
   - 使用 `-c copy`。
   - 画质与音频码流完全不变。
   - 不能调整码流或编码格式。
   - 要求各段关键流参数一致。

2. **视频转码拼接**
   - H.264 或 H.265。
   - 1–1000 Mbps。
   - CPU、NVIDIA NVENC、Intel Quick Sync、AMD AMF、Apple VideoToolbox。
   - 不同编码、分辨率或帧率的视频可统一为第1段分辨率和指定帧率。
   - 属于重新编码，不再是原码无损。

#### 序列帧

1. **连续序列帧**
   - 原图文件字节保持不变。
   - 不在原目录改名，不覆盖源文件。
   - 第一段结束后，第二段从下一个编号继续。
   - 默认示例：`frame_000001.png`、`frame_000002.png`……
   - 各段需使用相同图像扩展名、分辨率、像素格式/位深和透明通道状态。

2. **真无损视频**
   - H.264 RGB 真无损。
   - H.265 Lossless。
   - FFV1 数学无损。
   - 当前使用 CPU，以保证颜色和像素路径可靠。

3. **目标码流视频**
   - H.264/H.265，1–1000 Mbps。
   - 可使用 GPU，失败自动回退 CPU。
   - 属于有损压缩。

### 组合预览

- 按素材列表从上到下播放。
- 支持仅预览所选片段。
- 每段保持自身实际时间轴。
- 支持 `24000/1001`、`30000/1001`、`60000/1001` 等分数帧率。
- 视频预览使用 Qt/系统媒体后端，自动尝试硬件解码。
- 序列帧预览使用高精度计时、缩放读取和缓存；设备跟不上时允许跳过显示帧，但保持正确播放速度。

### 构建产物

推送到 `main` 自动生成：

- Windows x64 便携 ZIP。
- Windows x64 双语 EXE 安装程序。
- macOS Apple Silicon DMG/PKG。
- macOS Intel DMG/PKG。
- 每个文件对应的 SHA-256 校验文件。

## English

FrameJoin Studio is a Windows/macOS video joining and image-sequence processing tool with stream-copy joining, video transcode joining, image-sequence-to-video export, and continuous image-sequence output.

### What is new in 0.25

- Fixes combined video preview getting stuck on the first frame of the next clip at clip boundaries.
- Uses a one-shot asynchronous source transition and ignores stale end/position events from the previous clip.
- Supports continuous ordered preview across two, three, or more video clips.
- Image sequences keep their independent precise real-FPS timeline across segment boundaries.
- Video still defaults to FFmpeg `-c copy` stream-copy joining.
- An explicit “Enable Video Transcode Output” option adds H.264/H.265, 1–1000 Mbps, CPU/GPU encoding, source/custom frame rate, and audio processing.
- Video audio can be AAC 320 kbps, copied unchanged when all streams match, or omitted.
- Image sequences can now be exported as one continuously numbered sequence without modifying or re-encoding the source images.
- Continuous sequence output supports filename prefix, start number, and numeric padding.
- Frames are copied into a sibling staging directory and atomically promoted only after every file succeeds.

### Output modes

#### Video

1. **Fast stream-copy join (default)**
   - Uses `-c copy`.
   - Preserves original video/audio bitstreams.
   - Bitrate and codec cannot be changed.
   - Requires matching critical stream parameters.

2. **Video transcode join**
   - H.264 or H.265.
   - 1–1000 Mbps.
   - CPU, NVIDIA NVENC, Intel Quick Sync, AMD AMF, or Apple VideoToolbox.
   - Mixed codec/resolution/frame-rate inputs are normalized to the first clip resolution and selected frame rate.
   - This is re-encoding, not lossless stream copy.

#### Image sequences

1. **Continuous image sequence**
   - Preserves original image bytes.
   - Never renames or overwrites source files.
   - The next segment continues with the next frame number.
   - Example: `frame_000001.png`, `frame_000002.png`, ...
   - Segments must share image extension, resolution, pixel format/bit depth, and alpha state.

2. **True-lossless video**
   - H.264 RGB true lossless.
   - H.265 lossless.
   - FFV1 mathematically lossless.
   - CPU encoders are used for reliable colour and pixel handling.

3. **Target-bitrate video**
   - H.264/H.265 at 1–1000 Mbps.
   - May use GPU encoding with CPU fallback.
   - This mode is lossy.

### Preview

- Plays media from top to bottom in list order.
- Optional selected-clip-only mode.
- Preserves each segment's actual timeline.
- Supports fractional rates such as `24000/1001`, `30000/1001`, and `60000/1001`.
- Video preview uses Qt/system media backends and automatically attempts hardware decoding.
- Sequence preview uses a precise clock, scaled reads, and caching; it may skip display frames to maintain real-time speed.

### Installer outputs

Every push to `main` builds:

- Windows x64 portable ZIP.
- Windows x64 bilingual EXE installer.
- macOS Apple Silicon DMG/PKG.
- macOS Intel DMG/PKG.
- SHA-256 files for every artifact.
