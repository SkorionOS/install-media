"""
NetworkManager wrapper for network operations
"""
import gi
gi.require_version('NM', '1.0')
from gi.repository import NM, GLib


class NetworkManager:
    """Wrapper for NetworkManager operations"""
    
    def __init__(self):
        """Initialize NetworkManager client"""
        try:
            self.client = NM.Client.new(None)
            print("[NM] NetworkManager client initialized")
        except Exception as e:
            print(f"[NM] Failed to initialize: {e}")
            self.client = None
    
    def is_available(self):
        """Check if NetworkManager is available"""
        return self.client is not None
    
    def get_wifi_device(self):
        """Get WiFi device"""
        if not self.client:
            return None
        
        for device in self.client.get_devices():
            if device.get_device_type() == NM.DeviceType.WIFI:
                return device
        return None
    
    def scan_networks(self):
        """
        Scan for available WiFi networks
        
        Returns:
            list: List of (ap, ssid) tuples, sorted by signal strength
        """
        wifi_device = self.get_wifi_device()
        if not wifi_device:
            return []
        
        # Request scan
        try:
            wifi_device.request_scan_async(None, None, None)
        except Exception as e:
            print(f"[NM] WiFi scan request failed: {e}")
        
        # Get access points
        access_points = wifi_device.get_access_points()
        if not access_points:
            return []
        
        # Sort by signal strength
        access_points = sorted(
            access_points,
            key=lambda ap: ap.get_strength(),
            reverse=True
        )
        
        # Deduplicate by SSID
        result = []
        seen_ssids = set()
        
        for ap in access_points:
            ssid_bytes = ap.get_ssid()
            if not ssid_bytes:
                continue
            
            # Safely convert SSID to UTF-8
            try:
                ssid = NM.utils_ssid_to_utf8(ssid_bytes.get_data())
            except Exception as e:
                print(f"[NM] Invalid SSID encoding: {e}")
                ssid = f"<Hidden Network {len(seen_ssids) + 1}>"
            
            if ssid in seen_ssids:
                continue
            seen_ssids.add(ssid)
            
            result.append((ap, ssid))
        
        return result
    
    def get_ethernet_devices(self):
        """
        Get active ethernet connections
        
        Returns:
            list: List of active ethernet devices
        """
        if not self.client:
            return []
        
        result = []
        for device in self.client.get_devices():
            if device.get_device_type() == NM.DeviceType.ETHERNET:
                if device.get_state() == NM.DeviceState.ACTIVATED:
                    result.append(device)
        return result
    
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
    
    def is_secured(self, ap):
        """Check if access point is secured"""
        flags = ap.get_wpa_flags() | ap.get_rsn_flags()
        return flags != 0
    
    def get_connected_wifi_ssid(self):
        """Get the SSID of currently connected WiFi, or None"""
        if not self.client:
            return None
        
        try:
            active_connections = self.client.get_active_connections()
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
            print(f"[NM] Failed to get connected WiFi: {e}")
        
        return None
    
    def is_wifi_connected(self, ssid):
        """Check if a specific WiFi network is currently connected"""
        connected_ssid = self.get_connected_wifi_ssid()
        return connected_ssid == ssid if connected_ssid else False
    
    def is_online(self):
        """Check if network is online"""
        if not self.client:
            return False
        return self.client.get_connectivity() == NM.ConnectivityState.FULL
    
    def connect_to_wifi(self, ap, ssid, password, callback):
        """
        Connect to a WiFi network
        
        Args:
            ap: Access point object
            ssid: Network SSID
            password: Network password (can be empty for open networks)
            callback: Callback function(success, error_msg, ssid)
        """
        if not self.client:
            callback(False, "NetworkManager not available", ssid)
            return
        
        wifi_device = self.get_wifi_device()
        if not wifi_device:
            callback(False, "No WiFi device found", ssid)
            return
        
        # Create connection settings
        conn = NM.SimpleConnection.new()
        
        # Connection settings
        s_con = NM.SettingConnection.new()
        s_con.set_property(NM.SETTING_CONNECTION_ID, ssid)
        s_con.set_property(NM.SETTING_CONNECTION_TYPE, "802-11-wireless")
        s_con.set_property(NM.SETTING_CONNECTION_UUID, NM.utils_uuid_generate())
        s_con.set_property(NM.SETTING_CONNECTION_AUTOCONNECT, True)
        conn.add_setting(s_con)
        
        # WiFi settings
        s_wifi = NM.SettingWireless.new()
        s_wifi.set_property(NM.SETTING_WIRELESS_SSID, ap.get_ssid())
        s_wifi.set_property(NM.SETTING_WIRELESS_MODE, "infrastructure")
        conn.add_setting(s_wifi)
        
        # Security settings
        if self.is_secured(ap):
            s_wifi_sec = NM.SettingWirelessSecurity.new()
            s_wifi_sec.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, "wpa-psk")
            s_wifi_sec.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, password)
            conn.add_setting(s_wifi_sec)
        
        # IPv4 settings (automatic)
        s_ip4 = NM.SettingIP4Config.new()
        s_ip4.set_property(NM.SETTING_IP_CONFIG_METHOD, "auto")
        conn.add_setting(s_ip4)
        
        # IPv6 settings (automatic)
        s_ip6 = NM.SettingIP6Config.new()
        s_ip6.set_property(NM.SETTING_IP_CONFIG_METHOD, "auto")
        conn.add_setting(s_ip6)
        
        print(f"[NM] Connecting to: {ssid}")
        
        # Connect asynchronously
        def on_activate_finish(client, result, user_data):
            try:
                active_conn = client.add_and_activate_connection_finish(result)
                
                if active_conn:
                    state = active_conn.get_state()
                    print(f"[NM] Connection activated, state: {state}")
                    
                    # Monitor state changes
                    def on_state_changed(ac, state, reason):
                        print(f"[NM] State changed: {state}, reason: {reason}")
                        
                        if state == NM.ActiveConnectionState.ACTIVATED:
                            print(f"[NM] ✅ Connected to: {ssid}")
                            callback(True, None, ssid)
                            ac.disconnect_by_func(on_state_changed)
                        
                        elif state in [NM.ActiveConnectionState.DEACTIVATING,
                                      NM.ActiveConnectionState.DEACTIVATED]:
                            error_msg = self._get_error_message(reason)
                            print(f"[NM] ❌ Connection failed: {error_msg}")
                            callback(False, error_msg, ssid)
                            ac.disconnect_by_func(on_state_changed)
                    
                    active_conn.connect("state-changed", on_state_changed)
                    
                    # Initial state check
                    if state == NM.ActiveConnectionState.ACTIVATED:
                        print(f"[NM] ✅ Already connected to: {ssid}")
                        callback(True, None, ssid)
                else:
                    callback(False, "Failed to create connection", ssid)
            
            except Exception as e:
                error_msg = str(e)
                print(f"[NM] Connection error: {error_msg}")
                callback(False, error_msg, ssid)
        
        self.client.add_and_activate_connection_async(
            conn, wifi_device, ap.get_path(),
            None, on_activate_finish, None
        )
    
    def disconnect_wifi(self, ssid, callback):
        """
        Disconnect from a WiFi network
        
        Args:
            ssid: Network SSID to disconnect
            callback: Callback function(success, ssid)
        """
        if not self.client:
            callback(False, ssid)
            return
        
        # Find active connection
        active_connections = self.client.get_active_connections()
        target_conn = None
        
        for conn in active_connections:
            if conn.get_connection_type() == "802-11-wireless":
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
                                        target_conn = conn
                                        break
                                except:
                                    pass
        
        if not target_conn:
            print(f"[NM] No active connection found for: {ssid}")
            callback(False, ssid)
            return
        
        print(f"[NM] Disconnecting from: {ssid}")
        
        def on_deactivate_finish(client, result, user_data):
            try:
                success = client.deactivate_connection_finish(result)
                print(f"[NM] Disconnect result: {success}")
                callback(success, ssid)
            except Exception as e:
                print(f"[NM] Disconnect error: {e}")
                callback(False, ssid)
        
        self.client.deactivate_connection_async(
            target_conn, None, on_deactivate_finish, None
        )
    
    def _get_error_message(self, reason):
        """Convert NM state reason to user-friendly error message"""
        if reason == NM.ActiveConnectionStateReason.NO_SECRETS:
            return "密码错误"
        elif reason == NM.ActiveConnectionStateReason.DEVICE_DISCONNECTED:
            return "设备已断开"
        elif reason == NM.ActiveConnectionStateReason.USER_DISCONNECTED:
            return "用户断开连接"
        elif reason == NM.ActiveConnectionStateReason.DEVICE_REMOVED:
            return "设备已移除"
        elif reason == NM.ActiveConnectionStateReason.CONNECTION_REMOVED:
            return "连接已删除"
        elif reason in [NM.ActiveConnectionStateReason.CONNECT_TIMEOUT,
                       NM.ActiveConnectionStateReason.SERVICE_START_TIMEOUT]:
            return "连接超时"
        else:
            return f"连接失败 (reason: {reason})"

