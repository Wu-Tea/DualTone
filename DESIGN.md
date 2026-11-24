# DualTone interface

User-approved references: SoundSource for the compact everyday control panel;
FabFilter for a dominant interactive response/spectrum canvas; FxSound for
direct detailed EQ controls. User rejected the first generic settings-form
layout as insufficient visual translation of those references.

Operate mode. Native main window is 440 × 800 logical pixels, with one grouped device
selector, supplementary gain/mute, a response/spectrum preview, preset and queue
status. Detailed adjustment uses a separate nonmodal 940 × 760 window, retaining
the main control panel rather than stretching it into a large form.

Slint Fluent is the native component framework in v0.2. It supplies the compact
shell's menus, selectors and switches. Custom Slint controls supply the instrument
panel with its explicit dark palette. native-app/ui/main.slint owns control geometry;
native-app/gui.cpp supplies type-aware line icons and spectrum rendering.
Native title bars and keyboard behavior remain. The earlier Qt files remain as
the v0.1 reference, not a runtime dependency.
The compact panel follows the system light/dark scheme. The instrument canvas
uses graphite, amber for the processing curve, gray for source spectrum and
mint for auxiliary spectrum. The EQ curve excludes gain and preamp; spectra use
a separate dBFS axis and include the actual rendered gain.

No hardware essays in the UI. Help/research belong in the Markdown documents.
Queue size is explicitly distinct from unmeasured acoustic latency. Hidden
windows suspend spectrum analysis. FFT work is bounded and runs outside the
audio worker; the worker never waits for drawing. All sound processing remains
auxiliary-only, with unchanged JSON presets and local CLI control.

Main and auxiliary are routing roles, not hardware identities. Both selectors
list all current render endpoints with native rate/channel capability and any
unsupported reason. The main endpoint is a playback source read by loopback;
the auxiliary endpoint receives processed audio. No monitor-name heuristics or
48 kHz-only target filter. A fixed 48 kHz internal DSP clock is separate from
endpoint rates, bridged by causal streaming resamplers. Icons use Windows
form-factor metadata; unknown types use a waveform. Swap and refresh belong
in the device group. No automatic secondary-device choice. Explicit main-device selection, swap,
and starting forwarding synchronize Windows console/multimedia defaults;
communications remains unchanged. Main audio stays directly rendered by apps. Existing user device IDs and DSP settings survive upgrades.
Device controls use a 4 px spacing scale, following Fluent's layout guidance
(https://fluent2.microsoft.design/layout). The group has 12 px padding. A single
36 px control contains the icon, label and disclosure indicator, with 12 px
horizontal padding; its focus outline encloses that entire padded hit area.
The 20 px device icon and name have a 12 px gap. Menu surfaces have 4 px padding
and menu items have 8 px padding, so expanded and collapsed content share the
same column origins without removing internal breathing room. Two-line device
items are 56 px tall; placeholder items are 40 px. Selected items use a tinted
surface and a checkmark, independently of the neutral hover/keyboard highlight.
Keep at least 420 x 800 logical pixels so the footer remains inside the window.
Do not fix alignment by zeroing control padding or placing content on a focus
border. Verify open menus as well as the closed panel in light and dark themes.

Verification: actual Slint window captures at default and minimum size, keyboard
EQ editing, GUI/CLI shared-state tests, and real endpoint playback.

The detailed EQ is edited directly on the chart. Amber handles/curve represent
EQ gains; the dashed curve shows the band-filtered response. Keep handles at
the actual EQ gain so a bandpass cannot bury low-frequency controls at the
chart floor. Ten numeric inputs below share a width determined only by plot
geometry, aligned to the logarithmic band positions; text length never changes
columns. Drag, double-click reset, arrow-key adjustment and direct typing are
available. The two independent controls say “均衡器” and “频段过滤”; disabling
one does not disable the other or external system effects. Preset creation and
deletion are primary actions; import/export are in More. Only user-saved presets exist. Every dropdown entry resolves to saved DSP
values; “current settings” is never a selectable placeholder. Empty and
unmatched states use display text with currentIndex -1, without adding fake
entries. Deleting a preset retains current processing values.


多段过滤沿用编辑器的行式参数布局：每行开关、下限、上限、增益、删除；上方总开关旁显示启用段数和新增操作。列表最多 8 行，默认窗口显示 3 行、最小高度显示 2 行，其余滚动。新增行关闭，当前设置迁移为第一行。金色 EQ 锚点仍独立可拖动，虚线显示真实多段混合响应。数值非法时提交或失焦恢复实际参数，不能显示未生效值。


The main panel has two auxiliary processing modes: space and wet-only reverb.
A shared Row layout vertically centers mixed-height icons, labels and controls.
Device captions align with text inside the selectors; legends use vector line
segments and fixed compact columns. Filter rows explicitly label lower bound,
upper bound and gain, with units beside their inputs.

Reverb controls stay on the main panel: room size, decay seconds and brightness,
using a shared parameter row with a fixed label and right-aligned value column.
The existing auxiliary volume is the wet amount. Mode selection does not alter
old EQ, filter, body-retention or device settings. Reverb input processing is
labeled separately; the graph shows EQ/filter response, not the FDN response.


v0.4: Keep the compact panel geometry. A single 同步设置 entry in the main-device
caption opens a separate 480 × 410 settings window. Direct and dual-route modes
are mutually exclusive. Only sync mode shows virtual ingress selection and
main delay (numeric milliseconds, ±5 ms buttons, keyboard-accessible fader).
Transport settings are local routing, not sound presets. Device changes require
stopped playback in sync mode. Effects and comparison mute remain auxiliary-only;
main now optionally uses an independent delayed render queue. Status distinguishes
同步中 from ordinary 补声中. Restore owned default roles on normal stop/error.
