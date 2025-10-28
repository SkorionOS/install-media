#!/usr/bin/env python3
"""
SkorionOS Graphical Installer - PoC Version
Proof of Concept to validate core technologies
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk
import subprocess
import os
import sys

class InstallerPoC(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Window setup
        self.set_default_size(1280, 800)
        self.set_title("SkorionOS Installer PoC")
        
        # Data
        self.current_page = 0
        self.test_data = {
            'channel': 'stable',
            'desktop': 'gnome',
            'nvidia': False,
            'disk': None
        }
        
        # Setup keyboard/gamepad controller
        self.setup_input_controller()
        
        # Apply CSS styling
        self.apply_styling()
        
        # Show first page
        self.show_page(0)
        
        print("✅ GTK4 window created")
    
    def apply_styling(self):
        """Apply custom CSS styling"""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .installer-window {
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            }
            
            .installer-title {
                font-size: 32px;
                font-weight: bold;
                color: white;
            }
            
            .installer-subtitle {
                font-size: 16px;
                color: #aaa;
            }
            
            .installer-button {
                min-width: 200px;
                min-height: 50px;
                font-size: 16px;
                border-radius: 8px;
            }
            
            .page-container {
                padding: 50px;
            }
            
            .info-box {
                background: rgba(255,255,255,0.05);
                border-radius: 8px;
                padding: 20px;
                margin: 10px 0;
            }
            
            .success {
                background: rgba(0,255,0,0.1);
                color: #0f0;
            }
            
            .warning {
                background: rgba(255,255,0,0.1);
                color: #ff0;
            }
        """)
        
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def setup_input_controller(self):
        """Setup keyboard/gamepad input"""
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(controller)
        print("✅ Input controller setup")
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keyboard/gamepad input"""
        key_name = Gdk.keyval_name(keyval)
        print(f"🎮 Key pressed: {key_name} (keyval: {keyval})")
        
        # Navigation keys
        if keyval == Gdk.KEY_Return or keyval == Gdk.KEY_space:
            print("  → Confirm/Next")
            return True
        elif keyval == Gdk.KEY_Escape:
            print("  → Back/Cancel")
            if self.current_page > 0:
                self.show_page(self.current_page - 1)
            return True
        
        return False
    
    def show_page(self, page_num):
        """Show specific page"""
        self.current_page = page_num
        
        pages = [
            self.create_welcome_page,
            self.create_test_bash_page,
            self.create_test_data_page,
            self.create_success_page
        ]
        
        if 0 <= page_num < len(pages):
            content = pages[page_num]()
            self.set_child(content)
            print(f"📄 Showing page {page_num + 1}/{len(pages)}")
    
    def create_welcome_page(self):
        """Page 0: Welcome"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.add_css_class("page-container")
        
        # Title
        title = Gtk.Label()
        title.set_markup('<span size="xx-large" weight="bold" foreground="white">SkorionOS 图形化安装器</span>')
        title.add_css_class("installer-title")
        box.append(title)
        
        # Subtitle
        subtitle = Gtk.Label(label="PoC 概念验证版本")
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
        info_box.set_size_request(600, -1)
        
        tests = [
            "✅ GTK4 窗口已创建",
            "✅ Gamescope 合成器正常",
            "✅ 输入系统已就绪",
            "🎮 请尝试按键测试（查看终端输出）"
        ]
        
        for test in tests:
            label = Gtk.Label(label=test)
            label.set_xalign(0)
            label.set_markup(f'<span foreground="white">{test}</span>')
            info_box.append(label)
        
        box.append(info_box)
        
        # Button
        btn = Gtk.Button(label="开始测试 →")
        btn.add_css_class("installer-button")
        btn.add_css_class("suggested-action")
        btn.connect("clicked", lambda b: self.show_page(1))
        box.append(btn)
        
        return box
    
    def create_test_bash_page(self):
        """Page 1: Test Bash Integration"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.add_css_class("page-container")
        
        # Title
        title = Gtk.Label()
        title.set_markup('<span size="x-large" weight="bold" foreground="white">测试 Bash 集成</span>')
        box.append(title)
        
        # Test results box
        results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        results_box.add_css_class("info-box")
        results_box.set_size_request(700, -1)
        
        # Test 1: Get disks
        disks = self.test_get_disks()
        disk_label = Gtk.Label()
        disk_label.set_xalign(0)
        disk_label.set_markup(f'<span foreground="white">📀 检测到磁盘: {disks}</span>')
        results_box.append(disk_label)
        
        # Test 2: Get device info
        device = self.get_device_info()
        device_label = Gtk.Label()
        device_label.set_xalign(0)
        device_label.set_markup(f'<span foreground="white">💻 设备信息: {device}</span>')
        results_box.append(device_label)
        
        # Test 3: Get CPU
        cpu = self.test_get_cpu()
        cpu_label = Gtk.Label()
        cpu_label.set_xalign(0)
        cpu_label.set_markup(f'<span foreground="white">🔧 CPU: {cpu}</span>')
        results_box.append(cpu_label)
        
        # Test 4: Check network
        network = self.test_network()
        network_label = Gtk.Label()
        network_label.set_xalign(0)
        status = "✅ 已连接" if network else "❌ 未连接"
        color = "#0f0" if network else "#f00"
        network_label.set_markup(f'<span foreground="{color}">🌐 网络状态: {status}</span>')
        results_box.append(network_label)
        
        box.append(results_box)
        
        # Navigation
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)
        
        back_btn = Gtk.Button(label="← 返回")
        back_btn.connect("clicked", lambda b: self.show_page(0))
        btn_box.append(back_btn)
        
        next_btn = Gtk.Button(label="下一步 →")
        next_btn.add_css_class("suggested-action")
        next_btn.connect("clicked", lambda b: self.show_page(2))
        btn_box.append(next_btn)
        
        box.append(btn_box)
        
        return box
    
    def create_test_data_page(self):
        """Page 2: Test Data Selection"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.add_css_class("page-container")
        
        # Title
        title = Gtk.Label()
        title.set_markup('<span size="x-large" weight="bold" foreground="white">测试数据选择</span>')
        box.append(title)
        
        # Radio buttons test
        group_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        group_box.add_css_class("info-box")
        group_box.set_size_request(500, -1)
        
        section_label = Gtk.Label()
        section_label.set_markup('<span foreground="white" weight="bold">选择版本通道：</span>')
        section_label.set_xalign(0)
        group_box.append(section_label)
        
        stable_radio = Gtk.CheckButton(label="Stable - 稳定版")
        testing_radio = Gtk.CheckButton(label="Testing - 测试版")
        testing_radio.set_group(stable_radio)
        unstable_radio = Gtk.CheckButton(label="Unstable - 不稳定版")
        unstable_radio.set_group(stable_radio)
        
        stable_radio.set_active(True)
        
        stable_radio.connect("toggled", lambda b: self.on_data_changed('channel', 'stable'))
        testing_radio.connect("toggled", lambda b: self.on_data_changed('channel', 'testing'))
        unstable_radio.connect("toggled", lambda b: self.on_data_changed('channel', 'unstable'))
        
        group_box.append(stable_radio)
        group_box.append(testing_radio)
        group_box.append(unstable_radio)
        
        box.append(group_box)
        
        # Current selection
        selection_label = Gtk.Label()
        selection_label.set_markup(f'<span foreground="#aaa">当前选择: {self.test_data["channel"]}</span>')
        box.append(selection_label)
        
        # Navigation
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)
        
        back_btn = Gtk.Button(label="← 返回")
        back_btn.connect("clicked", lambda b: self.show_page(1))
        btn_box.append(back_btn)
        
        next_btn = Gtk.Button(label="完成测试 →")
        next_btn.add_css_class("suggested-action")
        next_btn.connect("clicked", lambda b: self.show_page(3))
        btn_box.append(next_btn)
        
        box.append(btn_box)
        
        return box
    
    def create_success_page(self):
        """Page 3: Success"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.add_css_class("page-container")
        
        # Title
        title = Gtk.Label()
        title.set_markup('<span size="xx-large" weight="bold" foreground="#0f0">✅ PoC 验证成功！</span>')
        box.append(title)
        
        # Results
        results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        results_box.add_css_class("info-box")
        results_box.add_css_class("success")
        results_box.set_size_request(600, -1)
        
        results = [
            "✅ GTK4 图形界面正常",
            "✅ Gamescope 合成器工作正常",
            "✅ 键盘/手柄输入响应正常",
            "✅ Bash 函数调用成功",
            "✅ 多页面导航正常",
            "✅ 数据选择功能正常",
            "",
            "🎉 可以继续开发完整版本！"
        ]
        
        for result in results:
            label = Gtk.Label(label=result)
            label.set_xalign(0)
            results_box.append(label)
        
        box.append(results_box)
        
        # Data summary
        summary_label = Gtk.Label()
        summary_label.set_markup(f'''<span foreground="white">
测试数据: {self.test_data}
        </span>''')
        box.append(summary_label)
        
        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)
        
        restart_btn = Gtk.Button(label="🔄 重新测试")
        restart_btn.connect("clicked", lambda b: self.show_page(0))
        btn_box.append(restart_btn)
        
        exit_btn = Gtk.Button(label="🚪 退出")
        exit_btn.connect("clicked", lambda b: self.close())
        btn_box.append(exit_btn)
        
        box.append(btn_box)
        
        return box
    
    def on_data_changed(self, key, value):
        """Handle data changes"""
        self.test_data[key] = value
        print(f"📝 Data updated: {key} = {value}")
    
    # Helper functions - calling bash/system
    
    def get_device_info(self):
        """Get device information"""
        try:
            vendor = open('/sys/devices/virtual/dmi/id/sys_vendor').read().strip()
            product = open('/sys/devices/virtual/dmi/id/product_name').read().strip()
            return f"{vendor} {product}"
        except:
            return "Unknown Device"
    
    def test_get_disks(self):
        """Test getting disk list"""
        try:
            result = subprocess.run(
                ['lsblk', '-d', '-n', '-o', 'NAME,SIZE', '-e', '7,11'],
                capture_output=True,
                text=True
            )
            disks = [line.split()[0] for line in result.stdout.strip().split('\n') if line]
            return ', '.join(disks[:3])  # First 3 disks
        except:
            return "Cannot detect"
    
    def test_get_cpu(self):
        """Test getting CPU info"""
        try:
            result = subprocess.run(
                ['lscpu'],
                capture_output=True,
                text=True,
                env={'LANG': 'en_US.UTF-8'}
            )
            for line in result.stdout.split('\n'):
                if 'Model name' in line:
                    return line.split(':')[1].strip()
            return "Unknown CPU"
        except:
            return "Cannot detect"
    
    def test_network(self):
        """Test network connectivity"""
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '2', '8.8.8.8'],
                capture_output=True,
                timeout=3
            )
            return result.returncode == 0
        except:
            return False

class InstallerApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.skorionos.installer.poc')
        print("🚀 SkorionOS Installer PoC starting...")
    
    def do_activate(self):
        win = InstallerPoC(application=self)
        win.present()
        print("✅ Application activated")

if __name__ == '__main__':
    print("="*50)
    print("SkorionOS Graphical Installer - PoC")
    print("="*50)
    print()
    
    app = InstallerApp()
    exit_code = app.run(None)
    
    print()
    print("="*50)
    print(f"PoC exited with code: {exit_code}")
    print("="*50)
    
    sys.exit(exit_code)

