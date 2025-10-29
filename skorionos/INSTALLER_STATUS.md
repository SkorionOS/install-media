# SkorionOS 图形化安装器 - 当前状态

> 最后更新: 2025-01-30 (第二次更新)

---

## 📦 项目结构

```
/usr/local/bin/
├── installer-modular          # 启动脚本（gamescope + 设备适配）
└── installer-poc-modular      # Python 入口

/usr/share/installer/
└── device-quirks              # 设备适配脚本（屏幕方向、输出优先级）

/usr/local/lib/installer/
├── __init__.py
├── config.py                   # 全局配置（缩放、路径）
├── main.py                     # 主窗口和页面导航
│
├── backend/                    # 后端工具模块
│   ├── disk_utils.py          # 磁盘检测和操作
│   ├── install_utils.py       # 安装后处理（Steam、post_install）
│   └── log_utils.py           # 日志清理和上传（fpaste）
│
├── network/                    # 网络管理模块
│   ├── manager.py             # NetworkManager 封装
│   └── dialogs.py             # 网络对话框
│
└── ui/                         # UI 组件模块
    ├── styling.py             # CSS 样式
    ├── keyboard.py            # 虚拟键盘
    ├── components/
    │   └── base.py            # BasePage、ExecutionPage、UIComponents
    └── pages/                 # 页面组件
        ├── network.py         # 1. 网络连接
        ├── disk.py            # 2. 磁盘选择
        ├── mode.py            # 3. 安装模式
        ├── confirm.py         # 4. 确认操作
        ├── bootstrap.py       # 5. 磁盘初始化（ExecutionPage）
        ├── version.py         # 6. 版本选择
        ├── install.py         # 7. 系统安装（ExecutionPage）
        └── complete.py        # 8. 完成页面（SUCCESS/CANCELLED/FAILED）
```

---

## 🔄 页面流程

```
0. 欢迎页 (Welcome) - 内置在 main.py
   ├─→ [退出] → 8. Complete 页 (CANCELLED)
   └─→ 1. 网络页 (Network)
       └─→ 2. 磁盘选择页 (Disk)
           └─→ 3. 安装模式页 (Mode) - 检测现有安装，选择 repair/fresh/dual
               ├─→ [退出] → 8. Complete 页 (CANCELLED)
               └─→ 4. 确认页 (Confirm) - 显示操作摘要
                   ├─→ [退出] → 8. Complete 页 (CANCELLED)
                   └─→ 5. Bootstrap 页 (Bootstrap) - 执行 frzr-bootstrap
                       ├─→ [失败/退出] → 8. Complete 页 (CANCELLED/FAILED)
                       └─→ 6. 版本选择页 (Version) - 选择通道/桌面/NVIDIA
                           ├─→ [退出] → 8. Complete 页 (CANCELLED)
                           └─→ 7. 安装页 (Install) - 执行 frzr-deploy
                               ├─→ [成功] → 8. Complete 页 (SUCCESS) ✅
                               └─→ [失败/退出] → 8. Complete 页 (FAILED/CANCELLED)

8. Complete 页面 (完成页面)
   - SUCCESS: 重启 / 打开命令行 / 关机
   - CANCELLED: 重新安装 / 打开命令行 / 关机
   - FAILED: 重新安装 / 打开命令行 / 关机
   - ✅ 自动上传日志到 fpaste，显示 URL
```

---

## ✅ 已实现功能

### 核心架构
- ✅ 模块化架构 (14个文件，清晰职责)
- ✅ BasePage/ExecutionPage 基类（统一UI）
- ✅ UIComponents 组件工厂
- ✅ 页面导航系统（支持字符串名称）
- ✅ CSS 自适应缩放
- ✅ 键盘/手柄输入支持（ESC 返回）
- ✅ **设备适配系统**（自动检测屏幕方向和输出优先级）

### 页面功能
- ✅ **Network 页面**: WiFi 扫描、连接、密码输入、虚拟键盘
- ✅ **Disk 页面**: 磁盘扫描、现有安装检测、后台线程扫描
- ✅ **Mode 页面**: repair/fresh/dual 模式选择
- ✅ **Confirm 页面**: 操作摘要显示
- ✅ **Bootstrap 页面**: frzr-bootstrap 执行、实时日志、错误处理、**Steam bootstrap 下载进度显示**
- ✅ **Version 页面**: 通道/桌面/NVIDIA 选择
- ✅ **Install 页面**: frzr-deploy 执行、进度显示、日志输出、**后安装配置**
- ✅ **Complete 页面**: 统一的结束页面
  - 三种状态：SUCCESS（成功）/ CANCELLED（取消）/ FAILED（失败）
  - 自动异步上传日志到 fpaste（后台线程）
  - 实时显示上传状态和 URL
  - 不同状态显示不同的操作按钮
  - 所有"退出"按钮都跳转到此页面，而非直接退出到 TTY

