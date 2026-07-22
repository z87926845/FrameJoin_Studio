# FrameJoin Studio 0.19 · 极速拼接与序列帧转视频

这是 Windows x64 视频原码拼接与序列帧转视频工具。

## 核心功能

- **视频极速无损拼接**：参数兼容的视频使用 FFmpeg `-c copy` 原码流复制，不重新编码。
- **序列帧转视频**：支持 PNG、JPG、TIFF、TGA、BMP、DPX、EXR、WebP、JXL 等编号序列。
- **输入帧率设置**：载入时可设置，也可在右侧统一应用到全部序列。
- **两种序列输出模式**：
  - 取消勾选“按目标码流输出”：按所选 H.264、H.265 或 FFV1 进行真无损输出。
  - 勾选“按目标码流输出”：填写 1–1000 Mbps，H.264/H.265 按目标码流压缩输出。
- **容器支持**：MP4、MOV、MKV；FFV1 使用 MOV 或 MKV。
- **静默预览加载**：FFmpeg/ffprobe 后台进程不弹黑色控制台窗口。
- **逐帧检查**：预览区提供“上一帧”“下一帧”按钮，并支持左右方向键。

## 使用方法

### 视频极速拼接

1. 拖入两段或更多参数一致的视频。
2. 调整列表顺序。
3. 选择输出容器。
4. 点击“开始无损拼接”。

### 序列帧转视频

1. 点击“添加序列帧”，选择序列中的任意一帧。
2. 设置输入帧率，例如 `24`、`25`、`30000/1001`、`60`。
3. 多组序列会按列表顺序连接；所有序列需要相同分辨率、帧率、像素格式和透明通道状态。
4. 选择 H.264、H.265 或 FFV1，以及 MP4、MOV 或 MKV。
5. 直接无损输出时不勾选“按目标码流输出”；需要控制文件大小时勾选并填写目标码流。
6. 点击“开始序列帧转视频”。

## 输出模式说明

- **H.264 直接无损**：`libx264rgb -crf 0`，保持 8-bit RGB 像素，但部分硬件播放器不能硬解。
- **H.265 直接无损**：`libx265 lossless` 与 RGB 4:4:4，压缩率通常优于无损 H.264。
- **FFV1 数学无损**：适合高位深、透明通道、归档和后期。
- **目标码流模式**：H.264/H.265 使用填写的目标码流及峰值限制进行压缩，属于有损输出；更适合控制文件大小和普通播放。
- MP4 不支持 FFV1，因此 FFV1 请使用 MOV 或 MKV。

## 获取完整源码

仓库中的 `source_parts/` 保存经过 SHA-256 校验的 0.19 完整源码包分卷。克隆仓库后，在 Windows 上双击：

```text
extract_source.bat
```

也可以在命令行执行：

```bash
python extract_source.py
```

脚本会依次完成：

1. 合并源码分卷。
2. 校验完整源码包 SHA-256：`907c9771b5ce0582dc8d83e35ca3cdb9dd176552ef343842a1f7392118f178b7`。
3. 将完整的 `framejoin/`、`main.py`、依赖清单和授权说明展开到仓库根目录。

仓库同时保留了 `.github/workflows/publish-source.yml`，也可在 GitHub Actions 页面手动运行 **Expand source archive**。

## 源码运行

1. 安装 Python 3.12。
2. 首次克隆先运行 `extract_source.bat` 或 `python extract_source.py`。
3. 执行 `pip install -r requirements.txt`。
4. 将 `ffmpeg.exe`、`ffprobe.exe` 和可选的 `ffplay.exe` 放入 `tools/` 目录，或加入系统 `PATH`。
5. 执行 `python main.py`。

## 便携版说明

完整 Windows 便携包包含 FFmpeg、Qt 和 Python 运行库，约 188 MB，超过 GitHub 普通单文件 100 MB 限制，因此仓库保存源码、校验值与构建说明，便携包单独提供下载。
