"""
Main installer application window
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib
import sys

from .config import config
from .ui.styling import apply_styling
from .ui.pages.network import create_network_page
from .ui.pages.disk import create_disk_page
from .ui.pages.mode import create_mode_page
from .ui.pages.confirm import create_confirm_page
from .ui.pages.bootstrap import create_bootstrap_page
from .ui.pages.version import create_version_page
from .ui.pages.install import create_install_page


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
        
        # Setup keyboard/gamepad controller
        self.setup_input_controller()
        
        # Apply CSS styling
        apply_styling(config.scaled)
        
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
            'install': 7,
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
            self.create_welcome_page,            # 0: Welcome
            lambda: create_network_page(self),   # 1: Network
            lambda: create_disk_page(self),      # 2: Disk selection
            lambda: create_mode_page(self),      # 3: Mode selection (NEW)
            lambda: create_confirm_page(self),   # 4: Confirmation
            lambda: create_bootstrap_page(self), # 5: Bootstrap (frzr-bootstrap)
            lambda: create_version_page(self),   # 6: Version selection
            lambda: create_install_page(self),   # 7: Installation
        ]
        
        if page_num < len(pages):
            page_content = pages[page_num]()
            self.set_child(page_content)
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
        title.set_markup('<span size="xx-large" weight="bold">SkorionOS 图形化安装器</span>')
        box.append(title)
        
        # Subtitle
        subtitle = Gtk.Label()
        subtitle.set_markup(f'<span size="large">版本 {config.version} PoC</span>')
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
        
        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        btn_box.set_halign(Gtk.Align.CENTER)
        
        start_btn = Gtk.Button(label="开始安装")
        start_btn.set_icon_name("go-next-symbolic")
        start_btn.add_css_class("installer-button")
        start_btn.add_css_class("suggested-action")
        start_btn.connect("clicked", lambda b: self.show_page(1))
        btn_box.append(start_btn)
        
        exit_btn = Gtk.Button(label="退出")
        exit_btn.set_icon_name("application-exit-symbolic")
        exit_btn.add_css_class("installer-button")
        exit_btn.connect("clicked", lambda b: self.close())
        btn_box.append(exit_btn)
        
        box.append(btn_box)
        
        return box
    
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
        except:
            pass
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
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())

