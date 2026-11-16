# 硬件与处理依据

2026-11-15。设备型号由本机音频端点与用户确认获得；下面区分厂家参数、代码证据和试听建议。

## Creative Pebble Pro

用户确认主音箱为 Pebble Pro，经 CX31993+97220 USB DAC 的 AUX 输出连接。Creative 官方规格：2 × 2.25 英寸全频单元、2 个被动辐射器、BassFlex，标称频响 80 Hz–20 kHz。该频响范围不等于带容差的平直响应曲线。

普通 USB 条件最高 10 W RMS；合适的 USB-C PD 供电最高 30 W RMS / 60 W 峰值。当前供电方式未核实，不能假定正在 30 W 模式。AUX 也支持经独立 PD 端口供电；无需为了供电更改音频路由。

- https://support.creative.com/kb/ShowArticle.aspx?sid=200789&type=search
- https://support.creative.com/kb/ShowArticle.aspx?c=&sid=200794
- https://us.creative.com/p/speakers/creative-pebble-pro/

## Samsung Odyssey G65B

本机端点名 Odyssey G65B，NVIDIA DP，48 kHz 双声道。查到的三星 G65B 系列 32 英寸官方资料确认内置扬声器、Adaptive Sound，但没有给出扬声器频响曲线或音频处理延迟。这个系列资料不证明本机具体尺寸，也不足以声称确定扬声器功率或低频延伸。

https://images.samsung.com/is/content/samsung/assets/de/display/pdf/Datenblatt_Monitor_LS32BG650EUXEN_022024.pdf

## 由这些证据得到的试用策略

这不是声学校准。Pebble Pro 负责主体；不尝试用用户反馈较差的显示器扬声器补 32/64 Hz 低音。默认 700–3500 Hz、8% 软件增益、平直 EQ，仅试探中频细节。8% 对应数字幅度约 −21.94 dB，还会叠加 EQ 余量、系统音量和设备自身增益，不代表显示器只有主音箱 8% 的实际响度。

脚步试听另设 300–3000 Hz。没有跨游戏通用的“只含脚步”频段。两个预设都用 A-B 对比验证，若声音更空、声像偏移或定位变差，就减弱或关闭。

用户截图曲线作为对照单独保留：32/64/125/250/500/1k/2k/4k/8k/16k Hz 对应约 +10.5/+8/+4/+0.5/+0.5/+3.5/+7/+10.5/+7.5/−8 dB。默认不启用它，因为没有证据说明这样的低频与高频提升适合这台显示器。

## Rara 静态分析结论

用户下载的 RaraAudioApp 5.0.37 安装包只做了解包和静态源码检查，没有运行包内代码。主程序是 Electron，存在 Voicemeeter 路由、VB-Audio cable、Equalizer APO VST 和部分配置的 HeSuVi 整合。

16 声道配置顺序可见 shots → ninja → compressor → EQ → compressor → ambience → renderer → peak，要求 48 kHz / 16 声道。模块名字不等于已知其内部算法；部分配方下载到本地、部分 DSP 在 native DLL 中，未还原完整策略。

可读 Eclipse EQ 段示例：20–80 Hz −7 dB；100 Hz −0.6；125–250 Hz +4；315 Hz–5 kHz −3.8；6.3/8 kHz +2.6；10 kHz 及以上 −3.8。它只是完整处理链中的一段，不能摘出来宣称是通用脚步增强。

可借鉴的是处理分工：压制强瞬态和背景遮蔽、适当压缩动态、按游戏调整 EQ，而不是所有游戏统一提高 2–4 kHz。本版实现独立 EQ 和带通，不包含 Rara 二进制文件、授权绕过或专有算法。

市面公开说明：SteelSeries Sonar 提供参数 EQ 与游戏预设；Creative Scout Mode 描述实时增强线索的专有算法；公开营销资料不足以推出完整滤波/压缩参数。

- https://www.raraaudio.com/
- https://support.steelseries.com/hc/en-us/articles/16954265292173-How-does-Sonar-work
- https://us.creative.com/technology/scoutmode/
- https://www.w3.org/TR/audio-eq-cookbook/

## 延迟优化记录

已发现并修正 SoundCard 0.4.6 播放路径中的包长问题：旧实现在短包时释放全部可用帧，本实现只提交真正写入的帧。还减少了启动期间积累队列，使用原生格式并把配置文件写入移出音频线程。

旧试听工具优化后两次数字回环测得约 17.82/18.65 ms 相对滞后，本轮之前对照约 27.44 ms。该结果不是新打包版本保证值，也不是声学测量。当前 DP 共享引擎报告固定 10 ms 周期；源允许约 7–10 ms。未改变设备混音格式，也未通过增加主路延迟强行对齐。

### 后续修复：线程超时并不等于高精度音频唤醒

实测 `threading.Event.wait(0.0005)` 中位等待 15.38 ms，而高精度 `time.sleep` 同一请求约 1.01 ms。捕获线程原先使用前者，造成包到达后不能及时处理。现在改用 `AUDCLNT_STREAMFLAGS_EVENTCALLBACK` 与音频就绪事件，等待由音频引擎的实际通知结束。没有全局更改 Windows 定时器分辨率，没有主路同步缓冲，也不丢弃音频包追赶。

同设置对照（12% 增益、700–3500 Hz）：旧版 24.994 / 25.013 ms；修复引擎 7.072 / 7.097 / 7.161 ms。相关系数 0.9992–1.0，捕获不连续和时间戳错误均为 0。测量在内存中进行，对源信号做相同 DSP 后比较，因此数字转发值不含匹配滤波的群延迟，更不包括声学传播与两台设备内部处理。

实际打包版另测三次重启，每轮在开始和持续播放后各测一次：11.626 / 11.839、5.457 / 5.563、9.444 / 9.589 ms。每轮持续约 26 秒，捕获不连续和时间戳错误均为 0。默认输出、端点音量与静音状态保持不变。可见最终结果有启动间差异，不能用原型的一次 7 ms 值宣称固定延迟。原始报告为开发目录的 `latency-packaged-event-validation.json`。

- https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording
- https://docs.python.org/3/library/time.html#time.sleep
