# 副路混响

v0.3 在主面板提供“空间补充 / 副路混响”切换。主音频继续由原程序直出；混响模式的副设备只播放效果声，不混入原声副本。切换时有 10 ms 的短交叉淡化，减少突变。

## 调节

- **副音频音量**：控制效果声整体音量，仍与其他模式共用。先保持较低，再用“静音对比”判断是否需要增加。
- **空间大小**：0–100%，改变反射之间的时间间隔。它不是房间尺寸的物理测量。
- **尾音时长**：0.2–4.0 秒，控制名义低频 RT60（衰减 60 dB 的时间）；高频会更快衰减，实际可听尾音也受内容、明暗、音量和设备影响。
- **明暗**：0–100%，向右更明亮，向左削减更多高频。

均衡器和多段过滤位于混响之前，图中的处理曲线描述这两级滤波，不描述完整混响响应。空间模式的“主体保留”会保留设置，但在混响模式下不参与处理。关闭输入频段后，已有尾音仍会自然衰减；“静音对比”和停止补声会立即停止副路发声。

普通显示器可以先用默认的空间大小 40%、尾音 1.2 秒、明暗 40% 试听。程序没有自动提高副路音量，也不修改显示器内部音效。这是算法混响，不是人声分离、和声生成或 5.1 解码。

## CLI 与配置

命令接口不变，新增设置可由 `schema` 发现：

```powershell
.\DualToneCLI.exe set --json '{"effect_mode":"reverb","reverb_size":40,"reverb_decay":1.2,"reverb_brightness":40}'
.\DualToneCLI.exe pause on
.\DualToneCLI.exe pause off
.\DualToneCLI.exe set --json '{"effect_mode":"space"}'
```

自定义预设、导入和导出包含这些设置。配置格式升级为 version 3；读取 version 1/2 时补齐新字段，默认仍为 `space`。首次保存前保留原版本备份，不覆盖已有备份。旧程序不识别新格式，回退时应使用对应旧备份。

混响本身含有意加入的反射时间，不能当成普通转发延迟。`latency` 在混响模式下会明确拒绝测量，界面相应入口禁用；切回空间补充后可测。主路从不因混响或设备同步而增加延迟。

## 实现与验证

实现位于 `native-app/reverb.cpp`，使用八条不等长延迟线、归一化 Hadamard 反馈矩阵、逐线衰减与低通阻尼。反馈网络采用正交混合以避免无阻尼网络凭空增加能量，衰减系数按每条延迟的长度和目标 RT60 计算。这一设计依据 Julius O. Smith 的 [FDN 混响说明](https://www.dsprelated.com/freebooks/pasp/FDN_Reverberation.html)和[反馈矩阵讨论](https://www.dsprelated.com/freebooks/pasp/Choice_Lossless_Feedback_Matrix.html)，代码为本项目实现。

混响输入另做 180 Hz 高通，避免让普通副音箱重复承担低频。参数平滑更新；尾音内部低通随明暗变化。效果输出经软饱和限制后进入既有增益及余量处理；暂停源流后继续处理剩余尾音，两倍名义 RT60 后清理不可听残余，避免静音时的非规格化浮点开销。不加载模型、音频素材或卷积脉冲文件。

`verify_reverb.py` 覆盖无直达声、立体声尾音、空间和衰减参数、分包一致性、实时参数变化、静音、旧配置备份、预设往返，以及实际 GUI 点击和 CLI 读值。`verify_native.py` 继续对照旧算法验证空间补充、EQ、频段和重采样。`verify_reverb_device.py` 使用独立配置检查真实端点、尾音和模式切换，核对主默认输出及用户配置不变。

本版同时修复命名管道响应在客户端读取前被断开的问题。回归测试 `verify_pipe_delivery.py` 故意延后读取，旧实现可复现 Windows 错误 233。服务器现在在既有超时边界内等待客户端读完并关闭，再断开管道，避免 [DisconnectNamedPipe 丢弃未读数据](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-disconnectnamedpipe)。
