# SkorionOS 图形化安装器 - 当前状态

> 最后更新: 2025-01-30 (第四次更新)
> 
> 基于 GTK4 + Python 的现代化安装器，支持手柄操作、多设备适配、进度显示、本地安装、高级选项

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
├── config.py                   # 全局配置（缩放、路径、Steam URL）
├── main.py                     # 主窗口和页面导航
│
├── backend/                    # 后端工具模块
│   ├── disk_utils.py          # 磁盘检测和操作
│   ├── install_utils.py       # 安装后处理（Steam、post_install）
│   ├── local_file_manager.py  # 本地文件扫描与挂载管理 🆕
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
        ├── version.py         # 6. 版本选择（含安装方式选择 🆕）
        ├── advanced.py        # 7. 高级选项（固件/CDN/Debug 🆕）
        ├── install.py         # 8. 系统安装（ExecutionPage，支持本地安装 🆕）
        └── complete.py        # 9. 完成页面（SUCCESS/CANCELLED/FAILED）
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
                   └─→ 5. Bootstrap 页 (Bootstrap) - 执行 frzr-bootstrap，扫描本地文件 🆕
                       ├─→ [失败/退出] → 8. Complete 页 (CANCELLED/FAILED)
                       └─→ 6. 版本选择页 (Version) - 选择安装方式（在线/本地）+ 配置 🆕
                           ├─→ [退出] → 9. Complete 页 (CANCELLED)
                           ├─→ [启用高级选项] → 7. 高级选项页 (Advanced) 🆕
                           │   ├─→ [退出] → 9. Complete 页 (CANCELLED)
                           │   └─→ 8. 安装页 (Install)
                           └─→ [不启用高级选项] → 8. 安装页 (Install) - 执行 frzr-deploy（在线或本地文件） 🆕
                               ├─→ [成功] → 9. Complete 页 (SUCCESS) ✅
                               └─→ [失败/退出] → 9. Complete 页 (FAILED/CANCELLED)

8. Complete 页面 (完成页面)
   - SUCCESS: 重启 / 打开命令行 / 关机
   - CANCELLED: 重新安装 / 打开命令行 / 关机
   - FAILED: 重新安装 / 打开命令行 / 关机
   - ✅ 自动上传日志到 fpaste，显示 URL
   - ✅ 自动清理临时挂载（本地安装） 🆕
```

---

## ✅ 已实现功能

### 核心架构
- ✅ 模块化架构 (15个文件，清晰职责)
- ✅ BasePage/ExecutionPage 基类（统一UI）
- ✅ UIComponents 组件工厂
- ✅ 页面导航系统（支持字符串名称）
- ✅ CSS 自适应缩放
- ✅ 键盘/手柄输入支持（ESC 返回）
- ✅ **设备适配系统**（自动检测屏幕方向和输出优先级）

### 页面功能
- ✅ **Network 页面**: WiFi 扫描、连接、密码输入、虚拟键盘
- ✅ **Disk 页面**: 磁盘扫描、现有安装检测、后台线程扫描、磁盘描述显示 `[内置]/[USB]/[SD卡]`
- ✅ **Mode 页面**: repair/fresh/dual 模式选择
- ✅ **Confirm 页面**: 操作摘要显示
- ✅ **Bootstrap 页面**: frzr-bootstrap 执行、实时日志、错误处理、**Steam bootstrap 下载进度显示**、**本地文件扫描** 🆕
- ✅ **Version 页面**: **安装方式选择（在线/本地）** 🆕、通道/桌面/NVIDIA 选择、**本地文件列表显示** 🆕、**高级选项开关** 🆕
- ✅ **Advanced 页面**: **固件覆盖、CDN 加速、备用源、Debug 模式** 🆕
- ✅ **Install 页面**: frzr-deploy 执行、**支持本地文件安装** 🆕、**应用高级选项配置** 🆕、进度显示、日志输出、**后安装配置**
- ✅ **Complete 页面**: 统一的结束页面、**自动清理临时挂载** 🆕
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
  - `get_disk_human_description()` - 获取磁盘描述（类型、厂商、型号、大小）
  - `get_disk_model_override()` - 读取 /root/overrides 自定义磁盘名称
  
- ✅ **local_file_manager.py** 🆕:
  - `LocalFileManager` - 本地文件扫描与挂载生命周期管理
  - `scan_files()` - 扫描所有支持分区的 FRZR_UPDATE 文件
  - `_get_or_mount()` - 智能挂载（已挂载直接用，未挂载临时挂载）
  - `_scan_partition()` - 扫描分区中的文件（支持 4 种格式）
  - `cleanup()` - 清理临时挂载
  - **完全对齐文本安装器的扫描逻辑**
  - **智能挂载管理**：不干预已有挂载，只清理自己创建的挂载
  - **延迟清理策略**：保持挂载到安装完成
  - **双重清理保障**：atexit + Complete 页面

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
  - `post_install()` - 后安装优化
    - 遍历所有 btrfs 部署子卷
    - 修改 Steam 会话文件（添加 -nobootstrapupdate 等参数）
    - 修改 steamos-update 脚本（防止运行时更新）
    - 处理 /source 文件（删除扩展名）
    - 设置子卷读写/只读状态
  - `_modify_steam_session()` - 修改 Steam 会话文件
  - `_modify_steamos_update()` - 修改 steamos-update 脚本

- ✅ **log_utils.py**:
  - `cleanup_log()` - 清理日志中的 ANSI 转义码
  - `upload_log_to_fpaste()` - 上传日志到 fpaste（带超时）
  - `AsyncLogUploader` - 异步上传器（后台线程 + 回调）

### 本地安装系统（LocalFileManager）🆕

**完全对齐文本安装器的扫描逻辑**：

#### 扫描策略
- ✅ 扫描所有支持的分区（ntfs/ext4/vfat/exfat/btrfs）
- ✅ 扫描所有设备类型（part/dm/crypt/lvm）
- ✅ 查找每个分区的 `FRZR_UPDATE/` 文件夹
- ✅ 文件名匹配（正则）：`^(chimeraos|skorionos)-.*(\.img\.tar\.xz|\.xz|\.zst|\.skosys)$`
- ✅ 显示设备名、文件大小、完整路径

#### 挂载生命周期管理
```python
# 智能挂载
if 已挂载:
    直接使用，不记录  # 不干预系统已有挂载
