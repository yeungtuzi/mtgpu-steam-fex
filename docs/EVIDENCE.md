# 证据索引

机器：Ubuntu 24.04 ARM64，内核 7.0.14，M1000（`mt-igpu`）。
Game Mode 下截图为 1280×720；早期 1080p 记录保留在开发分支，本仓库只收录代表性截图。

| 场景 | FPS | 文件 |
|---|---|---|
| Steam 大屏（720p Game Mode） | — | `evidence/steam-bigpicture-720p.png` |
| Hollow Knight 游戏内（720p，HUD `MT driver`） | 59.9 | `evidence/hollow-knight-720p.png` |
| Hollow Knight 语言菜单（1080p） | 507 | `evidence/hollow-knight-language-menu.png` |
| Hollow Knight King's Pass（1080p） | 79.5 | `evidence/hollow-knight-kings-pass.png` |
| Doki Doki Literature Club（720p，原生 OpenGL） | — | `evidence/ddlc-720p.png` |
| 红警2 / Reunion Lite（720p 窗口） | — | `evidence/ra2-reunion-lite-mission.png` |

判定标准：

- DXVK HUD 显示 `Driver: MT driver`（不是 llvmpipe）；
- 游戏窗口可交互、有实际画面（菜单 / 游戏内 / 对话），不是纯黑或纯白；
- Game Mode 下分辨率确认为 `1280x720@59.97`、`Scale: 1`。

更长的稳定性数据（31 分钟静置、RSS 曲线、FPS）见 [TESTING.md](TESTING.md)；
逐游戏细节见 [GAMES.md](GAMES.md)。