### 后端功能（代码已实现）
- ✅ **disk_utils.py**:
  - `get_boot_disk()` - 获取启动盘
  - `is_disk_external()` - 检测外部磁盘
  - `is_disk_smaller_than()` - 检查磁盘大小
  - `list_available_disks()` - 列出可用磁盘
  - `check_existing_frzr_installation()` - 检测现有安装
  - `check_free_space()` - 检测空闲空间
  - `list_shrinkable_partitions()` - 列出可缩小分区
  
- ✅ **install_utils.py**:
  - `grab_steam_bootstrap()` - 获取 Steam 引导文件（基础版，无进度报告）
  - `grab_steam_bootstrap_with_progress()` - 获取 Steam 引导文件（带进度回调）
    - **使用 Python urllib 替代 curl**（更精确的进度，更好的错误处理）
    - 支持本地文件优先（`/root/packages/`）
    - 自动下载 Steam 包（精确显示文件大小）
    - 实时进度报告（基于字节数，每 5% 更新）
    - **支持断点续传**（使用 HTTP Range 头）
    - 后台线程执行，不阻塞 UI
  - `_download_file_with_progress()` - 通用文件下载函数（带进度）
    - Python urllib 原生实现
    - 支持断点续传
    - 精确的字节级进度计算
    - 文件大小验证
  - `copy_network_config()` - 复制网络配置到安装系统
  - `post_install()` - 后安装优化（Steam 配置、steamos-update）

- ✅ **log_utils.py**:
  - `cleanup_log()` - 清理日志中的 ANSI 转义码
  - `upload_log_to_fpaste()` - 上传日志到 fpaste（带超时）
  - `AsyncLogUploader` - 异步上传器（后台线程 + 回调）

### 设备适配 (Device Quirks)
- ✅ **自动检测设备型号**（基于 DMI 信息）
- ✅ **屏幕方向适配**：
  - 左旋转 (left): OXP、AYANEO、AYN、Legion Go、ZOTAC 等
  - 右旋转 (right): GPD Win 系列
  - 正常 (normal): Steam Deck、ROG Ally、GPD Win 4/Max 2 等
- ✅ **自动宽高交换**：left/right 旋转时自动交换分辨率（如 1280x800 → 800x1280）
- ✅ **输出优先级**：
  - 默认: `*,eDP-1`
  - GPD 设备: `*,DSI-1`
  - AYANEO FLIP DS: `*,eDP-1,eDP-2`（优先顶部屏幕）
- ✅ **Shader 旋转**：GPD Win 2 等不支持硬件旋转的设备
- ✅ **支持 20+ 设备型号**（OXP、AOKZOE、AYANEO、AYN、GPD、Steam Deck、ROG Ally、Legion Go、Minisforum、ZOTAC、MSI）

### UI 改进
- ✅ 统一的错误处理（显示错误、返回/重试/退出按钮）
- ✅ 自动滚动日志视图
- ✅ 状态持久化（防止页面重新执行）
- ✅ Loading spinner 动画
- ✅ 居中对齐和边距优化
- ✅ **去除所有 emoji**：改用纯文本标记（`[成功]`、`[警告]`、`[失败]`、`[ERROR]` 等）
  - 更好的日志可读性和兼容性
  - 统一的状态标记格式

### UI 缩放系统
- ✅ **UI_SCALE 支持**：支持小数缩放（1.0, 1.5, 2.0 等）
- ✅ **自动 DPI 缩放**：通过 `gtk-xft-dpi` 设置，文字大小随 UI_SCALE 同步缩放
- ✅ **布局缩放**：通过 `config.scaled()` 缩放按钮、图标、间距、边距等
- ✅ **单选框/复选框缩放**：通过 CSS 设置 `min-width/min-height` 和 `-gtk-icon-size` 缩放圆点
- ✅ **分辨率适配**：根据屏幕高度自动调整 UI_SCALE (≥1440p: 2x, ≥1080p: 1x)
- 🔧 **工作原理**：
  - `gtk-xft-dpi`：控制所有文字渲染大小（Label、TextView、Button 文字等）
  - `config.scaled()`：控制 widget 尺寸、padding、margins、图标大小
  - CSS 规则：控制单选框圆点、滚动条等 GTK 内置元素
  - 三者配合确保整体 UI 协调缩放，不会出现"按钮变大文字不变"的问题

