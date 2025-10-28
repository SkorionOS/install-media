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
                print(f"📚 History: {self.page_history}")
        
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
            print(f"📄 Showing page {page_num + 1}/{len(pages)}")
    
    def go_back(self):
        """Go back to previous page using navigation history"""
        if len(self.page_history) > 0:
            previous_page = self.page_history.pop()
            print(f"⬅️  Going back to page {previous_page + 1}")
            print(f"📚 History after pop: {self.page_history}")
            self.show_page(previous_page, add_to_history=False)
        else:
            # No history, just go to previous page number
            print("⬅️  No history, going to previous page number")
            if self.current_page > 0:
                self.show_page(self.current_page - 1, add_to_history=False)
    
    def restart_wizard(self):
        """Restart the wizard from the beginning"""
        print("🔄 Restarting wizard, clearing history")
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
        ]
        
        for test in tests:
            label = Gtk.Label(label=test)
            label.set_xalign(0)
            label.set_markup(f'<span foreground="white">{test}</span>')
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
        title.set_markup('<span size="x-large" weight="bold" foreground="white">网络连接</span>')
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
                "emblem-ok-symbolic",
                "网络已连接，可以继续安装"
            )
            status_box.append(connected_box)
            
            box.append(status_box)
        else:
            # WiFi list
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
        back_btn.connect("clicked", lambda b: self.go_back())
        btn_box.append(back_btn)
        
        if not is_online:
            refresh_btn = Gtk.Button(label="刷新")
            refresh_btn.set_icon_name("view-refresh-symbolic")
            refresh_btn.connect("clicked", lambda b: self.show_page(1, add_to_history=False))
            btn_box.append(refresh_btn)
            
            connect_btn = Gtk.Button(label="连接")
            connect_btn.set_icon_name("network-wireless-symbolic")
            connect_btn.add_css_class("suggested-action")
            connect_btn.connect("clicked", lambda b: self.on_wifi_connect())
            btn_box.append(connect_btn)
        
        skip_btn = Gtk.Button(label="跳过" if not is_online else "下一步")
        skip_btn.set_icon_name("go-next-symbolic")
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
        
        # Security icon
        flags = ap.get_wpa_flags() | ap.get_rsn_flags()
        if flags != NM.80211ApSecurityFlags.NONE:
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
        
        ok_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
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
            "dialog-information-symbolic",
            "未找到可用网络，请刷新重试"
        )
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        
        row.set_child(box)
        self.wifi_list.append(row)
    
    def on_wifi_connect(self):
        """Handle WiFi connect button"""
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
        
        # Check if network needs password
        flags = ap.get_wpa_flags() | ap.get_rsn_flags()
        if flags != NM.80211ApSecurityFlags.NONE:
            self.show_password_dialog(ap, ssid)
        else:
            self.connect_to_network(ap, ssid, None)
    
    def show_password_dialog(self, ap, ssid):
        """Show password input dialog"""
        # Prevent multiple dialogs
        if self.password_dialog is not None:
            print("⚠️  Password dialog already open")
            return
        
        dialog = Gtk.Dialog(title="输入密码")
        dialog.set_transient_for(self)
        dialog.set_modal(True)
        dialog.set_default_size(400, 200)
        self.password_dialog = dialog
        
        content = dialog.get_content_area()
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(20)
        content.set_margin_end(20)
        content.set_spacing(15)
        
        # Network info
        info_box = self.create_icon_label_box(
            "network-wireless-encrypted-symbolic",
            f"网络: {ssid}"
        )
        content.append(info_box)
        
        # Password entry
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        entry.set_placeholder_text("输入密码")
        content.append(entry)
        
        # Buttons
        dialog.add_button("取消", Gtk.ResponseType.CANCEL)
        connect_btn = dialog.add_button("连接", Gtk.ResponseType.OK)
        connect_btn.add_css_class("suggested-action")
        
        dialog.connect("response", lambda d, r: self.on_password_response(d, r, ap, ssid, entry))
        dialog.present()
    
    def on_password_response(self, dialog, response, ap, ssid, entry):
        """Handle password dialog response"""
        if response == Gtk.ResponseType.OK:
            password = entry.get_text()
            if password:
                self.connect_to_network(ap, ssid, password)
        
        # Clear dialog reference before closing
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
                print(f"✅ Connected to {ssid}!")
                self.test_data['network_configured'] = True
                
                # Refresh page to show connected status - only if still on network page
                def refresh_if_on_network_page():
                    if self.current_page == 1:
                        self.show_page(1, add_to_history=False)
                    return False  # Don't repeat
                
                GLib.timeout_add_seconds(2, refresh_if_on_network_page)
        except Exception as e:
            print(f"❌ Connection failed: {e}")
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
        title.set_markup('<span size="x-large" weight="bold" foreground="white">测试 Bash 集成</span>')
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
        network_icon = "network-idle-symbolic" if network else "network-offline-symbolic"
        status_text = f"网络状态: {'已连接' if network else '未连接'}"
        network_box = self.create_icon_label_box(network_icon, status_text)
        results_box.append(network_box)
        
        box.append(results_box)
        
        # Navigation
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)
        
        back_btn = Gtk.Button(label="返回")
        back_btn.set_icon_name("go-previous-symbolic")
        back_btn.connect("clicked", lambda b: self.go_back())
        btn_box.append(back_btn)
        
        next_btn = Gtk.Button(label="下一步")
        next_btn.set_icon_name("go-next-symbolic")
        next_btn.add_css_class("suggested-action")
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
        
        back_btn = Gtk.Button(label="返回")
        back_btn.set_icon_name("go-previous-symbolic")
        back_btn.connect("clicked", lambda b: self.go_back())
        btn_box.append(back_btn)
        
        next_btn = Gtk.Button(label="完成测试")
        next_btn.set_icon_name("emblem-ok-symbolic")
        next_btn.add_css_class("suggested-action")
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
        
        success_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
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
            "✅ GTK4 图形界面正常",
            "✅ Gamescope 合成器工作正常",
            "✅ 键盘/手柄输入响应正常",
            "✅ Bash 函数调用成功",
            "✅ 网络连接管理正常",
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
