# SkorionOS 图形化安装器 - 当前状态

> 最后更新: 2025-01-28

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
│   └── install_utils.py       # 安装后处理（Steam、post_install）
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
        └── install.py         # 7. 系统安装（ExecutionPage）
```

---

## 🔄 页面流程

```
0. 欢迎页 (Welcome) - 内置在 main.py
   └─→ 1. 网络页 (Network)
       └─→ 2. 磁盘选择页 (Disk)
           └─→ 3. 安装模式页 (Mode) - 检测现有安装，选择 repair/fresh/dual
               └─→ 4. 确认页 (Confirm) - 显示操作摘要
                   └─→ 5. Bootstrap 页 (Bootstrap) - 执行 frzr-bootstrap
                       └─→ 6. 版本选择页 (Version) - 选择通道/桌面/NVIDIA
                           └─→ 7. 安装页 (Install) - 执行 frzr-deploy
                               └─→ ❌ Complete 页 (缺失！)
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
- ✅ **Bootstrap 页面**: frzr-bootstrap 执行、实时日志、错误处理
- ✅ **Version 页面**: 通道/桌面/NVIDIA 选择
- ✅ **Install 页面**: frzr-deploy 执行、进度显示、日志输出

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
  - `grab_steam_bootstrap()` - 获取 Steam 引导文件
  - `post_install()` - 后安装优化（Steam 配置）

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

### 状态栏
- ✅ **顶部状态栏**：显示系统状态信息，固定在所有页面顶部
  - **电池信息**（左侧）：
    - 电量百分比和状态（充电中/已充满）
    - GTK 图标根据电量和状态自动变化
    - 台式机/虚拟机显示"AC 电源"
    - 每分钟自动更新
  - **日期时间**（右侧）：
    - 格式：`YYYY-MM-DD HH:MM`
    - 每秒自动更新
  - **样式**：淡色半透明背景，底部分隔线

---

## ❌ 缺失功能（阻塞性）

### 🔴 严重问题
1. **Complete 页面不存在**
   - `install.py` 第213行调用 `show_page('complete')`
   - 但 `main.py` 没有注册此页面
   - **后果**: 安装成功后报错，用户无法重启

2. **install.py 缺少后安装步骤**
   - ❌ 未调用 `grab_steam_bootstrap()`（代码已在 install_utils.py）
   - ❌ 未调用 `post_install()`（代码已在 install_utils.py）
   - ❌ 未复制网络配置到安装系统
   - ❌ 未验证启动配置
   - **后果**: Steam 启动需要额外配置，网络配置丢失

3. **disk.py 未使用安全检查函数**
   - ✅ 函数已实现（`is_disk_external`, `is_disk_smaller_than`）
   - ❌ 但 UI 未调用，不会警告用户
   - **后果**: 可能安装到外部磁盘或太小的磁盘

---

## ⚠️ 需要修复

### 必须立即修复（第一优先级）

#### 1. 创建 Complete 页面
```python
# 文件: ui/pages/complete.py
class CompletePage(BasePage):
    """Installation complete page with reboot options."""
    
    def populate_content(self, content_box):
        # 显示成功信息
        # 显示安装日志路径
    
    def populate_buttons(self, button_box):
        # 重启按钮 -> subprocess.run(['reboot'])
        # 关机按钮 -> subprocess.run(['poweroff'])
        # 退出按钮 -> sys.exit(0)
```

