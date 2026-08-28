"""
Generic message page for warnings, errors, and confirmations.
Provides a unified interface for displaying various types of messages to the user.
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from ...config import config
from ..components.base import BasePage, UIComponents


class MessagePage(BasePage):
    """Generic message page that can display warnings, errors, and confirmations."""
    
    # Message types (semantic categories)
    TYPE_CONFIRM = "confirm"      # Confirmation (orange warning icon)
    TYPE_WARNING = "warning"      # Warning (orange warning icon)
    TYPE_ERROR = "error"          # Error (red error icon)
    
    def __init__(self, app):
        super().__init__(app)
        # Default values
        self.message_type = self.TYPE_WARNING
        self.icon_name = "dialog-warning-symbolic"
        self.title_text = ""
        self.title_color = "orange"
        self.main_message = ""
        self.details_list = []  # Left-aligned bullet points
        self.additional_warning = ""  # Centered additional text (usually red/orange)
        self.question = ""  # Final question (centered)
        self.buttons_config = []  # List of (label, icon, callback, css_class) tuples
    
    def configure(self, message_type=None, icon=None, title=None, 
                  color=None, main_msg=None, details=None, 
                  additional=None, question=None, buttons=None):
        """
        Configure the message page (builder pattern).
        
        Args:
            message_type: TYPE_CONFIRM, TYPE_WARNING, or TYPE_ERROR
            icon: Icon name (e.g., "dialog-warning-symbolic")
            title: Title text
            color: Title color (e.g., "orange", "red")
            main_msg: Main message (centered, can be multiline)
            details: List of detail lines (left-aligned) or single string
            additional: Additional warning text (centered)
            question: Question text (centered)
            buttons: List of (label, icon, callback, css_class) tuples
        
        Returns:
            self (for chaining)
        """
        if message_type:
            self.message_type = message_type
        if icon:
            self.icon_name = icon
        if title:
            self.title_text = title
        if color:
            self.title_color = color
        if main_msg:
            self.main_message = main_msg
        # Reused MessagePage must not leak bullets/warnings from the previous gate.
        self.details_list = []
        self.additional_warning = ""
        self.question = ""
        if details is not None:
            self.details_list = details if isinstance(details, list) else [details]
        if additional:
            self.additional_warning = additional
        if question:
            self.question = question
        if buttons:
            self.buttons_config = buttons
        
        # Reload content if page already created
        if hasattr(self, '_content_box') and self._content_box:
            # Clear content
            child = self._content_box.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self._content_box.remove(child)
                child = next_child
            # Repopulate
            self.populate_content(self._content_box)
            
            # Clear and repopulate buttons
            child = self._button_box.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self._button_box.remove(child)
                child = next_child
            self.populate_buttons(self._button_box)
        
        return self
    
    def create_title(self) -> Gtk.Widget:
        """Create icon + title layout."""
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
        title_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name(self.icon_name)
        icon.set_pixel_size(config.scaled(64))
        title_box.append(icon)
        
        title = Gtk.Label()
        title.set_markup(f'<span size="xx-large" weight="bold" foreground="{self.title_color}">{self.title_text}</span>')
        title_box.append(title)
        
        return title_box
    
    def populate_content(self, content_box: Gtk.Box):
        """Populate page content."""
        content_box.set_halign(Gtk.Align.CENTER)
        
        # Main message (centered)
        if self.main_message:
            main_label = Gtk.Label()
            main_label.set_markup(self.main_message)
            main_label.set_justify(Gtk.Justification.CENTER)
            main_label.set_wrap(True)
            content_box.append(main_label)
        
        # Details (left-aligned)
        if self.details_list:
            details_text = '\n'.join(self.details_list)
            details_label = Gtk.Label()
            details_label.set_markup(details_text)
            details_label.set_justify(Gtk.Justification.LEFT)
            details_label.set_halign(Gtk.Align.START)
            details_label.set_wrap(True)
            content_box.append(details_label)
        
        # Additional warning (centered)
        if self.additional_warning:
            warning_label = Gtk.Label()
            warning_label.set_markup(self.additional_warning)
            warning_label.set_justify(Gtk.Justification.CENTER)
            warning_label.set_wrap(True)
            content_box.append(warning_label)
        
        # Question (centered)
        if self.question:
            question_label = Gtk.Label()
            question_label.set_markup(f'<span size="large">{self.question}</span>')
            question_label.set_justify(Gtk.Justification.CENTER)
            question_label.set_margin_top(config.scaled(10))
            question_label.set_wrap(True)
            content_box.append(question_label)
    
    def populate_buttons(self, button_box: Gtk.Box):
        """Populate button area based on configuration."""
        for btn_config in self.buttons_config:
            label, icon, callback, css_class = btn_config
            btn = UIComponents.create_button(label, icon)
            if css_class:
                btn.add_css_class(css_class)
            btn.connect("clicked", callback)
            button_box.append(btn)


def create_message_page(app):
    """Create the message page using the configured instance."""
    # Use the already configured message page instance
    if not hasattr(app, '_message_page') or not app._message_page:
        # Fallback: create new instance if not exists
        app._message_page = MessagePage(app)
    
    return app._message_page.create()

