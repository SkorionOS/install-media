# SkorionOS 图形化安装器

> 最后更新: 2025-01-30
> 
> 基于 GTK4 + Python 的现代化安装器，支持手柄操作、多设备适配、进度显示

---

## 📦 项目概览

### 项目结构

```
/usr/local/bin/
├── installer-modular          # 启动脚本（gamescope + 设备适配）
└── installer-poc-modular      # Python 入口

/usr/share/installer/
└── device-quirks              # 设备适配脚本（屏幕方向、输出优先级）

/usr/local/lib/installer/
├── config.py                  # 全局配置（缩放、路径、Steam URL）
├── main.py                    # 主窗口和页面导航
├── backend/                   # 后端工具（disk_utils, install_utils, log_utils）
├── network/                   # 网络管理（NetworkManager 封装）
└── ui/                        # UI 组件（pages/, components/, styling.py）
```

### 安装流程

```
欢迎页 → 网络配置 → 磁盘选择 → 模式选择 → 确认操作 
      → 磁盘初始化 → 版本选择 → 系统安装 → 完成页面
```

---

## 🎯 功能状态

### ✅ 已完成功能

#### 核心安装流程
- [x] 网络连接（WiFi 扫描、密码输入、虚拟键盘）
- [x] 磁盘选择（自动扫描、磁盘类型显示 `[内置]/[USB]/[SD卡]`）
- [x] 安装模式（Repair/Fresh/Dual 三种模式）
- [x] 磁盘初始化（frzr-bootstrap + 实时日志）
- [x] 版本选择（通道/桌面/NVIDIA）
- [x] **在线安装**（frzr-deploy + 进度显示 + 后安装配置）
- [x] 完成页面（SUCCESS/CANCELLED/FAILED 三种状态）

#### 后端功能
- [x] 磁盘工具（检测、分区、安全检查）
- [x] Steam bootstrap 下载（**urllib + 进度 + 断点续传**）
- [x] 网络配置复制（WiFi 自动保留）
- [x] post_install 优化（Steam 自动配置）
- [x] 日志上传（fpaste + 异步）

#### UI/UX
- [x] 响应式缩放（UI_SCALE 支持小数、自动 DPI）
- [x] 设备适配（20+ 设备屏幕方向、输出优先级）
- [x] 手柄支持（ESC 返回）
- [x] 状态栏（电池、时间、主题切换）
- [x] 统一组件（BasePage、ExecutionPage、UIComponents）
- [x] overrides 文件支持（自定义磁盘名称）

### 🔄 部分完成功能

#### 本地安装（离线安装）
- [x] 扫描本地文件（`bootstrap.py: _scan_frzr_update_files()`）
- [ ] **Version 页面未显示本地安装选项**
- [ ] **未让用户选择"本地/在线"安装**
- [ ] **Install 页面未使用本地文件**

**需要实现**：
1. Version 页面添加安装方式选择（在线/本地）
2. 显示本地文件列表（如果可用）
3. Install 页面支持 `frzr-deploy /path/to/file.img.tar.zst`

### ⏳ 待实现功能

#### 高级选项 UI
- [ ] 固件覆盖选项（`--disable-kernel-upgrade`）
- [ ] CDN 选择
- [ ] Debug 模式
- [ ] 自定义安装路径

#### 用户体验
- [ ] 帮助系统/FAQ
- [ ] 更精确的 frzr-deploy 进度解析
- [ ] 安装时间估算

### 🧪 待测试功能

1. [ ] 完整安装流程（repair/fresh/dual 三种模式）
2. [ ] Steam bootstrap 下载（删除本地文件测试）
3. [ ] 断点续传（中断后继续下载）
4. [ ] 安全检查对话框（小磁盘、外部磁盘）
5. [ ] 网络配置复制（安装后 WiFi 保留）
6. [ ] Steam 首次启动（无需额外配置）

---

## 🔧 技术细节

### 架构设计

#### 模块化
- 14 个文件，每个 < 600 行
- 清晰的职责分离（backend/network/ui）
- 独立的配置文件（config.py）

