"""
Version selection page (Channel, Desktop, NVIDIA driver)
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from ...config import config
from ..components.base import BasePage, UIComponents


class VersionPage(BasePage):
    """Version selection page for choosing installation configuration."""
    
    def __init__(self, app):
        super().__init__(app)
        
        # Initialize selections if not exist
        if not hasattr(app, 'version_selections'):
            app.version_selections = {
                'channel': 'stable',
                'desktop': 'gnome',
                'nvidia': False
            }
        
        self.config_label = None
    
    def create_title(self) -> Gtk.Widget:
        """Create title with icon."""
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
        title_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("view-list-symbolic")
        icon.set_pixel_size(config.scaled(48))
        title_box.append(icon)
        
        title = UIComponents.create_title("版本选择")
        title_box.append(title)
        
        return title_box
    
    def populate_content(self, content_box: Gtk.Box):
        """Populate the content area with selection sections."""
        # Selection container - horizontal layout
        selection_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(15))
        selection_box.set_halign(Gtk.Align.CENTER)
        selection_box.set_margin_top(config.scaled(10))
        
        # Section 1: Channel selection
        channel_section = self._create_compact_section(
            "版本通道",
            [
                ('stable', '稳定版', '推荐日常使用'),
                ('testing', '测试版', '较新功能'),
                ('unstable', '不稳定版', '开发测试')
            ],
            self.app.version_selections['channel'],
            lambda value: self._on_selection_changed('channel', value)
        )
        selection_box.append(channel_section)
        
        # Section 2: Desktop selection
        desktop_section = self._create_compact_section(
            "桌面环境",
            [
                ('gnome', 'GNOME', '默认推荐'),
                ('kde', 'KDE Plasma', '类似 Steam Deck')
            ],
            self.app.version_selections['desktop'],
            lambda value: self._on_selection_changed('desktop', value)
        )
        selection_box.append(desktop_section)
        
        # Section 3: NVIDIA driver selection
        nvidia_section = self._create_compact_section(
            "NVIDIA 驱动",
            [
                (False, '标准版', '开源驱动'),
                (True, 'NV 版', '含 NVIDIA 专有驱动')
            ],
            self.app.version_selections['nvidia'],
            lambda value: self._on_selection_changed('nvidia', value)
        )
        selection_box.append(nvidia_section)
        
        content_box.append(selection_box)
        
        # Show selected configuration
        config_display_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(5))
        config_display_box.set_halign(Gtk.Align.CENTER)
        config_display_box.set_margin_top(config.scaled(10))
        
        self.config_label = Gtk.Label()
        target = self._build_target(self.app.version_selections)
        self.config_label.set_markup(f'<span size="large">当前配置: <b>{target}</b></span>')
        config_display_box.append(self.config_label)
        
        content_box.append(config_display_box)
    
    def populate_buttons(self, button_box: Gtk.Box):
        """Populate the button area."""
        # Back button
        back_btn = UIComponents.create_button("返回", "go-previous-symbolic")
        back_btn.connect("clicked", lambda b: self.app.go_back())
        button_box.append(back_btn)
        
        # Cancel button (closes the app)
        cancel_btn = UIComponents.create_button("取消", "process-stop-symbolic")
        cancel_btn.connect("clicked", lambda b: self.app.close())
        button_box.append(cancel_btn)
        
        # Continue button
        continue_btn = UIComponents.create_button("开始安装", "system-software-install-symbolic")
        continue_btn.add_css_class("suggested-action")
        continue_btn.connect("clicked", lambda b: self._on_continue())
        button_box.append(continue_btn)
    
    def _create_compact_section(self, title, options, current_value, on_change_callback):
        """
        Create a compact selection section (card style).
        
        Args:
            title: Section title
            options: List of (value, label, description) tuples
            current_value: Currently selected value
            on_change_callback: Callback function(value)
        
        Returns:
            Gtk.Box: Selection section widget
        """
        # Card container
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(8))
        section.add_css_class("info-box")
        section.set_size_request(config.scaled(220), -1)
        
        # Title
        title_label = Gtk.Label()
        title_label.set_markup(f'<span weight="bold">{title}</span>')
        title_label.set_xalign(0.5)
        section.append(title_label)
        
        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(config.scaled(5))
        separator.set_margin_bottom(config.scaled(5))
        section.append(separator)
        
        # Radio buttons with compact descriptions
        first_btn = None
        for value, label, description in options:
            # Radio button
            if first_btn is None:
                btn = Gtk.CheckButton()
                first_btn = btn
            else:
                btn = Gtk.CheckButton()
                btn.set_group(first_btn)
            
            # Content inside button
            content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(2))
            
            # Label
            label_widget = Gtk.Label(label=label)
            label_widget.set_xalign(0)
            content_box.append(label_widget)
            
            # Description
            desc_label = Gtk.Label(label=description)
            desc_label.set_xalign(0)
            desc_label.set_margin_start(config.scaled(15))
            desc_label.set_wrap(True)
            desc_label.set_max_width_chars(20)
            desc_label.add_css_class("dim-label")
            desc_label.set_markup(f'<span size="small" foreground="#888">{description}</span>')
            content_box.append(desc_label)
            
            btn.set_child(content_box)
            
            # Set active if current value
            if value == current_value:
                btn.set_active(True)
            
            # Connect signal
            btn.connect("toggled", lambda b, v=value: on_change_callback(v) if b.get_active() else None)
            
            section.append(btn)
        
        return section
    
    def _on_selection_changed(self, key, value):
        """Handle selection change."""
        print(f"[VERSION] {key} = {value}")
        self.app.version_selections[key] = value
        
        # Update config label
        if self.config_label:
            target = self._build_target(self.app.version_selections)
            self.config_label.set_markup(
                f'<span size="large">当前配置: <b>{target}</b></span>'
            )
    
    def _build_target(self, selections):
        """Build TARGET string from selections."""
        channel = selections['channel']
        desktop = selections['desktop']
        nvidia = selections['nvidia']
        
        if nvidia:
            return f"{channel}:{desktop}-nv"
        else:
            return f"{channel}:{desktop}"
    
    def _on_continue(self):
        """Handle continue button."""
        target = self._build_target(self.app.version_selections)
        print(f"[VERSION] Selected target: {target}")
        
        # Store target for installation
        self.app.install_target = target
        
        # Go to installation page
        self.app.show_page('install')


def create_version_page(app):
    """Create the version selection page using the new page architecture."""
    page = VersionPage(app)
    return page.create()
