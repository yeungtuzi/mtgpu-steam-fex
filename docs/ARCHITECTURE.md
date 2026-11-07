# 架构与两条运行路径

目标：Ubuntu 24.04 ARM64 + 摩尔线程 M1000 上，用 Steam（linuxarm64 public-beta）
+ FEX + Proton ARM64 跑 x86_64 Windows 游戏，GPU 走 M1000 原生 Vulkan。

## 隔离模型

```
/opt/steamos/                 # 唯一安装前缀
├── steam/                    # Steam 客户端 + steamapps + compatibilitytools.d
├── fex/                      # FEX-Emu（PPA deb 解包，非 apt 安装）
├── fex-emu/RootFS/ArchLinux  # FEX 的 x86_64 rootfs
├── bin/steam                 # 启动器
├── xorg-m1000.conf           # 独立 Xorg（modesetting，1920×1080）
├── INSTALL-MANIFEST.tsv      # 系统级写入账单
└── src/, deps/, gamescope/   # 实验性构建产物（随前缀整体删除）
```

系统级写入只有：
- `/usr/share/guestos/fex-mesa` → FEX rootfs 的 symlink（Steam FEX 工具硬编码路径）；
- `/etc/binfmt.d/FEX-x86_64.conf`（systemd 转义文本，注册 x86_64 ELF 解释器）；
- 用户级 symlink/desktop/env（`~/.steam`、`~/.local/share/Steam`、`~/.config/environment.d` 等）。

全部登记在 manifest，`scripts/uninstall.py` 逆操作；删除 binfmt 后会重启 `systemd-binfmt`。

## 路径 A：Steam → FEX → x86_64 Proton

```
Steam(arm64) → FEX 兼容工具(2607) → SLR 3.0 sniper(x86_64) → Proton 8(x86_64) → 游戏
```

- 能启动、能出画面，但 DXVK 在 **guest** Vulkan loader 里看不到 `VK_KHR_surface`，
  回退 llvmpipe（6–14 FPS），不满足 GPU 验收。
- 该链路保留为“能跑起来”的对照，不作为 M1000 路径。

## 路径 B：arm64 Wine + DXVK 2.3.1（当前可玩路径）

```
Steam(arm64) 或直接启动
  → Proton 11 (ARM64) 自带的 arm64 Wine（WOW64 跑 x86_64 PE）
  → DXVK 2.3.1（prefix system32）
  → 宿主 Vulkan loader → M1000（MT driver）
```

关键点：
1. **DXVK 版本**：2.7 在 M1000 上报 `No adapters found`，必须用 2.3.1；
2. **独立 Xorg `:3`**（vt8，modesetting on `mt-igpu`）：KWin 的 rootless Xwayland
   不映射 Wine 顶层窗口，也不能切显示模式；
3. **窗口管理器**：`:3` 上跑 `mutter --replace`，否则 Wine 收不到激活事件，
   菜单/游戏输入全部失效（Unity 还会因失焦节流到 ~1 FPS）；
4. **存档读档**：新游戏的 `Opening_Sequence` 场景切换会在 `dxgi`/`unityplayer`
   崩溃，放入 `user1.dat` 后从存档进入可绕过；
5. SteamAPI：用 **Proton 自己创建的 prefix**（`compatdata/367520-arm64/pfx`）并在 Steam
   客户端运行时，`Player.log` 会出现 `Steam logged in as ...` / `Steam stats received.`。
   我们手工的 `pfx-arm64` 缺 Proton 的 lsteamclient 布局，才会 `Steam failed to initialize`。
   Steam 兼容工具本身能注册并被调用（`M1000ARM64/proton waitforexitandrun ...`）。

## 脚本分工

| 脚本 | 作用 |
|---|---|
| `install.py` | 下载/解包 Steam、rootfs、FEX、Proton，注册 binfmt，写 manifest |
| `setup-m1000.sh` | 安装 Xorg 配置、DXVK 2.3.1、可选存档 |
| `run-hk-m1000.sh` | 启动 Xorg `:3` + 游戏 + 焦点保持 |
| `hk-continue.sh` | 主菜单点进存档位 1 |
| `collect-evidence.sh` | 定时截图 + 进程/Vulkan 信息 |
| `uninstall.py` | 按 manifest 逆操作（dry-run 默认） |
