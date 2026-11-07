# M1000 验收测试流程

目标：在 **Ubuntu 24.04 ARM64 + 摩尔线程 M1000** 上，用 Steam(arm64 public-beta) +
FEX + Proton ARM64 实际进入 x86_64 Windows 游戏，记录帧率、稳定性和
「M1000 原生 Vulkan（非 llvmpipe）」证据。

## 前置条件

- `scripts/install.py` 已执行，`/opt/steamos` 完整；
- M1000 Vulkan 可用：`/etc/vulkan/icd.d/mtvk.json`，`vulkaninfo --summary` 能看到 M1000；
- 独立 Xorg 配置 `/opt/steamos/xorg-m1000.conf`（modesetting，1920×1080，VT8）；
- 游戏 prefix 内是 **patched DXVK 2.3.1**（DXVK 2.7 在 M1000 上报 `No adapters found`）。

## 启动

```bash
# 启动独立 Xorg :3 + arm64 Wine + Hollow Knight
scripts/run-hk-m1000.sh
# 可选：进入后按 Escape 跳过开场
# 停止
scripts/run-hk-m1000.sh --stop
```

`run-hk-m1000.sh` 会自动后台启动 `scripts/keep-focus.sh`，每 5 秒重新聚焦游戏窗口
（Unity 失焦会掉到 ~1 FPS，且窗口 ID 在场景切换后会变）。
需要手动保持焦点时也可以单独运行：`scripts/keep-focus.sh :3`。

脚本会导出 `DXVK_HUD=fps,devinfo`，HUD 左上角应显示：

```
modesetting
Driver:  MT driver
Version: Oct 23 2026
FPS:     ...
```

## 采集证据

```bash
scripts/collect-evidence.sh 600 /tmp/steam-fex-evidence
```

输出：
- `shot-*.png`：每 10 秒一张整屏；
- `summary.txt`：Vulkan 设备、进程、窗口信息；
- `ps.log`：CPU/内存随时间变化。

判定标准：
- HUD 必须是 `MT driver`，不能是 `llvmpipe`；
- 分辨率 1920×1080；
- 菜单/游戏内 FPS 有具体数值；
- 连续 30 分钟进程不退出、不黑屏、FPS 不跌到个位数。
- 实测：King's Pass 静置 **31 分 37 秒**，FPS 78–80 稳定，RSS 1.63 GB（无明显增长），
  进程始终存活，139 张截图（`/tmp/ev-game30`）。此前另有一次 17 分钟运行。

注意：切换到别的 VT（KDE）会让 Xorg `:3` 挂起 AIGLX，截图会变成很小/全黑；
采集前先 `sudo fgconsole` 确认停留在 `:3` 所在 VT（默认 vt8），或用 `sudo chvt 8`。

## 当前实测结果（2026-11-07）

| 场景 | 证据 | FPS |
|---|---|---|
| 语言菜单 | `docs/evidence/2026-11-07-hk-m1000-language-menu.png` | 507 |
| 主菜单 | `docs/evidence/2026-11-07-hk-m1000-main-menu.png` | 96.6 |
| 存档选择 | `docs/evidence/2026-11-07-hk-m1000-profiles.png` | 91.8 |
| SCALE/BRIGHTNESS 校准（场景已渲染） | `/tmp/r16_play2.png` | 92.3 |
| 新游戏开场白字 | `docs/evidence/2026-11-07-hk-m1000-intro-176fps.png` | 176.8 |
| 主菜单静置 20 分钟 | `docs/evidence/2026-11-07-hk-m1000-menu-20min-throttled.png` | 0.9（见下） |
| 同一会话重新聚焦后 | `docs/evidence/2026-11-07-hk-m1000-menu-refocus-96fps.png` | 96.6 |
| 焦点保持 30+ 分钟后 | `docs/evidence/2026-11-07-hk-m1000-30min-menu.png` | 59.9（Quit 确认框） |
| 游戏内 King's Pass 静置 17 分钟 | `docs/evidence/2026-11-07-hk-m1000-gameplay-17min-79fps.png` | 79.0 |
| **游戏内 King's Pass 静置 31 分 37 秒** | `docs/evidence/2026-11-07-hk-m1000-gameplay-31min-79fps.png` | **79.5** |

均为 **MT driver / M1000 / 1920×1080**。

### 焦点与帧率

无窗口管理器时，Unity 窗口失焦会进入后台节流（实测主菜单从 96 FPS 掉到 **0.9 FPS**，
进程仍存活、CPU ~41%）。`xdotool windowfocus` 重新聚焦后立刻恢复到 96.6 FPS。
因此测试/游玩前必须保持窗口焦点；同时窗口 ID 在场景切换后会变化，需要每次重新查询。

## 进入实际游戏（绕过开场）

新游戏的 `Opening_Sequence` 在 arm64 Wine 下会崩（dxgi/unityplayer 栈，见下），
但 **加载存档可以正常进入 King's Pass 并操作**：

1. 准备一个存档放到
   `.../compatdata/367520/pfx-arm64/drive_c/users/steamuser/AppData/LocalLow/Team Cherry/Hollow Knight/user1.dat`；
2. 在 `:3` 上启动一个窗口管理器，否则 Wine 收不到激活事件、菜单不响应：
   `DISPLAY=:3 mutter --replace &`