### UI 组件统一
- ✅ **统一选择按钮组件**：`UIComponents.create_selection_button()` 用于所有选择列表
  - 磁盘选择、模式选择都使用同一组件
  - 统一的边距（10px start/end, 8px top/bottom）
  - 统一的标题粗体、描述灰色样式
- ✅ **统一边框样式**：所有选择列表使用 `info-box` CSS 类
  - 磁盘选择、模式选择、版本选择、网络列表
  - 统一的圆角边框（8px，随 UI_SCALE 缩放）
  - 统一的内边距（20px）和外边距（10px 上下）
- ✅ **滚动优化**：边框固定，内容滚动
  - 网络页面：容器边框固定，WiFi 列表在内部滚动
  - 圆角处理：第一行/最后一行添加圆角，避免覆盖边框圆角
  - 高亮效果：保留 GTK 主题的 hover/selected 背景色

### ExecutionPage 进度组件
- ✅ **标准化的进度显示组件**：
  - `self.status_label` - 大标题状态标签（支持 markup）
  - `self.progress_bar` - 进度条（0.0-1.0）
  - `self.log_view` - 滚动日志视图
- ✅ **标准化的更新方法**：
  - `update_status(text, markup=True)` - 更新状态标签
  - `update_progress(fraction, text="")` - 更新进度条
  - `append_log(text)` - 追加日志（自动滚动）
- ✅ **Bootstrap 页面应用**：
  - Steam bootstrap 下载使用进度回调
  - 实时更新状态、进度条、日志（显示 MB 和百分比）
  - 后台线程 + `GLib.idle_add` 确保线程安全

### 下载系统（urllib）
- ✅ **使用 Python urllib 替代 curl**：
  - 原生 Python 支持，无需外部命令
  - 精确的字节级进度计算（不是解析文本输出）
  - 显示精确文件大小（MB）和下载进度（%）
  - **支持断点续传**：检测部分下载，使用 HTTP Range 头继续下载
  - 更好的错误处理：HTTPError、URLError、TimeoutError
  - 文件大小验证：下载后比对 Content-Length
- ✅ **配置集中管理**（config.py）：
  - Steam 包 URL
  - 文件名
  - 存储路径
  - 易于维护和更新

### 状态栏
- ✅ **顶部状态栏**：显示系统状态信息，固定在所有页面顶部
  - **电池信息**（左侧）：
    - 电量百分比和状态（充电中/已充满）
    - GTK 图标根据电量和状态自动变化
    - 台式机/虚拟机显示"AC 电源"
    - 每分钟自动更新
  - **日期时间**（中间靠右）：
    - 格式：`YYYY-MM-DD HH:MM`
    - 每秒自动更新
  - **主题切换按钮**（最右侧）：
    - 暗色模式：显示太阳图标 ☀️（点击切换到亮色）
    - 亮色模式：显示月亮图标 🌙（点击切换到暗色）
    - 默认暗色模式启动
    - 使用 libadwaita StyleManager 实现主题切换
    - 扁平按钮样式，hover 时显示半透明背景
  - **样式**：淡色半透明背景，底部分隔线

---

## ❌ 缺失功能（阻塞性）

### 🟢 已解决的严重问题
1. ✅ **install.py 后安装步骤**（已完成 2025-01-30）
   - ✅ 已调用 `copy_network_config()` - 复制网络配置
   - ✅ 已调用 `grab_steam_bootstrap_with_progress()` - 在 bootstrap 页面执行
   - ✅ 已调用 `post_install()` - 系统优化
   - ✅ 已调用 `_verify_boot_config()` - 验证启动配置
   - **结果**: Steam 自动配置完成，网络配置保留

2. ✅ **disk.py 安全检查**（已完成 2025-01-30）
   - ✅ 已调用 `is_disk_smaller_than(disk, 55)` - 检查磁盘最小 55GB
   - ✅ 已调用 `is_disk_external(disk)` - 警告外部磁盘安装
   - ✅ 已实现对话框提示用户
   - **结果**: 用户安装前会收到明确警告

