# DualTone interface · v0.5

The user requested a complete visual rework using the local yolo-study-001 project
as the implementation reference. Its current web interface separates materials,
controls, typography and task layout. DualTone translates that method to Slint;
it keeps the native audio core and CLI and does not embed the reference app,
React or a browser runtime.

## Visual system

`native-app/ui/controls.slint` owns the shared Theme, surfaces and controls.
Use a cool graphite foundation, softly lit surfaces, restrained rims, pale-blue
selection/focus, neutral text, and muted mint only for audio activity. This is
native gradient/shadow rendering, not OS backdrop blur. Theme tokens provide
light equivalents; charts read the same palette from Slint in gui.cpp.

Dark is the initial appearance. Light and system-following remain available in
the main menu and persist separately in `data/appearance.json`. They are also
accessible with `DualToneCLI appearance dark|light|system`. Appearance must not
alter sound presets, routing or the audio worker.

The base scale is 4 px: page inset 20, surface inset 16, control gap 8–12,
control height 36, control radius 10, surface radius 14. Body text is 13 px,
secondary text 12, window titles 20–22. Numeric fields keep a fixed width and
right-align values with units; buttons do not absorb unused row width.

The material palette is adapted from the reference project's Solid Glass
system (DeepLethe, MIT). Include native-app/SolidGlass.LICENSE in distributions.
No reference assets, application code or hardware-specific defaults are copied.

## Task surfaces

- Main: 460 × 590 (including a 36 px custom caption), minimum width 420. Only devices, auxiliary volume/mute,
  effect selection, one mode-specific quick parameter and preset selection remain
  visible, with one complete sound editor entry. No chart, duplicated processing toggles, unexplained
  meters or software queue telemetry on the everyday surface.
- Sound editor: 980 × 896, minimum 840 × 856. Effect parameters, editable spectrum,
  EQ and frequency filtering share one workspace. Effect selection on the main
  panel determines which parameters appear here.
- Diagnostics: reachable from the menu, owns queue/meter feedback and digital
  latency measurement. Errors stay visible on the operational windows.
- Presets: one management window for create, view/select/load, update from current
  sound, rename, delete, import and export. Update/delete request explicit UI
  confirmation. Applying presets keeps the current device routes and delay.
- Information and confirmation windows share the palette, padding, field styling
  and button scale; errors remain visible and leave persisted settings intact.

## Behavior

Every custom control has a keyboard focus indication. Pickers support arrow
navigation, Enter to commit and Escape to dismiss without changing data. Slider
arrows perform a defined step; adjacent numbers provide exact entry. Invalid
numbers produce a validation error. Selection is owned by persisted settings,
not by a widget's first item. Empty and modified preset states are placeholders.

Selecting a primary device keeps existing routing behavior. Changing the main endpoint requires stopped playback. EQ, multi-band filters, spatial processing,
reverb and comparison mute remain auxiliary-only. The virtual-input sync route is withdrawn in v0.5.2; old sync configurations load
as direct and keep sound parameters. Windows owns the physical main volume. Custom captions share the app palette. Native hit-testing retains drag, resize,
maximize/restore, the system menu, and the maximize snap target. Main close exits
cleanly; editor/manager close only hides that window. Tray behavior stays.

## Verification

Render actual Slint windows in dark and light modes, including minimum-size
main/editor windows, open pickers, populated/empty preset management and errors.
Exercise numeric entry and picker keyboard events through Windows; validate
preset CRUD and theme persistence through CLI, then check GUI state. Existing
DSP, reverb, synchronization and shared GUI/CLI state regressions remain required.

## Artwork and window integration

`ui/assets/` contains compact built-in imagegen artwork (model revision not exposed):
a double-wave application icon and an About-only illustration. PNG alpha is
preserved, with a PNG-backed ICO for the executable and tray. These do not add
runtime dependencies. Asset prompts and provenance are in ui/assets/README.md.

`window_frame.hpp` replaces native frame painting using WM_NCCALCSIZE while
retaining WS_THICKFRAME and Windows non-client hit testing. Theme-owned caption
measurements are shared with Slint, scaled by the window DPI. Hooks are installed
only once the lazy native HWND exists, and weak component references avoid an
ownership cycle. Follow Microsoft custom-frame and snap-layout guidance:
https://learn.microsoft.com/en-us/windows/win32/dwm/customframe
https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-snap-layout-menu
