"""
CSS styling for the installer
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk


def apply_styling(scaled_func):
    """
    Apply minimal custom CSS styling
    
    Args:
        scaled_func: Function that scales values based on UI scale factor
    """
    # Enable GTK dark theme
    settings = Gtk.Settings.get_default()
    if settings:
        settings.set_property("gtk-application-prefer-dark-theme", True)
    
    # Scaled font sizes
    font_size = scaled_func(16)
    title_size = scaled_func(32)
    subtitle_size = scaled_func(16)
    button_font_size = scaled_func(14)
    nav_button_font = scaled_func(15)
    
    # Scaled layout sizes
    button_min_width = scaled_func(200)
    button_min_height = scaled_func(50)
    small_button_height = scaled_func(36)
    nav_button_height = scaled_func(44)
    nav_button_min_width = scaled_func(120)
    
    # Scaled spacing
    padding_small = scaled_func(6)
    padding = scaled_func(10)
    padding_medium = scaled_func(20)
    padding_large = scaled_func(50)
    spacing = scaled_func(10)
    spacing_medium = scaled_func(24)
    
    # Scaled borders
    border_radius_small = scaled_func(4)
    border_radius = scaled_func(6)
    border_radius_large = scaled_func(8)
    
    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(f"""
        /* Scale icons globally */
        image {{
            -gtk-icon-size: {scaled_func(16)}px;
        }}
        
        button image {{
            -gtk-icon-size: {scaled_func(16)}px;
        }}
        
        /* Larger navigation buttons */
        button.nav-button {{
            min-height: {scaled_func(48)}px;
            padding: {scaled_func(12)}px {scaled_func(24)}px;
            font-size: {scaled_func(16)}px;
        }}
        
        button.nav-button image {{
            -gtk-icon-size: {scaled_func(20)}px;
        }}
        
        .installer-button {{
            min-width: {scaled_func(200)}px;
            min-height: {scaled_func(50)}px;
            font-size: {scaled_func(16)}px;
        }}
        
        .installer-button image {{
            -gtk-icon-size: {scaled_func(24)}px;
        }}
        
        /* Info box - use GTK theme colors */
        .info-box {{
            border: 1px solid alpha(currentColor, 0.2);
            border-radius: {border_radius_large}px;
            padding: {padding_medium}px;
            margin: {padding}px 0;
        }}
        
        .success {{
            background: alpha(@success_color, 0.1);
        }}
        
        /* Virtual keyboard styling */
        .keyboard-key {{
            min-width: {scaled_func(40)}px;
            min-height: {scaled_func(40)}px;
            font-size: {scaled_func(14)}px;
            font-weight: bold;
            padding: 0;
        }}
        
        /* Wider scrollbar */
        scrollbar slider {{
            min-width: {scaled_func(12)}px;
            min-height: {scaled_func(12)}px;
        }}
    """.encode())
    
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

