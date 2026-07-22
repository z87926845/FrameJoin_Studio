# 功能联动检查 / Functional Linkage Verification

自动测试覆盖 / Automated coverage:

- 固定启动界面与 Logo SHA-256 校验。
- 中文/English 字符串与主窗口构建。
- 视频和序列帧混合任务拦截。
- 多组序列帧顺序、分数帧率和缺帧检测。
- H.264/H.265/FFV1 真无损输出。
- H.264/H.265 目标码流命令。
- NVENC、QSV、AMF、VideoToolbox 检测与 CPU 回退。
- 视频 `-c copy` 拼接不受序列帧设置影响。
- 工程文件、静默子进程、逐帧预览。

Local FFmpeg regression passed on Linux. GitHub Actions additionally runs UI smoke tests and packaging on Windows and both macOS architectures. Real GPU encoding still requires physical machines with matching GPUs and drivers; hosted runners generally do not expose a user video-encoding GPU.
