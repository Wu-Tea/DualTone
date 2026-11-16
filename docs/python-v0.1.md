# DualTone · 主副音频路由

[下载 Windows 免安装版](https://github.com/Wu-Tea/DualTone/releases/tag/v0.1.0) · [版本说明](RELEASE_NOTES.md)

免安装 Windows x64 应用。解压整个文件夹，双击 `DualTone.exe`，选择主音频和副音频，再打开右上角开关。主音频是读取其播放内容的来源；副音频是接收处理结果的输出。主音频继续由原程序直接播放，选择主音频或开始补声时会同步 Windows 默认播放输出（普通与多媒体角色），不会插入主路同步缓冲；默认通信设备不变。固定指定输出设备的游戏仍可能需要在游戏内切换。保留 `_internal` 文件夹。无需安装 Python、Voicemeeter 或新驱动。

两条路由均可选择当前可用的立体声 float32 设备，支持 44.1 / 48 / 88.2 / 96 / 176.4 / 192 kHz，输入与输出采样率可以不同。不再按显示器名称或 48 kHz 筛选副音频。设备图标来自 Windows 的设备类型；不支持的格式会显示原因。停止时可交换主副路由；交换也会同步 Windows 默认输出。新配置不自动猜测副设备，避免意外向手柄或其他设备发声。

默认用于 Creative Pebble Pro（AUX）+ Odyssey G65B（DP）：主音箱保持直接输出；显示器只做 700–3500 Hz、8% 软件增益的轻量试听。这个比例不是两台设备实际声压比，也不是测量校准。听到人声偏向屏幕、空洞或脚步位置变散，就降低补声量，或点击“静音对比”。设备选择在主面板标为“主音频 / 副音频”。

- 主面板：设备、补声音量、静音对比、频谱与预设；支持收至托盘，托盘菜单可控制或退出。
- 空间补充默认生效，不再选择原声/空间模式。“主体保留”显示副路居中成分的保留比例：向左减少人声和居中乐器，环境细节相对突出；向右保留更多主体。它不是人声识别或分离。主音频不变，音量、EQ 和频段独立设置；参数随自定义预设保存。
- 蓝牙副音箱：在 Windows 连接后点副音频旁的“刷新”，选择它即可。副音频可在播放中切换，应用仅重启补声工作线程，不改变主设备默认输出；支持原生 44.1/48 kHz 等立体声格式。不打开蓝牙麦克风，也不为无线传输延迟增加主路延迟。设备断开时显示错误，重新连接后刷新并启动，不自动跳到其他设备。
- 详细调节：独立窗口，图上十段 EQ：拖动频点、双击归零、方向键微调，下方数值可直接输入、来源/补声实时频谱、自动预留峰值余量。
- 多段过滤：可增删 1–8 段，每段独立开关、上下限与 −24 到 +12 dB 增益。启用的频段并行混合，边界逐渐衰减；所有行关闭时副路静音，关闭总开关则旁通为全频。新增行默认关闭，避免意外改变声音。
- 预设：仅显示自己保存的配置，可新增、切换、删除。没有内置预设，也没有“当前设置”占位选项。空列表显示“尚无预设”，参数未匹配已保存预设时显示“未保存为预设”；当前参数仍会自动保存。删除预设保留当前声音设置，导入导出位于“更多”。
- 设置保存在应用旁 `data/settings.json`，正常启动默认停止。关闭应用即停止补声。
- 仅同步默认播放设备，不修改系统音量、默认通信设备、Equalizer APO 或 Rara 配置。“本机音效”可只读检查 APO 安装信息、配置内容与两端设备挂载；不能据此确认实时生效，也不覆盖游戏内部 EQ 或显示器内部处理。

## CLI / AI 控制

`DualToneCLI.exe` 是真正的控制接口：界面打开时，命令通过当前用户的本地命名管道操作同一个实例；未打开时，`start` 启动无界面后台服务。后台运行时先 `shutdown` 再打开 GUI。所有正常命令输出 UTF-8 JSON，成功退出码 0，失败退出码 1；帮助和参数用法由 `--help` 给出。

PowerShell 示例（在应用文件夹里）：

```powershell
.\DualToneCLI.exe devices
.\DualToneCLI.exe schema
.\DualToneCLI.exe get
.\DualToneCLI.exe set --json '{"spatial_mode":"space","spatial_strength":60}'
.\DualToneCLI.exe set --json '{"spatial_strength":0}' # 主体保留 100%
.\DualToneCLI.exe set --json '{"gain":8,"band_enabled":true,"low":700,"high":3500}'
.\DualToneCLI.exe preset-add '我的预设'
.\DualToneCLI.exe preset '我的预设'
.\DualToneCLI.exe start
.\DualToneCLI.exe status
.\DualToneCLI.exe latency
.\DualToneCLI.exe latency --probe
.\DualToneCLI.exe pause on
.\DualToneCLI.exe pause off
.\DualToneCLI.exe stop
.\DualToneCLI.exe export '.\my-preset.json'
.\DualToneCLI.exe import '.\my-preset.json'
.\DualToneCLI.exe shutdown
```

完整命令：`devices / schema / presets / preset / preset-add / preset-delete / effects / get / set / start / stop / status / latency / pause / import / export / shutdown / serve`。

`latency` 使用正在播放的声音做数字回环测量；`--probe` 会额外播放约四秒低音量测试信号。副音频须已启动且未静音。结果明确标记可靠性，不包含参考滤波器群延迟和未测量的设备内部/声学延迟；设备时间戳异常时拒绝报告数值。

- `set --file patch.json` 接受设置补丁，适合避免 shell JSON 转义。只更改给出的字段。
- `set` 支持 `source_id`, `target_id`, `gain`, `eq_enabled`, `gains`, `band_enabled`, `bands`, `low`, `high`；单位和范围看 `schema`。`gains` 顺序是 32、64、125、250、500、1k、2k、4k、8k、16k Hz。
- 运行中可直接切换副音频；切换主音频须先 `stop` 再 `set`。EQ、频段、增益和主体保留可实时更新。
- 导入预设保留当前设备选择；换设备必须明确 `set` 设备 ID。CLI 与 GUI 共用校验与 DSP 实现。
- `get / set / presets / preset` 在没有实例时读取/写入保存配置，并标注 `offline: true`。`status` 返回 `running:false`。
- `start` 返回启动阶段状态；再读 `status` 确认 `audio.state` 是 `running`，设备失败时会显示 `error` 和原因。
- `--data-dir 路径` 放在子命令前，用于选择配置目录。`serve` 在前台运行服务，适合外部进程管理器。
- 控制接口只监听本机当前用户，不开启网络端口。音频仅在内存处理，不录音到磁盘。

十段均衡器与频段过滤独立：关闭均衡器保留十段数值，频段过滤仍按自己的开关生效；两者都只处理副路，不会关闭系统音效。详细图中金色曲线和频点表示均衡器，虚线表示频段过滤后的响应。

新增 CLI 命令：`preset-add 名称` 保存当前设置，`preset-delete 名称` 删除自定义预设（保留当前设置），`effects` 返回本机音效的只读检测结果。

## 从源码构建（Windows x64 / Python 3.11）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\build.ps1 -PythonExecutable .\.venv\Scripts\python.exe -StageOnly
.\.venv\Scripts\python.exe package_release.py --version 0.1.0
```

发布附件生成到 `artifacts/`，包含 SHA-256 校验文件。打包只读取干净的 `staging/` 构建，不复制运行目录的 `data/`。首次运行会生成自己的配置。图形界面依赖 Windows 桌面会话。

## 参数与实现

`source/config.py` 集中定义采样率约束、滤波器阶数、EQ Q 值、预留余量、轮询周期、频谱窗口、配置大小上限和具名默认值。`source/settings.py` 定义具名预设与用户配置校验，`source/audio_engine.py` 是 GUI / CLI 共用引擎。界面编辑步长为 EQ 0.1 dB、频率 1 Hz、音量 0.1%；CLI 提交的有效值保留原精度，显示格式不会改写配置。

界面采用 Qt Quick Controls，主面板使用官方 FluentWinUI3 控件，详细调节使用 Basic 控件与统一仪表配色。频谱是 4096 帧 Hann 窗分析，约 10 Hz 刷新，仅用于显示；不加入音频输出缓冲。收至托盘后暂停频谱分析。处理曲线使用 dB 轴，频谱使用独立 dBFS 轴，曲线不含输出音量与预留余量。

主副两端按各自的 Windows 原生混音采样率打开；内部 DSP 固定为 48 kHz，输入/输出由有状态的因果多相重采样器衔接，分包边界不插入或丢失帧。96→48 kHz 保留 63 抽头、21 kHz 截止的幅频特性，改为最小相位后 500–4000 Hz 群延迟从约 0.323 ms 降至约 0.027–0.029 ms；通带幅度差小于 0.001 dB。这约 0.3 ms 的改进不是整个设备链路的延迟改善保证。频段采用 3 阶 Butterworth 原型带通；EQ 使用 RBJ 参数均衡器、Q=1.4，拟合截图的十个锚点。

自动余量是对多段混合与 EQ 的总频率响应峰值再留至少 1 dB，不是限制器，也不保证任何输入瞬态都不会超出满幅。默认补声增益很低。高音量试听需自己合理调整。

## 同步与边界

应用不延迟主音箱。WASAPI 按实际包长度提交，避免多提交未写入的帧；原生格式转发避免额外系统重采样。捕获使用 WASAPI 音频就绪事件，数据到达即唤醒，不再使用 Windows 上会把 0.5 ms 等待拉长到约 15 ms 的通用线程超时。100 ms 空闲超时只用于无音频时检查停止，不会让到达的音频等待 100 ms。事件回环捕获要求 Windows 10 1703 或更新系统。

此前事件捕获版用相同的 700–3500 Hz 设置做数字回环对照：修复前两次约 25.0 ms；事件捕获版经过三次重启及每轮持续播放，六次测得 5.46–11.84 ms（匹配 DSP 的相关测量，排除参考滤波器群延迟）。这是此前版本的本机结果，不是新版界面重新测得的保证值。

G65B 的 IAudioClient3 共享周期仍为 480 帧（10 ms），新旧共享接口缓冲容量均为 1056 帧（22 ms），没有切换到无收益的新接口。独占模式试验出现队列增长，没有作为正式路径启用。实时工作线程注册 Windows MMCSS Pro Audio 调度，退出时解除；不改变全局计时器或进程优先级。

USB 音源曾返回异常的回环帧位置与 QPC 时间戳，两种独立绑定得到一致异常；系统重启后恢复。恢复后的既有路径三次数字转发测量为 3.60–6.24 ms，先填首包再启动的试验约 10 ms，后者未采用。工作线程与 CLI 会检查时间戳有效性，不硬减偏移量或拿主机接收时间冒充设备时间。界面队列不等于两路实际声音的延迟。

通用路由版本的后续实测为 11.06–13.31 ms，不能把前面的最低结果当作稳定保证；这次更新尚未解决两路听感不同步。测试中时间戳有效、无捕获断流，主设备默认输出及两端系统音量保持不变。48 kHz → 96 kHz 反向路由也已用零输出增益验证。20 项自动化测试及打包版 GUI/CLI 联动检查通过。

队列长度不等于声音到耳朵的延迟。G65B 内部 DSP、Pebble Pro 内部处理及距离没有通过麦克风测量，不能承诺声学零延迟或精准相位对齐。

同一频段包含多种声音。频段过滤无法只提取脚步；这个应用没有实现 Rara 的专有检测、压缩或环绕渲染。

空间补充采用 Mid/Side 矩阵：M=(L+R)/2，S=(L−R)/2，输出为 kM+S、kM−S。CLI 的 spatial_strength 为 0–100%，对应 Mid 衰减 0–12 dB，Side 不放大。界面的主体保留百分比为 100×10^(−12×spatial_strength/100/20)，约 25–100%，100% 为不削弱主体。旧 original 模式配置迁移为主体保留 100%，保持旧预设声音；新配置默认空间强度 60%。变化在 10 ms 内平滑改变系数，不缓存或延迟音频样本。参数集中在 config.py。空间补充不是人声分离或独立后方声道，偏向一边的人声仍可能保留，实际效果取决于素材及摆位。其数学原理参考 [FabFilter Mid/Side 文档](https://www.fabfilter.com/help/pro-g/using/midsideprocessing)。

依赖及开源声明在 `licenses`，源码和锁定依赖版本在 `source`。构建脚本通过 `-PythonExecutable` 显式选择 Python，默认使用命令行可发现的 `python`，没有开发机器的固定路径。运行免安装版不依赖 Python。

## 多段配置与旧版兼容

`bands` 是完整频段数组；每行使用 `low` / `high`（Hz）、`gain_db`（dB）、`enabled`（布尔值）。`set --file patch.json` 可提交下列结构（示例不会自动应用）：

```json
{"band_enabled":true,"bands":[{"low":700,"high":1500,"gain_db":0,"enabled":true},{"low":2000,"high":5000,"gain_db":-6,"enabled":true}]}
```

旧版 `low` / `high` 命令只修改第一段，其他段保留；读取时也是第一段的兼容投影。新版格式为 version 2，导入继续支持 version 1。首次保存旧配置时保留原文件到 `data/settings.v1.backup.json`，已有自定义预设一并迁移。0 Hz 或无效范围不会应用，输入框提交或失焦时恢复实际值。频率没有负数；负 dB 表示衰减。

各段增益是混合前的相对权重；总响应超过 0 dB 时整体降低预增益并另留 1 dB，所以提升一段并不意味着输出等量变响。重叠处有相位叠加，图中虚线显示实际混合响应；它不表示理想矩形频段的并集。

多段过滤没有新增队列或前瞻等待，但滤波器仍有群延迟。特别窄的频段会拖长瞬态：当前算法的 700–800 Hz 带通在中心约有 6.37 ms 群延迟，而 700–1500 Hz 约 0.80 ms、2000–5000 Hz 约 0.21 ms；这些是滤波器计算值，不是整机或声学延迟。不能把数字转发的低读数当作实际声音完全同步。

脚步、听感偏好及同类应用研究见随包的《脚步与听感研究.md》。没有新增内置预设或自动套用网上曲线。
