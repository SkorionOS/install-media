"""
Complete network connection page with full WiFi management
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import threading

from ...config import config
from ...network.manager import NetworkManager
from ...network.dialogs import PasswordDialog
from ..components.base import BasePage, UIComponents
from ...logger import get_logger

logger = get_logger('network')


class NetworkPage(BasePage):
    """Network connection page for WiFi and ethernet management."""
    
    def __init__(self, app):
        super().__init__(app)
        
        # Initialize network manager if not exists
        if not hasattr(app, 'nm'):
            app.nm = NetworkManager()
        
        self.is_online = app.nm.is_online()
        self.wifi_list = None
        
        # If already online (e.g., ethernet), start async timezone detection
        if self.is_online:
            start_async_timezone_detection(app)
    
    def create_title(self) -> Gtk.Widget:
        """Create title with icon."""
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
        title_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("network-wireless-symbolic")
        icon.set_pixel_size(config.scaled(48))
        title_box.append(icon)
        
        title = UIComponents.create_title("网络连接")
        title_box.append(title)
        
        return title_box
    
    def populate_content(self, content_box: Gtk.Box):
        """Populate content with network status and WiFi list."""
        # Show success status if online
        if self.is_online:
            status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(10))
            status_box.add_css_class("info-box")
            status_box.add_css_class("success")
            status_box.set_size_request(config.scaled(600), -1)
            status_box.set_halign(Gtk.Align.CENTER)
            
            icon_label = _create_icon_label_box("radio-checked-symbolic", "网络已连接，可以继续安装")
            status_box.append(icon_label)
            
            # Get connection info
            conn_ssid = self.app.nm.get_connected_wifi_ssid()
            if conn_ssid:
                info_label = Gtk.Label(label=f"当前连接: {conn_ssid}")
                info_label.set_wrap(True)
                status_box.append(info_label)
            
            content_box.append(status_box)
        
        # WiFi list container with fixed border
        wifi_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        wifi_container.add_css_class("info-box")
        
        # WiFi list
        self.wifi_list = Gtk.ListBox()
        self.wifi_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.app.wifi_list = self.wifi_list
        
        # Scroll window (inside the bordered container)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(config.scaled(200))
        # scroll.set_max_content_height(config.scaled(300))
        scroll.set_propagate_natural_height(False)
        scroll.set_child(self.wifi_list)
        
        wifi_container.append(scroll)
        content_box.append(wifi_container)
        
        # Scan networks
        _scan_networks(self.app)
    
    def populate_buttons(self, button_box: Gtk.Box):
        """Populate button area with network actions."""
        # Back button
        back_btn = UIComponents.create_button("返回", "go-previous-symbolic")
        back_btn.connect("clicked", lambda b: self.app.go_back())
        button_box.append(back_btn)
        
        # Refresh button
        refresh_btn = UIComponents.create_button("刷新", "view-refresh-symbolic")
        refresh_btn.connect("clicked", lambda b: self.app.show_page(1, add_to_history=False))
        button_box.append(refresh_btn)
        
        # Connect/Disconnect button
        if self.is_online:
            conn_btn = UIComponents.create_button("重新连接", "network-wireless-symbolic")
            conn_btn.connect("clicked", lambda b: _on_wifi_connect(self.app))
            button_box.append(conn_btn)
            
            # Disconnect button for currently connected WiFi
            connected_ssid = self.app.nm.get_connected_wifi_ssid()
            if connected_ssid:
                disconnect_btn = UIComponents.create_button("断开", "network-wireless-offline-symbolic")
                disconnect_btn.connect("clicked", lambda b: _on_wifi_disconnect(self.app, connected_ssid))
                button_box.append(disconnect_btn)
        else:
            conn_btn = UIComponents.create_button("连接", "network-wireless-symbolic")
            conn_btn.connect("clicked", lambda b: _on_wifi_connect(self.app))
            button_box.append(conn_btn)
        
        # Skip/Continue button
        skip_btn = UIComponents.create_button("继续" if self.is_online else "跳过", "go-next-symbolic")
        skip_btn.add_css_class("suggested-action")
        skip_btn.connect("clicked", lambda b: self.app.show_page(2))
        button_box.append(skip_btn)


def create_network_page(app):
    """Create the network page using the new page architecture."""
    page = NetworkPage(app)
    return page.create()


def start_async_timezone_detection(app):
    """
    Start timezone detection in background thread after network connection.
    This runs asynchronously to avoid blocking the installation flow.
    """
    # Check if timezone already detected
    if hasattr(app, 'timezone_detected') and app.timezone_detected:
        logger.info("Timezone already detected, skipping")
        return
    
    # Check if timezone was copied from existing system
    import os
    if 'INSTALLER_TIMEZONE' in os.environ:
        existing_tz = os.environ['INSTALLER_TIMEZONE']
        logger.info(f"Timezone already configured from existing system: {existing_tz}")
        app.timezone_detected = True
        # Refresh status bar to show the time in correct timezone
        GLib.idle_add(lambda: app.status_bar.refresh_timezone())
        return
    
    def detect_timezone_thread():
        """Background thread for timezone detection"""
        try:
            from ...backend.timezone_utils import auto_detect_timezone, apply_timezone_to_live
            import os
            
            logger.info("Starting async timezone detection...")
            
            # Detect timezone
            detected_timezone = auto_detect_timezone()
            
            # Apply to live environment
            if apply_timezone_to_live(detected_timezone):
                logger.info(f"Timezone detected and applied: {detected_timezone}")
                
                # Save to environment variable for later use
                os.environ['INSTALLER_TIMEZONE'] = detected_timezone
                
                # Mark as detected
                app.timezone_detected = True
                
                # Refresh status bar timezone cache in main thread
                GLib.idle_add(lambda: app.status_bar.refresh_timezone())
            else:
                logger.warning("Failed to apply timezone to live environment")
                
        except Exception as e:
            logger.exception(f"Async timezone detection failed: {e}")
    
    # Start background thread
    thread = threading.Thread(target=detect_timezone_thread, daemon=True)
    thread.start()
    logger.debug("Async timezone detection thread started")


def _scan_networks(app):
    """Scan and display WiFi networks"""
    if not app.nm.is_available():
        _add_no_nm_row(app)
        return
    
    # Clear existing list
    while True:
        row = app.wifi_list.get_row_at_index(0)
        if row is None:
            break
        app.wifi_list.remove(row)
    
    # Scan networks
    networks = app.nm.scan_networks()
    
    if not networks:
        wifi_device = app.nm.get_wifi_device()
        if not wifi_device:
            _add_no_wifi_row(app)
        else:
            _add_no_networks_row(app)
        return
    
    # Add WiFi rows
    for ap, ssid in networks:
        _add_wifi_row(app, ap, ssid)
    
    # Check ethernet
    ethernet_devices = app.nm.get_ethernet_devices()
    for device in ethernet_devices:
        _add_ethernet_row(app, device)


def _add_wifi_row(app, ap, ssid):
    """Add a WiFi network row"""
    row = Gtk.ListBoxRow()
    row.add_css_class("wifi-row")
    
    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
    hbox.set_margin_top(config.scaled(10))
    hbox.set_margin_bottom(config.scaled(10))
    hbox.set_margin_start(config.scaled(10))
    hbox.set_margin_end(config.scaled(10))
    
    # Check if connected
    is_connected = app.nm.is_wifi_connected(ssid)
    
    # Connected indicator
    if is_connected:
        connected_icon = Gtk.Image.new_from_icon_name("radio-checked-symbolic")
        connected_icon.set_icon_size(Gtk.IconSize.NORMAL)
        hbox.append(connected_icon)
    else:
        placeholder = Gtk.Box()
        placeholder.set_size_request(config.scaled(16), config.scaled(16))
        hbox.append(placeholder)
    
    # Security icon
    if app.nm.is_secured(ap):
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
    
    # Signal strength
    strength = ap.get_strength()
    signal_icon_name = app.nm.get_signal_icon(strength)
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
    app.wifi_list.append(row)


def _add_ethernet_row(app, device):
    """Add ethernet connection row"""
    row = Gtk.ListBoxRow()
    row.set_sensitive(False)
    row.add_css_class("wifi-row")
    
    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
    hbox.set_margin_top(config.scaled(10))
    hbox.set_margin_bottom(config.scaled(10))
    hbox.set_margin_start(config.scaled(10))
    hbox.set_margin_end(config.scaled(10))
    
    icon = Gtk.Image.new_from_icon_name("network-wired-symbolic")
    icon.set_icon_size(Gtk.IconSize.NORMAL)
    hbox.append(icon)
    
    label = Gtk.Label(label="有线网络（已连接）")
    label.set_xalign(0)
    label.set_hexpand(True)
    hbox.append(label)
    
    ok_icon = Gtk.Image.new_from_icon_name("radio-checked-symbolic")
    ok_icon.set_icon_size(Gtk.IconSize.NORMAL)
    hbox.append(ok_icon)
    
    row.set_child(hbox)
    app.wifi_list.append(row)


def _add_no_wifi_row(app):
    """Add row when no WiFi device found"""
    row = Gtk.ListBoxRow()
    row.set_sensitive(False)
    
    box = _create_icon_label_box("dialog-warning-symbolic", "未检测到 WiFi 设备")
    box.set_margin_top(config.scaled(10))
    box.set_margin_bottom(config.scaled(10))
    
    row.set_child(box)
    app.wifi_list.append(row)


def _add_no_nm_row(app):
    """Add row when NetworkManager not available"""
    row = Gtk.ListBoxRow()
    row.set_sensitive(False)
    
    box = _create_icon_label_box("dialog-error-symbolic", "NetworkManager 不可用")
    box.set_margin_top(config.scaled(10))
    box.set_margin_bottom(config.scaled(10))
    
    row.set_child(box)
    app.wifi_list.append(row)


def _add_no_networks_row(app):
    """Add row when no networks found"""
    row = Gtk.ListBoxRow()
    row.set_sensitive(False)
    
    box = _create_icon_label_box("radio-checked-symbolic", "未找到可用网络，请刷新重试")
    box.set_margin_top(config.scaled(10))
    box.set_margin_bottom(config.scaled(10))
    
    row.set_child(box)
    app.wifi_list.append(row)


def _create_icon_label_box(icon_name, text):
    """Create a box with icon and label"""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(8))
    
    icon = Gtk.Image.new_from_icon_name(icon_name)
    icon.set_icon_size(Gtk.IconSize.NORMAL)
    box.append(icon)
    
    label = Gtk.Label(label=text)
    label.set_xalign(0)
    label.set_wrap(True)
    box.append(label)
    
    return box


def _on_wifi_connect(app):
    """Handle WiFi connect button"""
    print("[INFO] WiFi connect button clicked")
    
    # Prevent multiple connection attempts
    if hasattr(app, 'connecting') and app.connecting:
        print("[INFO] Already connecting, ignoring")
        return
    
    selected_row = app.wifi_list.get_selected_row()
    if not selected_row or not hasattr(selected_row, 'ap'):
        print("[INFO] No network selected")
        return
    
    ap = selected_row.ap
    ssid = selected_row.ssid
    
    # Check if network is secured
    if app.nm.is_secured(ap):
        print(f"[INFO] Network {ssid} is secured, showing password dialog")
        _show_password_dialog(app, ap, ssid)
    else:
        print(f"[INFO] Network {ssid} is open, connecting directly")
        _connect_to_network(app, ap, ssid, "")


def _show_password_dialog(app, ap, ssid):
    """Show password input dialog"""
    def on_password_entered(password):
        if password is not None:
            print(f"[INFO] Password entered for {ssid}")
            _connect_to_network(app, ap, ssid, password)
        else:
            print(f"[INFO] Password dialog canceled for {ssid}")
    
    dialog = PasswordDialog(app, ssid, on_password_entered)
    app.password_dialog = dialog
    dialog.show()


def _connect_to_network(app, ap, ssid, password):
    """Connect to WiFi network"""
    app.connecting = True
    
    # Set connecting state in dialog if exists
    if hasattr(app, 'password_dialog') and app.password_dialog:
        app.password_dialog.set_connecting(True)
    
    print(f"[INFO] Connecting to: {ssid}")
    
    def on_connection_result(success, error_msg, result_ssid):
        print(f"[INFO] Connection result: success={success}, ssid={result_ssid}")
        app.connecting = False
        
        if hasattr(app, 'password_dialog') and app.password_dialog:
            if success:
                app.password_dialog.close()
                app.password_dialog = None
                # Start async timezone detection after successful connection
                start_async_timezone_detection(app)
                # Refresh page after short delay to show connected status
                GLib.timeout_add(500, lambda: app.show_page(1, add_to_history=False))
            else:
                app.password_dialog.show_error(error_msg or "连接失败")
        else:
            # No dialog, just refresh page to show status
            if success:
                # Start async timezone detection after successful connection
                start_async_timezone_detection(app)
                GLib.timeout_add(500, lambda: app.show_page(1, add_to_history=False))
            else:
                print(f"[ERROR] Connection failed: {error_msg}")
    
    app.nm.connect_to_wifi(ap, ssid, password, on_connection_result)


def _on_wifi_disconnect(app, ssid):
    """Handle WiFi disconnect button"""
    print(f"[INFO] Disconnecting from: {ssid}")
    
    def on_disconnect_result(success, result_ssid):
        print(f"[INFO] Disconnect result: success={success}, ssid={result_ssid}")
        if success:
            # Refresh page after short delay to show disconnected status
            GLib.timeout_add(500, lambda: app.show_page(1, add_to_history=False))
        else:
            print(f"[ERROR] Disconnect failed for {result_ssid}")
    
    app.nm.disconnect_wifi(ssid, on_disconnect_result)
