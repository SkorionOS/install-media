"""
Configuration module for the installer
"""
import os
import subprocess


class Config:
    """Global configuration for the installer"""
    
    def __init__(self):
        # Get screen resolution from environment
        inner_width = os.environ.get('INSTALLER_WIDTH', '1280')
        inner_height = os.environ.get('INSTALLER_HEIGHT', '720')
        self.screen_width = int(inner_width) if inner_width else 1280
        self.screen_height = int(inner_height) if inner_height else 720
        
        # Get scaling factors
        self.gdk_scale = os.environ.get('GDK_SCALE', '1')
        ui_scale = os.environ.get('UI_SCALE', '1')
        self.ui_scale = float(ui_scale)
        
        # Version
        self.version = "3.0.0"
        
        # Installation paths
        self.mount_path = "/tmp/frzr_root"
        self.log_file = "/tmp/frzr.log"
        
        # Disk requirements
        self.min_disk_size = 55  # GB
        
        # Steam bootstrap configuration
        self.steam_package_url = "https://steamdeck-packages.steamos.cloud/archlinux-mirror/jupiter-main/os/x86_64/steam-jupiter-stable-1.0.0.81-2.6-x86_64.pkg.tar.zst"
        self.steam_package_filename = "steam-jupiter-stable.pkg.tar.zst"
        self.steam_bootstrap_filename = "bootstraplinux_ubuntu12_32.tar.xz"
        self.steam_packages_dir = "/root/packages"
        
        # Device information (for disk overrides)
        self.device_vendor = self._read_file('/sys/devices/virtual/dmi/id/sys_vendor')
        self.device_product = self._read_file('/sys/devices/virtual/dmi/id/product_name')
        self.device_cpu = self._get_cpu_vendor()
        
        print(f"[CONFIG] Screen: {self.screen_width}x{self.screen_height}")
        print(f"[CONFIG] GDK_SCALE: {self.gdk_scale}")
        print(f"[CONFIG] UI scale: {self.ui_scale:.2f}x")
        print(f"[CONFIG] Device: {self.device_vendor} {self.device_product} ({self.device_cpu})")
    
    def _read_file(self, path):
        """Read a file and return its content, or empty string on error"""
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except:
            return ''
    
    def _get_cpu_vendor(self):
        """Get CPU vendor from lscpu"""
        try:
            result = subprocess.run(
                ['lscpu'],
                capture_output=True,
                text=True,
                env={'LANG': 'en_US.UTF-8'}
            )
            for line in result.stdout.split('\n'):
                if 'Vendor ID:' in line or 'Vendor' in line:
                    parts = line.split(':', 1)
                    if len(parts) >= 2:
                        return parts[1].strip()
            return ''
        except:
            return ''
    
    def scaled(self, value):
        """Apply UI scale to a value"""
        return int(value * self.ui_scale)


# Global config instance
config = Config()

