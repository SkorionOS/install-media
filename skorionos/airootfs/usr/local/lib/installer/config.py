"""
Configuration module for the installer
"""
import os


class Config:
    """Global configuration for the installer"""
    
    def __init__(self):
        # Get screen resolution from environment
        self.screen_width = int(os.environ.get('INNER_WIDTH', '1280'))
        self.screen_height = int(os.environ.get('INNER_WIDTH', '720'))
        
        # Get scaling factors
        self.gdk_scale = os.environ.get('GDK_SCALE', '1')
        ui_scale = os.environ.get('UI_SCALE', '1')
        self.ui_scale = float(ui_scale)
        
        # Version
        self.version = "2.1.1"
        
        print(f"[CONFIG] Screen: {self.screen_width}x{self.screen_height}")
        print(f"[CONFIG] GDK_SCALE: {self.gdk_scale}")
        print(f"[CONFIG] UI scale: {self.ui_scale:.2f}x")
    
    def scaled(self, value):
        """Apply UI scale to a value"""
        return int(value * self.ui_scale)


# Global config instance
config = Config()

