"""
Advanced options page for installation configuration.
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from ...config import config
from ...flow import copy as flow_copy
from ..components.base import BasePage, UIComponents


class AdvancedOptionsPage(BasePage):
    """Advanced installation options page."""
    
    def __init__(self, app):
        super().__init__(app)
        self.checkboxes = {}
    
    def create_title(self) -> Gtk.Widget:
        """Create title with icon."""
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
        title_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("preferences-system-symbolic")
        icon.set_pixel_size(config.scaled(48))
        title_box.append(icon)
        
        title = UIComponents.create_title(flow_copy.ADVANCED_TITLE)
        title_box.append(title)
        
        return title_box
    
    def populate_content(self, content_box: Gtk.Box):
        """Populate advanced options."""
        # Description
        desc_label = Gtk.Label()
        desc_label.set_markup(f'<span size="large">{flow_copy.ADVANCED_SUBTITLE}</span>')
        desc_label.set_margin_bottom(config.scaled(15))
        content_box.append(desc_label)
        
        # Options container
        options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(10))
        options_box.set_halign(Gtk.Align.CENTER)
        options_box.add_css_class("info-box")
        options_box.set_size_request(config.scaled(600), -1)
        
        # Define options (key, label, description, default)
        options = flow_copy.ADVANCED_OPTIONS
        
        for key, label, description, default in options:
            option_box = self._create_option_checkbox(key, label, description, default)
            options_box.append(option_box)
        
        content_box.append(options_box)
    
    def _create_option_checkbox(self, key, label, description, default):
        """Create a checkbox option with label and description."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(5))
        box.set_margin_start(config.scaled(10))
        box.set_margin_end(config.scaled(10))
        box.set_margin_top(config.scaled(8))
        box.set_margin_bottom(config.scaled(8))
        
        # Checkbox with label
        checkbox = Gtk.CheckButton()
        checkbox.set_label(label)
        checkbox.set_active(self.app.advanced_options.get(key, default))
        checkbox.connect("toggled", lambda cb, k=key: self._on_option_changed(k, cb.get_active()))
        
        # Description
        desc_label = Gtk.Label(label=description)
        desc_label.set_xalign(0)
        desc_label.set_margin_start(config.scaled(30))  # Indent under checkbox
        desc_label.set_markup(f'<span size="small" foreground="#888">{description}</span>')
        
        box.append(checkbox)
        box.append(desc_label)
        
        self.checkboxes[key] = checkbox
        
        return box
    
    def _on_option_changed(self, key, value):
        """Handle option change."""
        print(f"[ADVANCED] {key} = {value}")
        self.app.advanced_options[key] = value
    
    def populate_buttons(self, button_box: Gtk.Box):
        """Populate button area."""
        # Back button
        back_btn = UIComponents.create_button("返回", "go-previous-symbolic")
        back_btn.connect("clicked", lambda b: self.app.go_back())
        button_box.append(back_btn)
        
        # Exit button
        exit_btn = UIComponents.create_button("退出", "application-exit-symbolic")
        exit_btn.connect("clicked", lambda b: self._on_exit())
        button_box.append(exit_btn)
        
        # Continue button
        continue_btn = UIComponents.create_button(flow_copy.ADVANCED_CONTINUE, "go-next-symbolic")
        continue_btn.add_css_class("suggested-action")
        continue_btn.connect("clicked", lambda b: self._on_continue())
        button_box.append(continue_btn)
    
    def _on_exit(self):
        """Handle exit button."""
        from .complete import CompletePage
        print("[ADVANCED] User requested exit")
        self.app.show_complete_page(
            CompletePage.STATUS_CANCELLED,
            "安装已取消",
            "您在高级选项页面选择了退出安装"
        )
    
    def _on_continue(self):
        """Handle continue button."""
        print(f"[ADVANCED] Options: {self.app.advanced_options}")
        self.app.show_page('install')


def create_advanced_options_page(app):
    """Create advanced options page."""
    page = AdvancedOptionsPage(app)
    return page.create()

