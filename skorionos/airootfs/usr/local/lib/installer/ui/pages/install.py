"""
Installation page - executes the actual system installation.
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import subprocess
import threading
import os
from ...config import config
from ..components.base import ExecutionPage, UIComponents


class InstallPage(ExecutionPage):
    """Installation page that executes the system installation process."""
    
    def __init__(self, app):
        super().__init__(app)
        self.install_thread = None
        self.install_process = None
    
    def get_title_text(self) -> str:
        return "安装系统"
    
    def get_initial_status_text(self) -> str:
        return "准备开始安装..."
    
    def get_initial_progress_text(self) -> str:
        return "等待中"
    
    def get_start_button_text(self) -> str:
        return "开始安装"
    
    def create_title(self) -> Gtk.Widget:
        """Create title with icon."""
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
        title_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("system-software-install-symbolic")
        icon.set_pixel_size(config.scaled(48))
        title_box.append(icon)
        
        title = UIComponents.create_title(self.get_title_text())
        title_box.append(title)
        
        return title_box
    
    def create(self) -> Gtk.Box:
        """Create and return the page widget."""
        page_box = super().create()
        
        # Show start and cancel buttons initially (user must click to start)
        self.show_buttons(back=False, cancel=True, start=True)
        
        # Store references for backward compatibility
        self.app.install_status_label = self.status_label
        self.app.install_progress_bar = self.progress_bar
        self.app.install_cancel_btn = self.cancel_btn
        self.app.install_start_btn = self.start_btn
        
        return page_box
    
    def on_start_clicked(self, button):
        """Handle start/retry button click."""
        self.start_execution()
    
    def on_cancel_clicked(self, button):
        """Handle cancel button click - go back to previous page."""
        if self.is_executing and self.install_process:
            # TODO: Implement process termination
            pass
        self.app.go_back()
    
    def execute(self):
        """Execute the actual installation process."""
        try:
            # Get installation parameters
            version = getattr(self.app, 'selected_version', 'stable')
            desktop = getattr(self.app, 'selected_desktop', 'steamos')
            nvidia = getattr(self.app, 'nvidia_driver', False)
            
            # Use unified log file (append mode, bootstrap already wrote to it)
            log_path = config.log_file
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            
            with open(log_path, 'a') as f:
                f.write(f"\n{'='*60}\n")
                f.write("=== frzr-deploy started ===\n")
                f.write(f"{'='*60}\n")
                f.write(f"Version: {version}\n")
                f.write(f"Desktop: {desktop}\n")
                f.write(f"NVIDIA: {nvidia}\n\n")
            
            # Update status
            GLib.idle_add(self.update_status, '<span size="large">正在下载系统镜像...</span>')
            GLib.idle_add(self.update_progress, 0.1, "下载中")
            
            # Build install command
            cmd = self._build_install_command(version, desktop, nvidia)
            
            GLib.idle_add(self.append_log, f"=== Executing: {' '.join(cmd)} ===\n\n")
            
            # Execute installation
            self.install_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Read output line by line
            with open(log_path, 'a') as log_file:
                for line in self.install_process.stdout:
                    log_file.write(line)
                    log_file.flush()
                    GLib.idle_add(self.append_log, line)
                    
                    # Update progress based on output
                    self._update_progress_from_output(line)
            
            # Wait for completion
            self.install_process.wait()
            
            if self.install_process.returncode != 0:
                GLib.idle_add(self.append_log, f"\n[ERROR] 安装失败 (退出码: {self.install_process.returncode})\n")
                self.on_execution_error(f"安装失败 (退出码: {self.install_process.returncode})")
                return
            
            GLib.idle_add(self.append_log, "\n[SUCCESS] 安装完成\n")
            self.on_execution_success()
            
        except Exception as e:
            self.on_execution_error(f"安装错误: {str(e)}")
    
    def _build_install_command(self, version, desktop, nvidia):
        """Build the installation command based on user selections."""
        cmd = ['frzr-deploy']
        
        # Add version parameter
        if version == 'stable':
            cmd.append('skorionos/stable')
        elif version == 'beta':
            cmd.append('skorionos/beta')
        elif version == 'nightly':
            cmd.append('skorionos/nightly')
        
        # Add desktop parameter
        if desktop != 'steamos':
            cmd.extend(['--desktop', desktop])
        
        # Add NVIDIA driver flag
        if nvidia:
            cmd.append('--nvidia')
        
        return cmd
    
    def _update_progress_from_output(self, line):
        """Update progress bar based on installation output."""
        line_lower = line.lower()
        
        if 'downloading' in line_lower or '下载' in line_lower:
            GLib.idle_add(self.update_status, '<span size="large">正在下载系统镜像...</span>')
            GLib.idle_add(self.update_progress, 0.3, "下载中")
        elif 'extracting' in line_lower or '解压' in line_lower:
            GLib.idle_add(self.update_status, '<span size="large">正在解压系统镜像...</span>')
            GLib.idle_add(self.update_progress, 0.5, "解压中")
        elif 'installing' in line_lower or '安装' in line_lower:
            GLib.idle_add(self.update_status, '<span size="large">正在安装系统...</span>')
            GLib.idle_add(self.update_progress, 0.7, "安装中")
        elif 'configuring' in line_lower or '配置' in line_lower:
            GLib.idle_add(self.update_status, '<span size="large">正在配置系统...</span>')
            GLib.idle_add(self.update_progress, 0.9, "配置中")
    
    def on_execution_success(self):
        """Called when installation completes successfully - go to complete page."""
        from .complete import CompletePage
        
        # Update success message in log first
        GLib.idle_add(self._update_success_message)
        
        # Perform post-installation steps
        GLib.idle_add(self._post_install_steps)
        
        # Go to complete page with SUCCESS status
        def show_success():
            self.app.show_complete_page(
                CompletePage.STATUS_SUCCESS,
                "SkorionOS 已成功安装到您的设备",
                "请选择下一步操作"
            )
            return False
        
        # Delay slightly to let log update and post-install finish
        GLib.timeout_add(1000, show_success)
    
    def _update_success_message(self):
        """Update success message in log."""
        self.append_log(f"\n{'='*60}\n")
        self.append_log("系统安装成功完成！\n")
        self.append_log(f"{'='*60}\n")
        return False
    
    def _post_install_steps(self):
        """Perform post-installation configuration."""
        from ...config import config
        mount_path = config.mount_path
        
        self.append_log(f"\n{'='*60}\n")
        self.append_log("正在进行后安装配置...\n")
        self.append_log(f"{'='*60}\n\n")
        
        try:
            from ...backend.install_utils import copy_network_config, post_install
            
            # Step 1: Copy network configuration
            self.append_log("正在复制网络配置...\n")
            if copy_network_config(mount_path):
                self.append_log("[成功] 网络配置已复制\n")
            else:
                self.append_log("[警告] 网络配置复制失败\n")
            
            # Step 2: Post-installation optimizations
            self.append_log("\n正在执行系统优化...\n")
            if post_install(mount_path):
                self.append_log("[成功] 系统优化完成\n")
            else:
                self.append_log("[警告] 系统优化失败\n")
            
            # Step 3: Verify boot configuration
            self.append_log("\n正在验证启动配置...\n")
            self._verify_boot_config(mount_path)
            
            self.append_log(f"\n{'='*60}\n")
            self.append_log("后安装配置完成！\n")
            self.append_log(f"{'='*60}\n\n")
            
        except Exception as e:
            self.append_log(f"\n[警告] 后安装步骤出错: {str(e)}\n")
        
        return False
    
    def _verify_boot_config(self, mount_path):
        """Verify boot configuration exists."""
        boot_cfg = f"{mount_path}/boot/loader/entries/frzr.conf"
        
        if os.path.exists(boot_cfg):
            self.append_log("[成功] 启动配置文件存在\n")
            # Read and display boot config
            try:
                with open(boot_cfg, 'r') as f:
                    content = f.read()
                    self.append_log(f"\n启动配置内容:\n{content}\n")
            except:
                pass
        else:
            self.append_log("[警告] 启动配置文件不存在！\n")
    
    def on_execution_error(self, error_msg: str):
        """Called when installation fails."""
        # Call parent to update UI
        super().on_execution_error(error_msg)
        
        # Update start button label to show "重试安装"
        GLib.idle_add(self._update_retry_button_label)
    
    def _update_retry_button_label(self):
        """Update start button label to '重试安装'."""
        if self.start_btn:
            child = self.start_btn.get_child()
            if isinstance(child, Gtk.Box):
                # Find the label widget in the box
                widget = child.get_first_child()
                while widget:
                    if isinstance(widget, Gtk.Label):
                        widget.set_text("重试安装")
                        break
                    widget = widget.get_next_sibling()
        return False
    
    def on_continue_clicked(self, button):
        """Navigate to completion page after successful installation."""
        self.app.show_page('complete')


def create_install_page(app):
    """Create the installation page using the new page architecture."""
    page = InstallPage(app)
    return page.create()