#### 组件复用
- **BasePage**: 所有页面的基类（标题、内容、按钮）
- **ExecutionPage**: 执行类页面的基类（状态、进度条、日志）
- **UIComponents**: 统一 UI 元素工厂

#### 配置集中管理
```python
# config.py
self.mount_path = "/tmp/frzr_root"
self.log_file = "/tmp/frzr.log"
self.min_disk_size = 55  # GB
self.steam_package_url = "https://..."
self.steam_packages_dir = "/root/packages"
```

### 下载系统（urllib）

**使用 Python urllib 替代 curl**：
- 原生 Python，无需外部命令
- 精确的字节级进度计算
- 显示精确文件大小和百分比
- **支持断点续传**（HTTP Range 头）
- 更好的错误处理（HTTPError、URLError、TimeoutError）
- 文件大小验证（Content-Length）

### 设备适配

**自动检测 20+ 设备型号**：
- 屏幕方向（left/right/normal）
- 自动宽高交换（90/270 度旋转）
- 输出优先级（eDP-1/DSI-1）
- Shader 旋转（不支持硬件旋转的设备）

支持品牌：OXP、AOKZOE、AYANEO、AYN、GPD、Steam Deck、ROG Ally、Legion Go、Minisforum、ZOTAC、MSI

### UI 缩放系统

**三位一体缩放**：
1. `gtk-xft-dpi` - 控制所有文字渲染大小
2. `config.scaled()` - 控制 widget 尺寸、padding、margins
3. CSS 规则 - 控制单选框圆点、滚动条等内置元素

**自动适配**：
- ≥1440p: UI_SCALE=2.0
- ≥1080p: UI_SCALE=1.0
- 支持小数缩放（1.5, 2.5 等）

### 日志系统

#### 统一日志路径
所有阶段日志写入 `/tmp/frzr.log`：
- Launcher（installer-modular 环境信息）
- Bootstrap（frzr-bootstrap 输出）
- Install（frzr-deploy 输出）
- Post-install（Steam bootstrap、post_install）

#### 自动上传（fpaste）
- 检查日志存在性
- 清理 ANSI 转义码
- 异步上传（后台线程 + 回调）
- 实时显示 URL（可复制）
- 超时 10 秒

### 系统依赖

**核心**：gamescope、gtk4、libadwaita、python-gobject

**图形**：mesa、vulkan-icd-loader、wayland、adwaita-icon-theme

**网络**：libnm

**字体**：wqy-microhei

---

## 📝 更新历史

### 最近完成（2025-01-30）

1. ✅ 使用 urllib 替代 curl（精确进度、断点续传）
2. ✅ 配置集中管理（Steam URL 移到 config.py）
3. ✅ 修复所有硬编码（55GB、/tmp/frzr_root 等）
4. ✅ 去除所有 emoji（改用 `[成功]`/`[警告]`/`[失败]`）
5. ✅ Complete 页面（统一退出流程）
6. ✅ 后安装步骤（网络配置、Steam、验证）
7. ✅ 安全检查（磁盘大小、外部磁盘警告）

### 下一步 TODO

#### 优先级：高
- [ ] **完成本地安装功能**
  - Version 页面添加"本地/在线"选择
  - 显示本地文件列表
  - Install 页面支持本地文件

#### 优先级：中
- [ ] 全面测试（repair/fresh/dual 模式）
- [ ] 添加高级选项 UI
- [ ] 改进进度解析精确度

#### 优先级：低
- [ ] 帮助系统/FAQ
- [ ] 安装时间估算

### 已修复问题

#### 2025-01-30
- ✅ Steam bootstrap 下载无进度 → urllib + 实时进度
- ✅ 日志使用 emoji → 纯文本标记
- ✅ 配置硬编码 → config.py 集中管理

#### 2025-01-29
- ✅ 日志未统一 → 统一写入 /tmp/frzr.log
- ✅ Complete 页面按钮不显示 → 重写 populate_buttons()
- ✅ 日志不存在提示不友好 → 添加文件检查

---

*文档生成于 2025-01-30*
