# Reunion Lite — 原生 Linux/Qt 移植（已合入上游 0.2）

目标：把 `~/文档/ra2reunion/ReunionLite-src`（Win32 C++）移植为原生 ARM64 Linux 程序，
不再依赖 Wine；游戏本体 `gamemd.exe` 仍然走 Wine/FEX。

## 已完成

- 复用 `src/core/`（ini / campaign / launch，均为可移植 C++17）；
- 新增 `src/platform/linux/encoding.cpp`：GB18030 ↔ UTF-8（iconv），替代 Windows codepage；
- 新增 `src/app_qt.cpp`：Qt6 Widgets 界面（搜索、任务表、重新扫描、状态栏）；
- 构建：CMake + Qt6 Widgets，原生 aarch64 二进制；
- **路径修复**：`core/campaign.cpp` 的 `Fs()` 在非 Windows 下把 `\` 转 `/`，
  否则任务目录全部判为不存在（列表为空）；
- 实测：原生 Wayland 窗口正常，扫描 **1247 任务包 / 3390 任务 / 3307 可启动**。

## 0.2 已完成

1. 移植 `runprep`（准备 `Run/`、写 `spawn.ini`、overlay 清理、按任务包隔离存档）；
2. 启动 `gamemd-spawn.exe`（`scripts/linux/ra2-launch.sh`：Steam Linux Runtime + FEX + x86_64 Wine）；
3. 地图 `[Tags]` 行的 GB18030 容错（修复 `0x7C8D40` 崩溃）；
4. 实测进入盟军第一关，地图/建筑/单位正常渲染。

尚未实现：右侧选项面板（模组/难度/资金/速度/音乐/过场/Ares/Phobos 等），计划后续版本。

## 构建

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j4
./build/reunion-lite-qt ~/文档/ra2reunion
```