---

## ⚠️ 需要测试

### 核心功能测试
1. **完整安装流程测试** - 测试 repair/fresh/dual 模式
2. **Steam bootstrap 下载** - 删除本地文件测试下载进度显示
3. **安全检查对话框** - 测试小磁盘和外部磁盘警告
4. **网络配置复制** - 验证安装后 WiFi 连接保留
5. **post_install 优化** - 验证 Steam 首次启动无需额外配置

---

## 🟡 可选改进（第二优先级）

### 功能增强
- [ ] 本地安装文件扫描（scan_frzr_update_files）
- [ ] 高级选项 UI（固件覆盖、CDN、Debug）
- [ ] 帮助页面/对话框

### 体验优化
- [ ] 更精确的 frzr-deploy 进度解析
- [ ] 磁盘描述显示 transport 类型（内置/USB/SD卡）
- [ ] overrides 文件支持（设备特定型号名称）
- [ ] 安装时间估算

---

## 🎯 下一步 TODO

### 已完成（2025-01-30）
1. ✅ 清理过时文档
2. ✅ 创建 `ui/pages/complete.py`
3. ✅ 在 `main.py` 注册 complete 页面
4. ✅ 修复 `install.py` 添加后安装步骤
5. ✅ 在 `disk.py` 添加安全检查
6. ✅ 实现 Steam bootstrap 下载进度显示
7. ✅ 去除所有 emoji，改用纯文本标记
8. ✅ **使用 urllib 替代 curl 进行下载**（精确进度、断点续传）
9. ✅ **配置集中管理**（Steam URL 移到 config.py）

### 待测试（本周）
8. [ ] 测试完整安装流程（repair/fresh/dual）
9. [ ] 测试 Steam bootstrap 下载进度（无本地文件场景）
10. [ ] 测试安全检查对话框（小磁盘、外部磁盘）
11. [ ] 验证网络配置复制功能
12. [ ] 验证 Steam 首次启动优化

### 近期执行（后续）
13. [ ] 实现本地安装文件扫描（FRZR_UPDATE）
14. [ ] 添加高级选项 UI（固件覆盖、CDN、Debug）
15. [ ] 改进 frzr-deploy 进度解析精确度
16. [ ] 添加帮助系统/FAQ

---

## 📝 已修复的已知问题

### 2025-01-30 已修复
1. ✅ ~~**安装成功后无法重启**~~ - Complete 页面已实现
2. ✅ ~~**Steam 首次启动慢**~~ - 已在 bootstrap 页面调用 `grab_steam_bootstrap_with_progress()`
3. ✅ ~~**安装后需重新配置 WiFi**~~ - 已在 install 页面调用 `copy_network_config()`
4. ✅ ~~**可能安装到不安全的磁盘**~~ - disk 页面已添加安全检查对话框

### 待观察
- [ ] frzr-deploy 进度解析精确度（当前基于行数估算）
- [ ] 长时间安装过程中的超时处理
- [ ] 网络断开时的重试机制

---

## 🏆 架构优势

### 模块化设计
- 清晰的职责分离
- 每个文件 < 600 行
- 易于测试和维护

### 组件复用
- BasePage 提供统一结构
- ExecutionPage 统一执行流程
- UIComponents 统一 UI 元素

### 可扩展性
- 新增页面只需继承 BasePage
- 新增后端功能独立于 UI
- 样式统一通过 CSS 管理

---

## 📦 系统依赖

安装器需要以下软件包（已添加到 `skorionos/packages.x86_64`）：

### 核心依赖
- **gamescope** - Wayland 合成器，提供全屏显示环境
- **gtk4** - GTK 4 图形界面库
- **libadwaita** - Adwaita 主题库，提供主题切换功能
- **python-gobject** - Python GTK 绑定

### 图形和网络
- **mesa** / **libdrm** - OpenGL/Vulkan 驱动
- **vulkan-icd-loader** / **vulkan-radeon** / **vulkan-intel** - Vulkan 支持
- **wayland** - Wayland 协议库
- **libnm** - NetworkManager 库（网络管理）
- **adwaita-icon-theme** - Adwaita 图标主题
- **wqy-microhei** - 中文字体

---

## 🚀 启动流程

### Live CD 自动启动流程

