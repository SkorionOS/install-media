"""
Installation confirmation page.
Displays operation summary based on selected mode (repair/fresh/dual).
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from ...config import config
from ..components.base import BasePage, UIComponents


class ConfirmPage(BasePage):
    """Confirmation page that displays operation summary before installation."""
    
    def __init__(self, app):
        super().__init__(app)
    
    def create_title(self) -> Gtk.Widget:
        """Create warning icon with title."""
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
        title_box.set_halign(Gtk.Align.CENTER)
        
        warning_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        warning_icon.set_pixel_size(config.scaled(64))
        title_box.append(warning_icon)
        
        title = Gtk.Label()
        title.set_markup('<span size="xx-large" weight="bold" foreground="orange">确认安装</span>')
        title_box.append(title)
        
        return title_box
    
    def populate_content(self, content_box: Gtk.Box):
        """Populate content with operation summary."""
        # Set content area to center align
        content_box.set_halign(Gtk.Align.CENTER)
        
        # Get installation parameters
        disk_name = getattr(self.app, 'selected_disk', '未知')
        disk_desc = getattr(self.app, 'selected_disk_desc', '')
        mode = getattr(self.app, 'install_mode', 'unknown')
        
        # Mode title (centered)
        mode_title = Gtk.Label()
        if mode == 'repair':
            mode_title.set_markup('<span size="large" weight="bold">修复安装</span>')
        elif mode == 'fresh':
            mode_title.set_markup('<span size="large" weight="bold">全新安装</span>')
        elif mode == 'dual':
            dual_mode = getattr(self.app, 'dual_mode', 'auto')
            if dual_mode == 'shrink':
                mode_title.set_markup('<span size="large" weight="bold">双系统安装 - 缩小分区</span>')
            elif dual_mode == 'delete':
                mode_title.set_markup('<span size="large" weight="bold">双系统安装 - 删除分区</span>')
            else:
                mode_title.set_markup('<span size="large" weight="bold">双系统安装</span>')
        else:
            mode_title.set_markup(f'<span size="large" weight="bold">未知模式: {mode}</span>')
        mode_title.set_justify(Gtk.Justification.CENTER)
        content_box.append(mode_title)
        
        # Disk info (centered)
        disk_label = Gtk.Label()
        disk_label.set_markup(f'<span size="large">磁盘: /dev/{disk_name}</span>\n<span>{disk_desc}</span>')
        disk_label.set_justify(Gtk.Justification.CENTER)
        content_box.append(disk_label)
        
        # Operation details (left-aligned list items)
        if mode == 'repair':
            ops_label = Gtk.Label()
            ops_label.set_markup(
                '<span>此操作将：</span>\n'
                '<span>• 保留用户数据（/home、/var）</span>\n'
                '<span>• 重装引导加载器</span>\n'
                '<span>• 清理系统部署</span>'
            )
            ops_label.set_justify(Gtk.Justification.LEFT)
            ops_label.set_halign(Gtk.Align.START)
            content_box.append(ops_label)
        
        elif mode == 'fresh':
            ops_label = Gtk.Label()
            ops_label.set_markup(
                '<span>此操作将：</span>\n'
                '<span>• 格式化整个磁盘</span>\n'
                '<span>• 删除所有现有分区和数据</span>\n'
                '<span>• 创建新的系统分区</span>'
            )
            ops_label.set_justify(Gtk.Justification.LEFT)
            ops_label.set_halign(Gtk.Align.START)
            content_box.append(ops_label)
            
            # Warning (centered)
            warning_label = Gtk.Label()
            warning_label.set_markup('<span foreground="red" weight="bold">警告: 磁盘上的所有数据将被永久删除！</span>')
            warning_label.set_justify(Gtk.Justification.CENTER)
            content_box.append(warning_label)
        
        elif mode == 'dual':
            dual_mode = getattr(self.app, 'dual_mode', 'auto')
            
            if dual_mode == 'auto':
                ops_label = Gtk.Label()
                ops_label.set_markup(
                    '<span>将使用磁盘上的未分配空间创建分区</span>\n'
                    '<span>现有系统将被保留</span>'
                )
                ops_label.set_justify(Gtk.Justification.LEFT)
                ops_label.set_halign(Gtk.Align.START)
                content_box.append(ops_label)
            
            elif dual_mode == 'shrink':
                shrink_part = getattr(self.app, 'shrink_partition', '未知')
                shrink_size = getattr(self.app, 'shrink_size', 0)
                ops_label = Gtk.Label()
                ops_label.set_markup(
                    f'<span foreground="orange" weight="bold">将缩小分区: {shrink_part}</span>\n'
                    f'<span>释放空间: {shrink_size} GB</span>'
                )
                ops_label.set_justify(Gtk.Justification.LEFT)
                ops_label.set_halign(Gtk.Align.START)
                content_box.append(ops_label)
                
                warning_label = Gtk.Label()
                warning_label.set_markup('<span size="small" foreground="red">警告: 此操作有风险，请确保已备份重要数据！</span>')
                warning_label.set_justify(Gtk.Justification.CENTER)
                content_box.append(warning_label)
            
            elif dual_mode == 'delete':
                delete_part = getattr(self.app, 'delete_partition', '未知')
                warning_label = Gtk.Label()
                warning_label.set_markup(
                    f'<span foreground="red" weight="bold" size="large">警告: 将删除分区 {delete_part}！</span>\n'
                    '<span foreground="red" weight="bold">该分区上的所有数据将永久丢失！</span>'
                )
                warning_label.set_justify(Gtk.Justification.CENTER)
                content_box.append(warning_label)
        
        # Confirmation question (centered)
        confirm_label = Gtk.Label()
        confirm_label.set_markup('<span size="small">您是否要继续？</span>')
        confirm_label.set_justify(Gtk.Justification.CENTER)
        confirm_label.set_margin_top(config.scaled(10))
        content_box.append(confirm_label)
    
    def populate_buttons(self, button_box: Gtk.Box):
        """Populate button area with navigation buttons."""
        # Back button
        back_btn = UIComponents.create_button("返回", "go-previous-symbolic")
        back_btn.connect("clicked", lambda b: self.app.go_back())
        button_box.append(back_btn)
        
        # Exit button (go to complete page - cancelled)
        exit_btn = UIComponents.create_button("退出", "application-exit-symbolic")
        exit_btn.connect("clicked", lambda b: self._on_exit())
        button_box.append(exit_btn)
        
        # Continue button
        continue_btn = UIComponents.create_button("继续", "go-next-symbolic")
        continue_btn.add_css_class("suggested-action")
        continue_btn.connect("clicked", lambda b: self.app.show_page('bootstrap'))
        button_box.append(continue_btn)
    
    def _on_exit(self):
        """Handle exit button - go to complete page with CANCELLED status."""
        from .complete import CompletePage
        print("[CONFIRM] User requested exit")
        self.app.show_complete_page(
            CompletePage.STATUS_CANCELLED,
            "安装已取消",
            "您在确认页面选择了退出安装"
        )


def create_confirm_page(app):
    """Create the confirmation page using the new page architecture."""
    page = ConfirmPage(app)
    return page.create()
