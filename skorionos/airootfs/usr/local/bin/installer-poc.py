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

class InstallerPoC(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Window setup
        self.set_default_size(1280, 800)
        self.set_title("SkorionOS Installer PoC")
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
        
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .installer-window {
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: #e0e0e0;
            }
            
            .installer-window label {
                color: #e0e0e0;
            }
            
            .installer-window image {
                color: #e0e0e0;
            }
            
            /* Dialog styling */
            dialog {
                background: #2b2b2b;
                color: #e0e0e0;
            }
            
            dialog .dialog-content-area {
                background: #2b2b2b;
            }
            
            dialog label {
                color: #e0e0e0;
            }
            
            dialog entry {
                background: #3a3a3a;
                color: white;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 10px;
                font-size: 16px;
            }
            
            .password-title {
                font-size: 20px;
                font-weight: bold;
                color: #e0e0e0;
            }
            
            /* Dialog action area (bottom buttons) */
            dialog .dialog-action-area {
                padding: 20px;
            }
            
            dialog .dialog-action-area button {
                min-height: 44px;
                min-width: 120px;
                margin-left: 8px;
                margin-right: 8px;
                padding: 10px 24px;
                font-size: 15px;
            }
            
            dialog .dialog-action-area button:first-child {
                margin-left: 0;
            }
            
            dialog .dialog-action-area button:last-child {
                margin-right: 0;
            }
            
            .installer-title {
                font-size: 32px;
                font-weight: bold;
                color: white;
            }
            
            .installer-subtitle {
                font-size: 16px;
                color: #bbb;
            }
            
            .installer-button {
                min-width: 200px;
                min-height: 50px;
                font-size: 16px;
                border-radius: 8px;
            }
            
            button {
                background: rgba(255,255,255,0.15);
                color: #e0e0e0;
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 6px;
                padding: 6px 12px;
                min-height: 36px;
                font-size: 14px;
            }
            
            button:hover {
                background: rgba(255,255,255,0.25);
                border-color: rgba(255,255,255,0.3);
            }
            
            button image {
                color: #e0e0e0;
            }
            
            button.suggested-action {
                background: rgba(52, 152, 219, 0.8);
                color: white;
                border-color: rgba(52, 152, 219, 1);
            }
            
            button.suggested-action:hover {
                background: rgba(52, 152, 219, 1);
            }
            
            button.suggested-action image {
                color: white;
            }
            
            /* Larger nav buttons at page bottom */
            button.nav-button {
                min-height: 44px;
                padding: 10px 24px;
                font-size: 15px;
            }
            
            /* Virtual keyboard buttons */
            .keyboard-key {
                background: #505050;
                color: white;
                border: 1px solid #707070;
                border-radius: 4px;
                min-width: 48px;
                min-height: 48px;
                font-size: 16px;
                font-weight: bold;
                padding: 0;
            }
            
            .keyboard-key:hover {
                background: #606060;
                border-color: #808080;
            }
            
            .keyboard-key:active {
                background: #404040;
            }
            
            .page-container {
                padding: 50px;
            }
            
            .info-box {
                background: rgba(255,255,255,0.05);
                border-radius: 8px;
                padding: 20px;
                margin: 10px 0;
                color: #e0e0e0;
            }
            
            .info-box label {
                color: #e0e0e0;
            }
            
            .wifi-row {
                padding: 10px;
                border-radius: 6px;
            }
            
            .wifi-row:hover {
                background: rgba(255,255,255,0.1);
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
        logo.set_pixel_size(128)
        box.append(logo)
        
        # Title
        title = Gtk.Label()
        title.set_markup('<span size="xx-large" weight="bold">SkorionOS 图形化安装器</span>')
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
        
        # Button
        btn = Gtk.Button(label="开始测试")
        btn.set_icon_name("go-next-symbolic")
        btn.add_css_class("installer-button")
        btn.add_css_class("suggested-action")
        btn.connect("clicked", lambda b: self.show_page(1))
        box.append(btn)
        
        return box
    
    def create_network_page(self):
        """Page 1: Network Connection"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.add_css_class("page-container")
        
        # Title with icon
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title_box.set_halign(Gtk.Align.CENTER)
        
        network_icon = Gtk.Image.new_from_icon_name("network-wireless-symbolic")
        network_icon.set_icon_size(Gtk.IconSize.LARGE)
        network_icon.set_pixel_size(48)
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
            status_box.set_size_request(600, -1)
            
            connected_box = self.create_icon_label_box(
                "radio-checked-symbolic",
                "网络已连接，可以继续安装"
            )
            status_box.append(connected_box)
            
            box.append(status_box)
        
        # Always show WiFi list for reselection
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_size_request(700, 300)
        scroll.set_child(self.wifi_list)
        box.append(scroll)
        
        # Scan networks
        self.scan_networks()
        
        # Navigation buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(20)
        
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
        
        connect_btn = Gtk.Button(label="连接" if not is_online else "重新连接")
        connect_btn.set_icon_name("network-wireless-symbolic")
        connect_btn.add_css_class("suggested-action")
        connect_btn.add_css_class("nav-button")
        connect_btn.connect("clicked", lambda b: self.on_wifi_connect())
        btn_box.append(connect_btn)
        
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
        hbox.set_margin_top(10)
        hbox.set_margin_bottom(10)
        hbox.set_margin_start(10)
        hbox.set_margin_end(10)
        
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
            placeholder.set_size_request(16, 16)  # Same size as icon
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
    
    def is_wifi_connected(self, ssid):
        """Check if a specific WiFi network is currently connected"""
        if not self.nm_client:
            return False
        
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
                                        if active_ssid == ssid:
                                            return True
                                    except:
                                        pass
        except Exception as e:
            print(f"[ERROR] Failed to check connected WiFi: {e}")
        
        return False
    
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
        hbox.set_margin_top(10)
        hbox.set_margin_bottom(10)
        hbox.set_margin_start(10)
        hbox.set_margin_end(10)
        
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
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        
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
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        
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
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        
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
    
    def show_password_dialog(self, ap, ssid):
        """Show password input dialog with virtual keyboard"""
        # Prevent multiple dialogs
        if self.password_dialog is not None:
            print("⚠️  Password dialog already open")
            return
        
        print(f"[INFO] Showing password dialog for: {ssid}")
        
        # Create dialog (same 16:10 ratio as main window)
        dialog = Gtk.Dialog(title=f"连接到: {ssid}")
        dialog.set_transient_for(self)
        dialog.set_modal(True)
        dialog.set_default_size(960, 600)  # 16:10 ratio
        self.password_dialog = dialog
        
        # Content area
        content = dialog.get_content_area()
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(20)
        content.set_margin_end(20)
        content.set_spacing(20)
        
        # Network info with icon
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        info_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("network-wireless-encrypted-symbolic")
        icon.set_pixel_size(32)
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
        toggle_btn.set_size_request(45, 45)
        toggle_btn.set_tooltip_text("显示/隐藏密码")
        toggle_btn.connect("clicked", lambda b: self.toggle_password_visibility(entry, b))
        entry_box.append(toggle_btn)
        
        content.append(entry_box)
        
        # Virtual keyboard (pass dialog for Enter key)
        keyboard = self.create_virtual_keyboard(entry, dialog)
        content.append(keyboard)
        
        # Dialog buttons
        cancel_btn = dialog.add_button("取消", Gtk.ResponseType.CANCEL)
        connect_btn = dialog.add_button("连接", Gtk.ResponseType.OK)
        
        # Apply styling to buttons - make them wider
        cancel_btn.set_size_request(150, 44)
        cancel_btn.set_margin_end(8)
        
        connect_btn.set_size_request(150, 44)
        connect_btn.set_margin_start(8)
        connect_btn.set_margin_end(30)
        connect_btn.add_css_class("suggested-action")
        
        # Handle response
        dialog.connect("response", lambda d, r: self.on_password_response(d, r, ap, ssid, entry))
        
        dialog.present()
        print("[INFO] Password dialog presented")
    
    def create_virtual_keyboard(self, entry, dialog=None):
        """Create virtual keyboard for password input"""
        # Keyboard button size configuration (easy to adjust)
        self.key_size = 48  # Base key size (was 40)
        self.key_height = 48  # Key height (was 40)
        self.key_spacing = 4  # Spacing between keys
        
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
        
        if response == Gtk.ResponseType.OK:
            password = entry.get_text()
            print(f"[INFO] Password length: {len(password)}")
            if password:
                self.connect_to_network(ap, ssid, password)
            else:
                print("⚠️  Password is empty")
        
        # Close dialog
        self.password_dialog = None
        dialog.close()
    
    def connect_to_network(self, ap, ssid, password):
        """Connect to selected network"""
        if not self.nm_client:
            return
        
        # Set connecting flag
        self.connecting = True
        
        # Show connecting dialog
        self.show_connecting_dialog(ssid)
        
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
        
        # Close connecting dialog
        self.close_connecting_dialog()
        
        try:
            active_conn = client.add_and_activate_connection_finish(result)
            if active_conn:
                print(f"[NETWORK] Connected to {ssid}!")
                self.test_data['network_configured'] = True
                
                # Refresh page to show connected status - only if still on network page
                def refresh_if_on_network_page():
                    if self.current_page == 1:
                        self.show_page(1, add_to_history=False)
                    return False  # Don't repeat
                
                GLib.timeout_add_seconds(2, refresh_if_on_network_page)
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            # Show error dialog
            self.show_connection_error(str(e))
    
    def show_connecting_dialog(self, ssid):
        """Show connecting progress dialog"""
        if self.connecting_dialog is not None:
            return
        
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text=f"正在连接到 {ssid}"
        )
        dialog.format_secondary_text("请稍候...")
        
        # Add spinner
        content = dialog.get_content_area()
        spinner = Gtk.Spinner()
        spinner.set_spinning(True)
        spinner.set_size_request(32, 32)
        spinner.set_margin_top(10)
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
        
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="连接失败"
        )
        dialog.format_secondary_text(friendly_msg)
        dialog.connect("response", lambda d, r: d.close())
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
        results_box.set_size_request(700, -1)
        
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
        group_box.set_size_request(500, -1)
        
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
        success_icon.set_pixel_size(64)
        title_box.append(success_icon)
        
        title = Gtk.Label()
        title.set_markup('<span size="xx-large" weight="bold" foreground="#0f0">PoC 验证成功！</span>')
        title_box.append(title)
        
        box.append(title_box)
        
        # Results
        results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        results_box.add_css_class("info-box")
        results_box.add_css_class("success")
        results_box.set_size_request(600, -1)
        
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
    print()
    
    app = InstallerApp()
    exit_code = app.run(None)
    
    print()
    print("="*50)
    print(f"PoC exited with code: {exit_code}")
    print("="*50)
    
    sys.exit(exit_code)
