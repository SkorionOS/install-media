#!/usr/bin/env python3
"""
SkorionOS Graphical Installer - PoC Version
Proof of Concept to validate core technologies
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('NM', '1.0')
from gi.repository import Gtk, GLib, Gdk, NM
import subprocess
import os
import sys
import argparse

class InstallerPoC(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get window size from environment
        window_width = int(os.environ.get('INSTALLER_WIDTH', '1280'))
        window_height = int(os.environ.get('INSTALLER_HEIGHT', '800'))
        gdk_scale = os.environ.get('GDK_SCALE', '1')
        
        # Calculate UI scale factor based on screen height (base: 800p)
        # self.ui_scale = window_width / 1280
        ui_scale = os.environ.get('UI_SCALE', '1')

        self.ui_scale = float(ui_scale)
        
        print(f"[DISPLAY] GDK_SCALE: {gdk_scale}")
        print(f"[DISPLAY] Window size: {window_width}x{window_height}")
        print(f"[DISPLAY] UI scale factor: {self.ui_scale:.2f}x")

        # Window setup
        self.set_title("SkorionOS Installer PoC")
        self.set_default_size(window_width, window_height)
        self.add_css_class("installer-window")
        
        # Data
        self.current_page = 0
        self.page_history = []  # Navigation history stack
        self.wifi_list = None  # WiFi list widget
        self.connecting = False  # Connection in progress flag
        self.password_dialog = None  # Current password dialog
        self.connecting_dialog = None  # Connecting progress dialog
        self.test_data = {
            'channel': 'stable',
            'desktop': 'gnome',
            'nvidia': False,
            'disk': None,
            'network_configured': False
        }
        
        # NetworkManager client
        try:
            self.nm_client = NM.Client.new(None)
        except Exception as e:
            print(f"NetworkManager initialization failed: {e}")
            self.nm_client = None
        
        # Setup keyboard/gamepad controller
        self.setup_input_controller()
        
        # Apply CSS styling
        self.apply_styling()
        
        # Show first page (no history for initial page)
        self.show_page(0, add_to_history=False)
        
        print("[INFO] GTK4 window created")
    
    def apply_styling(self):
        """Apply custom CSS styling and dark theme"""
        # Enable dark theme globally
        settings = Gtk.Settings.get_default()
        if settings:
            settings.set_property("gtk-application-prefer-dark-theme", True)
        
        # Scaled font sizes
        font_size = self.scaled(16)
        title_size = self.scaled(32)
        subtitle_size = self.scaled(16)
        button_font_size = self.scaled(14)
        nav_button_font = self.scaled(15)
        
        # Scaled layout sizes
        button_min_width = self.scaled(200)
        button_min_height = self.scaled(50)
        small_button_height = self.scaled(36)
        nav_button_height = self.scaled(44)
        nav_button_min_width = self.scaled(120)
        
        # Scaled spacing
        padding_small = self.scaled(6)
        padding = self.scaled(10)
        padding_medium = self.scaled(20)
        padding_large = self.scaled(50)
        spacing = self.scaled(10)
        spacing_medium = self.scaled(24)
        
        # Scaled borders
        border_radius_small = self.scaled(4)
        border_radius = self.scaled(6)
        border_radius_large = self.scaled(8)
        
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(f"""
            .installer-window {{
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: #e0e0e0;
            }}
            
            .installer-window label {{
                color: #e0e0e0;
                font-size: {font_size}px;
            }}
            
            .installer-window image {{
                color: #e0e0e0;
                -gtk-icon-size: {self.scaled(16)}px;
            }}
            
            /* Dialog styling */
            dialog {{
                background: #2b2b2b;
                color: #e0e0e0;
            }}
            
            dialog .dialog-content-area {{
                background: #2b2b2b;
            }}
            
            dialog label {{
                color: #e0e0e0;
                font-size: {font_size}px;
            }}
            
            dialog entry {{
                background: #3a3a3a;
                color: white;
                border: 1px solid #555;
                border-radius: {border_radius}px;
                padding: {padding}px;
                font-size: {font_size}px;
            }}
            
            .password-title {{
                font-size: {self.scaled(20)}px;
                font-weight: bold;
                color: #e0e0e0;
            }}
            
            /* Dialog action area (bottom buttons) */
            dialog .dialog-action-area {{
                padding: {padding_medium}px;
            }}
            
            dialog .dialog-action-area button {{
                min-height: {nav_button_height}px;
                min-width: {nav_button_min_width}px;
                margin-left: {self.scaled(8)}px;
                margin-right: {self.scaled(8)}px;
                padding: {padding}px {spacing_medium}px;
                font-size: {nav_button_font}px;
            }}
            
            dialog .dialog-action-area button:first-child {{
                margin-left: 0;
            }}
            
            dialog .dialog-action-area button:last-child {{
                margin-right: 0;
            }}
            
            .installer-title {{
                font-size: {title_size}px;
                font-weight: bold;
                color: white;
            }}
            
            .installer-subtitle {{
                font-size: {subtitle_size}px;
                color: #bbb;
            }}
            
            .installer-button {{
                min-width: {button_min_width}px;
                min-height: {button_min_height}px;
                font-size: {font_size}px;
                border-radius: {border_radius_large}px;
                -gtk-icon-size: {self.scaled(24)}px;
            }}
            
            .installer-button image {{
                -gtk-icon-size: {self.scaled(24)}px;
            }}
            
            button {{
                background: rgba(255,255,255,0.15);
                color: #e0e0e0;
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: {border_radius}px;
                padding: {padding_small}px {self.scaled(12)}px;
                min-height: {small_button_height}px;
                font-size: {button_font_size}px;
                -gtk-icon-size: {self.scaled(16)}px;
            }}
            
            button:hover {{
                background: rgba(255,255,255,0.25);
                border-color: rgba(255,255,255,0.3);
            }}
            
            button image {{
                color: #e0e0e0;
                -gtk-icon-size: {self.scaled(16)}px;
            }}
            
            button.suggested-action {{
                background: rgba(52, 152, 219, 0.8);
                color: white;
                border-color: rgba(52, 152, 219, 1);
            }}
            
            button.suggested-action:hover {{
                background: rgba(52, 152, 219, 1);
            }}
            
            button.suggested-action image {{
                color: white;
            }}
            
            /* Larger nav buttons at page bottom */
            button.nav-button {{
                min-height: {nav_button_height}px;
                padding: {padding}px 24px;
                font-size: {nav_button_font}px;
                -gtk-icon-size: {self.scaled(20)}px;
            }}
            
            button.nav-button image {{
                -gtk-icon-size: {self.scaled(20)}px;
            }}
            
            /* Virtual keyboard buttons - size controlled by Python code */
            .keyboard-key {{
                background: #505050;
                color: white;
                border: 1px solid #707070;
                border-radius: {border_radius_small}px;
                font-size: {font_size}px;
                font-weight: bold;
                padding: 0;
            }}
            
            .keyboard-key:hover {{
                background: #606060;
                border-color: #808080;
            }}
            
            .keyboard-key:active {{
                background: #404040;
            }}
            
            .page-container {{
                padding: {padding_large}px;
            }}
            
            .info-box {{
                background: rgba(255,255,255,0.05);
                border-radius: {border_radius_large}px;
                padding: {padding_medium}px;
                margin: {padding}px 0;
                color: #e0e0e0;
            }}
            
            .info-box label {{
                color: #e0e0e0;
                font-size: {font_size}px;
            }}
            
            .wifi-row {{
                padding: {padding}px;
                border-radius: {border_radius}px;
            }}
            
            .wifi-row:hover {{
                background: rgba(255,255,255,0.1);
            }}
            
            .wifi-row image {{
                -gtk-icon-size: {self.scaled(16)}px;
            }}
            
            .success {{
                background: rgba(0,255,0,0.1);
                color: #0f0;
            }}
            
            .warning {{
                background: rgba(255,255,0,0.1);
                color: #ff0;
            }}
        """.encode())
        
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
        print("[INFO] Input controller setup")
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keyboard/gamepad input"""
        key_name = Gdk.keyval_name(keyval)
        print(f"[INPUT] Key pressed: {key_name} (keyval: {keyval})")
        
        # Navigation keys
        if keyval == Gdk.KEY_Return or keyval == Gdk.KEY_space:
            print("  → Confirm/Next")
            return True
        elif keyval == Gdk.KEY_Escape:
            print("  → Back/Cancel")
            self.go_back()
            return True
        
        return False
    
    def scaled(self, value):
        """Apply UI scale to a value"""
        return int(value * self.ui_scale)
    
    def create_icon_label_box(self, icon_name, text, icon_size=Gtk.IconSize.NORMAL):
        """Create a box with icon and label"""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        # Icon
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_icon_size(icon_size)
        box.append(icon)
        
        # Label
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.set_hexpand(True)
        box.append(label)
        
        return box
    
    def show_page(self, page_num, add_to_history=True):
        """Show specific page with navigation history support"""
        # Add current page to history before navigating
        if add_to_history and self.current_page != page_num:
            # Avoid duplicate entries
            if len(self.page_history) == 0 or self.page_history[-1] != self.current_page:
                self.page_history.append(self.current_page)
                print(f"[NAV] History: {self.page_history}")
        
        self.current_page = page_num
        
        pages = [
            self.create_welcome_page,
            self.create_network_page,
            self.create_test_bash_page,
            self.create_test_data_page,
            self.create_success_page
        ]
        
        if 0 <= page_num < len(pages):
            content = pages[page_num]()
            self.set_child(content)
            print(f"[PAGE] Showing page {page_num + 1}/{len(pages)}")
    
    def go_back(self):
        """Go back to previous page using navigation history"""
        if len(self.page_history) > 0:
            previous_page = self.page_history.pop()
            print(f"[NAV] Going back to page {previous_page + 1}")
            print(f"[NAV] History after pop: {self.page_history}")
            self.show_page(previous_page, add_to_history=False)
        else:
            # No history, just go to previous page number
            print("[NAV] No history, going to previous page number")
            if self.current_page > 0:
                self.show_page(self.current_page - 1, add_to_history=False)
    
    def restart_wizard(self):
        """Restart the wizard from the beginning"""
        print("[NAV] Restarting wizard, clearing history")
        self.page_history.clear()
        self.show_page(0, add_to_history=False)
    
    def create_welcome_page(self):
        """Page 0: Welcome"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.add_css_class("page-container")
        
        # Logo/Icon
        logo = Gtk.Image.new_from_icon_name("computer-symbolic")
        logo.set_icon_size(Gtk.IconSize.LARGE)
        logo.set_pixel_size(self.scaled(128))
        box.append(logo)
        
        # Title
        title = Gtk.Label()
        title.set_markup('<span size="xx-large" weight="bold">SkorionOS 图形化安装器</span>')
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
        info_box.set_size_request(self.scaled(600), -1)
        
        tests = [
            "• GTK4 窗口已创建",
            "• Gamescope 合成器正常",
            "• 输入系统已就绪",
        ]
        
        for test in tests:
            label = Gtk.Label(label=test)
            label.set_xalign(0)
            info_box.append(label)
        
        # Gamepad hint with icon
        gamepad_box = self.create_icon_label_box(
            "input-gaming-symbolic",
            "请尝试按键测试（查看终端输出）"
        )
        info_box.append(gamepad_box)
        
        box.append(info_box)
        
        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        btn_box.set_halign(Gtk.Align.CENTER)
        
        start_btn = Gtk.Button(label="开始测试")
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
    
    def create_network_page(self):
        """Page 1: Network Connection"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.FILL)
        box.set_valign(Gtk.Align.FILL)
        box.set_margin_start(self.scaled(50))
        box.set_margin_end(self.scaled(50))
        box.set_margin_top(self.scaled(20))
        box.set_margin_bottom(self.scaled(20))
        
        # Title with icon
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title_box.set_halign(Gtk.Align.CENTER)
        
        network_icon = Gtk.Image.new_from_icon_name("network-wireless-symbolic")
        network_icon.set_icon_size(Gtk.IconSize.LARGE)
        network_icon.set_pixel_size(self.scaled(48))
        title_box.append(network_icon)
        
        title = Gtk.Label()
        title.set_markup('<span size="x-large" weight="bold">网络连接</span>')
        title_box.append(title)
        
        box.append(title_box)
        
        # Check current network status
        is_online = self.test_network()
        
        # Always create WiFi list widget
        self.wifi_list = Gtk.ListBox()
        self.wifi_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.wifi_list.add_css_class("info-box")
        
        if is_online:
            status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            status_box.add_css_class("info-box")
            status_box.add_css_class("success")
            status_box.set_size_request(self.scaled(600), -1)
            
            connected_box = self.create_icon_label_box(
                "radio-checked-symbolic",
                "网络已连接，可以继续安装"
            )
            status_box.append(connected_box)
            
            box.append(status_box)
        
        # Always show WiFi list for reselection
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_size_request(self.scaled(700), self.scaled(300))
        scroll.set_child(self.wifi_list)
        box.append(scroll)
        
        # Scan networks
        self.scan_networks()
        
        # Navigation buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(self.scaled(20))
        
        back_btn = Gtk.Button(label="返回")
        back_btn.set_icon_name("go-previous-symbolic")
        back_btn.add_css_class("nav-button")
        back_btn.connect("clicked", lambda b: self.go_back())
        btn_box.append(back_btn)
        
        # Always show refresh and connect buttons
        refresh_btn = Gtk.Button(label="刷新")
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.add_css_class("nav-button")
        refresh_btn.connect("clicked", lambda b: self.show_page(1, add_to_history=False))
        btn_box.append(refresh_btn)
        
        # Check if currently connected to WiFi
        connected_wifi = self.get_connected_wifi_ssid()
        
        connect_btn = Gtk.Button(label="连接" if not is_online else "重新连接")
        connect_btn.set_icon_name("network-wireless-symbolic")
        connect_btn.add_css_class("suggested-action")
        connect_btn.add_css_class("nav-button")
        connect_btn.connect("clicked", lambda b: self.on_wifi_connect())
        btn_box.append(connect_btn)
        
        # Add disconnect button if connected to WiFi
        if connected_wifi:
            disconnect_btn = Gtk.Button(label="断开连接")
            disconnect_btn.set_icon_name("network-wireless-offline-symbolic")
            disconnect_btn.add_css_class("destructive-action")
            disconnect_btn.add_css_class("nav-button")
            disconnect_btn.connect("clicked", lambda b: self.on_wifi_disconnect())
            btn_box.append(disconnect_btn)
        
        skip_btn = Gtk.Button(label="跳过" if not is_online else "下一步")
        skip_btn.set_icon_name("go-next-symbolic")
        skip_btn.add_css_class("nav-button")
        skip_btn.connect("clicked", lambda b: self.show_page(2))
        btn_box.append(skip_btn)
        
        box.append(btn_box)
        
        return box
    
    def scan_networks(self):
        """Scan for available WiFi networks"""
        if not self.nm_client:
            self.add_no_nm_row()
            return
        
        # Clear existing list and clean up references
        while True:
            row = self.wifi_list.get_row_at_index(0)
            if row is None:
                break
            # Clean up AP reference to avoid memory leaks
            if hasattr(row, 'ap'):
                delattr(row, 'ap')
            if hasattr(row, 'ssid'):
                delattr(row, 'ssid')
            self.wifi_list.remove(row)
        
        # Get WiFi device
        wifi_device = None
        for device in self.nm_client.get_devices():
            if device.get_device_type() == NM.DeviceType.WIFI:
                wifi_device = device
                break
        
        if not wifi_device:
            self.add_no_wifi_row()
            return
        
        # Request scan
        try:
            wifi_device.request_scan_async(None, None, None)
        except Exception as e:
            print(f"⚠️  WiFi scan request failed: {e}")
        
        # Get access points
        access_points = wifi_device.get_access_points()
        
        if not access_points:
            self.add_no_networks_row()
            return
        
        # Sort by signal strength
        access_points = sorted(
            access_points,
            key=lambda ap: ap.get_strength(),
            reverse=True
        )
        
        # Deduplicate by SSID
        seen_ssids = set()
        for ap in access_points:
            ssid_bytes = ap.get_ssid()
            if not ssid_bytes:
                continue
            
            # Safely convert SSID to UTF-8
            try:
                ssid = NM.utils_ssid_to_utf8(ssid_bytes.get_data())
            except Exception as e:
                print(f"⚠️  Invalid SSID encoding: {e}")
                ssid = f"<Hidden Network {len(seen_ssids) + 1}>"
            
            if ssid in seen_ssids:
                continue
            seen_ssids.add(ssid)
            
            self.add_wifi_row(ap, ssid)
        
        # Check ethernet
        self.check_ethernet()
    
    def add_wifi_row(self, ap, ssid):
        """Add a WiFi network row"""
        row = Gtk.ListBoxRow()
        row.add_css_class("wifi-row")
        
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.set_margin_top(self.scaled(10))
        hbox.set_margin_bottom(self.scaled(10))
        hbox.set_margin_start(self.scaled(10))
        hbox.set_margin_end(self.scaled(10))
        
        # Check if this network is currently connected
        is_connected = self.is_wifi_connected(ssid)
        
        # Connected indicator at the front (or placeholder for alignment)
        if is_connected:
            connected_icon = Gtk.Image.new_from_icon_name("radio-checked-symbolic")
            connected_icon.set_icon_size(Gtk.IconSize.NORMAL)
            hbox.append(connected_icon)
        else:
            # Empty placeholder to keep alignment
            placeholder = Gtk.Box()
            placeholder.set_size_request(self.scaled(16), self.scaled(16))
            hbox.append(placeholder)
        
        # Security icon
        flags = ap.get_wpa_flags() | ap.get_rsn_flags()
        if flags != 0:  # Check if network has encryption
            icon_name = "network-wireless-encrypted-symbolic"
        else:
            icon_name = "network-wireless-symbolic"
        
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_icon_size(Gtk.IconSize.NORMAL)
        hbox.append(icon)
        
        # SSID
        ssid_label = Gtk.Label(label=ssid)
        ssid_label.set_xalign(0)
        ssid_label.set_hexpand(True)
        hbox.append(ssid_label)
        
        # Signal strength icon
        strength = ap.get_strength()
        signal_icon_name = self.get_signal_icon(strength)
        signal_image = Gtk.Image.new_from_icon_name(signal_icon_name)
        signal_image.set_icon_size(Gtk.IconSize.NORMAL)
        hbox.append(signal_image)
        
        # Frequency
        freq = ap.get_frequency()
        freq_label = Gtk.Label(label="5G" if freq > 5000 else "2.4G")
        freq_label.set_width_chars(5)
        hbox.append(freq_label)
        
        row.set_child(hbox)
        row.ap = ap
        row.ssid = ssid
        self.wifi_list.append(row)
    
    def get_signal_icon(self, strength):
        """Get signal strength icon name"""
        if strength > 75:
            return "network-wireless-signal-excellent-symbolic"
        elif strength > 50:
            return "network-wireless-signal-good-symbolic"
        elif strength > 25:
            return "network-wireless-signal-ok-symbolic"
        else:
            return "network-wireless-signal-weak-symbolic"
    
    def get_connected_wifi_ssid(self):
        """Get the SSID of currently connected WiFi, or None if not connected"""
        if not self.nm_client:
            return None
        
        try:
            active_connections = self.nm_client.get_active_connections()
            for conn in active_connections:
                if conn.get_connection_type() == "802-11-wireless":
                    # Get the SSID of the active connection
                    devices = conn.get_devices()
                    if devices:
                        device = devices[0]
                        if hasattr(device, 'get_active_access_point'):
                            active_ap = device.get_active_access_point()
                            if active_ap:
                                active_ssid_bytes = active_ap.get_ssid()
                                if active_ssid_bytes:
                                    try:
                                        active_ssid = active_ssid_bytes.get_data().decode('utf-8')
                                        return active_ssid
                                    except:
                                        pass
        except Exception as e:
            print(f"[ERROR] Failed to get connected WiFi: {e}")
        
        return None
    
    def is_wifi_connected(self, ssid):
        """Check if a specific WiFi network is currently connected"""
        connected_ssid = self.get_connected_wifi_ssid()
        return connected_ssid == ssid if connected_ssid else False
    
    def check_ethernet(self):
        """Check ethernet connections"""
        if not self.nm_client:
            return
        
        for device in self.nm_client.get_devices():
            if device.get_device_type() == NM.DeviceType.ETHERNET:
                if device.get_state() == NM.DeviceState.ACTIVATED:
                    self.add_ethernet_row(device)
    
    def add_ethernet_row(self, device):
        """Add ethernet connection row"""
        row = Gtk.ListBoxRow()
        row.set_sensitive(False)
        row.add_css_class("wifi-row")
        
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.set_margin_top(self.scaled(10))
        hbox.set_margin_bottom(self.scaled(10))
        hbox.set_margin_start(self.scaled(10))
        hbox.set_margin_end(self.scaled(10))
        
        icon = Gtk.Image.new_from_icon_name("network-wired-symbolic")
        icon.set_icon_size(Gtk.IconSize.NORMAL)
        hbox.append(icon)
        
        label = Gtk.Label()
        label.set_markup(f'<span foreground="green">有线连接 ({device.get_iface()}) - 已连接</span>')
        label.set_xalign(0)
        label.set_hexpand(True)
        hbox.append(label)
        
        ok_icon = Gtk.Image.new_from_icon_name("radio-checked-symbolic")
        ok_icon.set_icon_size(Gtk.IconSize.NORMAL)
        hbox.append(ok_icon)
        
        row.set_child(hbox)
        self.wifi_list.append(row)
    
    def add_no_wifi_row(self):
        """Add row when no WiFi device found"""
        row = Gtk.ListBoxRow()
        row.set_sensitive(False)
        
        box = self.create_icon_label_box(
            "dialog-warning-symbolic",
            "未检测到 WiFi 设备"
        )
        box.set_margin_top(self.scaled(10))
        box.set_margin_bottom(self.scaled(10))
        
        row.set_child(box)
        self.wifi_list.append(row)
    
    def add_no_nm_row(self):
        """Add row when NetworkManager not available"""
        row = Gtk.ListBoxRow()
        row.set_sensitive(False)
        
        box = self.create_icon_label_box(
            "dialog-error-symbolic",
            "NetworkManager 不可用"
        )
        box.set_margin_top(self.scaled(10))
        box.set_margin_bottom(self.scaled(10))
        
        row.set_child(box)
        self.wifi_list.append(row)
    
    def add_no_networks_row(self):
        """Add row when no networks found"""
        row = Gtk.ListBoxRow()
        row.set_sensitive(False)
        
        box = self.create_icon_label_box(
            "radio-checked-symbolic",
            "未找到可用网络，请刷新重试"
        )
        box.set_margin_top(self.scaled(10))
        box.set_margin_bottom(self.scaled(10))
        
        row.set_child(box)
        self.wifi_list.append(row)
    
    def on_wifi_connect(self):
        """Handle WiFi connect button"""
        print("[INFO] WiFi connect button clicked")
        # Prevent multiple connection attempts
        if self.connecting:
            print("⚠️  Connection already in progress")
            return
        
        row = self.wifi_list.get_selected_row()
        if not row or not hasattr(row, 'ap'):
            print("⚠️  No network selected")
            return
        
        ap = row.ap
        ssid = row.ssid
        print(f"[INFO] Selected network: {ssid}")
        
        # Check if network needs password
        flags = ap.get_wpa_flags() | ap.get_rsn_flags()
        print(f"[INFO] Network encryption flags: {flags}")
        if flags != 0:  # Check if network has encryption
            print("[INFO] Network requires password, showing dialog")
            self.show_password_dialog(ap, ssid)
        else:
            print("[INFO] Network is open, connecting directly")
            self.connect_to_network(ap, ssid, None)
    
    def on_wifi_disconnect(self):
        """Handle WiFi disconnect button"""
        print("[INFO] WiFi disconnect button clicked")
        
        if not self.nm_client:
            print("[ERROR] NetworkManager client not available")
            return
        
        # Get currently connected WiFi
        connected_ssid = self.get_connected_wifi_ssid()
        if not connected_ssid:
            print("[WARN] No WiFi connection to disconnect")
            return
        
        print(f"[INFO] Disconnecting from: {connected_ssid}")
        
        # Find and deactivate the active WiFi connection
        try:
            active_connections = self.nm_client.get_active_connections()
            for conn in active_connections:
                if conn.get_connection_type() == "802-11-wireless":
                    print(f"[INFO] Deactivating connection: {conn.get_id()}")
                    self.nm_client.deactivate_connection_async(
                        conn, None,
                        self.on_disconnection_complete, connected_ssid
                    )
                    return
        except Exception as e:
            print(f"[ERROR] Failed to disconnect: {e}")
    
    def on_disconnection_complete(self, client, result, ssid):
        """Handle disconnection result"""
        try:
            success = client.deactivate_connection_finish(result)
            if success:
                print(f"[NETWORK] Disconnected from {ssid}")
                self.test_data['network_configured'] = False
                
                # Refresh network page after a short delay to ensure state is updated
                def refresh_network_page():
                    if self.current_page == 1:
                        print(f"[NETWORK] Refreshing network page after disconnect")
                        self.show_page(1, add_to_history=False)
                    return False  # Don't repeat
                
                GLib.timeout_add(500, refresh_network_page)  # 0.5 second delay
            else:
                print(f"[ERROR] Failed to disconnect from {ssid}")
        except Exception as e:
            print(f"[ERROR] Disconnection error: {e}")
    
    def show_password_dialog(self, ap, ssid):
        """Show password input dialog with virtual keyboard"""
        # Prevent multiple dialogs
        if self.password_dialog is not None:
            print("⚠️  Password dialog already open")
            return
        
        print(f"[INFO] Showing password dialog for: {ssid}")
        
        # Create dialog (scaled 16:10 ratio)
        dialog = Gtk.Dialog(title=f"连接到: {ssid}")
        dialog.set_transient_for(self)
        dialog.set_modal(True)
        dialog.set_default_size(self.scaled(960), self.scaled(600))
        self.password_dialog = dialog
        
        # Content area
        content = dialog.get_content_area()
        content.set_margin_top(self.scaled(20))
        content.set_margin_bottom(self.scaled(20))
        content.set_margin_start(self.scaled(20))
        content.set_margin_end(self.scaled(20))
        content.set_spacing(self.scaled(20))
        
        # Network info with icon
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        info_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("network-wireless-encrypted-symbolic")
        icon.set_pixel_size(self.scaled(32))
        info_box.append(icon)
        
        ssid_label = Gtk.Label(label=ssid)
        ssid_label.add_css_class("password-title")
        info_box.append(ssid_label)
        
        content.append(info_box)
        
        # Password entry with show/hide toggle
        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        entry.set_placeholder_text("输入WiFi密码")
        entry.set_size_request(-1, 45)
        entry.set_hexpand(True)
        entry_box.append(entry)
        
        # Show/hide password toggle button
        self.password_visible = False
        toggle_btn = Gtk.Button()
        toggle_btn.set_icon_name("view-conceal-symbolic")
        toggle_btn.set_size_request(self.scaled(45), self.scaled(45))
        toggle_btn.set_tooltip_text("显示/隐藏密码")
        toggle_btn.connect("clicked", lambda b: self.toggle_password_visibility(entry, b))
        entry_box.append(toggle_btn)
        
        content.append(entry_box)
        
        # Status label (for connection feedback)
        status_label = Gtk.Label()
        status_label.set_wrap(True)
        status_label.set_justify(Gtk.Justification.CENTER)
        status_label.set_visible(False)  # Hidden by default
        content.append(status_label)
        dialog.status_label = status_label  # Store reference
        
        # Spinner for connecting state
        spinner = Gtk.Spinner()
        spinner.set_size_request(self.scaled(32), self.scaled(32))
        spinner.set_halign(Gtk.Align.CENTER)
        spinner.set_visible(False)
        content.append(spinner)
        dialog.spinner = spinner  # Store reference
        
        # Virtual keyboard (pass dialog for Enter key)
        keyboard = self.create_virtual_keyboard(entry, dialog)
        content.append(keyboard)
        dialog.keyboard = keyboard  # Store reference
        
        # Dialog buttons
        cancel_btn = dialog.add_button("取消", Gtk.ResponseType.CANCEL)
        connect_btn = dialog.add_button("连接", Gtk.ResponseType.OK)
        
        # Apply styling to buttons - make them wider
        cancel_btn.set_size_request(self.scaled(150), self.scaled(44))
        cancel_btn.set_margin_end(self.scaled(8))
        
        connect_btn.set_size_request(self.scaled(150), self.scaled(44))
        connect_btn.set_margin_start(self.scaled(8))
        connect_btn.set_margin_end(self.scaled(30))
        connect_btn.add_css_class("suggested-action")
        
        # Store button references for later access
        dialog.cancel_btn = cancel_btn
        dialog.connect_btn = connect_btn
        
        # Handle response
        dialog.connect("response", lambda d, r: self.on_password_response(d, r, ap, ssid, entry))
        
        dialog.present()
        print("[INFO] Password dialog presented")
    
    def create_virtual_keyboard(self, entry, dialog=None):
        """Create virtual keyboard for password input"""
        # Keyboard button size configuration with auto scaling
        self.key_size = self.scaled(48)
        self.key_height = self.scaled(48)
        self.key_spacing = self.scaled(4)
        
        # Create a container for keyboard
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.key_spacing)
        container.set_halign(Gtk.Align.CENTER)
        
        # Keyboard state and letter buttons list
        self.keyboard_shift = False
        self.caps_lock = False
        self.keyboard_symbol_mode = False  # False = letters, True = symbols
        self.keyboard_letter_btns = []
        
        # Create letter keyboard
        self.letter_keyboard = self.create_letter_keyboard(entry, dialog)
        # Create symbol keyboard
        self.symbol_keyboard = self.create_symbol_keyboard(entry)
        
        # Show letter keyboard by default
        container.append(self.letter_keyboard)
        self.current_keyboard_container = container
        
        return container
    
    def create_letter_keyboard(self, entry, dialog=None):
        """Create letter keyboard layout"""
        keyboard = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.key_spacing)
        keyboard.set_halign(Gtk.Align.CENTER)
        
        # Define keyboard layout: (label, units, callback)
        # units: -1 means expand/fill, positive number means fixed units
        layout = [
            # Row 1: Numbers + Backspace
            [
                ('1', 1), ('2', 1), ('3', 1), ('4', 1), ('5', 1),
                ('6', 1), ('7', 1), ('8', 1), ('9', 1), ('0', 1),
                ('←', 2, 'backspace'),
            ],
            # Row 2: Q-P
            [
                ('', 0.5), ('q', 1), ('w', 1), ('e', 1), ('r', 1), ('t', 1),
                ('y', 1), ('u', 1), ('i', 1), ('o', 1), ('p', 1), ('|', 1)
            ],
            # Row 3: Caps + A-L + Backspace
            [
                ('⇪', 1, 'caps'),
                ('a', 1), ('s', 1), ('d', 1), ('f', 1), ('g', 1),
                ('h', 1), ('j', 1), ('k', 1), ('l', 1),
                ('↵', -1, 'enter')
            ],
            # Row 4: Shift + Z-M + Enter
            [
                ('⇧', 1.5, 'shift'),
                ('z', 1), ('x', 1), ('c', 1), ('v', 1),
                ('b', 1), ('n', 1), ('m', 1),
                ('<', 1), ('>', 1), ('/', -1),
            ],
            # Row 5: Symbol + Space + Clear
            [
                ('?123', -1, 'symbol'),
                ('空格', 6, 'space'),
                ('清空', -1, 'clear'),
            ],
        ]
        
        for row_index, row_layout in enumerate(layout):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=self.key_spacing)
            
            for item in row_layout:
                label = item[0]
                units = item[1]
                action = item[2] if len(item) > 2 else None
                
                # Check if it's a spacer (empty label)
                is_spacer = (label == '' or label is None)
                
                if is_spacer:
                    # Create invisible spacer
                    spacer = Gtk.Box()
                    # Width includes spacing: units * key_size + (units-1) * spacing
                    if units > 0:
                        spacer_width = int(self.key_size * units + self.key_spacing * (units - 1))
                        spacer.set_size_request(spacer_width, self.key_height)
                    row.append(spacer)
                    continue
                
                btn = Gtk.Button(label=label)
                btn.add_css_class("keyboard-key")
                
                # Set button width based on units
                if units == -1:
                    # Expand to fill
                    btn.set_hexpand(True)
                    btn.set_size_request(-1, self.key_height)
                else:
                    # Fixed units: width includes spacing
                    # Formula: units * key_size + (units-1) * spacing
                    width = int(self.key_size * units + self.key_spacing * (units - 1))
                    btn.set_size_request(width, self.key_height)
                
                # Connect actions
                if action == 'backspace':
                    btn.connect("clicked", lambda b: self.on_keyboard_backspace(entry))
                elif action == 'caps':
                    self.caps_btn = btn
                    btn.connect("clicked", lambda b: self.on_keyboard_caps())
                elif action == 'shift':
                    self.shift_btn = btn
                    btn.connect("clicked", lambda b: self.on_keyboard_shift())
                elif action == 'enter':
                    if dialog:
                        btn.connect("clicked", lambda b: dialog.response(Gtk.ResponseType.OK))
                elif action == 'symbol':
                    btn.connect("clicked", lambda b: self.switch_keyboard_mode(entry))
                elif action == 'space':
                    btn.connect("clicked", lambda b: self.on_keyboard_key(entry, ' '))
                elif action == 'clear':
                    btn.connect("clicked", lambda b: entry.set_text(""))
                else:
                    # Regular letter/number key
                    btn.char = label
                    btn.connect("clicked", lambda b, l=label: self.on_keyboard_key(entry, l))
                    if label.isalpha():
                        self.keyboard_letter_btns.append(btn)
                
                row.append(btn)
            
            keyboard.append(row)
        
        return keyboard
    
    def create_symbol_keyboard(self, entry):
        """Create symbol keyboard layout"""
        keyboard = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.key_spacing)
        keyboard.set_halign(Gtk.Align.CENTER)
        
        # Define symbol keyboard layout
        layout = [
            # Row 1: Symbols + Backspace
            [
                ('!', 1), ('@', 1), ('#', 1), ('$', 1), ('%', 1),
                ('^', 1), ('&', 1), ('*', 1), ('(', 1), (')', 1),
                ('←', 2, 'backspace'),
            ],
            # Row 2: More symbols
            [
                ('', 0.5),
                ('+', 1), ('=', 1), ('<', 1), ('>', 1), ('?', 1),
                ('/', 1), ('\\', 1), ('|', 1), ('_', 1), ('-', 1),
            ],
            # Row 3: Even more symbols
            [
                ('', 1),
                (':', 1), (';', 1), ("'", 1), ('"', 1), (',', 1),
                ('.', 1), ('[', 1), (']', 1), ('{', 1), ('}', 1),
            ],
            # Row 4: Special symbols + Backspace
            [
                ('', 0.5),
                ('~', 1), ('`', 1), ('€', 1), ('£', 1), ('¥', 1),
                ('§', 1), ('©', 1), ('®', 1), ('™', 1),
                ('←', -1, 'backspace'),
            ],
            # Row 5: ABC + Space + Clear
            [
                ('ABC', -1, 'letter'),
                ('空格', 6, 'space'),
                ('清空', -1, 'clear'),
            ],
        ]
        
        for row_index, row_layout in enumerate(layout):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=self.key_spacing)
            
            for item in row_layout:
                label = item[0]
                units = item[1]
                action = item[2] if len(item) > 2 else None
                
                # Check if it's a spacer
                is_spacer = (label == '' or label is None)
                
                if is_spacer:
                    # Create invisible spacer
                    spacer = Gtk.Box()
                    if units > 0:
                        spacer_width = int(self.key_size * units + self.key_spacing * (units - 1))
                        spacer.set_size_request(spacer_width, self.key_height)
                    row.append(spacer)
                    continue
                
                btn = Gtk.Button(label=label)
                btn.add_css_class("keyboard-key")
                
                # Set button width
                if units == -1:
                    btn.set_hexpand(True)
                    btn.set_size_request(-1, self.key_height)
                else:
                    width = int(self.key_size * units + self.key_spacing * (units - 1))
                    btn.set_size_request(width, self.key_height)
                
                # Connect actions
                if action == 'backspace':
                    btn.connect("clicked", lambda b: self.on_keyboard_backspace(entry))
                elif action == 'letter':
                    btn.connect("clicked", lambda b: self.switch_keyboard_mode(entry))
                elif action == 'space':
                    btn.connect("clicked", lambda b: self.on_keyboard_key(entry, ' '))
                elif action == 'clear':
                    btn.connect("clicked", lambda b: entry.set_text(""))
                else:
                    # Regular symbol key
                    btn.char = label
                    btn.connect("clicked", lambda b, l=label: self.on_keyboard_key(entry, l))
                
                row.append(btn)
            
            keyboard.append(row)
        
        return keyboard
    
    def switch_keyboard_mode(self, entry):
        """Switch between letter and symbol keyboard"""
        self.keyboard_symbol_mode = not self.keyboard_symbol_mode
        
        # Remove current keyboard
        child = self.current_keyboard_container.get_first_child()
        if child:
            self.current_keyboard_container.remove(child)
        
        # Add the other keyboard
        if self.keyboard_symbol_mode:
            self.current_keyboard_container.append(self.symbol_keyboard)
        else:
            self.current_keyboard_container.append(self.letter_keyboard)
    
    def create_keyboard_button(self, char, entry, units=1):
        """Create a keyboard button with specified units"""
        btn = Gtk.Button(label=char)
        btn.add_css_class("keyboard-key")
        # Width includes spacing: units * key_size + (units-1) * spacing
        width = int(self.key_size * units + self.key_spacing * (units - 1))
        btn.set_size_request(width, self.key_height)
        btn.char = char  # Store original char
        btn.connect("clicked", lambda b: self.on_keyboard_key(entry, b.get_label()))
        return btn
    
    def on_keyboard_key(self, entry, char):
        """Handle keyboard key press"""
        current = entry.get_text()
        # Apply shift or caps lock for letters
        if (self.keyboard_shift or self.caps_lock) and char.isalpha():
            char = char.upper()
        entry.set_text(current + char)
        # Reset shift after letter input (but not caps lock)
        if self.keyboard_shift and char.isalpha():
            self.on_keyboard_shift()
    
    def on_keyboard_backspace(self, entry):
        """Handle backspace"""
        current = entry.get_text()
        if current:
            entry.set_text(current[:-1])
    
    def on_keyboard_shift(self):
        """Toggle shift state"""
        self.keyboard_shift = not self.keyboard_shift
        
        if self.keyboard_shift:
            self.shift_btn.add_css_class("suggested-action")
        else:
            self.shift_btn.remove_css_class("suggested-action")
        
        # Update all letter buttons
        self.update_letter_case()
    
    def on_keyboard_caps(self):
        """Toggle caps lock state"""
        self.caps_lock = not self.caps_lock
        
        if self.caps_lock:
            self.caps_btn.add_css_class("suggested-action")
        else:
            self.caps_btn.remove_css_class("suggested-action")
        
        # Update all letter buttons
        self.update_letter_case()
    
    def update_letter_case(self):
        """Update all letter buttons based on shift/caps state"""
        for btn in self.keyboard_letter_btns:
            current_label = btn.get_label()
            # Show uppercase if either shift OR caps is active
            if self.keyboard_shift or self.caps_lock:
                btn.set_label(current_label.upper())
            else:
                btn.set_label(current_label.lower())
    
    def toggle_password_visibility(self, entry, button):
        """Toggle password visibility"""
        self.password_visible = not self.password_visible
        entry.set_visibility(self.password_visible)
        
        # Update button icon
        if self.password_visible:
            button.set_icon_name("view-reveal-symbolic")
        else:
            button.set_icon_name("view-conceal-symbolic")
    
    def on_password_response(self, dialog, response, ap, ssid, entry):
        """Handle password dialog response"""
        print(f"[INFO] Password dialog response: {response}")
        
        if response == Gtk.ResponseType.CANCEL:
            # User cancelled
            self.password_dialog = None
            dialog.close()
            return
        
        if response == Gtk.ResponseType.OK:
            password = entry.get_text()
            print(f"[INFO] Password length: {len(password)}")
            if not password:
                print("⚠️  Password is empty")
                return
            
            # Disable the connect button to prevent multiple clicks
            dialog.connect_btn.set_sensitive(False)
            
            # Hide keyboard and show connecting status
            dialog.keyboard.set_visible(False)
            dialog.status_label.set_markup('<span foreground="#4a90d9">正在连接...</span>')
            dialog.status_label.set_visible(True)
            dialog.spinner.set_spinning(True)
            dialog.spinner.set_visible(True)
            
            # Start connection (don't close dialog yet)
            self.connect_to_network(ap, ssid, password)
    
    def connect_to_network(self, ap, ssid, password):
        """Connect to selected network"""
        if not self.nm_client:
            return
        
        # Set connecting flag
        self.connecting = True
        
        ssid_bytes = ap.get_ssid()
        
        # Create new connection
        connection = NM.SimpleConnection.new()
        
        s_con = NM.SettingConnection.new()
        s_con.set_property(NM.SETTING_CONNECTION_ID, ssid)
        s_con.set_property(NM.SETTING_CONNECTION_TYPE, "802-11-wireless")
        s_con.set_property(NM.SETTING_CONNECTION_AUTOCONNECT, True)
        
        s_wifi = NM.SettingWireless.new()
        s_wifi.set_property(NM.SETTING_WIRELESS_SSID, ssid_bytes)
        
        if password:
            s_wsec = NM.SettingWirelessSecurity.new()
            s_wsec.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, "wpa-psk")
            s_wsec.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, password)
            connection.add_setting(s_wsec)
        
        connection.add_setting(s_con)
        connection.add_setting(s_wifi)
        
        # Get WiFi device
        wifi_device = None
        for device in self.nm_client.get_devices():
            if device.get_device_type() == NM.DeviceType.WIFI:
                wifi_device = device
                break
        
        if not wifi_device:
            print("WiFi device not found")
            return
        
        # Add and activate connection
        print(f"Connecting to {ssid}...")
        self.nm_client.add_and_activate_connection_async(
            connection, wifi_device, None, None,
            self.on_connection_activated, ssid
        )
    
    def on_connection_activated(self, client, result, ssid):
        """Handle connection result"""
        self.connecting = False  # Reset connecting flag
        
        try:
            active_conn = client.add_and_activate_connection_finish(result)
            
            if active_conn:
                # Get the connection state
                state = active_conn.get_state()
                print(f"[NETWORK] Connection state: {state} ({state})")
                print(f"[NETWORK] State values: UNKNOWN=0, ACTIVATING=1, ACTIVATED=2, DEACTIVATING=3, DEACTIVATED=4")
                
                # State 1 = ACTIVATING, wait for it to become ACTIVATED or fail
                # State 2 = ACTIVATED (success)
                if state == 1:  # ACTIVATING
                    print(f"[NETWORK] Connection is activating, waiting for final state...")
                    # Monitor state changes
                    active_conn.connect('state-changed', lambda c, s, r: self.on_connection_state_changed(c, s, r, ssid))
                    return
                elif state == 2:  # ACTIVATED
                    print(f"[NETWORK] Successfully connected to {ssid}!")
                    self.test_data['network_configured'] = True
                    self.show_connection_result(True, None, ssid)
                else:
                    print(f"[NETWORK] Connection failed with state {state}")
                    self.show_connection_result(False, f"连接状态异常 (state={state})", ssid)
            else:
                print(f"[ERROR] active_conn is None")
                self.show_connection_result(False, "无法建立连接", ssid)
                
        except Exception as e:
            print(f"[ERROR] Connection failed with exception: {e}")
            import traceback
            traceback.print_exc()
            self.show_connection_result(False, str(e), ssid)
    
    def on_connection_state_changed(self, active_conn, state, reason, ssid):
        """Handle connection state changes during activation"""
        print(f"[NETWORK] State changed to {state}, reason: {reason}")
        
        if state == 2:  # ACTIVATED
            print(f"[NETWORK] Successfully connected to {ssid}!")
            self.test_data['network_configured'] = True
            self.show_connection_result(True, None, ssid)
        elif state in [3, 4]:  # DEACTIVATING or DEACTIVATED (failed)
            print(f"[NETWORK] Connection failed, state={state}, reason={reason}")
            # Reason codes: 0=unknown, 1=none, 2=user_disconnected, etc.
            if reason == 7:  # NO_SECRETS
                error_msg = "密码错误"
            elif reason == 8:  # SUPPLICANT_TIMEOUT
                error_msg = "认证超时，密码可能错误"
            else:
                error_msg = f"连接失败 (reason={reason})"
            self.show_connection_result(False, error_msg, ssid)
    
    def show_connection_result(self, success, error_msg, ssid):
        """Show connection result in password dialog"""
        if not self.password_dialog:
            return
        
        dialog = self.password_dialog
        dialog.spinner.set_spinning(False)
        dialog.spinner.set_visible(False)
        
        if success:
            # Show success status
            dialog.status_label.set_markup('<span foreground="#4e9a06">✓ 连接成功！</span>')
            
            # Close dialog after 1 second
            def close_dialog_and_refresh():
                if self.password_dialog:
                    self.password_dialog.close()
                    self.password_dialog = None
                
                # Refresh network list
                if self.current_page == 1:
                    self.show_page(1, add_to_history=False)
                return False
            
            GLib.timeout_add_seconds(1, close_dialog_and_refresh)
        else:
            # Show error status
            friendly_msg = self.get_friendly_error_message(error_msg)
            dialog.status_label.set_markup(f'<span foreground="#cc0000">✗ {friendly_msg}</span>')
            dialog.keyboard.set_visible(True)
            
            # Re-enable connect button for retry
            dialog.connect_btn.set_sensitive(True)
    
    def get_friendly_error_message(self, error_msg):
        """Convert technical error message to user-friendly message"""
        if not error_msg:
            return "连接失败"
        
        error_lower = error_msg.lower()
        if "secrets were required" in error_lower or "password" in error_lower:
            return "密码错误"
        elif "timeout" in error_lower:
            return "连接超时，请检查信号"
        elif "not found" in error_lower:
            return "网络不可用"
        elif "未能激活" in error_msg:
            return "密码可能不正确"
        else:
            return "连接失败，请重试"
    
    def show_connecting_dialog(self, ssid):
        """Show connecting progress dialog"""
        if self.connecting_dialog is not None:
            return
        
        # Create a simple dialog with spinner
        dialog = Gtk.Dialog(title="连接中")
        dialog.set_transient_for(self)
        dialog.set_modal(True)
        dialog.set_default_size(self.scaled(300), self.scaled(150))
        
        content = dialog.get_content_area()
        content.set_margin_top(self.scaled(20))
        content.set_margin_bottom(self.scaled(20))
        content.set_margin_start(self.scaled(20))
        content.set_margin_end(self.scaled(20))
        content.set_spacing(self.scaled(15))
        
        # Message
        label = Gtk.Label(label=f"正在连接到 {ssid}")
        label.set_wrap(True)
        content.append(label)
        
        sub_label = Gtk.Label(label="请稍候...")
        sub_label.add_css_class("dim-label")
        content.append(sub_label)
        
        # Spinner
        spinner = Gtk.Spinner()
        spinner.set_spinning(True)
        spinner.set_size_request(self.scaled(32), self.scaled(32))
        spinner.set_halign(Gtk.Align.CENTER)
        content.append(spinner)
        
        self.connecting_dialog = dialog
        dialog.present()
    
    def close_connecting_dialog(self):
        """Close connecting progress dialog"""
        if self.connecting_dialog is not None:
            self.connecting_dialog.close()
            self.connecting_dialog = None
    
    def show_connection_error(self, error_msg):
        """Show connection error dialog"""
        # Parse error message to make it more user-friendly
        if "secrets were required" in error_msg or "password" in error_msg.lower():
            friendly_msg = "密码错误，请重试"
        elif "timeout" in error_msg.lower():
            friendly_msg = "连接超时，请检查信号强度"
        elif "not found" in error_msg.lower():
            friendly_msg = "网络不可用"
        else:
            friendly_msg = error_msg
        
        # Create error dialog
        dialog = Gtk.Dialog(title="连接失败")
        dialog.set_transient_for(self)
        dialog.set_modal(True)
        dialog.set_default_size(self.scaled(350), self.scaled(150))
        
        content = dialog.get_content_area()
        content.set_margin_top(self.scaled(20))
        content.set_margin_bottom(self.scaled(20))
        content.set_margin_start(self.scaled(20))
        content.set_margin_end(self.scaled(20))
        content.set_spacing(self.scaled(15))
        
        # Error icon + title
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title_box.set_halign(Gtk.Align.CENTER)
        
        error_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
        error_icon.set_pixel_size(self.scaled(32))
        title_box.append(error_icon)
        
        title_label = Gtk.Label(label="连接失败")
        title_label.add_css_class("title-2")
        title_box.append(title_label)
        
        content.append(title_box)
        
        # Error message
        msg_label = Gtk.Label(label=friendly_msg)
        msg_label.set_wrap(True)
        msg_label.set_justify(Gtk.Justification.CENTER)
        content.append(msg_label)
        
        # OK button
        ok_btn = Gtk.Button(label="确定")
        ok_btn.set_halign(Gtk.Align.CENTER)
        ok_btn.set_size_request(self.scaled(100), self.scaled(40))
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", lambda b: dialog.close())
        content.append(ok_btn)
        
        dialog.present()
    
    def show_connection_success(self, ssid):
        """Show connection success dialog"""
        # Create success dialog
        dialog = Gtk.Dialog(title="连接成功")
        dialog.set_transient_for(self)
        dialog.set_modal(True)
        dialog.set_default_size(self.scaled(350), self.scaled(150))
        
        content = dialog.get_content_area()
        content.set_margin_top(self.scaled(20))
        content.set_margin_bottom(self.scaled(20))
        content.set_margin_start(self.scaled(20))
        content.set_margin_end(self.scaled(20))
        content.set_spacing(self.scaled(15))
        
        # Success icon + title
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title_box.set_halign(Gtk.Align.CENTER)
        
        success_icon = Gtk.Image.new_from_icon_name("object-select-symbolic")
        success_icon.set_pixel_size(self.scaled(32))
        title_box.append(success_icon)
        
        title_label = Gtk.Label(label="连接成功")
        title_label.add_css_class("title-2")
        title_box.append(title_label)
        
        content.append(title_box)
        
        # Success message
        msg_label = Gtk.Label(label=f"已成功连接到 {ssid}")
        msg_label.set_wrap(True)
        msg_label.set_justify(Gtk.Justification.CENTER)
        content.append(msg_label)
        
        # OK button
        ok_btn = Gtk.Button(label="确定")
        ok_btn.set_halign(Gtk.Align.CENTER)
        ok_btn.set_size_request(self.scaled(100), self.scaled(40))
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", lambda b: dialog.close())
        content.append(ok_btn)
        
        dialog.present()
    
    def create_test_bash_page(self):
        """Page 2: Test Bash Integration"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.add_css_class("page-container")
        
        # Title
        title = Gtk.Label()
        title.set_markup('<span size="x-large" weight="bold">测试 Bash 集成</span>')
        box.append(title)
        
        # Test results box
        results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        results_box.add_css_class("info-box")
        results_box.set_size_request(self.scaled(700), -1)
        
        # Test 1: Get disks
        disks = self.test_get_disks()
        disk_box = self.create_icon_label_box(
            "drive-harddisk-symbolic",
            f"检测到磁盘: {disks}"
        )
        results_box.append(disk_box)
        
        # Test 2: Get device info
        device = self.get_device_info()
        device_box = self.create_icon_label_box(
            "computer-symbolic",
            f"设备信息: {device}"
        )
        results_box.append(device_box)
        
        # Test 3: Get CPU
        cpu = self.test_get_cpu()
        cpu_box = self.create_icon_label_box(
            "computer-symbolic",
            f"CPU: {cpu}"
        )
        results_box.append(cpu_box)
        
        # Test 4: Check network
        network = self.test_network()
        network_icon = "network-wired-symbolic" if network else "network-offline-symbolic"
        status_text = f"网络状态: {'已连接' if network else '未连接'}"
        
        # Create network box with custom color
        network_label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        net_icon = Gtk.Image.new_from_icon_name(network_icon)
        net_icon.set_icon_size(Gtk.IconSize.NORMAL)
        network_label_box.append(net_icon)
        
        net_label = Gtk.Label(label=status_text)
        net_label.set_xalign(0)
        if network:
            net_label.set_markup(f'<span foreground="green">{status_text}</span>')
        network_label_box.append(net_label)
        
        results_box.append(network_label_box)
        
        box.append(results_box)
        
        # Navigation
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)
        
        back_btn = Gtk.Button(label="返回")
        back_btn.set_icon_name("go-previous-symbolic")
        back_btn.add_css_class("nav-button")
        back_btn.connect("clicked", lambda b: self.go_back())
        btn_box.append(back_btn)
        
        next_btn = Gtk.Button(label="下一步")
        next_btn.set_icon_name("go-next-symbolic")
        next_btn.add_css_class("suggested-action")
        next_btn.add_css_class("nav-button")
        next_btn.connect("clicked", lambda b: self.show_page(3))
        btn_box.append(next_btn)
        
        box.append(btn_box)
        
        return box
    
    def create_test_data_page(self):
        """Page 3: Test Data Selection"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.add_css_class("page-container")
        
        # Title
        title = Gtk.Label()
        title.set_markup('<span size="x-large" weight="bold">测试数据选择</span>')
        box.append(title)
        
        # Radio buttons test
        group_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        group_box.add_css_class("info-box")
        group_box.set_size_request(self.scaled(500), -1)
        
        section_label = Gtk.Label()
        section_label.set_markup('<span weight="bold">选择版本通道：</span>')
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
        
        back_btn = Gtk.Button(label="返回")
        back_btn.set_icon_name("go-previous-symbolic")
        back_btn.add_css_class("nav-button")
        back_btn.connect("clicked", lambda b: self.go_back())
        btn_box.append(back_btn)
        
        next_btn = Gtk.Button(label="完成测试")
        next_btn.set_icon_name("radio-checked-symbolic")
        next_btn.add_css_class("suggested-action")
        next_btn.add_css_class("nav-button")
        next_btn.connect("clicked", lambda b: self.show_page(4))
        btn_box.append(next_btn)
        
        box.append(btn_box)
        
        return box
    
    def create_success_page(self):
        """Page 4: Success"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.add_css_class("page-container")
        
        # Success icon + title
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        title_box.set_halign(Gtk.Align.CENTER)
        
        success_icon = Gtk.Image.new_from_icon_name("radio-checked-symbolic")
        success_icon.set_icon_size(Gtk.IconSize.LARGE)
        success_icon.set_pixel_size(self.scaled(64))
        title_box.append(success_icon)
        
        title = Gtk.Label()
        title.set_markup('<span size="xx-large" weight="bold" foreground="#0f0">PoC 验证成功！</span>')
        title_box.append(title)
        
        box.append(title_box)
        
        # Results
        results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        results_box.add_css_class("info-box")
        results_box.add_css_class("success")
        results_box.set_size_request(self.scaled(600), -1)
        
        results = [
            "• GTK4 图形界面正常",
            "• Gamescope 合成器工作正常",
            "• 键盘/手柄输入响应正常",
            "• Bash 函数调用成功",
            "• 网络连接管理正常",
            "• 多页面导航正常",
            "• 数据选择功能正常",
            "",
            ">> 可以继续开发完整版本！"
        ]
        
        for result in results:
            label = Gtk.Label(label=result)
            label.set_xalign(0)
            results_box.append(label)
        
        box.append(results_box)
        
        # Data summary
        summary_label = Gtk.Label()
        summary_label.set_markup(f'''<span>
测试数据: {self.test_data}
        </span>''')
        box.append(summary_label)
        
        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)
        
        restart_btn = Gtk.Button(label="重新测试")
        restart_btn.set_icon_name("view-refresh-symbolic")
        restart_btn.connect("clicked", lambda b: self.restart_wizard())
        btn_box.append(restart_btn)
        
        exit_btn = Gtk.Button(label="退出")
        exit_btn.set_icon_name("application-exit-symbolic")
        exit_btn.connect("clicked", lambda b: self.close())
        btn_box.append(exit_btn)
        
        box.append(btn_box)
        
        return box
    
    def on_data_changed(self, key, value):
        """Handle data changes"""
        self.test_data[key] = value
        print(f"[DATA] Updated: {key} = {value}")
    
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
        print("[START] SkorionOS Installer PoC starting...")
    
    def do_activate(self):
        win = InstallerPoC(application=self)
        win.present()
        print("[INFO] Application activated")

if __name__ == '__main__':
    print("="*50)
    print("SkorionOS Graphical Installer - PoC")
    print("="*50)
    print("Using GTK native DPI scaling")
    print()
    
    app = InstallerApp()
    exit_code = app.run(None)
    
    print()
    print("="*50)
    print(f"PoC exited with code: {exit_code}")
    print("="*50)
    
    sys.exit(exit_code)
