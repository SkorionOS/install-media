# SkorionOS 图形化安装器 - 当前状态

> 最后更新: 2025-10-31 (第十次更新)
> 
> 基于 GTK4 + Python 的现代化安装器，支持手柄操作、多设备适配、进度显示、本地安装、高级选项、统一日志系统、UI布局优化、智能回退机制、网络检测、离线模式、多系统安装、实时网速显示

---

## 📦 项目结构

```
/root/
└── install-init.sh            # Live ISO 入口脚本（智能回退机制 🆕）

/usr/local/bin/
├── installer-modular          # 启动脚本（gamescope + socket 检查 🆕）
└── installer                  # Python 入口

/usr/share/installer/
├── device-quirks              # 设备适配脚本（屏幕方向、输出优先级）
└── Skorion.svg                # 欢迎页 Logo

/usr/local/lib/installer/
├── __init__.py
├── config.py                   # 全局配置（缩放、路径、Steam URL）
├── logger.py                   # 统一日志系统（结构化日志、异常跟踪）🆕
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
        ├── partition_adjust.py # 4. 分区调整（多系统安装专用，三列布局 🆕）
        ├── confirm.py         # 5. 确认操作
        ├── bootstrap.py       # 6. 磁盘初始化（ExecutionPage）
        ├── version.py         # 7. 版本选择（含安装方式选择 🆕）
        ├── advanced.py        # 8. 高级选项（固件/CDN/Debug 🆕）
        ├── install.py         # 9. 系统安装（ExecutionPage，支持本地安装 🆕）
        └── complete.py        # 10. 完成页面（SUCCESS/CANCELLED/FAILED）
```

---

## 🔄 页面流程

```
0. 欢迎页 (Welcome) - 内置在 main.py
   ├─→ [退出] → 10. Complete 页 (CANCELLED)
   └─→ 1. 网络页 (Network)
       └─→ 2. 磁盘选择页 (Disk)
           └─→ 3. 安装模式页 (Mode) - 检测现有安装，选择 repair/fresh/dual
               ├─→ [退出] → 10. Complete 页 (CANCELLED)
               ├─→ [多系统安装 & 空间不足] → 4. 分区调整页 (PartitionAdjust) 🆕
               │   ├─→ [返回] → 2. 磁盘选择页
               │   └─→ [继续] → 5. 确认页 (Confirm) - 显示分区操作摘要
               └─→ [其他模式] → 5. 确认页 (Confirm) - 显示操作摘要
                   ├─→ [退出] → 10. Complete 页 (CANCELLED)
                   └─→ 6. Bootstrap 页 (Bootstrap) - 执行 frzr-bootstrap，扫描本地文件 🆕
                       ├─→ [失败/退出] → 10. Complete 页 (CANCELLED/FAILED)
                       └─→ 7. 版本选择页 (Version) - 选择安装方式（在线/本地）+ 配置 🆕
                           ├─→ [退出] → 10. Complete 页 (CANCELLED)
                           ├─→ [启用高级选项] → 8. 高级选项页 (Advanced) 🆕
                           │   ├─→ [退出] → 10. Complete 页 (CANCELLED)
                           │   └─→ 9. 安装页 (Install)
                           └─→ [不启用高级选项] → 9. 安装页 (Install) - 执行 frzr-deploy（在线或本地文件） 🆕
                               ├─→ [成功] → 10. Complete 页 (SUCCESS) ✅
                               └─→ [失败/退出] → 10. Complete 页 (FAILED/CANCELLED)

10. Complete 页面 (完成页面)
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
- ✅ **智能回退机制**（图形安装器失败自动降级到文本安装器）🆕

### 智能回退机制 🆕

参考 `gamescope-session-plus` 设计，实现了多层次的失败检测和自动恢复：

#### 第一层：Socket 检查（Gamescope 启动检测）
在 `installer-modular` 中：
- ✅ 创建 socket 用于 Gamescope 启动确认
- ✅ 15秒超时等待 Gamescope 响应
- ✅ 未响应 → 快速失败（exit 1）
- ✅ 提前检测 Gamescope 崩溃/GPU 问题

#### 第二层：运行时长判断（启动失败检测）
在 `install-init.sh` 中：
- ✅ 记录图形安装器运行时长
- ✅ 运行 < 15秒 → 判定为启动失败或崩溃
- ✅ 运行 ≥ 15秒 → 判定为正常退出（成功或用户主动）

#### 第三层：失败计数与自动降级
- ✅ 持久化失败记录（`/tmp/installer-failures`）
- ✅ 每行记录一次失败（时间戳）
- ✅ 失败 2 次 → 自动降级到文本安装器
- ✅ 正常退出 → 清除失败记录

#### 启动参数支持
- ✅ `installer=text` → 强制使用文本安装器
- ✅ 绕过图形安装器，直接进入稳定模式

#### 工作流程
```
图形安装器启动
    ↓
