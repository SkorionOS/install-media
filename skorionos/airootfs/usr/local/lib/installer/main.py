"""
Main installer application window
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gdk, GLib, Adw
import sys
import atexit

from .config import config
from .logger import get_logger

logger = get_logger('main')
from .ui.styling import apply_styling
from .ui.components.base import UIComponents
from .ui.pages.network import create_network_page
from .ui.pages.disk import create_disk_page
from .ui.pages.mode import create_mode_page
from .ui.pages.confirm import create_confirm_page
from .ui.pages.bootstrap import create_bootstrap_page
from .ui.pages.version import create_version_page
from .ui.pages.advanced import create_advanced_options_page
from .ui.pages.install import create_install_page
from .ui.pages.complete import CompletePage


class StatusBar:
    """Top status bar showing battery and time information"""
    
    def __init__(self):
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.box.add_css_class("status-bar")
        self.box.set_spacing(config.scaled(20))
        
        # Battery info (left side) - icon + label
        battery_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(8))
        self.battery_icon = Gtk.Image()
        self.battery_icon.set_icon_size(Gtk.IconSize.NORMAL)
        battery_box.append(self.battery_icon)
        
        self.battery_label = Gtk.Label()
        battery_box.append(self.battery_label)
        
        self.box.append(battery_box)
        
        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.box.append(spacer)
        
        # Time info (right side) - icon + label
        time_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(8))
        time_icon = Gtk.Image.new_from_icon_name("preferences-system-time-symbolic")
        time_icon.set_icon_size(Gtk.IconSize.NORMAL)
        time_box.append(time_icon)
        
        self.time_label = Gtk.Label()
        time_box.append(self.time_label)
        
        self.box.append(time_box)
        
        # Theme toggle button (far right)
        self.theme_button = Gtk.Button()
        self.theme_button.set_has_frame(False)  # Flat style
        self.theme_button.add_css_class("theme-toggle-btn")
        self.theme_icon = Gtk.Image()
        self.theme_icon.set_icon_size(Gtk.IconSize.NORMAL)
        self.theme_button.set_child(self.theme_icon)
        self.theme_button.connect("clicked", self.toggle_theme)
        self.box.append(self.theme_button)
        
        # Get initial theme state using libadwaita StyleManager
        self.style_manager = Adw.StyleManager.get_default()
        
        # Force dark mode by default
        self.dark_mode = True
        self.style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        
        self.update_theme_icon()
        
        # Update immediately
        self.update_battery()
        self.update_time()
        
        # Schedule updates
        GLib.timeout_add_seconds(60, self.update_battery)  # Every minute
        GLib.timeout_add_seconds(1, self.update_time)      # Every second
    
    def update_battery(self):
        """Update battery information"""
        try:
            import glob
            battery_paths = glob.glob('/sys/class/power_supply/BAT*')
            
            if not battery_paths:
                # Desktop/VM - AC power
                self.battery_icon.set_from_icon_name("ac-adapter-symbolic")
                self.battery_label.set_text("AC 电源")
                return True
            
            bat = battery_paths[0]
            
            # Read capacity
            with open(f"{bat}/capacity") as f:
                capacity = int(f.read().strip())
            
            # Read status
            with open(f"{bat}/status") as f:
                status = f.read().strip()
            
            # Choose icon based on status and capacity
            if status == "Charging":
                # For charging, use level icons (0-90), not 100
                level = self._get_battery_level(capacity)
                icon_name = f"battery-level-{level}-charging-symbolic"
                status_text = "充电中"
            elif status == "Full":
                # Only 'charged' has a 100 variant
                icon_name = "battery-level-100-charged-symbolic"
                status_text = "已充满"
            else:  # Discharging or Unknown
                level = self._get_battery_level(capacity)
                icon_name = f"battery-level-{level}-symbolic"
                status_text = ""
            
            self.battery_icon.set_from_icon_name(icon_name)
            
            text = f"{capacity}%"
            if status_text:
                text += f" {status_text}"
            self.battery_label.set_text(text)
            
        except Exception as e:
            logger.debug(f"Could not read battery status: {e}")
            self.battery_icon.set_from_icon_name("battery-missing-symbolic")
            self.battery_label.set_text("--")
        
        return True  # Continue timer
    
    def _get_battery_level(self, capacity):
        """
        Get battery level icon suffix based on capacity.
        Returns values that match available icon names: 0, 10, 20, 30, 40, 50, 60, 70, 80, 90.
        Note: Don't return "100" - it's only used for 'charged' state, not during charging.
        """
        if capacity >= 95:
            return "90"  # Max level for charging icons is 90
        elif capacity >= 85:
            return "90"
        elif capacity >= 75:
            return "80"
        elif capacity >= 65:
            return "70"
        elif capacity >= 55:
            return "60"
        elif capacity >= 45:
            return "50"
        elif capacity >= 35:
            return "40"
        elif capacity >= 25:
            return "30"
        elif capacity >= 15:
            return "20"
        elif capacity >= 5:
            return "10"
        else:
            return "0"
    
    def update_time(self):
        """Update time display"""
        from datetime import datetime
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M")
        self.time_label.set_text(time_str)
        return True  # Continue timer
    
    def toggle_theme(self, button):
        """Toggle between light and dark theme using libadwaita StyleManager"""
        self.dark_mode = not self.dark_mode
        
        # Use libadwaita StyleManager for proper theme switching
        if self.dark_mode:
            self.style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            self.style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        
        self.update_theme_icon()
        print(f"[THEME] Switched to {'dark' if self.dark_mode else 'light'} mode", flush=True)
    
    def update_theme_icon(self):
        """Update theme button icon based on current mode"""
        if self.dark_mode:
            # Dark mode - show sun icon (click to go light)
            self.theme_icon.set_from_icon_name("weather-clear-symbolic")
            self.theme_button.set_tooltip_text("切换到亮色模式")
        else:
            # Light mode - show moon icon (click to go dark)
            self.theme_icon.set_from_icon_name("weather-clear-night-symbolic")
            self.theme_button.set_tooltip_text("切换到暗色模式")


class InstallerApp(Gtk.ApplicationWindow):
    """Main installer window with page navigation"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Window setup
        self.set_title("SkorionOS Installer PoC")
        self.set_default_size(config.screen_width, config.screen_height)
        self.set_resizable(False)  # Force fixed size to maintain aspect ratio
        
        # Navigation state
        self.current_page = 0
        self.page_history = []
        
        # Data storage
        self.wifi_list = None
        self.connecting = False
        self.password_dialog = None
        self.connecting_dialog = None
        
        # Advanced options (initialized before any page)
        self.advanced_options = {
            'firmware_overrides': False,
            'cdn': False,
            'fallback_url': True,   # Default ON (recommended)
            'debug': False
        }
        self.use_advanced_options = False  # Toggle for showing advanced page
        
        # Setup keyboard/gamepad controller
        self.setup_input_controller()
        
        # Apply CSS styling
        apply_styling(config.scaled)
        
        # Create main container with status bar
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Add status bar at top
        self.status_bar = StatusBar()
        main_box.append(self.status_bar.box)
        
        # Add separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(separator)
        
        # Create page container with top margin
        self.page_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.page_container.set_vexpand(True)
        self.page_container.set_margin_top(config.scaled(20))
        main_box.append(self.page_container)
        
        # Set main container as window child
        self.set_child(main_box)
        
        # Show first page (no history for initial page)
        self.show_page(0, add_to_history=False)
        
        print("[INFO] GTK4 window created")
    
    def setup_input_controller(self):
        """Setup keyboard and gamepad input controller"""
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(controller)
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keyboard input"""
        # ESC key: go back
        if keyval == Gdk.KEY_Escape:
            print("  → Back/Cancel")
            self.go_back()
            return True
        
        return False
    
    def show_page(self, page_num, add_to_history=True):
        """Show a specific page (accepts int or string name)"""
        # Map string names to numbers
        page_map = {
            'welcome': 0,
            'network': 1,
            'disk': 2,
            'mode': 3,
            'confirm': 4,
            'bootstrap': 5,
            'version': 6,
            'advanced': 7,   # Advanced options (NEW)
            'install': 8,    # Moved from 7 to 8
            'complete': 9,   # Moved from 8 to 9
        }
        
        # Convert string to number if needed
        if isinstance(page_num, str):
            page_num = page_map.get(page_num, page_num)
        
        if add_to_history and self.current_page != page_num:
            self.page_history.append(self.current_page)
            print(f"[NAV] History: {self.page_history}")
        
        self.current_page = page_num
        print(f"[NAV] Showing page {page_num}")
        
        # Create page content
        pages = [
            self.create_welcome_page,                   # 0: Welcome
            lambda: create_network_page(self),          # 1: Network
            lambda: create_disk_page(self),             # 2: Disk selection
            lambda: create_mode_page(self),             # 3: Mode selection
            lambda: create_confirm_page(self),          # 4: Confirmation
            lambda: create_bootstrap_page(self),        # 5: Bootstrap (frzr-bootstrap)
            lambda: create_version_page(self),          # 6: Version selection
            lambda: create_advanced_options_page(self), # 7: Advanced options (NEW)
            lambda: create_install_page(self),          # 8: Installation
            lambda: self.create_complete_page(),        # 9: Complete
        ]
        
        if page_num < len(pages):
            # Remove old page content
            child = self.page_container.get_first_child()
            if child:
                self.page_container.remove(child)
            
            # Add new page content
            page_content = pages[page_num]()
            self.page_container.append(page_content)
        else:
            print(f"[ERROR] Page {page_num} does not exist")
    
    def go_back(self):
        """Go back to previous page"""
        if self.page_history:
            prev_page = self.page_history.pop()
            print(f"[NAV] Going back to page {prev_page}")
            self.show_page(prev_page, add_to_history=False)
        else:
            print("[NAV] No history, staying on current page")
    
    def restart_wizard(self):
        """Restart the wizard from the beginning"""
        print("[NAV] Restarting wizard")
        self.page_history = []
        self.show_page(0, add_to_history=False)
    
    def create_welcome_page(self):
        """Create the welcome page"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.add_css_class("page-container")
        
        # Logo/Icon
        logo = Gtk.Image.new_from_icon_name("computer-symbolic")
        logo.set_icon_size(Gtk.IconSize.LARGE)
        logo.set_pixel_size(config.scaled(128))
        box.append(logo)
        
        # Title
        title = Gtk.Label()
        title.set_markup('<span size="xx-large" weight="bold">SkorionOS 安装器</span>')
        box.append(title)
        
        # Subtitle
        subtitle = Gtk.Label()
        subtitle.set_markup(f'<span size="large">版本 {config.version}</span>')
        subtitle.add_css_class("installer-subtitle")
        box.append(subtitle)
        
        # Device info
        device_info = self.get_device_info()
        info_label = Gtk.Label()
        info_label.set_markup(f'<span foreground="#aaa">检测到设备: {device_info}</span>')
        box.append(info_label)
        
        # Test info box
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        info_box.add_css_class("info-box")
        info_box.set_size_request(config.scaled(600), -1)
        
        tests = [
            "• GTK4 窗口已创建",
            "• Gamescope 合成器正常",
            "• 输入系统已就绪",
            "• 准备进入安装流程"
        ]
        
        for test in tests:
            label = Gtk.Label(label=test)
            label.set_xalign(0)
            info_box.append(label)
        
        box.append(info_box)
        
        # Buttons (using standard button box and nav-button style)
        btn_box = UIComponents.create_button_box(spacing=20, homogeneous=True)
        
        # Exit to shell button (left side)
        exit_btn = UIComponents.create_button("打开命令行", "utilities-terminal-symbolic")
        exit_btn.connect("clicked", lambda b: sys.exit(0))
        btn_box.append(exit_btn)
        
        # Start button (right side, primary action)
        start_btn = UIComponents.create_button("开始安装", "go-next-symbolic")
        start_btn.add_css_class("suggested-action")
        start_btn.connect("clicked", lambda b: self.show_page(1))
        btn_box.append(start_btn)
        
        box.append(btn_box)
        
        return box
    
    def create_complete_page(self):
        """Create the complete page (reused instance)"""
        if not hasattr(self, '_complete_page_instance'):
            self._complete_page_instance = CompletePage(self)
        return self._complete_page_instance.create()
    
    def show_complete_page(self, status: str, summary: str = "", details: str = ""):
        """
        Show the complete page with specific status.
        
        Args:
            status: CompletePage.STATUS_SUCCESS, STATUS_CANCELLED, or STATUS_FAILED
            summary: Brief summary message
            details: Detailed information (optional)
        """
        # Store complete page state
        if not hasattr(self, '_complete_page_instance'):
            self._complete_page_instance = CompletePage(self)
        
        # Set status before showing page
        self._complete_page_instance.set_status(status, summary, details)
        
        # Show complete page (don't add to history - terminal page)
        self.show_page('complete', add_to_history=False)
    
    def get_device_info(self):
        """Get device information"""
        import subprocess
        try:
            result = subprocess.run(
                ["cat", "/sys/devices/virtual/dmi/id/product_name"],
                capture_output=True,
                text=True,
                timeout=1
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"Could not read device info: {e}")
        return "未知设备"


class InstallerApplication(Gtk.Application):
    """GTK Application wrapper"""
    
    def __init__(self):
        super().__init__(application_id='com.skorionos.installer')
    
    def do_activate(self):
        win = InstallerApp(application=self)
        win.present()


def main():
    """Main entry point"""
    print("[INFO] Starting SkorionOS Installer...")
    app = InstallerApplication()
    
    # Register cleanup function for local file manager
    def cleanup_local_files():
        """Cleanup local file manager mounts on exit"""
        if hasattr(app, 'local_file_manager'):
            print("[INFO] Cleaning up local file mounts...")
            app.local_file_manager.cleanup()
    
    atexit.register(cleanup_local_files)
    
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())

