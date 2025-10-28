"""
Bootstrap page - executes frzr-bootstrap and scans for local installation files.
This must run BEFORE version selection, as it mounts the disk and scans for files.
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import subprocess
import os
from ...config import config
from ..components.base import ExecutionPage, UIComponents


class BootstrapPage(ExecutionPage):
    """Bootstrap page that initializes disk partitions and prepares for installation."""
    
    def __init__(self, app):
        super().__init__(app)
        self.log_file_path = config.log_file
    
    def get_title_text(self) -> str:
        return "正在初始化磁盘"
    
    def get_initial_status_text(self) -> str:
        return "正在格式化磁盘并创建分区..."
    
    def get_initial_progress_text(self) -> str:
        return "准备中"
    
    def get_start_button_text(self) -> str:
        return "开始初始化"
    
    def create_title(self) -> Gtk.Widget:
        """Create title with icon."""
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
        title_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic")
        icon.set_pixel_size(config.scaled(48))
        title_box.append(icon)
        
        title = UIComponents.create_title(self.get_title_text())
        title_box.append(title)
        
        return title_box
    
    def create(self) -> Gtk.Box:
        """Create and return the page widget."""
        page_box = super().create()
        
        # Check if bootstrap already completed
        if hasattr(self.app, 'bootstrap_completed') and self.app.bootstrap_completed:
            # Already done, restore success state
            GLib.timeout_add(100, self._restore_success_state)
        else:
            # Start bootstrap process automatically
            GLib.timeout_add(100, lambda: (self.start_execution(), False)[1])
        
        return page_box
    
    def execute(self):
        """Execute frzr-bootstrap and scan for local files."""
        try:
            disk = self.app.selected_disk
            mode = self.app.install_mode
            
            # Step 1: Set NTP
            GLib.idle_add(self.update_status, '<span size="large">正在同步系统时间...</span>')
            subprocess.run(['timedatectl', 'set-ntp', 'true'], check=False)
            
            # Step 2: Execute frzr-bootstrap in non-interactive mode
            if mode == 'repair':
                status_msg = f'<span size="large">正在修复 /dev/{disk} 上的安装...</span>'
            elif mode == 'fresh':
                status_msg = f'<span size="large">正在格式化磁盘 /dev/{disk}...</span>'
            elif mode == 'dual':
                status_msg = '<span size="large">正在创建双系统分区...</span>'
            else:
                status_msg = f'<span size="large">正在初始化磁盘 /dev/{disk}...</span>'
            
            GLib.idle_add(self.update_status, status_msg)
            
            # Initialize log file
            os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
            with open(self.log_file_path, 'w') as f:
                f.write(f"=== frzr-bootstrap started (non-interactive mode) ===\n")
                f.write(f"Mode: {mode}\n")
                f.write(f"Disk: /dev/{disk}\n")
            
            # Build frzr-bootstrap command
            cmd = ['frzr-bootstrap', 'gamer', f'/dev/{disk}', mode]
            
            # Set up environment variables
            env = os.environ.copy()
            env['FRZR_NONINTERACTIVE'] = '1'
            
            # Add dual-boot specific parameters
            if mode == 'dual':
                dual_mode = getattr(self.app, 'dual_mode', 'auto')
                
                if dual_mode == 'shrink':
                    env['FRZR_SHRINK_PARTITION'] = self.app.shrink_partition
                    env['FRZR_SHRINK_SIZE'] = str(self.app.shrink_size)
                    with open(self.log_file_path, 'a') as f:
                        f.write(f"Dual mode: shrink {self.app.shrink_partition} by {self.app.shrink_size}GB\n")
                
                elif dual_mode == 'delete':
                    env['FRZR_DELETE_PARTITION'] = self.app.delete_partition
                    with open(self.log_file_path, 'a') as f:
                        f.write(f"Dual mode: delete {self.app.delete_partition}\n")
                
                else:  # auto
                    with open(self.log_file_path, 'a') as f:
                        f.write(f"Dual mode: auto (use available free space)\n")
            
            # Run frzr-bootstrap and capture output in real-time
            GLib.idle_add(self.append_log, f"=== Executing: {' '.join(cmd)} ===\n")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )
            
            # Read output line by line and update UI
            with open(self.log_file_path, 'a') as log_file:
                log_file.write(f"\n=== Executing: {' '.join(cmd)} ===\n\n")
                for line in process.stdout:
                    # Write to log file
                    log_file.write(line)
                    log_file.flush()
                    # Update UI
                    GLib.idle_add(self.append_log, line)
            
            # Wait for process to complete
            process.wait()
            
            if process.returncode != 0:
                GLib.idle_add(self.append_log, f"\n[ERROR] frzr-bootstrap 失败 (退出码: {process.returncode})\n")
                self.on_execution_error(f"frzr-bootstrap 失败 (退出码: {process.returncode})")
                return
            
            GLib.idle_add(self.append_log, "\n[SUCCESS] frzr-bootstrap 完成\n")
            
            # Step 3: Scan for local installation files
            GLib.idle_add(self.update_status, '<span size="large">正在扫描本地安装文件...</span>')
            local_files = self._scan_frzr_update_files()
            
            # Store results
            self.app.local_frzr_files = local_files
            
            # Mark as completed
            self.app.bootstrap_completed = True
            
            # Success
            self.on_execution_success()
            
        except Exception as e:
            self.on_execution_error(f"Bootstrap错误: {str(e)}")
    
    def _scan_frzr_update_files(self):
        """
        Scan mounted partitions for FRZR_UPDATE files.
        Returns list of available local files.
        """
        local_files = []
        
        try:
            # Check if FRZR_UPDATE label exists
            result = subprocess.run(
                ['ls', '-1', '/dev/disk/by-label'],
                capture_output=True,
                text=True
            )
            
            if 'FRZR_UPDATE' not in result.stdout:
                return local_files
            
            # Mount and scan FRZR_UPDATE partition
            update_mount = '/tmp/frzr_update_mount'
            os.makedirs(update_mount, exist_ok=True)
            
            subprocess.run(
                ['mount', '/dev/disk/by-label/FRZR_UPDATE', update_mount],
                check=False
            )
            
            # Scan for .img.tar.zst files
            if os.path.exists(update_mount):
                for file in os.listdir(update_mount):
                    if file.endswith('.img.tar.zst'):
                        local_files.append(os.path.join(update_mount, file))
            
            # Unmount
            subprocess.run(['umount', update_mount], check=False)
            
        except Exception as e:
            print(f"Error scanning FRZR_UPDATE: {e}")
        
        return local_files
    
    def on_execution_success(self):
        """Called when bootstrap completes successfully."""
        super().on_execution_success()
        
        # Update custom success message
        GLib.idle_add(self._update_success_message)
    
    def _update_success_message(self):
        """Update success message in log."""
        self.append_log(f"\n{'='*60}\n")
        self.append_log("磁盘初始化成功完成！\n")
        self.append_log(f"{'='*60}\n")
        self.append_log("\n点击下方「继续」按钮进入下一步\n")
        return False
    
    def on_continue_clicked(self, button):
        """Navigate to version selection page after successful bootstrap."""
        self.app.show_page('version')
    
    def _restore_success_state(self):
        """Restore success state when returning to page."""
        # Update UI
        self.update_status('<span size="large" foreground="green" weight="bold">✓ 磁盘初始化完成</span>')
        self.update_progress(1.0, "完成")
        
        # Reload log from file
        try:
            if os.path.exists(self.log_file_path):
                with open(self.log_file_path, 'r') as f:
                    log_content = f.read()
                    self.append_log(log_content)
        except Exception as e:
            print(f"[WARN] Could not reload log: {e}")
        
        # Show continue button
        self.show_buttons(back=False, cancel=False, start=False)
        
        if not self.continue_btn:
            self.continue_btn = UIComponents.create_button("继续", "go-next-symbolic")
            self.continue_btn.add_css_class("suggested-action")
            self.continue_btn.connect("clicked", self.on_continue_clicked)
            self._button_box.append(self.continue_btn)
        
        self.continue_btn.set_visible(True)
        
        return False


def create_bootstrap_page(app):
    """Create the bootstrap page using the new page architecture."""
    page = BootstrapPage(app)
    return page.create()
