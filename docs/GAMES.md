# 游戏兼容记录（M1000 / ARM64）

兼容工具：`M1000ARM64`（`scripts/steam-compat-tool/`），默认走 KDE 的 `:0`，
不启动独立 Xorg、不切 VT。

## Hollow Knight（367520）

- 状态：可玩，720p 下菜单 59.8 FPS。
- 启动参数由兼容工具按 exe 名注入：`-screen-fullscreen 0 -screen-width 1280 -screen-height 720`。
- 真全屏：兼容工具在游戏运行期间持续 `wmctrl -b add,fullscreen`，
  实测 `_NET_WM_STATE_FULLSCREEN`、位置 0,0、1280×720、无边框无 panel。
- 已知问题：重复启动时 Steam 会残留 `reaper` 进程，表现为“已有实例在运行”；
  需要清掉 `reaper` 或重启 Steam。

## Doki Doki Literature Club（698780）

- 状态：可玩（Ren'Py + OpenGL）。
- M1000 原生 OpenGL：`renderer = M1000`，`version = 4.6`（Xwayland `:0`），
  不需要 llvmpipe 软件渲染。
- 之前的“Win32 错误对话框”根因：兼容工具给所有游戏追加了 Unity 的
  `-screen-fullscreen 0 ...`，Ren'Py 把其中的 `0` 当成 base directory，
  报 `Base directory .../Doki Doki Literature Club/0 does not exist`。
- 修复：兼容工具只在 `hollow_knight.exe` 时注入 Unity 参数（提交见 git）。
- 截图：`docs/evidence/2026-11-08-ddlc-m1000-opengl.png`
- 全屏：兼容工具对 `DDLC.exe` 同样持续请求 KWin fullscreen，实测
  `_NET_WM_STATE_FULLSCREEN`、位置 0,0、1280×720（Game Mode 720p 下无边框无 panel）。
  截图：`docs/evidence/2026-11-08-ddlc-fullscreen-720p.png`
- 坑：prefix 的 `system32/ucrtbase.dll` 曾被替换成 32 位旧版，导致
  `wineboot` 报 `c000007b`，HK/DDLC 都启动失败；用 Proton 11 的
  `aarch64-windows/ucrtbase.dll` 覆盖后恢复。

## Halo: The Master Chief Collection（976730）

- 状态：**当前不可用**。
- 尝试记录：
  - 直接跑 `mcclauncher.exe`：缺 `libarm64ecfex.dll`，补齐后仍崩溃
    `c000001d`（illegal instruction，ARM64EC/FEX 路径）；
  - 把 976730 映射到 M1000ARM64、用 Proton 11 ARM64 prefix：仍在
    `mcclauncher`/`wineboot` 阶段 `c0000135`、`c000001d` 崩溃，
    **没走到 EAC on/off 对话框**；
  - Proton Experimental 的旧 prefix 与 Proton 11 DLL 混用会直接坏掉，
    已还原。
- 结论：EAC 不是当前瓶颈，瓶颈是 MCC 的 ARM64EC/FEX 代码路径在
  Proton 11 + M1000 组合下崩溃；后续需换 Proton 版本或等 FEX 修复。
