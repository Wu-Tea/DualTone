# Third-party components

- Slint 1.18.1 (SixtyFPS GmbH): Slint Royalty-free Desktop, Mobile, and Web Applications License 2.0. The application displays the AboutSlint widget in its top-level About dialog. Slint's original license notices and transitive third-party notices accompany this file.
- nlohmann/json 3.12.0: MIT; source is obtained by the pinned bootstrap script.
- Microsoft Visual C++ runtime: app-local redistributable DLLs from the installed Visual Studio redistribution directory, distributed under Microsoft's applicable Visual Studio license. These DLLs are used only to run the compiled Windows application.

No Python, Qt, NumPy, SciPy, neural model, virtual audio driver, or browser runtime is needed at application runtime. Windows supplies WASAPI, DirectWrite/Direct3D and GDI+.

Resampling coefficient tables are generated at build-development time using the documented FIR/minimum-phase design in the v0.1 source. Python and SciPy are only needed to regenerate these numeric tables or to run numerical comparisons against v0.1; they are not included in the native application.

The native control palette and layered surfaces adapt the Solid Glass visual system (DeepLethe, 2026, MIT), as used in the user-provided local reference project. See `SolidGlass.LICENSE`. No React, browser engine, reference application logic, or reference assets are bundled.
