# gamescope on M1000：现状与补丁

目标：用 SteamOS 同款 gamescope 提供全屏 + 分辨率缩放（FSR/NIS 等）。

## 已完成的构建与补丁

源码：`/opt/steamos/src/gamescope`（3.17.0），构建：`build/`，安装：`/opt/steamos/gamescope`。
运行时需要 `LD_LIBRARY_PATH=/opt/steamos/deps/lib/aarch64-linux-gnu`。

为 M1000 打了四处补丁（都已重新编译安装）：

1. **primary DRM 节点回退**（`src/rendervulkan.cpp`）
   M1000 的 `VK_EXT_physical_device_drm` 只报 render 节点，gamescope 在 DRM 后端要求 primary。
   现在回退到 `/dev/dri/card0` 的 dev id。
2. **DRM modifier 回退**（`src/rendervulkan.cpp`）
   目标格式没有可导出 modifier 时，改为 `DRM_FORMAT_MOD_LINEAR`，不再 `assert`。
3. **轮询时间线信号量**（`src/rendervulkan.cpp`）
   `vkWaitSemaphores` 在 M1000 上返回驱动私有错误（`-1000174001`），改为轮询
   `vkGetSemaphoreCounterValue`。
4. **SDL 平台 surface 扩展**（`src/Backends/SDLBackend.cpp`）
   `SDL_Vulkan_GetInstanceExtensions(nullptr, ...)` 只返回 `VK_KHR_surface`；
   按视频驱动补上 `VK_KHR_wayland_surface` / `VK_KHR_xcb_surface` / `VK_KHR_xlib_surface`。

## 实测结果

- **DRM 后端（eDP-1，1920×1080）**：能初始化、选模式、启动 Xwayland，Hollow Knight
  在 gamescope 内运行，DXVK 日志确认：

  ```
  Driver : MT driver 4.0.341
  Device : M1000
  ```

  但 **合成输出是黑的/损坏的**：用 gamescope 自带的截图机制（在它自己的 Xwayland
  root 上设置 `GAMESCOPECTRL_REQUEST_SCREENSHOT`，写 `/tmp/gamescope.png`）抓到的画面
  基本全黑、底部一条噪点，见 `docs/evidence/2026-11-07-gamescope-m1000-black-output.png`。
  kmsgrab 同样只能拿到黑帧。用 `SCREENSHOT_TYPE_FULL_COMPOSITION`（值 3）再抓一次，
  得到的是满屏像素噪点（`docs/evidence/2026-11-07-gamescope-m1000-full-composition-corrupt.png`），
  说明 gamescope 自己的合成缓冲已经损坏，不只是扫描输出问题。原因大概率是补丁 2 的 `DRM_FORMAT_MOD_LINEAR` 回退
  不被 M1000 扫描输出接受（scanout 需要真实 modifier）。
- **SDL 后端（Xorg `:3` / Xwayland `:0`）**：`vulkan_make_output failed`
  （`vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 返回 `-13`），嵌套窗口无法创建。
- **Wayland 后端（KDE `wayland-1`）**：`VK_KHR_wayland_surface` 已补，但仍受
  M1000 surface capabilities 限制。

### 补丁 5：完全禁用 M1000 的 modifier 路径

进一步在 gamescope 里对 `M1000` 设备强制 `m_bSupportsModifiers = false`，走非 modifier 的
scanout 路径，重新编译安装后再测：

- Hollow Knight：合成截图仍是黑底 + 底部噪点
  （`docs/evidence/2026-11-07-gamescope-m1000-nomodifier-corrupt.png`）；
- **vkcube**（最简单的 Vulkan 客户端）：FULL_COMPOSITION 截图同样是满屏花屏
  （`docs/evidence/2026-11-07-gamescope-vkcube-corrupt.png`）。

说明损坏发生在 gamescope 自己的合成器路径，与 Wine/游戏无关。

另外测试期间发现残留的 `explorer.exe`（Wine）会占用 `/dev/dri/card0`，导致 Xorg 启动
`drmSetMaster failed: Device or resource busy`；清理这些进程后恢复。启动 Xorg 前应先
`pkill -x explorer.exe`。

### 嵌套 Wayland 输出（KDE 里开普通窗口）

按“绕过 DRM、走普通 Wayland surface 输出”的思路重测 `--backend wayland`：

- 后端能初始化（`Post-Initted Wayland backend`），Xwayland 正常启动，vkcube 能跑；
- 但 gamescope 自己的 FULL_COMPOSITION 截图仍然是黑底 + 噪点；
- `--backend headless` 同样花屏 —— 说明损坏发生在 gamescope 的 Vulkan 渲染器内部，
  与输出后端（DRM / Wayland / headless）无关。

继续排查同步原语：

- `vkWaitSemaphores` → 驱动私有错误 `-1000174001`（已改成轮询 `GetSemaphoreCounterValue`）；
- 改用 `vkQueueWaitIdle` 想强制同步 → 返回 `VK_ERROR_DEVICE_LOST`（-4）；
- 说明 M1000 驱动在 gamescope 依赖的 queue/timeline 同步路径上不可靠，
  而 DXVK 用的 fence（`vkWaitForFences`）暂时没有复现该问题。

### 补丁 6：fence 同步改造（3.17）

把 gamescope 3.17 的同步从 timeline semaphore 改为 fence：

- 每次 `QueueSubmit` 带 `VkFence`，`wait()`/`descriptorSet()` 用 `vkWaitForFences`（1ms 超时循环）；
- 去掉 `vkWaitSemaphores`、`vkGetSemaphoreCounterValue`、`vkQueueWaitIdle` 依赖；
- 提交改为 fence-only（清空 timeline/external 信号量）。

结果：前 12 次提交/等待 `res=0` 正常，**第 13 次提交（首批合成命令）GPU 挂起**，
之后所有 wait 返回 `-1000174001`；最小 Vulkan 测试程序证明 M1000 的
`vkWaitForFences`/`vkWaitSemaphores` 本身正常。

### 尝试 gamescope 3.15.17

- 从 git tag 3.15.17 建 worktree、按 pin 拉取 wlroots 子模块、编译安装到
  `/opt/steamos/gamescope-3.15`；
- 修了 primary 节点回退、present_id/present_wait feature 链；
- 仍然在 `vkCreateDevice` 返回 `VK_ERROR_EXTENSION_NOT_PRESENT`（-7），
  即使清空扩展列表、置空 pNext 也一样（原因未定位，怀疑 3.15 的 device 创建
  与 M1000 的 feature/queue 组合不兼容）。

## 结论

gamescope 的 **Vulkan 合成/扫描输出路径**在 M1000 上还不完整：
DRM 能跑起游戏但输出黑屏，嵌套后端无法创建 surface。这不是配置问题，
需要 M1000 Vulkan 驱动提供可扫描输出的 DRM modifier，或 gamescope 走非 modifier 的
线性 DMA-BUF 导入路径。

当前可用的替代：`M1000_GAMESCOPE` **不默认开启**；游戏继续用 `:3` Xorg + DXVK 2.3.1，
分辨率固定 1920×1080（原生），全屏用 `--force-windows-fullscreen` / 无边框窗口。

依赖记账：`grim`（截图工具，`/opt/steamos/INSTALL-MANIFEST.tsv` 里有 apt 行）。