else:
    临时挂载到 /tmp/frzr_scan_*
    记录到 mounted_by_us[]  # 只清理我们创建的挂载

# 延迟清理
扫描后保持挂载  # 文件路径在临时挂载点上
安装时文件仍可访问
完成后自动清理  # atexit + Complete 页面双保障
```

#### Version 页面动态 UI
- ✅ 检测本地文件可用性
- ✅ 动态显示"安装方式"选择（在线/本地）
- ✅ 本地模式：显示文件列表（设备名、文件名、大小、选择）
- ✅ 在线模式：显示通道/桌面/NVIDIA 选择
- ✅ 智能 UI 切换（根据用户选择）

#### Install 页面适配
```python
if install_mode == 'local':
    cmd = ['frzr-deploy', '/tmp/frzr_scan_sda1/FRZR_UPDATE/skorionos.img.tar.zst']
else:
    cmd = ['frzr-deploy', 'skorionos/stable', '--desktop', 'gnome']
```

#### 与文本安装器的对比
| 特性 | 文本安装器 | 图形安装器 | 状态 |
|-----|----------|----------|------|
| 扫描范围 | 所有支持的分区 | 所有支持的分区 | ✅ 一致 |
| 文件格式 | 4种 | 4种 | ✅ 一致 |
| 文件名验证 | 正则匹配 | 正则匹配 | ✅ 一致 |
| 挂载管理 | 智能保持 | 智能保持 | ✅ 一致 |
| 文件信息 | 显示设备/大小 | 显示设备/大小 | ✅ 一致 |
| 清理机制 | trap EXIT | atexit + Complete | ✅ 一致 |

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
- ✅ **Bootstrap/Install 页面应用**：
  - Steam bootstrap 下载使用进度回调
  - 本地文件扫描显示结果
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
  ```python
  self.steam_package_url = "https://..."
  self.steam_package_filename = "steam-jupiter-stable.pkg.tar.zst"
  self.steam_bootstrap_filename = "bootstraplinux_ubuntu12_32.tar.xz"
  self.steam_packages_dir = "/root/packages"
  self.mount_path = "/tmp/frzr_root"
  self.log_file = "/tmp/frzr.log"
  self.min_disk_size = 55  # GB
  ```
  - 易于维护和更新
  - 避免硬编码

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

### 后安装流程（post_install）
- ✅ **遍历部署子卷**：
  - 列出所有 btrfs 子卷
  - 查找 `deployments/chimeraos` 和 `deployments/skorionos`
  - 对每个部署子卷执行优化
  
- ✅ **修改 Steam 会话文件**（`_modify_steam_session()`）：
  - 文件位置：`usr/share/gamescope-session-plus/sessions.d/steam`
  - 添加参数：`-nobootstrapupdate -skipinitialbootstrap`
  - 添加 loginusers.vdf 检查逻辑
  - 目的：防止 Steam 每次启动都重新下载引导文件
  
- ✅ **修改 steamos-update 脚本**（`_modify_steamos_update()`）：
  - 文件位置：`usr/bin/steamos-update`
  - 添加进程检查：`ps -ef | grep "nobootstrapupdate" && exit 0`
  - 目的：防止 Steam 运行时执行系统更新
  
- ✅ **设置子卷读写状态**：
  - 修改前：设置为可写（`ro false`）
  - 修改后：设置为只读（`ro true`）
  - 使用 btrfs property 命令
  
- ✅ **处理 /source 文件**：
  - 删除文件扩展名（例如 `.img`）
  - 确保 frzr-deploy 正确识别源

### 统一日志系统
- ✅ **单一日志文件**：所有阶段写入 `/tmp/frzr.log`
  - Launcher（installer-modular 环境信息）
  - Bootstrap（frzr-bootstrap 输出）
  - Install（frzr-deploy 输出）
  - Post-install（Steam bootstrap、post_install、验证）
- ✅ **自动清理**：删除 ANSI 转义码、空行、过长空格
- ✅ **自动上传**：Complete 页面异步上传到 fpaste，显示 URL

---

## ❌ 缺失功能（阻塞性）

**无** - 所有核心功能已实现，包括本地安装 🎉

---

## ⚠️ 待实现功能（非阻塞）

### 用户体验
- [ ] 帮助系统/FAQ
- [ ] 更精确的 frzr-deploy 进度解析（目前基于关键词）
- [ ] 安装时间估算

---

## 🧪 待测试功能

### 核心流程测试
1. [ ] 完整安装流程（repair/fresh/dual 三种模式）
2. [ ] 本地安装流程（有本地文件/无本地文件）
3. [ ] 多个 USB 设备同时插入（文件选择）
4. [ ] 断点续传（Steam bootstrap 下载中断后继续）

### 安全检查测试
5. [ ] 小磁盘警告（< 55GB）
6. [ ] 外部磁盘警告
7. [ ] 磁盘空间不足（dual 模式）

### 后安装测试
8. [ ] 网络配置复制（安装后 WiFi 保留）
9. [ ] Steam 首次启动（无需额外配置）
10. [ ] post_install 脚本修改（Steam 会话、steamos-update）

### 清理机制测试
11. [ ] 临时挂载清理（本地安装完成后）
12. [ ] 异常退出清理（Ctrl+C、断电等）

---

## 🔄 更新历史

### 最近完成（2025-01-30 第三次更新）🆕

1. ✅ **完成本地安装功能**
   - 创建 `LocalFileManager` 类（挂载生命周期管理）
   - 完全对齐文本安装器的扫描逻辑（支持 4 种文件格式）
   - Version 页面添加"安装方式"选择（在线/本地）
   - 动态显示本地文件列表（设备名、大小、选择）
   - Install 页面支持本地文件安装
   - 集成自动清理机制（atexit + Complete 页面）

2. ✅ **完成高级选项功能** 🆕
   - 创建 Advanced Options 页面（4 个选项）
   - 固件覆盖：创建 device-quirks 配置
   - CDN 加速：修改 frzr-sk.conf 的 release_cdn/api_cdn
   - 备用源：控制 fallback_url（默认启用）
   - Debug 模式：传递 DEBUG 环境变量
   - Version 页面添加"启用高级选项"切换
   - Install 页面应用配置（在 frzr-deploy 前执行）

### 最近完成（2025-01-30 第二次更新）

1. ✅ 使用 urllib 替代 curl（精确进度、断点续传）
2. ✅ 配置集中管理（Steam URL 移到 config.py）
3. ✅ 修复所有硬编码（55GB、/tmp/frzr_root 等）
4. ✅ 去除所有 emoji（改用 `[成功]`/`[警告]`/`[失败]`）
5. ✅ Complete 页面（统一退出流程）
6. ✅ 后安装步骤（网络配置、Steam、验证）
7. ✅ 安全检查（磁盘大小、外部磁盘警告）

### 最近完成（2025-01-29 第一次更新）

1. ✅ Complete 页面重写（按钮问题修复）
2. ✅ 日志统一到 /tmp/frzr.log
3. ✅ 日志上传到 fpaste（异步）
4. ✅ 状态栏实现（电池、时间、主题切换）
5. ✅ libadwaita 集成（主题切换）
6. ✅ 磁盘描述显示（[内置]/[USB]/[SD卡]）
7. ✅ overrides 文件支持

---

## 🐛 已修复问题

### 2025-01-30 (第三次更新)
- ✅ 本地安装功能不完整 → 完全实现（扫描、选择、安装、清理）
- ✅ 与文本安装器扫描逻辑不一致 → 完全对齐（4 种格式、智能挂载）
- ✅ 挂载管理缺失 → LocalFileManager（生命周期管理、自动清理）

### 2025-01-30 (第二次更新)
- ✅ Steam bootstrap 下载无进度 → urllib + 实时进度
- ✅ 日志使用 emoji → 纯文本标记
- ✅ 配置硬编码 → config.py 集中管理

### 2025-01-29
- ✅ 日志未统一 → 统一写入 /tmp/frzr.log
- ✅ Complete 页面按钮不显示 → 重写 populate_buttons()
- ✅ 日志不存在提示不友好 → 添加文件检查
- ✅ 主题切换无效 → 使用 libadwaita StyleManager
- ✅ 主题切换按钮太高 → CSS 优化
- ✅ Welcome 页按钮样式不统一 → UIComponents 统一创建
- ✅ 重新安装导致缩放异常 → 改为重置状态而非重启进程

---

## 📊 系统依赖

### 核心依赖
- `gamescope` - Wayland compositor
- `gtk4` - GTK 4 toolkit
- `libadwaita` - Adwaita widgets & theme support
- `python-gobject` - Python GTK bindings

### 图形依赖
- `mesa`
- `vulkan-icd-loader`
- `wayland`
- `adwaita-icon-theme`

### 网络依赖
- `libnm` - NetworkManager library

### 字体依赖
- `wqy-microhei` - 中文字体

---

*文档生成于 2025-01-30*
