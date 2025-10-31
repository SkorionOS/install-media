"""
Installation confirmation page.
Displays operation summary based on selected mode (repair/fresh/dual).
Now uses MessagePage for unified UI.
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from ...config import config
from ..components.base import BasePage
from .message import MessagePage


class ConfirmPage(BasePage):
    """Confirmation page - wraps MessagePage with installation-specific logic."""
    
    def __init__(self, app):
        super().__init__(app)
        self.message_page = None
    
    def create(self) -> Gtk.Box:
        """Create page by configuring MessagePage based on installation mode."""
        # Create MessagePage if not exists
        if not self.message_page:
            self.message_page = MessagePage(self.app)
        
        # Get installation parameters from app
        disk = getattr(self.app, 'selected_disk', '未知')
        disk_desc = getattr(self.app, 'selected_disk_desc', '')
        mode = getattr(self.app, 'install_mode', 'unknown')
        
        # Configure based on mode
        if mode == 'repair':
            self._configure_repair(disk, disk_desc)
        elif mode == 'fresh':
            self._configure_fresh(disk, disk_desc)
        elif mode == 'dual':
            self._configure_dual(disk, disk_desc)
        else:
            self._configure_unknown(disk, disk_desc, mode)
        
        return self.message_page.create()
    
    def _configure_repair(self, disk, disk_desc):
        """Configure page for repair mode."""
        self.message_page.configure(
            message_type=MessagePage.TYPE_CONFIRM,
            icon="dialog-warning-symbolic",
            title="确认安装",
            color="orange",
            main_msg=f'<span size="large" weight="bold">修复安装</span>\n<span size="large">磁盘: /dev/{disk}</span>\n<span>{disk_desc}</span>',
            details=[
                '<span>此操作将：</span>',
                '<span>• 保留用户数据（/home、/var）</span>',
                '<span>• 重装引导加载器</span>',
                '<span>• 清理系统部署</span>'
            ],
            question="您是否要继续？",
            buttons=[
                ("返回", "go-previous-symbolic", lambda b: self.app.go_back(), None),
                ("退出", "application-exit-symbolic", lambda b: self._on_exit(), None),
                ("继续", "go-next-symbolic", lambda b: self.app.show_page('bootstrap'), "suggested-action")
            ]
        )
    
    def _configure_fresh(self, disk, disk_desc):
        """Configure page for fresh install mode."""
        self.message_page.configure(
            message_type=MessagePage.TYPE_CONFIRM,
            icon="dialog-warning-symbolic",
            title="确认安装",
            color="orange",
            main_msg=f'<span size="large" weight="bold">全新安装</span>\n<span size="large">磁盘: /dev/{disk}</span>\n<span>{disk_desc}</span>',
            details=[
                '<span>此操作将：</span>',
                '<span>• 格式化整个磁盘</span>',
                '<span>• 删除所有现有分区和数据</span>',
                '<span>• 创建新的系统分区</span>'
            ],
            additional='<span foreground="red" weight="bold">警告: 磁盘上的所有数据将被永久删除！</span>',
            question="您是否要继续？",
            buttons=[
                ("返回", "go-previous-symbolic", lambda b: self.app.go_back(), None),
                ("退出", "application-exit-symbolic", lambda b: self._on_exit(), None),
                ("继续", "go-next-symbolic", lambda b: self.app.show_page('bootstrap'), "suggested-action")
            ]
        )
    
    def _configure_dual(self, disk, disk_desc):
        """Configure page for dual boot mode."""
        dual_mode = getattr(self.app, 'dual_mode', 'auto')
        
        if dual_mode == 'auto':
            main_msg = f'<span size="large" weight="bold">双系统安装</span>\n<span size="large">磁盘: /dev/{disk}</span>\n<span>{disk_desc}</span>'
            details = [
                '<span>将使用磁盘上的未分配空间创建分区</span>',
                '<span>现有系统将被保留</span>'
            ]
            additional = None
        
        elif dual_mode == 'shrink':
            shrink_part = getattr(self.app, 'shrink_partition', '未知')
            shrink_size = getattr(self.app, 'shrink_size', 0)
            main_msg = f'<span size="large" weight="bold">双系统安装 - 缩小分区</span>\n<span size="large">磁盘: /dev/{disk}</span>\n<span>{disk_desc}</span>'
            details = [
                f'<span foreground="orange" weight="bold">将缩小分区: {shrink_part}</span>',
                f'<span>释放空间: {shrink_size} GB</span>'
            ]
            additional = '<span size="small" foreground="red">警告: 此操作有风险，请确保已备份重要数据！</span>'
        
        elif dual_mode == 'delete':
            delete_part = getattr(self.app, 'delete_partition', '未知')
            main_msg = f'<span size="large" weight="bold">双系统安装 - 删除分区</span>\n<span size="large">磁盘: /dev/{disk}</span>\n<span>{disk_desc}</span>'
            details = []
            additional = f'<span foreground="red" weight="bold" size="large">警告: 将删除分区 {delete_part}！</span>\n<span foreground="red" weight="bold">该分区上的所有数据将永久丢失！</span>'
        
        else:
            main_msg = f'<span size="large" weight="bold">双系统安装</span>\n<span size="large">磁盘: /dev/{disk}</span>\n<span>{disk_desc}</span>'
            details = []
            additional = None
        
        self.message_page.configure(
            message_type=MessagePage.TYPE_CONFIRM,
            icon="dialog-warning-symbolic",
            title="确认安装",
            color="orange",
            main_msg=main_msg,
            details=details,
            additional=additional,
            question="您是否要继续？",
            buttons=[
                ("返回", "go-previous-symbolic", lambda b: self.app.go_back(), None),
                ("退出", "application-exit-symbolic", lambda b: self._on_exit(), None),
                ("继续", "go-next-symbolic", lambda b: self.app.show_page('bootstrap'), "suggested-action")
            ]
        )
    
    def _configure_unknown(self, disk, disk_desc, mode):
        """Configure page for unknown mode."""
        self.message_page.configure(
            message_type=MessagePage.TYPE_WARNING,
            icon="dialog-warning-symbolic",
            title="确认安装",
            color="orange",
            main_msg=f'<span size="large" weight="bold">未知模式: {mode}</span>\n<span size="large">磁盘: /dev/{disk}</span>\n<span>{disk_desc}</span>',
            question="您是否要继续？",
            buttons=[
                ("返回", "go-previous-symbolic", lambda b: self.app.go_back(), None),
                ("退出", "application-exit-symbolic", lambda b: self._on_exit(), None),
                ("继续", "go-next-symbolic", lambda b: self.app.show_page('bootstrap'), "suggested-action")
            ]
        )
    
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
