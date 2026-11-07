# Game Mode - Steam（720p）

目标：一键把 KDE 切到 **1280×720@120、scale 1.0**，打开 Steam 大屏，游戏以 720p 全屏运行；
退出时恢复原来的 **2880×1800、scale 2、120Hz**。

## 组成

| 文件 | 作用 |
|---|---|
| `scripts/game-mode.sh` | `start [--confirm] / stop / status`：用 `kscreen-doctor` 切到面板原生 **1280x720@59.97**，启动 Steam 大屏；`stop` 恢复原模式与 scale |
| `scripts/desktop/m1000-game-mode.desktop` | 应用菜单 **Game Mode - Steam** |
| `scripts/desktop/m1000-game-mode-exit.desktop` | 应用菜单 **Exit Game Mode** |
| `scripts/m1000-hotkeyd.py` | 读取 `/dev/input/event*`，检测 **Super+Shift+G** 后执行 `game-mode stop` |
| `scripts/systemd/m1000-hotkey.service` | 上述守护进程的 systemd 服务（开机自启） |

## 退出方式

1. **Super+Shift+G**（evdev 守护进程，任何界面都生效）；
2. 应用菜单 / 桌面“退出游戏模式”；
3. Steam 退出后自动恢复（watcher 每 5 秒检查 `steam` 进程）；
4. 手动：`/opt/steamos/bin/game-mode stop`。

## 已验证

- `game-mode start --confirm` → `kscreen-doctor` 确认 `13:1280x720@59.97*`、`Scale: 1`；
- `game-mode stop` → 恢复 `1:2880x1800@119.93*`、`Scale: 2`；
- 合成 **Super+Shift+G** 经 `m1000-hotkey.service` 实测：状态文件被清除、模式恢复
  （日志 `restored mode=1 scale=2 (manual)`）；
- 看门狗：`start` 不带 `--confirm` 时 20 秒后自动恢复。

## 备注

- 早先尝试的自定义 120Hz CVT 模式会导致黑屏，已放弃；现在使用面板原生 1280x720@59.97。
- 游戏窗口的“真全屏”（去掉边框与 KDE panel）仍在处理中：兼容工具会用 `wmctrl`
  请求 KWin 全屏，待实机验证。

## 工作目录约定

不再使用 `/tmp`。运行时日志与测试辅助脚本放在：

```
~/.local/share/m1000/work/          # 会话级工作目录（持久）
  compat.log                        # 兼容工具日志
  xorg-m1000.log                    # 旧 :3 Xorg 日志（如使用）
  test-chord.py                     # 合成 Super+Shift+G 的测试脚本
  evidence-*/                       # collect-evidence 输出
```

可用 `M1000_WORK_DIR=/some/path` 覆盖。
