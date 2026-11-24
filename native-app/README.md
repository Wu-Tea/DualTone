# DualTone · 原生轻量版

Windows x64 免安装工具，C++ 音频核心 + Slint 原生界面。解压后双击 `DualTone.exe`，选择主音频和副音频，点击右上角「开始」。整个文件夹一起保留，无需安装 Python 或 Qt。无需虚拟声卡。

## 播放方式

主音频直接由 Windows 播放，系统和键盘音量控制物理主设备；DualTone 只处理副音频。虚拟声卡双路同步已撤回，应用不再给主音频添加延迟。若播放器曾固定选择 RaraAudioApp / VB-Audio，请改回系统默认或物理主音箱。

旧版同步配置读入后使用直出，保留副音频参数和预设。首次写入前保存原配置备份；CLI 请求开启 sync 会返回明确错误。

## 声音与界面

- 默认直出模式中，主音频保持直出，选择主音频或开始补声会同步 Windows 普通与多媒体默认输出；通信默认设备不变。固定选择设备的游戏仍须在游戏内改输出。
- 直出模式的副音频支持播放中切换，修改主设备前须先停止。设备格式按 Windows 原生混音格式使用，支持立体声 float32、44.1/48/88.2/96/176.4/192 kHz。
- 首页提供设备、副音量、效果、预设，以及空间模式的中心声量或混响模式的尾音时长；完整参数、频谱、EQ 和频段在「声音调节」中。
- 统一的自绘标题栏支持最小化、最大化／还原、关闭、拖动和缩放；双声波图标和关于插图直接内嵌。
- 统一的深灰与浅蓝界面，主面板、声音调节和预设窗口共用控件与材质。主菜单可选择深色、浅色或跟随系统，外观单独保存，不影响声音配置。保留托盘、静音对比与实时频谱。
- “混响”：副设备只播放效果尾音，混响效果本身不延迟主路。可调空间大小 0–100%、尾音 0.2–4 秒、明暗 0–100%，补声量使用现有副音频音量。EQ 和过滤作用于混响输入；中心声量设置保留但在混响模式不参与处理。
- “中心声量”向左减少副路居中的人声与乐器，向右保留更多。它是 Mid/Side 处理，不是人声分离或 5.1 解码。
- 十段 EQ 可直接拖动曲线频点、双击归零、用方向键以 0.1 dB 微调、或在下方输入数值。均衡器与多段过滤独立开关。
- 可增删 1–8 段过滤，各段独立上下限、增益和开关。新增段默认关闭；所有行关闭时不再输入声音（混响模式已有尾音继续衰减），关闭总开关则旁通。
- “管理预设”集中提供新增、载入、更新、重命名、删除及导入导出；更新与删除会确认。队列、电平和数字延迟测量位于菜单的「诊断」；声音调节内可检查本机音效，不改系统音效。

## 原配置与 CLI

配置仍在应用旁 `data/settings.json`，使用 version 4 格式，可读取 version 1/2/3；旧配置首次保存前保留对应版本备份。播放方式默认 direct，声音模式默认 space，升级不改变原来的听感。原来的 original 模式迁移为中心声量 100%。损坏配置不会被默认值覆盖。发布包不携带用户设备 ID 或预设。

升级时可将旧版的 `data` 文件夹复制到原生版旁。先退出使用同一配置的旧实例，再启动新版；应用不会自动启动补声或猜测副设备。

```powershell
.\DualToneCLI.exe devices
.\DualToneCLI.exe schema
.\DualToneCLI.exe get
.\DualToneCLI.exe set --json '{"gain":8,"spatial_strength":60}'
.\DualToneCLI.exe set --json '{"effect_mode":"reverb","reverb_size":40,"reverb_decay":1.2,"reverb_brightness":40}'
.\DualToneCLI.exe set --file patch.json
.\DualToneCLI.exe preset-add '我的预设'
.\DualToneCLI.exe preset-update '我的预设'
.\DualToneCLI.exe preset-rename '我的预设' '夜间'
.\DualToneCLI.exe appearance dark
.\DualToneCLI.exe preset '夜间'
.\DualToneCLI.exe start
.\DualToneCLI.exe status
.\DualToneCLI.exe latency
.\DualToneCLI.exe pause on
.\DualToneCLI.exe pause off
.\DualToneCLI.exe stop
.\DualToneCLI.exe export preset.json
.\DualToneCLI.exe import preset.json
.\DualToneCLI.exe shutdown
```

完整命令：`devices / schema / get / set / presets / preset / preset-add / preset-delete / preset-update / preset-rename / appearance / effects / start / stop / status / latency / pause / import / export / shutdown / serve`。`--data-dir 路径` 放在子命令前。GUI 打开时 CLI 控制同一实例；未打开时 start 启动无界面服务。正常响应为 UTF-8 JSON，成功退出码 0、失败 1。命名管道仅当前用户可访问，不打开网络端口。

`latency --probe` 会播放约四秒低音量测试信号；不加此参数则使用正在播放的声音。混响模式不支持数字延迟测量，须在直出与空间补充模式使用。数字回环结果不包含完整设备、无线和声学延迟，时间戳异常或相关性不足时不得当作可靠延迟。

## 体积与同步边界

原生完整包保持轻量；构建打包脚本检查 ZIP 不超过 20 MiB。通过小体积 UI 运行库和原生 DSP 达成目标，不需要用户另外下载大型运行环境。

蓝牙兼容不代表与有线音箱同步。蓝牙传输和音箱内部缓冲依然可能有明显延迟，当前版本不提供主路延迟补偿。无 AI 分离模型。队列显示不是声音到耳朵的总延迟。

## 构建

需要 Visual Studio 2022 C++ 工具和 Windows SDK。构建脚本用 vswhere 查找实际安装位置；不改全局 PATH。使用官方 Slint 1.18.1 C++ SDK 和固定版本 JSON 头文件。

```powershell
.\bootstrap.ps1
cmd /c build.cmd
.\package.ps1 -Version 0.5.2
```

bootstrap 仅下载依赖到 `vendor`，可使用已有 7-Zip 或 Bandizip 解包官方 SDK；也可通过 `-SlintSdkDirectory 路径` 指定已解压 SDK。不执行 SDK 安装程序。运行版无需这些构建工具。

`verify_native.py` 使用仓库 v0.1 Python 源码做数值对照；`verify_devices.py` 使用隔离配置与数字静音验证实际设备路由。两者均不随运行版启动。所有处理常量集中在 `core.hpp` 和相应算法定义，Slint 布局在 `ui/main.slint`。

第三方许可见 `licenses/`，关于窗口含 Slint 声明。原生核心与 UI 源码在 `source/`。
