"""
Complete page - unified end-of-installation page.

Handles three states:
- SUCCESS: Installation successful
- CANCELLED: User cancelled installation
- FAILED: Installation failed with error

Features:
- Asynchronous log upload to fpaste
- Different buttons based on status
- Detailed summary display
"""
import os
import sys
from gi.repository import Gtk, GLib
from ..components.base import BasePage, UIComponents
from ...config import config


class CompletePage(BasePage):
    """Generic completion page with log upload."""
    
    # Status constants
    STATUS_SUCCESS = "success"
    STATUS_CANCELLED = "cancelled"
    STATUS_FAILED = "failed"
    
    def __init__(self, app):
        super().__init__(app)
        self.status = None
        self.summary = None
        self.details = None
        self.uploader = None
        self.upload_status_label = None
        self.upload_result_label = None
    
    def get_title_text(self) -> str:
        """Return title based on status."""
        if self.status == self.STATUS_SUCCESS:
            return "安装完成"
        elif self.status == self.STATUS_CANCELLED:
            return "安装已取消"
        elif self.status == self.STATUS_FAILED:
            return "安装失败"
        else:
            return "安装结束"
    
    def set_status(self, status: str, summary: str = "", details: str = ""):
        """
        Set page status and content.
        
        Args:
            status: STATUS_SUCCESS, STATUS_CANCELLED, or STATUS_FAILED
            summary: Brief summary message
            details: Detailed information (optional)
        """
        self.status = status
        self.summary = summary or self._get_default_summary(status)
        self.details = details
        
        # Reload page to update content
        if hasattr(self, '_content_box') and self._content_box:
            # Clear and repopulate
            child = self._content_box.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self._content_box.remove(child)
                child = next_child
            
            self.populate_content(self._content_box)
            self.populate_buttons(self._button_box)
    
    def _get_default_summary(self, status: str) -> str:
        """Get default summary message for status."""
        if status == self.STATUS_SUCCESS:
            return "SkorionOS 已成功安装到您的设备"
        elif status == self.STATUS_CANCELLED:
            return "安装已被取消"
        elif status == self.STATUS_FAILED:
            return "安装过程中遇到错误"
        return ""
    
    def populate_content(self, content_box: Gtk.Box):
        """Populate page content based on status."""
        # Status icon
        icon_name = self._get_status_icon()
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_icon_size(Gtk.IconSize.LARGE)
        icon.set_pixel_size(config.scaled(64))
        icon.set_margin_bottom(config.scaled(20))
        content_box.append(icon)
        
        # Summary message
        summary_label = Gtk.Label()
        summary_label.set_markup(f'<span size="large" weight="bold">{self.summary}</span>')
        summary_label.set_wrap(True)
        summary_label.set_justify(Gtk.Justification.CENTER)
        summary_label.set_margin_bottom(config.scaled(10))
        content_box.append(summary_label)
        
        # Details (if provided)
        if self.details:
            details_label = Gtk.Label(label=self.details)
            details_label.set_wrap(True)
            details_label.set_justify(Gtk.Justification.CENTER)
            details_label.set_margin_bottom(config.scaled(20))
            content_box.append(details_label)
        
        # Log file info
        log_label = Gtk.Label()
        log_label.set_markup(f'<span size="small">日志文件: {config.log_file}</span>')
        log_label.add_css_class("dim-label")
        log_label.set_margin_top(config.scaled(20))
        log_label.set_margin_bottom(config.scaled(10))
        content_box.append(log_label)
        
        # Upload status area
        upload_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(8))
        
        # Check if log file exists
        if not os.path.exists(config.log_file):
            # No log file yet (early exit)
            self.upload_status_label = Gtk.Label()
            self.upload_status_label.set_markup('<span size="small" foreground="gray">暂无日志文件（未执行安装操作）</span>')
            self.upload_status_label.set_xalign(0.5)
            upload_box.append(self.upload_status_label)
            content_box.append(upload_box)
            return  # Don't start upload
        
        # Upload status label
        self.upload_status_label = Gtk.Label()
        self.upload_status_label.set_markup('<span size="small">正在上传日志...</span>')
        self.upload_status_label.set_xalign(0.5)
        upload_box.append(self.upload_status_label)
        
        # Upload result label (initially hidden)
        self.upload_result_label = Gtk.Label()
        self.upload_result_label.set_xalign(0.5)
        self.upload_result_label.set_wrap(True)
        self.upload_result_label.set_selectable(True)  # Allow copying URL
        self.upload_result_label.set_visible(False)
        upload_box.append(self.upload_result_label)
        
        content_box.append(upload_box)
        
        # Start async upload
        self._start_log_upload()
    
    def _get_status_icon(self) -> str:
        """Get icon name based on status."""
        if self.status == self.STATUS_SUCCESS:
            return "object-select-symbolic"  # ✓ checkmark icon (emblem-ok-symbolic not available in Adwaita)
        elif self.status == self.STATUS_CANCELLED:
            return "process-stop-symbolic"
        elif self.status == self.STATUS_FAILED:
            return "dialog-error-symbolic"
        return "dialog-question-symbolic"
    
    def _start_log_upload(self):
        """Start asynchronous log upload."""
        from ...backend.log_utils import AsyncLogUploader
        
        def on_upload_complete(url):
            """Upload complete callback (from background thread)."""
            GLib.idle_add(self._update_upload_status, url)
        
        self.uploader = AsyncLogUploader(config.log_file, on_upload_complete)
        self.uploader.start()
    
    def _update_upload_status(self, url: str | None):
        """Update upload status (on main thread)."""
        if url:
            # Upload successful
            self.upload_status_label.set_markup(
                '<span size="small" foreground="green" weight="bold">日志上传成功</span>'
            )
            self.upload_result_label.set_markup(
                f'<span size="small">日志地址: <a href="{url}">{url}</a></span>'
            )
            self.upload_result_label.set_visible(True)
        else:
            # Upload failed or timed out
            self.upload_status_label.set_markup(
                '<span size="small" foreground="orange" weight="bold">日志上传失败</span>'
            )
            self.upload_result_label.set_markup(
                f'<span size="small">您可以稍后手动上传: <tt>fpaste {config.log_file}</tt></span>'
            )
            self.upload_result_label.set_visible(True)
        
        return False
    
    def populate_buttons(self, button_box: Gtk.Box):
        """Create navigation buttons based on status."""
        # Clear existing buttons
        child = button_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            button_box.remove(child)
            child = next_child
        
        # If status not set yet, show default buttons
        if self.status is None:
            shell_btn = UIComponents.create_button("打开命令行", "utilities-terminal-symbolic")
            shell_btn.connect("clicked", self._on_open_shell)
            button_box.append(shell_btn)
            
            shutdown_btn = UIComponents.create_button("关机", "system-shutdown-symbolic")
            shutdown_btn.connect("clicked", self._on_shutdown)
            button_box.append(shutdown_btn)
            return
        
        if self.status == self.STATUS_SUCCESS:
            # Success: Reboot / Shell / Shutdown
            reboot_btn = UIComponents.create_button("重启", "system-reboot-symbolic")
            reboot_btn.connect("clicked", self._on_reboot)
            button_box.append(reboot_btn)
            
            shell_btn = UIComponents.create_button("打开命令行", "utilities-terminal-symbolic")
            shell_btn.connect("clicked", self._on_open_shell)
            button_box.append(shell_btn)
            
            shutdown_btn = UIComponents.create_button("关机", "system-shutdown-symbolic")
            shutdown_btn.connect("clicked", self._on_shutdown)
            button_box.append(shutdown_btn)
            
        elif self.status == self.STATUS_CANCELLED:
            # Cancelled: Reinstall / Shell / Shutdown
            reinstall_btn = UIComponents.create_button("重新安装", "view-refresh-symbolic")
            reinstall_btn.connect("clicked", self._on_reinstall)
            button_box.append(reinstall_btn)
            
            shell_btn = UIComponents.create_button("打开命令行", "utilities-terminal-symbolic")
            shell_btn.connect("clicked", self._on_open_shell)
            button_box.append(shell_btn)
            
            shutdown_btn = UIComponents.create_button("关机", "system-shutdown-symbolic")
            shutdown_btn.connect("clicked", self._on_shutdown)
            button_box.append(shutdown_btn)
            
        elif self.status == self.STATUS_FAILED:
            # Failed: Reinstall / Shell / Shutdown
            reinstall_btn = UIComponents.create_button("重新安装", "view-refresh-symbolic")
            reinstall_btn.connect("clicked", self._on_reinstall)
            button_box.append(reinstall_btn)
            
            shell_btn = UIComponents.create_button("打开命令行", "utilities-terminal-symbolic")
            shell_btn.connect("clicked", self._on_open_shell)
            button_box.append(shell_btn)
            
            shutdown_btn = UIComponents.create_button("关机", "system-shutdown-symbolic")
            shutdown_btn.connect("clicked", self._on_shutdown)
            button_box.append(shutdown_btn)
    
    def _on_reboot(self, button):
        """Handle reboot button."""
        print("[COMPLETE] User selected: Reboot", flush=True)
        os.system("systemctl reboot")
    
    def _on_shutdown(self, button):
        """Handle shutdown button."""
        print("[COMPLETE] User selected: Shutdown", flush=True)
        os.system("systemctl poweroff")
    
    def _on_open_shell(self, button):
        """Handle open shell button - exit to TTY."""
        print("[COMPLETE] User selected: Open shell (exit to TTY)", flush=True)
        
        # Cleanup local file manager before exit
        if hasattr(self.app, 'local_file_manager'):
            print("[COMPLETE] Cleaning up local file mounts...", flush=True)
            self.app.local_file_manager.cleanup()
        
        sys.exit(0)
    
    def _on_reinstall(self, button):
        """Handle reinstall button - reset app and go to welcome page."""
        print("[COMPLETE] User selected: Reinstall (reset state)", flush=True)
        
        # Reset application state
        self.app.page_history = []
        self.app.current_page = 0
        
        # Clear installation data
        attrs_to_clear = [
            'selected_disk',
            'selected_mode',
            'dual_mode',
            'shrink_partition',
            'shrink_size',
            'delete_partition',
            'bootstrap_completed',
            'install_target',
            'selected_version',
            'selected_desktop',
            'nvidia_driver',
            'version_selections'
        ]
        
        for attr in attrs_to_clear:
            if hasattr(self.app, attr):
                delattr(self.app, attr)
        
        # Reset to welcome page
        self.app.show_page(0, add_to_history=False)