```
系统启动
  ↓
getty 自动登录 root
  ↓
.zshrc 执行
  ↓
install-init.sh
  ↓
copy_system_configs (复制已有系统配置)
  ↓
setup_controller_support (配置手柄支持)
  ↓
显示安装器选择器
  ├─ "modular" → 图形化安装器 (默认)
  │   └─ 直接启动 /usr/local/bin/installer-modular
  │
  └─ "text" → 文本安装器
      ↓
      check_internet_connection (检查网络)
      ├─ 有网络 → OFFLINE_MODE=false
      ├─ 无网络 → 显示菜单：
      │   ├─ "网络配置" → nmtui-connect
      │   ├─ "跳过" → OFFLINE_MODE=true (离线模式)
      │   └─ "退出" → exit
      ↓
      check_and_update_install_script (仅在线模式)
      ↓
      启动 install.sh
```

### 文本安装器离线模式支持

- ✅ **网络检测优化**：用户可选择跳过网络配置，进入离线模式
- ✅ **离线安装限制**：
  - 离线模式下只能使用本地镜像安装（USB 设备，标签 `FRZR_UPDATE`）
  - 不显示在线安装选项
  - 如果没有本地镜像，提示用户插入 USB 或重启联网
- ✅ **智能脚本更新**：离线模式下跳过 `install.sh` 的在线更新

### 图形化安装器运行方式

```bash
# 从 Live CD 启动（自动）
# 或手动启动图形化安装器
/usr/local/bin/installer-modular

# 查看日志
tail -f /tmp/installer-modular.log

# 自定义缩放
UI_SCALE=2.0 /usr/local/bin/installer-modular
```

### 日志系统

#### 统一日志路径
所有安装阶段的日志都写入同一个文件：`/tmp/frzr.log`

- ✅ **Launcher 阶段**：`installer-modular` 环境信息和 gamescope 启动 → `/tmp/frzr.log`
- ✅ **Bootstrap 阶段**：`frzr-bootstrap` 输出 → `/tmp/frzr.log`（追加模式）
- ✅ **Install 阶段**：`frzr-deploy` 输出 → `/tmp/frzr.log`（追加模式）
- ✅ **后安装步骤**：Steam bootstrap、post_install → `/tmp/frzr.log`（追加模式）

**双重日志保存**：
- `/tmp/installer-modular.log` - launcher 专用日志（便于单独查看环境信息）
- `/tmp/frzr.log` - 统一的完整日志（包含 launcher + bootstrap + install + post_install）

#### 自动日志上传（fpaste）
在 Complete 页面，安装器会自动：

1. **检查日志文件**：如果日志文件不存在（如用户在欢迎页直接退出），显示"暂无日志文件"，不进行上传
2. **清理日志**：移除 ANSI 转义码、多余空格、脚本标记
3. **异步上传**：后台线程上传到 fpaste，不阻塞 UI
4. **实时反馈**：
   - 无日志：显示 "暂无日志文件（未执行安装操作）"
   - 上传中：显示 "正在上传日志..."
   - 成功：显示 fpaste URL（可复制）
   - 失败：提示手动上传命令

**实现细节**：
- 文件：`backend/log_utils.py`
- 类：`AsyncLogUploader`（支持回调）
- 超时：10 秒
- 线程安全：使用 `GLib.idle_add` 更新 GTK UI
- 日志检查：在 `populate_content()` 中使用 `os.path.exists()` 检查文件存在性

### 退出按钮行为

所有页面的"退出"按钮**不再直接退出到 TTY**，而是跳转到 Complete 页面（CANCELLED 状态）：

| 页面 | 退出按钮行为 |
|------|--------------|
| 欢迎页 | → Complete (CANCELLED) |
| 模式选择 | → Complete (CANCELLED) |
| 确认页 | → Complete (CANCELLED) |
| 版本选择 | → Complete (CANCELLED) |
| Bootstrap（失败） | → Complete (CANCELLED/FAILED) |
| Install（失败） | → Complete (FAILED) |

在 Complete 页面，用户可以选择：
- **重新安装**：重启安装器
- **打开命令行**：退出到 TTY（真正的退出）
- **关机** / **重启**：系统操作

这种设计确保：
1. 用户不会意外退出到 TTY
2. 日志始终能上传（即使取消安装）
3. 所有退出路径统一、清晰

---

## 🐛 最近修复

### 2025-01-30 修复