3. 启动游戏后执行 `scripts/hk-continue.sh`，它会点 `START GAME` 和存档位 1；
   也可以手动点选（KING'S PASS）。

实测（2026-11-07）：King's Pass 场景可移动角色，HUD `MT driver`，1920×1080，
FPS 73–80。证据：
- `docs/evidence/2026-11-07-hk-m1000-gameplay-kings-pass-79fps.png`
- `docs/evidence/2026-11-07-hk-m1000-gameplay-moved-73fps.png`
- `docs/evidence/2026-11-07-hk-m1000-gameplay-reload-78fps.png`（重开一次复现）

此次成功运行的组合：**stock DXVK 2.3.1 + `FEX_TSOENABLED=0` + mutter + 存档加载**；
各因素尚未逐一隔离。

## 整合路径（SteamAPI + M1000 原生 Vulkan）

已验证可同时满足「Steam 已登录 + HUD `MT driver` + 可操作」：

1. 从 KDE 启动 Steam（登录状态正常）；
2. prefix 用 **Proton 自己创建的** `compatdata/367520-arm64/pfx`；
3. 把 DXVK 2.3.1 的 `d3d11.dll`/`dxgi.dll` 放到**游戏目录**（`steamapps/common/Hollow Knight/`），
   避免 prefix 里的 d3d11 symlink 被 Proton 自带 DXVK 覆盖；
4. 存档放进该 prefix 的 `.../AppData/LocalLow/Team Cherry/Hollow Knight/user1.dat`；
5. 用 arm64 Wine 启动，环境包含：

```bash
WINEPREFIX=.../compatdata/367520-arm64/pfx
WINEDLLOVERRIDES="d3d11,dxgi=n"
STEAM_COMPAT_CLIENT_INSTALL_PATH=/opt/steamos/steam
SteamAppId=367520 SteamGameId=367520
DXVK_HUD=fps,devinfo FEX_TSOENABLED=0
```

6. 点 `START GAME` → 存档位 1。实测：`Steam logged in as ...`、`Steam stats received.`，
   King's Pass 78.8 FPS，HUD `MT driver`。

证据：`docs/evidence/2026-11-07-hk-m1000-steamapi-gameplay-79fps.png`。
该路径另做了两次静置采集：
- 16 分 41 秒（`/tmp/ev-steam`，39 张截图），结束 FPS 79.9，RSS 1.76 GB；
- **31 分 39 秒**（`/tmp/ev-int30`，140 张截图），结束 FPS **80.6**，RSS 1.73 GB，
  进程全程存活。

## SteamAPI 备注

在 **Proton 创建的 prefix**（`compatdata/367520-arm64/pfx`）里、且 Steam 客户端运行时，
`Player.log` 会显示：

```
Steam logged in as <persona>
Steam stats received.
```

而手工 prefix `pfx-arm64` 里是 `Steam failed to initialize`。两者 DXVK 都需要单独换成 2.3.1。

## 从 Steam 直接启动（兼容工具）

`scripts/steam-compat-tool/` 三个文件放到 `steamapps/compatibilitytools.d/M1000ARM64/`，
在游戏属性 → 兼容性里选 “M1000 ARM64 Wine”，然后点 Play。工具会自动：

- 复用 Proton prefix（SteamAPI 正常）；
- 在游戏目录放 DXVK 2.3.1 并 `WINEDLLOVERRIDES="d3d11,dxgi=n"`；
- 启动 `:3` 的 Xorg + mutter；
- 设 `FEX_TSOENABLED=0`、`DXVK_HUD`。

实测：Steam 内 Play → King's Pass 可玩，86 FPS，`Steam logged in`、`Steam stats received.`。

## 已知阻塞

开场之后卡在 Unity `Opening_Sequence` 场景切换：

```
Levels are ready before cinematics are finished. Cinematics made skippable.
Opening sequience skipping.
Opening sequience changing sequences.
```

gdb 显示主线程停在 Wine ntdll `wait_select_reply()`（匿名管道 fd），
`Loading.AsyncReady` 线程空闲。已排除 esync/fsync、`-force-gfx-direct`、视频解码
（mfplat/winegstreamer 存在）。因此 **30 分钟游戏内稳定性尚未完成**。

## 卸载验证

```bash
python3 scripts/uninstall.py --prefix /opt/steamos            # dry-run 看账单
sudo python3 scripts/uninstall.py --prefix /opt/steamos --yes
# 可选：一并移除 manifest 里记录的纯新增 apt 包
sudo python3 scripts/uninstall.py --prefix /opt/steamos --yes --remove-apt
```

卸载会删除 `/opt/steamos`、`/etc/binfmt.d/FEX-x86_64.conf` 并重启 `systemd-binfmt`，
以及 manifest 里登记的用户级 symlink/desktop/env 文件。

执行路径已在合成 prefix 上验证（不影响真实安装）：

```
/tmp/steamos-fake/INSTALL-MANIFEST.tsv  （file + symlink + apt 三类）
python3 scripts/uninstall.py --prefix /tmp/steamos-fake --yes
→ remove symlink ... / remove file ... / apt 未安装则跳过 / remove /tmp/steamos-fake
```

真实 `/opt/steamos` 的 `--yes` 演练尚未执行（会清空当前可运行环境，需操作者确认）。
