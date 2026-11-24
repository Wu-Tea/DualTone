# DualTone · 原生轻量主副音频工具

[下载 Windows 免安装版](https://github.com/Wu-Tea/DualTone/releases/tag/v0.5.2) · [完整使用说明](native-app/README.md) · [版本说明](native-app/RELEASE_NOTES.md)

把 Windows 主音频的播放内容处理后送到另一台设备，用来补充环境细节。主音频由 Windows 直接播放，音量键控制物理主设备；DualTone 仅处理副音频。

v0.5 使用 **C++20、Slint 原生 UI 和原生 WASAPI**，不再打包 Python、Qt、NumPy 或 SciPy。原生完整包保持轻量，打包脚本检查 ZIP 不超过 20 MiB。解压整个文件夹后双击 `DualTone.exe`，保留旁边的 DLL，无需另装运行环境，无需虚拟声卡。

## 功能

- v0.5.2 撤回虚拟声卡双路同步，旧同步配置恢复直出并保留副路参数；保留新版 UI。
- 重做的统一外观：深灰材质、浅蓝选中态、对齐的数值与单位；主面板、声音调节和预设窗口共用控件。支持深色、浅色、跟随系统。
- 主副设备选择、交换、刷新；直出模式播放中可切换副设备。在直出模式选择主音频时同步 Windows 普通及多媒体默认输出，通信设备不变。
- 默认空间补充与中心声量、副路音量、静音对比；新增[副路混响](docs/auxiliary-reverb.md)，可调空间大小、尾音时长和明暗，主路不受混响效果处理。
- 图上拖动十段 EQ、键盘微调、下方数值输入；独立的均衡器和多段过滤开关。
- 增删 1–8 个过滤频段，各段独立上下限、增益与开关。
- 独立预设管理：新增、载入、更新、重命名、删除、导入导出；本机音效只读检查和数字延迟测量。
- 全部 JSON CLI 命令；GUI 打开时控制同一实例，也可通过 CLI 启动无界面服务。

可读取旧版 `data/settings.json` 和预设，首次保存为 version 4 前自动留备份。退出旧实例后，把原来的 `data` 文件夹复制到新版旁即可；启动默认停止，不猜测副设备。发布包不携带个人配置。

空间补充采用 Mid/Side 处理，不是 AI 人声分离或真正的 5.1。蓝牙设备可以作为副路，但无线和设备内部缓冲仍可能明显滞后。队列显示与数字回环结果不代表声音到耳朵的总延迟。

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
.\package.ps1 -Version 0.5.2
```

原生源码在 [`native-app/`](native-app/)，许可证随发布包提供。数值回归以保留的 v0.1 Python 实现为参考，覆盖 DSP、全部受支持采样率与分包边界、配置迁移及 GUI/CLI 共享状态；实际路由另用隔离配置和数字静音验证。运行版不依赖这些 Python 测试工具。

[原生版性能实测](docs/native-performance.md)记录同机 14 轮 CPU、内存与副路延迟对比：主面板 CPU 下降约 66%，数字转发延迟中位数从 16.67 ms 降至 8.29 ms；GUI 内存没有明显下降，纯 CLI 后台工作集从约 138 MiB 降至 19 MiB。测试条件和限制见记录，不作为其他设备的性能保证。

历史 Python 源码仍保留用于对照；[v0.1 说明及算法记录](docs/python-v0.1.md)描述其旧构建方式和此前测试结果，不作为 v0.2 的性能保证。