#### 问题 1：Steam bootstrap 下载无进度显示
**现象**：下载 Steam 包（~300MB）时，用户界面无任何进度反馈，显示卡住。

**第一次修复**（使用 curl）：
1. 在 `install_utils.py` 添加 `grab_steam_bootstrap_with_progress()` 函数
   - 支持进度回调 `progress_callback(message, progress_fraction)`
   - 使用 `subprocess.Popen` 实时解析 curl 的 `-#` 进度输出
   - 每 5% 更新一次进度
2. 修改 `bootstrap.py` 的 `_grab_steam_bootstrap()` 方法
   - 后台线程执行下载，使用 `GLib.idle_add` 确保线程安全

**第二次改进**（使用 urllib - 推荐）：
1. **配置集中管理**（`config.py`）
   - 添加 `steam_package_url` 等配置，易于维护
2. **使用 Python urllib 替代 curl**（`install_utils.py`）
   - 新增 `_download_file_with_progress()` 通用下载函数
   - 基于字节数精确计算进度（而非解析文本）
   - 显示精确文件大小和下载进度（如 "下载中... 50.5% (152.3MB / 304.5MB)"）
   - **支持断点续传**：自动检测部分下载，使用 HTTP Range 头继续
   - 更好的错误处理和文件验证
3. 修改 `grab_steam_bootstrap_with_progress()` 使用新下载函数
   - 从 `config` 读取 URL 和路径配置
   - 调用 `_download_file_with_progress()` 替代 curl

**结果**：
- 用户可以看到精确的下载进度和文件大小
- 支持断点续传（下载中断后可继续）
- 无需依赖外部 curl 命令
- 配置集中管理，易于维护

#### 问题 2：日志输出使用 emoji
**现象**：日志中大量使用 emoji（✓、⚠️、❌ 等），在某些终端或日志查看器中显示异常，影响可读性。

**修复**：统一替换所有 emoji 为纯文本标记：
- `✓` → `[成功]`
- `⚠️` → `[警告]`
- `❌` → `[失败]` / `[ERROR]`
- `🔄` / `🚀` / `📝` 等 → 移除或改为描述性文本

**修改文件**：
- `install_utils.py`
- `bootstrap.py`
- `install.py`
- `base.py`
- `installer-modular`
- `network/manager.py`

**结果**：日志更具可读性和兼容性，适合任何终端环境。

### 2025-01-29 修复

#### 问题 1：日志未统一
**现象**：`installer-modular` 的日志输出到 `/tmp/installer-modular.log`，与安装器内部日志分离，不便于排查问题。

**修复**：
- 修改 `installer-modular` 脚本
- 添加 `UNIFIED_LOG="/tmp/frzr.log"`
- 使用 `tee -a` 同时输出到两个文件：
  ```bash
  } 2>&1 | tee "$LOGFILE" | tee -a "$UNIFIED_LOG"
  ```

**结果**：所有日志（launcher + installer）都追加到 `/tmp/frzr.log`，同时保留 `/tmp/installer-modular.log` 便于单独查看环境信息。

#### 问题 2：Complete 页面按钮不显示
**现象**：用户退出到 Complete 页面后，页面下方没有任何按钮，无法进行任何操作。

**原因**：
1. `CompletePage` 定义了 `create_nav_buttons()` 方法，但 `BasePage` 调用的是 `populate_buttons()`
2. 页面首次通过 `create()` 创建时，调用空的 `populate_buttons()`，导致没有按钮
3. 只有调用 `set_status()` 后才会调用 `create_nav_buttons()`

**修复**：
- 将 `create_nav_buttons()` 改名为 `populate_buttons()`（重写基类方法）
- 在 `populate_buttons()` 开头添加 `if self.status is None` 处理默认按钮
- 修改 `set_status()` 调用 `populate_buttons()` 而不是 `create_nav_buttons()`

**结果**：页面首次创建时也能正确显示按钮。

#### 问题 3：日志不存在时提示不友好
**现象**：用户在欢迎页直接点"退出"，Complete 页面立即显示"日志上传失败"，但实际上是因为日志文件还不存在。

**修复**：
- 在 `populate_content()` 中添加 `os.path.exists()` 检查
- 如果日志文件不存在，显示"暂无日志文件（未执行安装操作）"
- 跳过日志上传流程

**结果**：用户体验更友好，信息更准确。

---

*基于实际代码生成 - 2025-01-29*