#### 2. 修复 install.py 的 execute() 函数
```python
def execute(self):
    # ... 现有的 frzr-deploy 代码 ...
    
    # 在 frzr-deploy 成功后，添加：
    
    # 1. 复制网络配置
    self._copy_network_config()
    
    # 2. 获取 Steam bootstrap
    from ...backend.install_utils import grab_steam_bootstrap
    grab_steam_bootstrap(mount_path)
    
    # 3. 后安装优化
    from ...backend.install_utils import post_install
    post_install(mount_path)
    
    # 4. 验证启动配置
    self._verify_boot_config()

def _copy_network_config(self):
    """Copy NetworkManager configs to installed system."""
    import shutil
    SYS_CONN_DIR = "/etc/NetworkManager/system-connections"
    TARGET_DIR = f"/tmp/frzr_root{SYS_CONN_DIR}"
    
    if os.path.isdir(SYS_CONN_DIR) and os.listdir(SYS_CONN_DIR):
        os.makedirs(TARGET_DIR, exist_ok=True)
        os.chmod(TARGET_DIR, 0o700)
        for file in os.listdir(SYS_CONN_DIR):
            shutil.copy2(
                os.path.join(SYS_CONN_DIR, file),
                os.path.join(TARGET_DIR, file)
            )

def _verify_boot_config(self):
    """Verify boot configuration exists."""
    boot_cfg = "/tmp/frzr_root/boot/loader/entries/frzr.conf"
    if not os.path.exists(boot_cfg):
        self.append_log("⚠️  警告: 启动配置文件缺失\n")
```

#### 3. 在 disk.py 添加安全检查
```python
def _on_disk_selected(app, disk_name):
    """Handle disk selection with safety checks."""
    from ...backend.disk_utils import is_disk_external, is_disk_smaller_than
    from ...config import config
    
    # 检查磁盘大小
    if is_disk_smaller_than(disk_name, 55):
        dialog = Gtk.AlertDialog()
        dialog.set_message("磁盘太小")
        dialog.set_detail(f"磁盘 {disk_name} 小于 55GB，无法安装 SkorionOS")
        dialog.set_buttons(["返回"])
        dialog.choose(app, None, None, None)
        return
    
    # 检查是否外部磁盘
    if is_disk_external(disk_name):
        dialog = Gtk.AlertDialog()
        dialog.set_message("外部磁盘警告")
        dialog.set_detail(
            f"磁盘 {disk_name} 似乎是外部设备（USB等）\n\n"
            "在外部磁盘上安装可能导致:\n"
            "• 性能不佳\n"
            "• 磁盘损坏\n\n"
            "是否继续？"
        )
        dialog.set_buttons(["取消", "继续安装"])
        # ... 处理用户选择
```

#### 4. 在 main.py 注册 complete 页面
```python
from .ui.pages.complete import create_complete_page

# 在 show_page() 的 page_map 中添加:
page_map = {
    # ...
    'complete': 8,
}

# 在 pages 列表中添加:
pages = [
    # ... 现有页面 ...
    lambda: create_complete_page(self),  # 8: Complete
]
```

---

## 🟡 可选改进（第二优先级）

### 功能增强
- [ ] 本地安装文件扫描（scan_frzr_update_files）
- [ ] 高级选项 UI（固件覆盖、CDN、Debug）
- [ ] 日志上传到 fpaste
- [ ] 帮助页面/对话框

### 体验优化
- [ ] 更精确的 frzr-deploy 进度解析
- [ ] 磁盘描述显示 transport 类型（内置/USB/SD卡）
- [ ] overrides 文件支持（设备特定型号名称）
- [ ] 安装时间估算

---

## 🎯 下一步 TODO

### 立即执行（今天）
1. ✅ 清理过时文档
2. [ ] 创建 `ui/pages/complete.py`
3. [ ] 在 `main.py` 注册 complete 页面
4. [ ] 修复 `install.py` 添加后安装步骤
5. [ ] 在 `disk.py` 添加安全检查
6. [ ] 测试完整安装流程

### 近期执行（本周）
7. [ ] 实现本地安装文件扫描
8. [ ] 添加高级选项 UI
9. [ ] 改进进度显示精确度
10. [ ] 添加帮助系统

---

## 📝 已知问题

1. **安装成功后无法重启** - 缺少 complete 页面
2. **Steam 首次启动慢** - 未调用 grab_steam_bootstrap
3. **安装后需重新配置 WiFi** - 未复制网络配置
4. **可能安装到不安全的磁盘** - 未使用安全检查

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

## 🚀 运行方式

```bash
# 启动图形化安装器
/usr/local/bin/installer-modular

# 查看日志
tail -f /tmp/installer-modular.log

# 自定义缩放
UI_SCALE=2.0 /usr/local/bin/installer-modular
```

---

*基于实际代码生成 - 2025-01-28*

