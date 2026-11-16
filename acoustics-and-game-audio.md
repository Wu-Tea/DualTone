# 脚步增强、听感偏好与 DualTone 的取舍

研究日期：2026-11-16。针对 Pebble Pro 主音频 + G65B 副音频。以下频段是试听建议，不是三款游戏的录音测量结果，也没有自动写入用户配置。

## 脚步不是一个固定频率

脚步的冲击、主体与摩擦细节分布在不同区域，同区域也有枪声、语音和环境音。SteelSeries 的一般说明将脚步等主要信息放在宽泛的 250 Hz–4 kHz 中频范围；Audeze 官方脚步预设同时使用低频和中频的增减。两者都不能推出一个通用的“只保留脚步”带通。[SteelSeries](https://steelseries.com/blog/best-eq-settings-for-gaming)、[Audeze](https://www.audeze.com/pages/maxwell-user-guide)

| 游戏 | 官方资料确认的影响因素 | 对配置的含义 |
|---|---|---|
| 使命召唤（以 BO6 为例） | 反射、材质、遮挡、声音优先级及耳机 HRTF 共同参与 | 同一脚步的频谱会随场景变化；耳机空间处理不能当作扬声器 EQ 曲线直接复制 |
| THE FINALS | 12.0 更新重混脚步，调整不同地面、体型、上下楼及敌我线索 | 更新前的网络预设可能不适合更新后的混音；需要用当前版本比较 |
| 战地（以 BF6 为例） | 大场面音频优先级、性能和遮挡影响脚步，部分问题涉及素材没有播放 | 外部 EQ 只能处理游戏已经输出的信号，无法恢复未播放的脚步 |

来源：[COD 音频团队说明](https://www.callofduty.com/blog/2024/10/call-of-duty-black-ops-6-dynamic-soundscape-audio-intel)、[THE FINALS 12.0](https://www.reachthefinals.com/patchnotes/12-00)、[Battlefield 音频改进](https://www.ea.com/games/battlefield/battlefield-6/news/battlefield-6-community-update-ongoing-quality-of-life-improvements)。这些资料没有给出可通用于该系列所有作品的脚步 EQ 系数。

建议先把不同线索分开试听：150–400 Hz 作为低频冲击观察区，700–1500 Hz 作为中频主体观察区，2000–5000 Hz 作为摩擦和清晰度观察区。这个划分是本项目的调试假设，具体声音会跨区，不能据此识别敌我。

对于当前硬件，低频主要交给 Pebble Pro；显示器先试听 700–1500 Hz，再单独试听 2000–5000 Hz，第二段可先用 −6 dB 相对权重。不要一开始把三段都放大。保持游戏和主音量相同，比较副路静音、仅第一段、仅第二段、两段混合四种状态，分别判断是否更早听清、方向是否更准、枪声是否更刺耳。需要同时满足前两项才值得保留。

## 人更喜欢哪些频段？

这里有三个不同问题：听觉敏感度、完整音色的偏好、特定线索的可辨识度。

人耳在中高频一带较敏感；UNSW 的声学说明给出约 1–4 kHz 的高敏感区域，并指出实际测试依赖耳机与声卡校准。这不意味着该区域越响越舒服。[UNSW 声学教学](https://www.phys.unsw.edu.au/jw/hearing.html)

ISO 226 的等响曲线研究的是不同频率的连续纯音需要多大声压才听起来同样响。它不是喜好调查，更不能直接反转成游戏或音乐的万能 EQ。[ISO 226:2023](https://www.iso.org/standard/83117.html)

Harman 作者的受控耳机研究发现平均偏好与目标曲线有关，同时存在不同听众群体。可借鉴的是“完整平衡 + 个体试听”的方法；耳机目标不是 G65B 在房间里的补偿曲线。[AES 2019 偏好研究](https://aes.org/publications/elibrary/elibrary-page/?id=20289)

因此日常悦耳和竞技清晰应分别保存为自己的配置。日常调整评价整体平衡；竞技调整评价遮蔽、瞬态与定位。比较时尽量匹配总体响度，避免只因为更响就判断更好。没有麦克风测量的显示器补声仍是主观调整，不是硬件校准。

## 常见增强应用在做什么

| 应用 | 可核实的方法 | 可以学习的部分与当前边界 |
|---|---|---|
| SteelSeries Sonar | 分开 Game、Chat、Media 等音频通道，每通道参数 EQ | 按用途分配处理、展示可编辑参数；DualTone 当前读取主设备混音，不做应用分流 |
| FxSound | EQ、Clarity/Bass 音色调整、Dynamic Boost、Ambience/Surround | 将音色、响度、空间分开控制，避免一个模糊的“增强”开关 |
| Creative Scout Mode | 专有实时算法强调脚步、换弹等线索 | 可学习目标，公开资料不足以复刻内部系数或保证自动分离脚步 |
| Rara | 本机此前静态检查发现 APO/VST、压缩、环境处理与空间渲染相关链路 | 可学习处理分工；不把安装包中的组件名当作已知完整算法 |

来源：[Sonar 官方支持](https://support.steelseries.com/hc/en-us/articles/16954265292173-How-does-Sonar-work)、[FxSound 官方效果指南](https://forum.fxsound.com/t/how-to-use-fxsound-effects/6332)、[Creative Scout Mode](https://us.creative.com/technology/scoutmode/)。Rara 本机证据见同目录《硬件与研究.md》，没有复制其二进制组件到 DualTone。

FxSound 工程师说明 Dynamic Boost 的响度最大化包含前瞻限制器，会短暂延迟信号以处理峰值。它不适合直接照搬到当前“尽量降低副路延迟”的默认链路。[工程师说明](https://forum.fxsound.com/t/what-does-dynamic-boost-do-exactly/6900)、[团队身份](https://www.fxsound.com/contribute)

EQ 会同时影响同频段的脚步和枪声；动态压缩能缩小强弱差距，但也可能把背景一起抬起；空间效果会改变定位线索。当前优先实现透明、可旁通、可逐段试听的 EQ 与多段过滤。未来若加入动态处理，应明确阈值、比率、起音和释放时间，并单独测量延迟，而不是给“脚步增强”按钮塞一组不可见参数。

## 当前实现与验证

多段过滤支持 1–8 段，各段开关、上下限、−24 至 +12 dB 权重独立；所有启用带通并行求和，曲线画实际复数频响的叠加结果。重叠频段可能相互增强或抵消，不能把它们当作理想矩形区域直接拼接。总输出按滤波与 EQ 的组合峰值预留至少 1 dB，十段 EQ 与多段总开关独立。

没有新增音频队列、前瞻等待或主音频延迟。因果滤波仍有群延迟：同一算法在通带中心附近，700–800 Hz 约 6.37 ms，700–1500 Hz 约 0.80 ms，2000–5000 Hz 约 0.21 ms。因此过窄带通可能拖长脚步瞬态。这里是滤波器计算值，不是测得的扬声器延迟。

本机 8 段 + 十段 EQ 基准：每包 480 帧立体声／48 kHz，即 10 ms 音频；1000 次计时中位 0.228 ms，P99 0.574 ms。该基准不含驱动、采集和播放队列，不能推出整机低于 1 ms。当前没有证据支持仅为这个计算量重写为 C++。

旧单段迁移为第一段，原始 version 1 文件自动备份。新增段默认关闭。CLI 的 `bands` 数组与 GUI 共用校验和 DSP；`schema` 给出字段、范围与语义。`test_multiband.py` 验证两段通带与中间衰减、权重、流式分包一致性、旁通、混合峰值余量和旧配置兼容。