Socket 检查（15秒）
    ├─ 成功 → 运行...
    └─ 失败 → exit 1 → 计入失败次数
         ↓
    运行时长判断
    ├─ < 15秒 → 计入失败次数
    │   ├─ 失败 1 次 → 自动重试
    │   └─ 失败 2 次 → 自动降级到文本安装器
    └─ ≥ 15秒 → 清除失败记录
```

#### 优势
- ✅ **完全自动化**：无需用户交互
- ✅ **双重检测**：Socket（提前）+ 运行时长（兜底）
- ✅ **精确判断**：区分崩溃和用户主动退出
- ✅ **自动恢复**：首次失败自动重试，多次失败降级
- ✅ **用户无感知**：自动处理，平滑过渡

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
  - `grab_steam_bootstrap_with_progress()` - 获取 Steam 引导文件（带进度回调）🆕
    - **使用 Python urllib 替代 curl**（更精确的进度，更好的错误处理）
    - 支持本地文件优先（`/root/packages/`）
    - 自动下载 Steam 包（精确显示文件大小）
    - 实时进度报告（基于字节数，每 5% 更新）
    - **支持断点续传**（使用 HTTP Range 头）
    - **自动重试机制**（最多3次，文件损坏自动删除并重新下载）🆕
    - **完整性验证**（文件大小 > 250MB，tar/xz 格式验证）🆕
    - **详细错误日志**（捕获 tar/xz 的 stderr 输出）🆕
    - 后台线程执行，不阻塞 UI
  - `_download_file_with_progress()` - 通用文件下载函数（带进度）
    - Python urllib 原生实现
    - 支持断点续传
    - 精确的字节级进度计算
    - 文件大小验证
  - `_extract_bootstrap_from_steam_pkg()` - 从 Steam 包提取引导文件 🆕
    - 文件大小检查（必须 > 250MB）
    - tar 内容列表验证（30秒超时）
    - 提取到临时文件并验证 xz 格式
    - 捕获并记录所有命令错误输出（tar/xz stderr）
    - 检测损坏文件自动删除
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

### 多系统安装与分区调整 🆕

#### PartitionAdjustPage（分区调整页面）

**触发条件**：多系统安装时磁盘空闲空间不足（< 55GB）

**三列水平布局设计**：
```
┌─────────────────┬─────────────────┬─────────────────┐
│  分区列表（左）   │  操作选择（中）   │  空间大小（右）   │
│  ● /dev/sda3    │  ● 缩小分区      │  ● 60GB         │
│  ○ /dev/sda4    │  ○ 删除整个分区   │  ○ 100GB        │
│  ○ /dev/sda5    │                 │  ○ 200GB        │
│  [ScrolledWin]  │                 │                 │
└─────────────────┴─────────────────┴─────────────────┘
```

**功能特性**：
- ✅ **三列独立滚动**：分区列表支持滚动，操作和大小固定显示
- ✅ **全行可点击**：所有选项使用 `UIComponents.create_selection_button()`
- ✅ **智能联动**：选择"删除分区"时自动禁用大小选择
- ✅ **单选按钮组**：替代 ComboBox，更直观的视觉反馈
- ✅ **空间优化**：水平布局充分利用屏幕宽度，减少垂直高度

**交互逻辑**：
```python
# 收集用户选择
partition = app.selected_partition  # 例如: /dev/sda3
operation = app.partition_operation  # 'shrink' 或 'delete_entire_partition'
size_gb = app.shrink_size_gb  # 60, 100, 200 (仅 shrink 时有效)

# 传递给 frzr-bootstrap（非交互模式）
env = {
    'FRZR_NONINTERACTIVE': '1',
    'FRZR_SHRINK_PARTITION': partition if operation == 'shrink' else '',
    'FRZR_SHRINK_SIZE': str(size_gb) if operation == 'shrink' else '',
    'FRZR_DELETE_PARTITION': partition if operation == 'delete_entire_partition' else ''
}
```

#### frzr-bootstrap 非交互模式增强 🆕

**修改的 whiptail 确认点**：

1️⃣ **删除分区确认**（shrink_selected_partition, line 676）：
```bash
if [ "$IS_NONINTERACTIVE" = true ]; then
    echo "[NONINTERACTIVE] Skipping delete partition confirmation for: $partition"
