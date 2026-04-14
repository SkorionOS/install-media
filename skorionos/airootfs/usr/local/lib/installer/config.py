"""
Configuration module for the installer
"""
import os
import subprocess
from .logger import get_logger

logger = get_logger('config')


class Config:
    """Global configuration for the installer"""
    
    def __init__(self):
        # Get screen resolution from environment
        self.screen_width = os.environ.get('SCREEN_WIDTH', '1280')
        self.screen_height = os.environ.get('SCREEN_HEIGHT', '720')
        self.windows_width = int(os.environ.get('INSTALLER_WIDTH', '1280'))
        self.windows_height = int(os.environ.get('INSTALLER_HEIGHT', '720'))
        
        # Get scaling factors
        self.gdk_scale = os.environ.get('GDK_SCALE', '1')
        ui_scale = os.environ.get('UI_SCALE', '1')
        self.ui_scale = float(ui_scale)
        
        # Version
        self.version = "3.5.2"
        
        # Installation paths
        self.mount_path = "/tmp/frzr_root"
        self.log_file = "/tmp/frzr.log"
        
        # Disk requirements
        self.min_disk_size = 55  # GB
        
        # Steam bootstrap configuration
        self.steam_package_url = "https://steamdeck-packages.steamos.cloud/archlinux-mirror/jupiter-main/os/x86_64/steam-jupiter-stable-1.0.0.85-2-x86_64.pkg.tar.zst"
        self.steam_package_filename = "steam-jupiter-stable.pkg.tar.zst"
        self.steam_bootstrap_filename = "bootstraplinux_ubuntu12_32.tar.xz"
        self.steam_packages_dir = "/root/packages"
        
        # Device information (for disk overrides)
        self.device_vendor = self._read_file('/sys/devices/virtual/dmi/id/sys_vendor')
        self.device_product = self._read_file('/sys/devices/virtual/dmi/id/product_name')
        self.device_cpu = self._get_cpu_vendor()
        
        print(f"[CONFIG] Window size: {self.windows_width}x{self.windows_height}")
        print(f"[CONFIG] Screen size: {self.screen_width}x{self.screen_height}")
        print(f"[CONFIG] GDK_SCALE: {self.gdk_scale}")
        print(f"[CONFIG] UI scale: {self.ui_scale:.2f}x")
        print(f"[CONFIG] Device: {self.device_vendor} {self.device_product} ({self.device_cpu})")
    
    def _read_file(self, path):
        """Read a file and return its content, or empty string on error"""
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.debug(f"File not found: {path}")
            return ''
        except Exception as e:
            logger.warning(f"Could not read {path}: {e}")
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
        except FileNotFoundError:
            logger.warning("lscpu command not found")
            return ''
        except Exception as e:
            logger.warning(f"Could not get CPU vendor: {e}")
            return ''
    
    def scaled(self, value):
        """Apply UI scale to a value"""
        return int(value * self.ui_scale)


# Global config instance
config = Config()

