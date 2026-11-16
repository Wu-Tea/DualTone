# DualTone · 原生轻量主副音频工具

[下载 Windows 免安装版](https://github.com/Wu-Tea/DualTone/releases/tag/v0.2.1) · [完整使用说明](native-app/README.md) · [版本说明](native-app/RELEASE_NOTES.md)

把 Windows 主音频的播放内容处理后送到另一台设备，用来补充环境细节。主音频继续由原程序直接播放，DualTone 只处理副路，不给主路增加同步延迟。

v0.2 使用 **C++20、Slint Fluent UI 和原生 WASAPI**，不再打包 Python、Qt、NumPy 或 SciPy。完整 ZIP 约 **15.3 MiB**，解压约 **31.9 MiB**；打包脚本检查 ZIP 不超过 20 MiB。解压整个文件夹后双击 `DualTone.exe`，保留旁边的 DLL，无需另装运行环境或驱动。

## 保留的功能

- 紧凑主面板、独立深色声音调节窗口、系统明暗主题、实时频谱和托盘。
- 主副设备选择、交换、刷新；播放中可切换副设备。选择主音频时同步 Windows 普通及多媒体默认输出，通信设备不变。
- 默认空间补充与主体保留、副路音量、静音对比。
- 图上拖动十段 EQ、键盘微调、下方数值输入；独立的均衡器和多段过滤开关。
- 增删 1–8 个过滤频段，各段独立上下限、增益与开关。
- 自定义预设增删、导入导出、本机音效只读检查、数字延迟测量。
- 全部 JSON CLI 命令；GUI 打开时控制同一实例，也可通过 CLI 启动无界面服务。

旧版 `data/settings.json` 和预设格式兼容。退出旧实例后，把原来的 `data` 文件夹复制到新版旁即可；启动默认停止，不猜测副设备。发布包不携带个人配置。

空间补充采用 Mid/Side 处理，不是 AI 人声分离或真正的 5.1。蓝牙设备可以作为副路，但无线和设备内部缓冲仍可能明显滞后；本应用不会延迟主路来对齐。队列显示与数字回环结果不代表声音到耳朵的总延迟。

## CLI 示例

```powershell
.\DualToneCLI.exe devices
.\DualToneCLI.exe schema
.\DualToneCLI.exe set --json '{"gain":8,"spatial_strength":60}'
.\DualToneCLI.exe start
.\DualToneCLI.exe status
.\DualToneCLI.exe pause on
.\DualToneCLI.exe shutdown
```

所有设置范围、命令和迁移说明见 [原生版文档](native-app/README.md)。控制接口仅当前用户可访问，不打开网络端口。

## 构建与验证

需要 Visual Studio 2022 C++ 工具和 Windows SDK。固定版本依赖下载到项目内，不改变全局 PATH：

```powershell
cd native-app
.\bootstrap.ps1
cmd /c build.cmd
.\package.ps1 -Version 0.2.1
```

原生源码在 [`native-app/`](native-app/)，许可证随发布包提供。数值回归以保留的 v0.1 Python 实现为参考，覆盖 DSP、全部受支持采样率与分包边界、配置迁移及 GUI/CLI 共享状态；实际路由另用隔离配置和数字静音验证。运行版不依赖这些 Python 测试工具。

[原生版性能实测](docs/native-performance.md)记录同机 14 轮 CPU、内存与副路延迟对比：主面板 CPU 下降约 66%，数字转发延迟中位数从 16.67 ms 降至 8.29 ms；GUI 内存没有明显下降，纯 CLI 后台工作集从约 138 MiB 降至 19 MiB。测试条件和限制见记录，不作为其他设备的性能保证。

历史 Python 源码仍保留用于对照；[v0.1 说明及算法记录](docs/python-v0.1.md)描述其旧构建方式和此前测试结果，不作为 v0.2 的性能保证。