else
    whiptail --yesno "*** 最终确认 - 不可逆操作 ***" ...
fi
```

2️⃣ **缩小分区确认**（shrink_selected_partition, line 711）：
```bash
if [ "$IS_NONINTERACTIVE" = true ]; then
    echo "[NONINTERACTIVE] Skipping shrink partition confirmation: $partition, releasing: $display_size"
else
    whiptail --yesno "确认缩小分区?" ...
fi
```

3️⃣ **多空闲空间选择**（select_free_space, line 439）：
```bash
if [ "$IS_NONINTERACTIVE" = true ]; then
    echo "[NONINTERACTIVE] Multiple free spaces found, auto-selecting first one"
    selected="${usable_spaces[0]}"  # 自动选择最大的
else
    whiptail --menu "选择要使用的空闲空间:" ...
fi
```

**完全非交互执行流程**：
```
图形界面选择分区参数 → 传递环境变量 → frzr-bootstrap 自动执行
                                          ↓
                    检测到 IS_NONINTERACTIVE=true
                                          ↓
                    跳过所有 whiptail 确认
                                          ↓
                    自动执行分区操作（缩小/删除）
                                          ↓
                    自动选择空闲空间
                                          ↓
                    创建 SkorionOS 分区
                                          ↓
                    继续安装流程
