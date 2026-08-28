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
from ...logger import get_logger
from ...engine import InstallPlan, DeployService, EventKind

logger = get_logger('install')


class InstallPage(ExecutionPage):
    """Installation page that executes the system installation process."""
    
    # Class-level lock to prevent concurrent executions
    _execution_lock = None
    
    def __init__(self, app):
        super().__init__(app)
        self.install_thread = None
        self.install_process = None
        self.deploy_service = None
    
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
        
        # Store references for backward compatibility
        self.app.install_status_label = self.status_label
        self.app.install_progress_bar = self.progress_bar
        self.app.install_cancel_btn = self.cancel_btn
        self.app.install_start_btn = self.start_btn
        
        # Check if installation already completed (in case user navigates back)
        if hasattr(self.app, 'install_completed') and self.app.install_completed:
            # Already done, don't restart
            GLib.timeout_add(100, self._restore_success_state)
        else:
            # Start installation automatically (like bootstrap page)
            GLib.timeout_add(100, lambda: (self.start_execution(), False)[1])
        
        return page_box
    
    def on_start_clicked(self, button):
        """Handle start/retry button click."""
        self.start_execution()
    
    def on_cancel_clicked(self, button):
        """Handle cancel button click - terminate process and clean up."""
        if not self.is_executing:
            self.app.go_back()
            return
        
        # Show cancellation in progress
        GLib.idle_add(self.update_status, '<span size="large">正在取消安装...</span>')
        GLib.idle_add(self.append_log, "\n" + "="*60 + "\n")
        GLib.idle_add(self.append_log, "用户请求取消安装\n")
        GLib.idle_add(self.append_log, "="*60 + "\n\n")
        
        # Execute cleanup in background thread
        def cleanup_thread():
            try:
                # 1. Terminate process
                self._terminate_process()
                
                # 2. Wait for process to release file handles
                import time
                time.sleep(3)
                
                # 3. Clean up mounts (allows frzr-deploy to remount on retry)
                GLib.idle_add(self.append_log, "正在清理挂载点...\n")
                self._cleanup_mounts()
                
                # 4. Clean up partial deployment
                GLib.idle_add(self.append_log, "正在清理未完成的系统部署...\n")
                self._cleanup_partial_deployment()
                
                # 5. Clean up temporary files
                GLib.idle_add(self.append_log, "正在清理临时文件...\n")
                self._cleanup_temp_files()
                
                # 6. Reset state flags
                self.is_executing = False
                self.execution_completed = False
                self.execution_failed = False
                self.install_process = None
                
                # Clear install_completed flag to allow retry
                if hasattr(self.app, 'install_completed'):
                    delattr(self.app, 'install_completed')
                
                GLib.idle_add(self.append_log, "\n" + "="*60 + "\n")
                GLib.idle_add(self.append_log, "清理完成，您可以选择：\n")
                GLib.idle_add(self.append_log, "• 重试安装 - frzr-deploy 会自动重新挂载磁盘\n")
                GLib.idle_add(self.append_log, "• 返回重新配置安装选项\n")
                GLib.idle_add(self.append_log, "• 退出安装程序\n")
                GLib.idle_add(self.append_log, "="*60 + "\n")
                
                # Show retry UI
                GLib.idle_add(self._show_retry_ui)
                
            except Exception as e:
                GLib.idle_add(self.append_log, f"\n[错误] 清理过程出错: {e}\n")
                GLib.idle_add(self._show_retry_ui)
        
        # Start cleanup thread
        import threading
        cleanup_thread_obj = threading.Thread(target=cleanup_thread, daemon=True)
        cleanup_thread_obj.start()
    
    def execute(self):
        """Execute the actual installation process."""
        # Prevent concurrent executions using class-level lock
        if InstallPage._execution_lock is not None:
            logger.warning("Installation already in progress, ignoring duplicate call")
            GLib.idle_add(self.append_log, "[WARNING] 检测到重复执行请求，已忽略\n")
            return
        
        InstallPage._execution_lock = True
        
        try:
            plan = InstallPlan.from_app_state(self.app)
            self.app.plan = plan
            log_path = config.log_file
            os.makedirs(os.path.dirname(log_path), exist_ok=True)

            if plan.source == 'local':
                if not plan.local_file or not os.path.exists(plan.local_file):
                    raise Exception(f"本地镜像文件不存在: {plan.local_file}")
                filename = os.path.basename(str(plan.local_file))
                GLib.idle_add(self.update_status, '<span size="large">正在从本地镜像安装...</span>')
                GLib.idle_add(self.append_log, f"使用本地镜像: {filename}\n\n")
            else:
                GLib.idle_add(self.update_status, '<span size="large">正在下载系统镜像...</span>')

            GLib.idle_add(self.update_progress, 0.1, "准备中")
            from ...flow.env import simulation

            if simulation():
                from ...flow.lifecycle import apply_advanced_options

                apply_advanced_options(
                    plan.advanced,
                    log=lambda m: GLib.idle_add(self.append_log, m + "\n"),
                )
            else:
                self._apply_advanced_options()

            def on_engine_event(event):
                if event.kind == EventKind.LOG and event.message:
                    GLib.idle_add(self.append_log, event.message)
                    self._update_progress_from_output(event.message)
                elif event.kind == EventKind.STAGE and event.message:
                    GLib.idle_add(self.append_log, f"[stage:{event.stage}] {event.message}\n")

            if plan.advanced.get('debug'):
                GLib.idle_add(self.append_log, "[信息] Debug 模式已启用\n")

            self.deploy_service = DeployService(on_event=on_engine_event)
            result = self.deploy_service.run(plan, log_file=log_path)
            self.install_process = self.deploy_service.process

            if result.returncode != 0:
                GLib.idle_add(self.append_log, f"\n[ERROR] 安装失败 (退出码: {result.returncode})\n")
                self.on_execution_error(f"安装失败 (退出码: {result.returncode})")
                return

            GLib.idle_add(self.append_log, "\n[SUCCESS] 安装完成\n")
            self.on_execution_success()

        except Exception as e:
            self.on_execution_error(f"安装错误: {str(e)}")
        finally:
            # Release lock when done
            InstallPage._execution_lock = None

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
        
        # Mark installation as completed
        self.app.install_completed = True
        
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
            from ...flow.env import simulation

            if simulation():
                from ...flow.lifecycle import after_deploy_success

                after_deploy_success(log=lambda m: self.append_log(m + "\n"))
            else:
                from ...backend.install_utils import copy_network_config, copy_timezone_config, post_install

                self.append_log("正在复制网络配置...\n")
                if copy_network_config(mount_path):
                    self.append_log("[成功] 网络配置已复制\n")
                else:
                    self.append_log("[警告] 网络配置复制失败\n")

                self.append_log("\n正在复制时区配置...\n")
                timezone = os.environ.get('INSTALLER_TIMEZONE', 'UTC')
                if copy_timezone_config(mount_path, timezone):
                    self.append_log(f"[成功] 时区已设置为: {timezone}\n")
                else:
                    self.append_log("[警告] 时区配置复制失败，目标系统将使用 UTC\n")

                self.append_log("\n正在执行系统优化...\n")
                if post_install(mount_path):
                    self.append_log("[成功] 系统优化完成\n")
                else:
                    self.append_log("[警告] 系统优化失败\n")

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
            except Exception as e:
                logger.debug(f"Could not read boot config: {e}")
        else:
            self.append_log("[警告] 启动配置文件不存在！\n")
    
    def _apply_advanced_options(self):
        """Apply advanced options before installation."""
        options = self.app.advanced_options
        
        GLib.idle_add(self.append_log, f"\n{'='*60}\n")
        GLib.idle_add(self.append_log, "正在应用高级选项...\n")
        GLib.idle_add(self.append_log, f"{'='*60}\n\n")
        
        # 1. Firmware overrides
        if options.get('firmware_overrides', False):
            self._apply_firmware_overrides()
        
        # 2. CDN settings
        self._apply_cdn_settings(options.get('cdn', False))
        
        # 3. Fallback URL
        self._apply_fallback_setting(options.get('fallback_url', True))
        
        GLib.idle_add(self.append_log, "[信息] 高级选项已应用\n\n")
    
    def _apply_firmware_overrides(self):
        """Create device-quirks configuration."""
        from ...config import config
        quirks_dir = f"{config.mount_path}/etc/device-quirks"
        
        try:
            os.makedirs(quirks_dir, exist_ok=True)
            
            # Create device-quirks.conf
            config_file = f"{quirks_dir}/device-quirks.conf"
            with open(config_file, 'w') as f:
                f.write("export USE_FIRMWARE_OVERRIDES=1\n")
                f.write("export USB_WAKE_ENABLED=1\n")
            
            # Create dsdt_override.log
            log_file = f"{quirks_dir}/dsdt_override.log"
            with open(log_file, 'w') as f:
                f.write("LAST_DSDT=None\n")
                f.write("LAST_BIOS_DATE=None\n")
                f.write("LAST_BIOS_RELEASE=None\n")
                f.write("LAST_BIOS_VENDOR=None\n")
                f.write("LAST_BIOS_VERSION=None\n")
            
            GLib.idle_add(self.append_log, "[成功] 固件覆盖配置已创建\n")
            
        except Exception as e:
            GLib.idle_add(self.append_log, f"[警告] 固件覆盖配置失败: {e}\n")
    
    def _apply_cdn_settings(self, enable_cdn):
        """Modify frzr-sk.conf for CDN settings."""
        try:
            config_file = "/etc/frzr-sk.conf"
            if not os.path.exists(config_file):
                GLib.idle_add(self.append_log, "[警告] frzr-sk.conf 不存在\n")
                return
            
            # Read config
            with open(config_file, 'r') as f:
                content = f.read()
            
            # Modify CDN settings
            import re
            content = re.sub(r'^release_cdn\s*=.*', f'release_cdn = {"true" if enable_cdn else "false"}', content, flags=re.MULTILINE)
            content = re.sub(r'^api_cdn\s*=.*', f'api_cdn = {"true" if enable_cdn else "false"}', content, flags=re.MULTILINE)
            
            # Write back
            with open(config_file, 'w') as f:
                f.write(content)
            
            status = "启用" if enable_cdn else "禁用"
            GLib.idle_add(self.append_log, f"[成功] CDN 加速已{status}\n")
            
        except Exception as e:
            GLib.idle_add(self.append_log, f"[警告] CDN 配置失败: {e}\n")
    
    def _apply_fallback_setting(self, enable_fallback):
        """Modify frzr-sk.conf for fallback URL."""
        try:
            config_file = "/etc/frzr-sk.conf"
            if not os.path.exists(config_file):
                return
            
            with open(config_file, 'r') as f:
                content = f.read()
            
            import re
            content = re.sub(r'^fallback_url\s*=.*', f'fallback_url = {"true" if enable_fallback else "false"}', content, flags=re.MULTILINE)
            
            with open(config_file, 'w') as f:
                f.write(content)
            
            status = "启用" if enable_fallback else "禁用"
            GLib.idle_add(self.append_log, f"[成功] 备用源已{status}\n")
            
        except Exception as e:
            GLib.idle_add(self.append_log, f"[警告] 备用源配置失败: {e}\n")
    
    def on_execution_error(self, error_msg: str):
        """Match TUI: deploy failure opens complete/failed."""
        self.is_executing = False
        self.execution_failed = True
        from .complete import CompletePage
        from ...flow import copy as flow_copy

        def go():
            self.app.show_complete_page(
                CompletePage.STATUS_FAILED,
                flow_copy.COMPLETE_FAIL_SUMMARY,
                error_msg,
            )
            return False

        GLib.idle_add(go)
    
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
    
    def _restore_success_state(self):
        """Restore success state if installation was already completed."""
        self.update_status('<span size="large" foreground="green" weight="bold">安装已完成！</span>')
        self.update_progress(1.0, "完成")
        self.show_buttons(back=False, cancel=False, exit=False, start=False)
        
        # Show continue button
        if self._button_box and not self.continue_btn:
            self.continue_btn = UIComponents.create_button("继续", "go-next-symbolic")
            self.continue_btn.connect("clicked", self.on_continue_clicked)
            self._button_box.append(self.continue_btn)
        
        if self.continue_btn:
            self.continue_btn.set_visible(True)
        
        return False
    
    def _terminate_process(self):
        """Terminate frzr-deploy process."""
        if self.deploy_service:
            try:
                GLib.idle_add(self.append_log, "正在终止 frzr-deploy 进程...\n")
                self.deploy_service.cancel()
                GLib.idle_add(self.append_log, "✓ 进程已终止\n")
                return
            except Exception as e:
                GLib.idle_add(self.append_log, f"[警告] 进程终止出错: {e}\n")
        if self.install_process and self.install_process.poll() is None:
            try:
                GLib.idle_add(self.append_log, "正在终止 frzr-deploy 进程...\n")
                self.install_process.terminate()
                try:
                    self.install_process.wait(timeout=5)
                    GLib.idle_add(self.append_log, "✓ 进程已优雅终止\n")
                except subprocess.TimeoutExpired:
                    GLib.idle_add(self.append_log, "进程未响应，强制终止...\n")
                    self.install_process.kill()
                    self.install_process.wait()
                    GLib.idle_add(self.append_log, "✓ 进程已强制终止\n")
            except Exception as e:
                GLib.idle_add(self.append_log, f"[警告] 进程终止出错: {e}\n")
    
    def _cleanup_mounts(self):
        """Unmount all frzr_root mounts - allows frzr-deploy to remount on retry."""
        mount_path = config.mount_path
        
        # Unmount in reverse order (deepest first)
        mount_points = [
            f"{mount_path}/boot/efi",
            f"{mount_path}/boot",
            mount_path
        ]
        
        for mount_point in mount_points:
            try:
                # Check if mounted
                result = subprocess.run(
                    ['mountpoint', '-q', mount_point],
                    timeout=2
                )
                
                if result.returncode == 0:  # Is mounted
                    GLib.idle_add(self.append_log, f"  卸载: {mount_point}\n")
                    
                    # Sync to ensure data is written
                    subprocess.run(['sync'], timeout=5)
                    
                    # Try normal unmount
                    result = subprocess.run(
                        ['umount', mount_point],
                        timeout=10,
                        capture_output=True
                    )
                    
                    if result.returncode == 0:
                        GLib.idle_add(self.append_log, f"  ✓ 已卸载\n")
                    else:
                        # Force unmount
                        GLib.idle_add(self.append_log, f"  使用强制卸载...\n")
                        subprocess.run(['umount', '-f', mount_point], timeout=5)
                        GLib.idle_add(self.append_log, f"  ✓ 已强制卸载\n")
            
            except subprocess.TimeoutExpired:
                # Use lazy unmount as last resort
                try:
                    subprocess.run(['umount', '-l', mount_point])
                    GLib.idle_add(self.append_log, f"  ⚠ 使用 lazy unmount: {mount_point}\n")
                except:
                    pass
            except Exception as e:
                GLib.idle_add(self.append_log, f"  [跳过] {mount_point}: {str(e)}\n")
        
        GLib.idle_add(self.append_log, "✓ 挂载点清理完成\n\n")
    
    def _cleanup_partial_deployment(self):
        """Clean up partially created btrfs subvolumes."""
        mount_path = config.mount_path
        
        try:
            # Check if mount path is still mounted
            result = subprocess.run(['mountpoint', '-q', mount_path])
            if result.returncode != 0:
                GLib.idle_add(self.append_log, "  磁盘已卸载，跳过子卷清理\n\n")
                return
            
            # List all deployment subvolumes
            result = subprocess.run(
                ['btrfs', 'subvolume', 'list', mount_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout:
                # Find incomplete deployments (exclude currently running system)
                current_release = None
                try:
                    current_release = subprocess.run(
                        ['frzr-release'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    ).stdout.strip()
                except:
                    pass
                
                deleted_count = 0
                for line in result.stdout.split('\n'):
                    if 'deployments/' in line:
                        parts = line.split()
                        if parts:
                            subvol_path = parts[-1]
                            full_path = f"{mount_path}/{subvol_path}"
                            
                            # Don't delete currently running system
                            if current_release and current_release in subvol_path:
                                continue
                            
                            try:
                                GLib.idle_add(self.append_log, f"  删除未完成的部署: {subvol_path}\n")
                                # Set to read-write
                                subprocess.run(
                                    ['btrfs', 'property', 'set', '-fts', full_path, 'ro', 'false'],
                                    timeout=5
                                )
                                # Delete subvolume
                                subprocess.run(
                                    ['btrfs', 'subvolume', 'delete', full_path],
                                    timeout=10
                                )
                                GLib.idle_add(self.append_log, f"  ✓ 已删除\n")
                                deleted_count += 1
                            except Exception as e:
                                GLib.idle_add(self.append_log, f"  [警告] 删除失败: {e}\n")
                
                if deleted_count > 0:
                    GLib.idle_add(self.append_log, f"✓ 已清理 {deleted_count} 个未完成的部署\n\n")
                else:
                    GLib.idle_add(self.append_log, "  未发现需要清理的部署\n\n")
        
        except Exception as e:
            GLib.idle_add(self.append_log, f"[信息] 子卷清理跳过: {e}\n\n")
    
    def _cleanup_temp_files(self):
        """Clean up temporary files from interrupted installation."""
        import glob
        import shutil
        
        temp_patterns = [
            f'{config.mount_path}/*.img.*',
            '/tmp/frzr_*.img',
            '/tmp/frzr_download/*',
        ]
        
        deleted_count = 0
        for pattern in temp_patterns:
            try:
                for path in glob.glob(pattern):
                    try:
                        if os.path.isfile(path):
                            os.remove(path)
                            GLib.idle_add(self.append_log, f"  删除临时文件: {os.path.basename(path)}\n")
                            deleted_count += 1
                        elif os.path.isdir(path):
                            shutil.rmtree(path)
                            GLib.idle_add(self.append_log, f"  删除临时目录: {os.path.basename(path)}\n")
                            deleted_count += 1
                    except Exception as e:
                        logger.debug(f"Failed to delete {path}: {e}")
            except Exception as e:
                logger.debug(f"Error processing pattern {pattern}: {e}")
        
        if deleted_count > 0:
            GLib.idle_add(self.append_log, f"✓ 已清理 {deleted_count} 个临时文件\n\n")
        else:
            GLib.idle_add(self.append_log, "  未发现需要清理的临时文件\n\n")
    
    def _show_retry_ui(self):
        """Show UI with retry option after cancellation."""
        self.update_status('<span size="large">安装已取消</span>')
        self.update_progress(0.0, "已取消")
        
        # Show back, retry, and exit buttons
        self.show_buttons(back=True, cancel=False, exit=True, start=True)
        
        # Update start button text to "重试安装"
        if self.start_btn:
            child = self.start_btn.get_child()
            if isinstance(child, Gtk.Box):
                widget = child.get_first_child()
                while widget:
                    if isinstance(widget, Gtk.Label):
                        widget.set_text("重试安装")
                        break
                    widget = widget.get_next_sibling()
        
        return False


def create_install_page(app):
    """Create the installation page using the new page architecture."""
    page = InstallPage(app)
    return page.create()
