"""
Network-related dialogs (password input, connection progress, etc.)
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

from ..config import config
from ..ui.keyboard import VirtualKeyboard


class PasswordDialog:
    """Password input dialog with virtual keyboard"""
    
    def __init__(self, parent, ssid, callback):
        """
        Initialize password dialog
        
        Args:
            parent: Parent window
            ssid: Network SSID
            callback: Callback function(password) or None if canceled
        """
        self.parent = parent
        self.ssid = ssid
        self.callback = callback
        self.password_visible = False
        
        # Create dialog
        self.dialog = Gtk.Dialog(title=f"连接到: {ssid}")
        self.dialog.set_transient_for(parent)
        self.dialog.set_modal(True)
        self.dialog.set_default_size(config.scaled(960), config.scaled(600))
        
        # Content area
        content = self.dialog.get_content_area()
        content.set_margin_top(config.scaled(20))
        content.set_margin_bottom(config.scaled(20))
        content.set_margin_start(config.scaled(20))
        content.set_margin_end(config.scaled(20))
        content.set_spacing(config.scaled(20))
        
        # Network info with icon
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        info_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("network-wireless-encrypted-symbolic")
        icon.set_pixel_size(config.scaled(32))
        info_box.append(icon)
        
        ssid_label = Gtk.Label(label=ssid)
        ssid_label.add_css_class("password-title")
        info_box.append(ssid_label)
        
        content.append(info_box)
        
        # Password entry with toggle button
        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        entry_box.set_halign(Gtk.Align.CENTER)
        
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("输入密码")
        self.entry.set_visibility(False)
        self.entry.set_size_request(config.scaled(400), -1)
        entry_box.append(self.entry)
        
        # Show/hide password toggle
        toggle_btn = Gtk.Button()
        toggle_btn.set_icon_name("view-conceal-symbolic")
        toggle_btn.set_size_request(config.scaled(45), config.scaled(45))
        toggle_btn.set_tooltip_text("显示/隐藏密码")
        toggle_btn.connect("clicked", self._toggle_visibility)
        self.toggle_btn = toggle_btn
        entry_box.append(toggle_btn)
        
        content.append(entry_box)
        
        # Virtual keyboard
        self.keyboard = VirtualKeyboard(self.entry, self.dialog)
        content.append(self.keyboard.get_widget())
        
        # Status label (for connection feedback)
        self.status_label = Gtk.Label()
        self.status_label.set_wrap(True)
        content.append(self.status_label)
        
        # Spinner (hidden by default)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(config.scaled(32), config.scaled(32))
        self.spinner.set_visible(False)
        content.append(self.spinner)
        
        # Dialog buttons
        cancel_btn = self.dialog.add_button("取消", Gtk.ResponseType.CANCEL)
        connect_btn = self.dialog.add_button("连接", Gtk.ResponseType.OK)
        
        # Style buttons
        cancel_btn.set_size_request(config.scaled(150), config.scaled(44))
        cancel_btn.set_margin_end(config.scaled(8))
        
        connect_btn.set_size_request(config.scaled(150), config.scaled(44))
        connect_btn.set_margin_start(config.scaled(8))
        connect_btn.set_margin_end(config.scaled(30))
        connect_btn.add_css_class("suggested-action")
        
        # Store button references
        self.cancel_btn = cancel_btn
        self.connect_btn = connect_btn
        
        # Connect response signal
        self.dialog.connect("response", self._on_response)
    
    def show(self):
        """Show the dialog"""
        self.dialog.present()
    
    def close(self):
        """Close the dialog"""
        self.dialog.close()
    
    def set_connecting(self, connecting):
        """
        Set connecting state (disable buttons, show spinner)
        
        Args:
            connecting: True if connecting, False otherwise
        """
        self.cancel_btn.set_sensitive(not connecting)
        self.connect_btn.set_sensitive(not connecting)
        self.entry.set_sensitive(not connecting)
        
        if connecting:
            self.spinner.set_visible(True)
            self.spinner.start()
            self.status_label.set_text("正在连接...")
        else:
            self.spinner.stop()
            self.spinner.set_visible(False)
            self.status_label.set_text("")
    
    def show_error(self, message):
        """
        Show error message in dialog
        
        Args:
            message: Error message to display
        """
        self.status_label.set_markup(f'<span foreground="red">{message}</span>')
        self.cancel_btn.set_sensitive(True)
        self.connect_btn.set_sensitive(True)
        self.entry.set_sensitive(True)
        self.spinner.stop()
        self.spinner.set_visible(False)
    
    def _toggle_visibility(self, button):
        """Toggle password visibility"""
        self.password_visible = not self.password_visible
        self.entry.set_visibility(self.password_visible)
        
        if self.password_visible:
            button.set_icon_name("view-reveal-symbolic")
        else:
            button.set_icon_name("view-conceal-symbolic")
    
    def _on_response(self, dialog, response):
        """Handle dialog response"""
        if response == Gtk.ResponseType.OK:
            password = self.entry.get_text()
            self.callback(password)
        else:
            # Cancel button - close dialog and call callback with None
            self.callback(None)
            self.close()


class ConnectingDialog:
    """Simple connecting progress dialog"""
    
    def __init__(self, parent, ssid):
        """
        Initialize connecting dialog
        
        Args:
            parent: Parent window
            ssid: Network SSID
        """
        self.dialog = Gtk.Dialog(title="连接中")
        self.dialog.set_transient_for(parent)
        self.dialog.set_modal(True)
        self.dialog.set_default_size(config.scaled(300), config.scaled(150))
        
        content = self.dialog.get_content_area()
        content.set_margin_top(config.scaled(20))
        content.set_margin_bottom(config.scaled(20))
        content.set_margin_start(config.scaled(20))
        content.set_margin_end(config.scaled(20))
        content.set_spacing(config.scaled(15))
        
        # Message
        label = Gtk.Label(label=f"正在连接到 {ssid}")
        label.set_wrap(True)
        content.append(label)
        
        sub_label = Gtk.Label(label="请稍候...")
        sub_label.add_css_class("dim-label")
        content.append(sub_label)
        
        # Spinner
        spinner = Gtk.Spinner()
        spinner.set_size_request(config.scaled(32), config.scaled(32))
        spinner.start()
        content.append(spinner)
    
    def show(self):
        """Show the dialog"""
        self.dialog.present()
    
    def close(self):
        """Close the dialog"""
        self.dialog.close()


def show_message_dialog(parent, title, message, message_type="info"):
    """
    Show a simple message dialog
    
    Args:
        parent: Parent window
        title: Dialog title
        message: Message text
        message_type: "info", "error", or "success"
    """
    dialog = Gtk.Dialog(title=title)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)
    dialog.set_default_size(config.scaled(350), config.scaled(150))
    
    content = dialog.get_content_area()
    content.set_margin_top(config.scaled(20))
    content.set_margin_bottom(config.scaled(20))
    content.set_margin_start(config.scaled(20))
    content.set_margin_end(config.scaled(20))
    content.set_spacing(config.scaled(15))
    
    # Icon + title
    title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    title_box.set_halign(Gtk.Align.CENTER)
    
    if message_type == "error":
        icon_name = "dialog-error-symbolic"
    elif message_type == "success":
        icon_name = "object-select-symbolic"
    else:
        icon_name = "dialog-information-symbolic"
    
    icon = Gtk.Image.new_from_icon_name(icon_name)
    icon.set_pixel_size(config.scaled(32))
    title_box.append(icon)
    
    title_label = Gtk.Label(label=title)
    title_label.add_css_class("title-2")
    title_box.append(title_label)
    
    content.append(title_box)
    
    # Message
    message_label = Gtk.Label(label=message)
    message_label.set_wrap(True)
    content.append(message_label)
    
    # OK button
    ok_btn = dialog.add_button("确定", Gtk.ResponseType.OK)
    ok_btn.set_size_request(config.scaled(100), config.scaled(40))
    ok_btn.add_css_class("suggested-action")
    
    dialog.connect("response", lambda d, r: d.close())
    dialog.present()