```

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
  - 磁盘选择、模式选择、本地文件选择都使用同一组件
  - 统一的边距（10px start/end, 8px top/bottom）
  - 统一的标题粗体、描述灰色样式
  - 整行可点击，hover 时有视觉反馈
- ✅ **统一边框样式**：所有选择列表使用 `info-box` CSS 类
  - 磁盘选择、模式选择、版本选择、本地文件选择、网络列表
  - 统一的圆角边框（8px，随 UI_SCALE 缩放）
  - 统一的内边距（20px）和外边距（10px 上下）
- ✅ **滚动优化**：边框固定，内容滚动
  - 网络页面：容器边框固定，WiFi 列表在内部滚动
  - 本地文件列表：支持垂直滚动（max 400px）
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
  - **网速显示**（电池右侧）🆕：
    - 实时显示上传/下载速度（⬆ 上传 ⬇ 下载）
    - 自动单位换算（B/s → KB/s → MB/s → GB/s）
    - 自动检测活动网卡（WiFi/以太网）
    - 无网络连接时显示 `--`
    - 每秒自动更新
    - 读取 `/sys/class/net/*/statistics/` 获取实时流量
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

### 统一日志系统 🆕
- ✅ **结构化日志框架**（`logger.py`）：
  - `InstallerLogger` 类：提供 debug/info/warning/error/exception 方法
  - 时间戳格式：`[2025-01-30 12:34:56] [INFO] [component] message`
  - 组件标识：每个模块可创建独立 logger（如 `logger = get_logger('install')`）
  - 自动异常跟踪：`logger.exception()` 自动包含完整堆栈信息
  - 输出到 stdout：通过 `tee` 重定向到 `/tmp/frzr.log`
  
- ✅ **全局异常处理改进**：
  - 消除所有 bare `except:` 块
  - 所有异常捕获使用 `except Exception as e:` 或更具体的异常类型
  - 异常处理统一使用 `logger.exception()` 记录完整堆栈
  - UI日志同步：`append_log()` 输出到 stdout，自动被 `tee` 捕获
  
- ✅ **单一日志文件**：所有阶段写入 `/tmp/frzr.log`
  - Launcher（installer-modular 环境信息）
  - Bootstrap（frzr-bootstrap 输出 + Steam bootstrap 详细日志）
  - Install（frzr-deploy 输出）
  - Post-install（Steam bootstrap、post_install、验证）
  - Python 日志（所有 logger 输出）
  
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

### 最近完成（2025-10-29 第六次更新）🆕

1. ✅ **版本信息传递修复**
   - 修复 `install.py` 错误读取旧的 `selected_version/selected_desktop/nvidia_driver` 属性
   - 正确从 `version_selections` 字典读取参数：
     - `channel` (stable/testing/unstable) ← 原来错误读 `version`
     - `desktop` (gnome/kde) ← 原来错误读 `selected_desktop`
     - `nvidia` (True/False) ← 原来错误读 `nvidia_driver`
   - 修复命令构建逻辑，匹配 `install.sh` 格式：
     - **正确格式**：`frzr-deploy "3003n/skorionos:channel:desktop[-nv]"`
     - **示例**：`frzr-deploy "3003n/skorionos:stable:gnome-nv"`
     - **原来错误**：`frzr-deploy skorionos/beta --desktop gnome --nvidia`
   - 添加详细文档注释说明格式和示例

2. ✅ **Version 页面 UI 重构**
   - 移除"安装方式"的 info-box 边框（改为扁平样式）
   - 整合顶部元素（安装方式 + 当前配置 + 高级选项）为一个区域
   - 统一字体大小（移除 `size="large"`）
   - 缩小上下边距和元素间距（更紧凑布局）
   - 信息层级更清晰（控制区无边框，选择区有 info-box）

3. ✅ **单选框显示修复**
   - 发现 GTK4 设计逻辑：单个选项显示方形复选框，多个选项才显示圆形单选框
   - 实施方案2：总是显示两个选项保证视觉一致性
     - "安装方式"：在线安装 + 本地安装（无本地文件时禁用并显示提示）
     - "磁盘选择"：单磁盘时自动选中
   - 移除错误的 CSS hack（`border-radius: 50%`），让 GTK 主题自动处理

4. ✅ **XKB/Xwayland 启动失败修复**
   - 在 `installer-modular` 启动前清理 XKB 缓存：`rm -rf /var/lib/xkb/*`
   - 清理 stale sockets：`/tmp/.X11-unix/*`, `${XDG_RUNTIME_DIR}/wayland-*`
   - 确保目录权限：`mkdir -p /var/lib/xkb && chmod 755 /var/lib/xkb`
   - 解决概率性 UI 启动失败问题

5. ✅ **Live ISO 空间配置**
   - 添加 `cow_spacesize=4G` 到 EFI 和 Syslinux 引导选项
   - 明确指定 tmpfs 覆盖层大小，避免空间不足

6. ✅ **Complete 页面图标修复**
   - 修复成功图标加载失败（`emblem-ok-symbolic` 不存在于 Adwaita 主题）
   - 改用 `object-select-symbolic` (勾选图标)
   - 更符合 GTK4/Adwaita 的图标命名规范

7. ✅ **欢迎页 Logo 更新**
   - 使用自定义 Skorion.svg 替代通用的 `computer-symbolic` 图标
   - Logo 路径：`/usr/share/installer/Skorion.svg`
   - 蓝色主题，尺寸 512x512，支持缩放

8. ✅ **欢迎页系统信息展示**
   - 替换静态测试信息为实时系统信息
   - 显示内容：CPU 型号和核心数、内存容量、磁盘数量、引导模式 (UEFI/BIOS)、屏幕分辨率和缩放
   - 缩放计算：`UI_SCALE × GDK_SCALE`（正确显示实际缩放倍数）
   - 使用 GTK Adwaita 图标（全部验证存在）：
     - `applications-system-symbolic` - CPU 信息
     - `drive-multidisk-symbolic` - 内存信息
     - `drive-harddisk-symbolic` - 磁盘信息
     - `preferences-system-symbolic` - 引导模式
     - `video-display-symbolic` - 屏幕信息
   - 图标 + 文本横向布局，信息清晰易读
   - 异常容错：无法获取信息时显示默认 fallback 内容

9. ✅ **文件重命名（清理 POC 命名）**
   - `installer-poc-modular` → `installer`
   - 更新所有引用（`installer-modular`, `profiledef.sh`, 文档）
   - 清理注释，反映当前稳定状态

### 最近完成（2025-10-29 第八次更新）

1. ✅ **网络检测与离线模式**
   - **网络状态检测**：版本选择页面通过 `NetworkManager.is_online()` 检测网络状态
   - **UI 自动适配**：
     - 离线时：禁用"在线安装"选项，显示 tooltip "未检测到网络连接"
     - 离线时：自动选中"本地安装"（如果有本地文件）
     - 在线时：保持默认选择（在线安装）
   - **二次验证**：点击"开始安装"时再次检查网络
     - 离线尝试在线安装 → 显示 AlertDialog 提示："网络连接已断开，请连接网络后重试，或选择本地安装"
     - 阻止无网络环境下的在线安装（防止后续失败）
   - **用户体验优化**：
     - 清晰的视觉反馈（禁用+tooltip）
     - 友好的错误提示（AlertDialog）
     - 自动降级到可用选项（本地安装）

2. ✅ **本地安装列表 UI 改进**
   - **使用统一组件**：
     - 改用 `UIComponents.create_selection_button()` 创建列表项
     - 与磁盘选择页面保持一致的样式和交互
     - 整行可点击（不仅仅是单选框圆圈）
     - 统一的内边距（10px 左右，8px 上下）
     - Hover 时有背景色变化
   - **滚动支持**：
     - 添加 `Gtk.ScrolledWindow` 包裹文件列表
     - 最小高度 200px，最大高度 400px
     - 文件列表过长时自动显示滚动条
     - `set_propagate_natural_height(True)` 确保内容不撑大窗口
   - **更好的文本显示**：
     - 文件名作为标题（粗体显示）
     - 设备和大小信息作为描述（灰色小字）
     - 文本支持自动换行
     - 整体宽度 650px
   - **代码简化**：
     - 从手动构建布局简化为调用统一组件
     - 代码量减少约 50%
     - 更易维护和调试

3. ✅ **本地镜像分区挂载权限修复**（关键！）
   - **问题根源**：`LocalFileManager._get_or_mount()` 使用 `mount -o ro`（只读挂载）
   - **影响**：本地安装时无法在同目录执行文件合并操作（写入失败）
   - **修复**：改为 `mount -o rw`（读写挂载）
   - **对齐文本安装器**：与 `install.sh` 的 `scan_frzr_update_files()` 保持一致
   - **文件位置**：`/usr/local/lib/installer/backend/local_file_manager.py` 第 133 行
   - **日志更新**：`Mounted (rw)` 明确显示挂载模式
   - **注释更新**：`# Mount read-write for file operations (needed for local installation merge)`

### 最近完成（2025-01-30 第四次更新）

1. ✅ **统一日志系统改造**
   - 创建 `logger.py` 模块（`InstallerLogger` 类）
   - 结构化日志格式：`[时间戳] [级别] [组件] 消息`
   - 全局消除 bare `except:` 块（改用 `except Exception as e:`）
   - 所有异常使用 `logger.exception()` 记录完整堆栈
   - UI 日志通过 stdout + `tee` 统一到 `/tmp/frzr.log`
   - 替换所有 `print()` 为 `logger.info/warning/error()`

2. ✅ **Steam Bootstrap 健壮性增强**
   - 自动重试机制（最多3次，间隔2秒）
   - 文件完整性检查（大小 > 250MB）
   - 损坏文件自动删除并重新下载
   - 捕获并记录命令错误输出（tar/xz stderr）
   - 超时保护（tar 命令30秒超时）
   - 详细的错误日志（包括堆栈跟踪）

### 最近完成（2025-01-30 第三次更新）

1. ✅ **完成本地安装功能**
   - 创建 `LocalFileManager` 类（挂载生命周期管理）
   - 完全对齐文本安装器的扫描逻辑（支持 4 种文件格式）
   - Version 页面添加"安装方式"选择（在线/本地）
   - 动态显示本地文件列表（设备名、大小、选择）
   - Install 页面支持本地文件安装
   - 集成自动清理机制（atexit + Complete 页面）

2. ✅ **完成高级选项功能**
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

### 最近完成（2025-10-31 第十次更新）

1. ✅ **状态栏网速显示** 🆕
   - 实时显示上传/下载速度（⬆ 上传 ⬇ 下载）
   - 自动单位换算（B/s → KB/s → MB/s → GB/s）
   - 自动检测活动网卡（WiFi/以太网）
   - 每秒自动更新
   - 使用 `go-down-symbolic` 和 `go-up-symbolic` 图标
2. ✅ **CI/CD 自动下载 UEFI 控制器驱动** 🆕
   - 从 honjow/UsbXbox360Dxe 获取最新 release
   - 自动下载所有 `.efi` 文件到 `skorionos/efiboot/EFI/systemd/drivers/`
   - 支持动态文件名和多驱动（无硬编码）
   - UEFI 引导菜单支持 Xbox 360 手柄操作
3. ✅ **文本安装器启动入口** 🆕
   - Syslinux 添加 "Install SkorionOS (Text Mode)" 启动项
   - systemd-boot 添加 `archiso-x86_64-linux-text.conf` 配置
   - 支持 `installer=text` 内核参数强制文本模式

### 之前完成（2025-01-29 第一次更新）

1. ✅ Complete 页面重写（按钮问题修复）
2. ✅ 日志统一到 /tmp/frzr.log
3. ✅ 日志上传到 fpaste（异步）
4. ✅ 状态栏实现（电池、时间、主题切换）
5. ✅ libadwaita 集成（主题切换）
6. ✅ 磁盘描述显示（[内置]/[USB]/[SD卡]）
7. ✅ overrides 文件支持

---

## 🐛 已修复问题

### 2025-10-29 (第九次更新)
- ✅ **多系统安装导入错误** → 修复 `mode.py` 中的 `from .disk_new` 错误导入（改为 `from .disk`）
- ✅ **磁盘空间不足使用 Dialog 弹窗** → 创建 `PartitionAdjustPage` 统一页面风格
- ✅ **分区调整页面垂直排列空间利用率低** → 重构为三列水平布局（分区列表/操作选择/空间大小）
- ✅ **分区操作列表不可点击** → 使用 `UIComponents.create_selection_button()` 实现全行可选
- ✅ **分区大小使用 ComboBox 选择不直观** → 改为单选按钮组（60GB/100GB/200GB）
- ✅ **多系统安装流程卡在确认对话框** → `frzr-bootstrap` 非交互模式跳过所有 `whiptail` 对话框
- ✅ **分区缩小和删除需要手动确认** → 非交互模式自动执行，基于图形界面传递的参数
- ✅ **多个空闲空间需要手动选择** → 非交互模式自动选择第一个（最大的）空闲空间

### 2025-10-29 (第八次更新)
- ✅ **离线环境仍可选择在线安装** → 版本页面检测网络状态，离线时禁用"在线安装"选项
- ✅ **网络断开后点击开始安装无提示** → 添加二次验证，网络断开时显示友好错误提示
- ✅ **本地安装列表样式不统一** → 使用 `UIComponents.create_selection_button()` 统一组件
- ✅ **本地安装列表只有圆圈可点击** → 整行可点击，与磁盘选择保持一致
- ✅ **本地安装列表过长无法滚动** → 添加 ScrolledWindow，支持滚动显示
- ✅ **本地镜像所在分区只读挂载** → 修改为读写挂载（`-o rw`），支持本地安装合并操作

### 2025-10-29 (第七次更新)
- ✅ **图形安装器启动失败无兜底方案** → 实现智能回退机制（Socket 检查 + 运行时长判断）
- ✅ **Gamescope 崩溃无法提前检测** → installer-modular 添加 socket 检查（15秒超时）
- ✅ **启动失败和用户主动退出无法区分** → 基于运行时长判断（< 15秒 = 失败）
- ✅ **失败后需要手动切换安装器** → 自动重试 + 2次失败后自动降级到文本安装器
- ✅ **无法强制使用文本安装器** → 支持 `installer=text` 启动参数

### 2025-10-29 (第六次更新)
- ✅ 版本信息未正确传递给 frzr-deploy → 修复参数读取逻辑，构建正确的 TARGET 字符串
- ✅ 命令格式不匹配 install.sh → 改为 `frzr-deploy "3003n/skorionos:channel:desktop[-nv]"` 格式
- ✅ Version 页面布局混乱 → 重构为顶部控制区 + 底部选择区，层次清晰
- ✅ 单选框显示为方形 → 总是显示多个选项，让 GTK 自动渲染圆形单选框
- ✅ UI 启动概率性失败 → 清理 XKB 缓存和 stale sockets
- ✅ Live ISO 空间不足 → 配置 `cow_spacesize=4G`
- ✅ 成功页面图标加载失败 → 使用 `object-select-symbolic` 替代不存在的 `emblem-ok-symbolic`

### 2025-01-30 (第四次更新)
- ✅ 日志系统不统一 → 创建 logger.py（结构化日志、异常跟踪）
- ✅ 使用 print() 而非日志工具 → 全局替换为 logger
- ✅ 存在 bare except 块 → 全部改为具体异常类型
- ✅ 缺少异常堆栈信息 → 使用 logger.exception() 自动记录
- ✅ Steam 包损坏无法重试 → 自动重试3次 + 损坏文件删除
- ✅ 命令错误信息丢失 → 捕获并记录 stderr 输出
- ✅ 状态栏电池图标错误 → 修复充电图标选择逻辑
- ✅ Adwaita 警告 → 移除废弃的 gtk-application-prefer-dark-theme 设置

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
