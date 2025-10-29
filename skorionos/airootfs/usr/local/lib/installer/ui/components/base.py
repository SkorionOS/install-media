"""
Base page components and classes for the installer UI.
Provides reusable UI components and base page architecture to reduce code duplication.
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import threading
from typing import Optional, Callable, Dict, Any
from ...config import config


class UIComponents:
    """Factory class for creating common UI components with consistent styling."""
    
    @staticmethod
    def create_title(text: str, css_class: str = "page-title") -> Gtk.Label:
        """Create a page title label."""
        label = Gtk.Label()
        label.set_markup(f'<span size="xx-large" weight="bold">{text}</span>')
        label.add_css_class(css_class)
        label.set_halign(Gtk.Align.CENTER)
        return label
    
    @staticmethod
    def create_status_label(text: str = "", size: str = "large") -> Gtk.Label:
        """Create a status label for displaying operation status."""
        label = Gtk.Label()
        if text:
            label.set_markup(f'<span size="{size}">{text}</span>')
        label.set_halign(Gtk.Align.CENTER)
        return label
    
    @staticmethod
    def create_progress_bar() -> Gtk.ProgressBar:
        """Create a progress bar with consistent sizing."""
        progress = Gtk.ProgressBar()
        progress.set_show_text(True)
        progress.set_size_request(config.scaled(600), config.scaled(30))
        progress.set_halign(Gtk.Align.CENTER)
        return progress
    
    @staticmethod
    def create_scrolled_text_view(
        editable: bool = False,
        monospace: bool = True,
        wrap_mode: Gtk.WrapMode = Gtk.WrapMode.WORD_CHAR
    ) -> tuple[Gtk.ScrolledWindow, Gtk.TextView, Gtk.TextBuffer]:
        """
        Create a scrolled text view for displaying logs or text content.
        Returns: (scrolled_window, text_view, text_buffer)
        """
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_size_request(config.scaled(700), config.scaled(300))
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        text_view = Gtk.TextView()
        text_view.set_editable(editable)
        text_view.set_cursor_visible(editable)
        text_view.set_wrap_mode(wrap_mode)
        text_view.set_left_margin(config.scaled(10))
        text_view.set_right_margin(config.scaled(10))
        text_view.set_top_margin(config.scaled(10))
        text_view.set_bottom_margin(config.scaled(10))
        
        if monospace:
            text_view.add_css_class("monospace")
        
        text_buffer = text_view.get_buffer()
        scrolled.set_child(text_view)
        
        return scrolled, text_view, text_buffer
    
    @staticmethod
    def create_button(
        label: str,
        icon_name: Optional[str] = None,
        css_class: str = "nav-button"
    ) -> Gtk.Button:
        """Create a button with optional icon and consistent styling."""
        button = Gtk.Button()
        
        if icon_name:
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(8))
            box.set_halign(Gtk.Align.CENTER)  # Center the content horizontally
            icon = Gtk.Image.new_from_icon_name(icon_name)
            label_widget = Gtk.Label(label=label)
            box.append(icon)
            box.append(label_widget)
            button.set_child(box)
        else:
            button.set_label(label)
        
        button.add_css_class(css_class)
        return button
    
    @staticmethod
    def create_button_box(
        spacing: int = 10,
        homogeneous: bool = False
    ) -> Gtk.Box:
        """Create a horizontal box for holding buttons."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(spacing))
        box.set_homogeneous(homogeneous)
        box.set_halign(Gtk.Align.CENTER)
        return box
    
    @staticmethod
    def create_selection_button(
        group: Optional[Gtk.CheckButton],
        title: str,
        description: Optional[str] = None,
        orientation: Gtk.Orientation = Gtk.Orientation.VERTICAL
    ) -> Gtk.CheckButton:
        """
        Create a radio button for selection lists (disk, mode, etc.) with consistent styling.
        
        Args:
            group: Group button (None for first button in group)
            title: Main title text (will be bold)
            description: Optional description text (can be None)
            orientation: Box orientation (VERTICAL for stacked, HORIZONTAL for side-by-side)
        
        Returns:
            Gtk.CheckButton: Configured radio button with consistent margins
        """
        if group is None:
            btn = Gtk.CheckButton()
        else:
            btn = Gtk.CheckButton()
            btn.set_group(group)
        
        # Content box with consistent margins
        spacing = config.scaled(4) if orientation == Gtk.Orientation.VERTICAL else config.scaled(10)
        content_box = Gtk.Box(orientation=orientation, spacing=spacing)
        content_box.set_margin_start(config.scaled(10))
        content_box.set_margin_end(config.scaled(10))
        content_box.set_margin_top(config.scaled(8))
        content_box.set_margin_bottom(config.scaled(8))
        
        # Title
        title_label = Gtk.Label()
        title_label.set_markup(f'<b>{title}</b>')
        title_label.set_xalign(0)
        title_label.set_wrap(True)
        content_box.append(title_label)
        
        # Description (optional)
        if description:
            desc_label = Gtk.Label(label=description)
            desc_label.set_xalign(0)
            desc_label.set_wrap(True)
            desc_label.add_css_class("dim-label")
            content_box.append(desc_label)
        
        btn.set_child(content_box)
        return btn


class BasePage:
    """
    Base class for all installer pages.
    Provides consistent structure: title at top, content in middle, buttons at bottom.
    """
    
    def __init__(self, app):
        self.app = app
        self._page_box = None
        self._content_box = None
        self._button_box = None
    
    def create(self) -> Gtk.Box:
        """
        Create and return the page widget.
        Override this method to customize page layout.
        """
        # Main container
        self._page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(20))
        self._page_box.set_margin_top(config.scaled(20))
        self._page_box.set_margin_bottom(config.scaled(20))
        self._page_box.set_margin_start(config.scaled(20))
        self._page_box.set_margin_end(config.scaled(20))
        
        # Title (top)
        title = self.create_title()
        if title:
            self._page_box.append(title)
        
        # Content area (middle, expandable)
        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(15))
        self._content_box.set_vexpand(True)
        self._content_box.set_valign(Gtk.Align.FILL)
        self._content_box.set_margin_start(config.scaled(40))
        self._content_box.set_margin_end(config.scaled(40))
        self.populate_content(self._content_box)
        self._page_box.append(self._content_box)
        
        # Button box (bottom)
        self._button_box = UIComponents.create_button_box()
        self.populate_buttons(self._button_box)
        self._page_box.append(self._button_box)
        
        return self._page_box
    
    def create_title(self) -> Optional[Gtk.Widget]:
        """
        Create the page title widget.
        Override to provide custom title or return None for no title.
        """
        return None
    
    def populate_content(self, content_box: Gtk.Box):
        """
        Populate the content area.
        Override to add page-specific content.
        """
        pass
    
    def populate_buttons(self, button_box: Gtk.Box):
        """
        Populate the button area.
        Override to add page-specific buttons.
        """
        pass
    
    def get_page_box(self) -> Gtk.Box:
        """Get the main page container."""
        return self._page_box
    
    def get_content_box(self) -> Gtk.Box:
        """Get the content container."""
        return self._content_box
    
    def get_button_box(self) -> Gtk.Box:
        """Get the button container."""
        return self._button_box


class ExecutionPage(BasePage):
    """
    Base class for pages that execute long-running commands and show progress.
    Used by bootstrap and install pages.
    """
    
    def __init__(self, app):
        super().__init__(app)
        
        # UI components
        self.status_label: Optional[Gtk.Label] = None
        self.progress_bar: Optional[Gtk.ProgressBar] = None
        self.log_view: Optional[Gtk.TextView] = None
        self.log_buffer: Optional[Gtk.TextBuffer] = None
        self.scrolled_window: Optional[Gtk.ScrolledWindow] = None
        
        # Buttons
        self.back_btn: Optional[Gtk.Button] = None
        self.cancel_btn: Optional[Gtk.Button] = None
        self.exit_btn: Optional[Gtk.Button] = None
        self.start_btn: Optional[Gtk.Button] = None
        self.continue_btn: Optional[Gtk.Button] = None
        
        # State
        self.is_executing = False
        self.execution_completed = False
        self.execution_failed = False
        self.execution_thread: Optional[threading.Thread] = None
    
    def create_title(self) -> Optional[Gtk.Widget]:
        """Create page title - override to customize."""
        return UIComponents.create_title(self.get_title_text())
    
    def get_title_text(self) -> str:
        """Get the title text - override in subclass."""
        return "执行中"
    
    def populate_content(self, content_box: Gtk.Box):
        """Create the execution page content: status, progress, and log view."""
        # Status label
        self.status_label = UIComponents.create_status_label(self.get_initial_status_text())
        content_box.append(self.status_label)
        
        # Progress bar
        self.progress_bar = UIComponents.create_progress_bar()
        self.progress_bar.set_text(self.get_initial_progress_text())
        content_box.append(self.progress_bar)
        
        # Log view
        self.scrolled_window, self.log_view, self.log_buffer = UIComponents.create_scrolled_text_view()
        content_box.append(self.scrolled_window)
    
    def populate_buttons(self, button_box: Gtk.Box):
        """Create the button area."""
        # Back button (initially visible)
        self.back_btn = UIComponents.create_button("返回", "go-previous-symbolic")
        self.back_btn.connect("clicked", self.on_back_clicked)
        button_box.append(self.back_btn)
        
        # Cancel button (hidden initially, shown during execution)
        self.cancel_btn = UIComponents.create_button("取消", "process-stop-symbolic")
        self.cancel_btn.connect("clicked", self.on_cancel_clicked)
        self.cancel_btn.set_visible(False)
        button_box.append(self.cancel_btn)
        
        # Exit button (hidden initially, shown on error to allow closing the app)
        self.exit_btn = UIComponents.create_button("退出", "application-exit-symbolic")
        self.exit_btn.connect("clicked", self.on_exit_clicked)
        self.exit_btn.set_visible(False)
        button_box.append(self.exit_btn)
        
        # Start button (hidden initially, can be shown for manual start or retry)
        self.start_btn = UIComponents.create_button(self.get_start_button_text(), "system-run-symbolic")
        self.start_btn.connect("clicked", self.on_start_clicked)
        self.start_btn.set_visible(False)
        button_box.append(self.start_btn)
    
    def get_initial_status_text(self) -> str:
        """Get initial status text - override in subclass."""
        return "准备开始..."
    
    def get_initial_progress_text(self) -> str:
        """Get initial progress text - override in subclass."""
        return "等待中"
    
    def get_start_button_text(self) -> str:
        """Get start button text - override in subclass."""
        return "开始"
    
    def append_log(self, text: str):
        """Append text to log view with auto-scrolling."""
        if not self.log_buffer:
            return
        
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, text)
        
        # Auto-scroll to bottom
        if self.log_view:
            mark = self.log_buffer.get_insert()
            self.log_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
    
    def update_status(self, text: str, markup: bool = True):
        """Update status label."""
        if self.status_label:
            if markup:
                self.status_label.set_markup(text)
            else:
                self.status_label.set_text(text)
    
    def update_progress(self, fraction: float, text: str = ""):
        """Update progress bar."""
        if self.progress_bar:
            self.progress_bar.set_fraction(fraction)
            if text:
                self.progress_bar.set_text(text)
    
    def show_buttons(self, back: bool = False, cancel: bool = False, exit: bool = False, start: bool = False):
        """Show/hide buttons."""
        if self.back_btn:
            self.back_btn.set_visible(back)
        if self.cancel_btn:
            self.cancel_btn.set_visible(cancel)
        if self.exit_btn:
            self.exit_btn.set_visible(exit)
        if self.start_btn:
            self.start_btn.set_visible(start)
    
    def on_back_clicked(self, button):
        """Handle back button click."""
        self.app.go_back()
    
    def on_cancel_clicked(self, button):
        """Handle cancel button click - override to implement cancellation."""
        pass
    
    def on_exit_clicked(self, button):
        """Handle exit button click - go to complete page with CANCELLED status."""
        from ..pages.complete import CompletePage
        print(f"[{self.__class__.__name__}] User requested exit")
        self.app.show_complete_page(
            CompletePage.STATUS_CANCELLED,
            "安装已取消",
            f"您在{self.get_title_text()}页面选择了退出安装"
        )
    
    def on_start_clicked(self, button):
        """Handle start button click - override to implement execution start."""
        pass
    
    def start_execution(self):
        """Start the execution in a background thread."""
        if self.is_executing:
            return
        
        self.is_executing = True
        self.execution_completed = False
        self.execution_failed = False
        
        # Update UI
        self.show_buttons(back=False, cancel=True, exit=False, start=False)
        self.update_status(f'<span size="large">正在执行...</span>')
        self.update_progress(0.0, "进行中")
        
        # Clear log
        if self.log_buffer:
            self.log_buffer.set_text("")
        
        # Start execution thread
        self.execution_thread = threading.Thread(target=self.execute, daemon=True)
        self.execution_thread.start()
    
    def execute(self):
        """
        Execute the actual command/operation.
        Override this method in subclass to implement the actual work.
        """
        pass
    
    def on_execution_success(self):
        """
        Called when execution completes successfully.
        Override to customize success handling.
        """
        self.is_executing = False
        self.execution_completed = True
        
        GLib.idle_add(self._update_ui_on_success)
    
    def _update_ui_on_success(self):
        """Update UI on successful completion."""
        self.update_status('<span size="large" foreground="green" weight="bold">执行完成！</span>')
        self.update_progress(1.0, "完成")
        self.append_log(f"\n{'='*60}\n")
        self.append_log("✓ 执行成功完成\n")
        self.append_log(f"{'='*60}\n")
        
        # Replace cancel with continue button
        if self.cancel_btn:
            self.cancel_btn.set_visible(False)
        
        # Create and show continue button
        if self._button_box and not self.continue_btn:
            self.continue_btn = UIComponents.create_button("继续", "go-next-symbolic")
            self.continue_btn.connect("clicked", self.on_continue_clicked)
            self._button_box.append(self.continue_btn)
        
        if self.continue_btn:
            self.continue_btn.set_visible(True)
        
        return False
    
    def on_execution_error(self, error_msg: str):
        """
        Called when execution fails.
        Override to customize error handling.
        """
        self.is_executing = False
        self.execution_failed = True
        
        GLib.idle_add(self._update_ui_on_error, error_msg)
    
    def _update_ui_on_error(self, error_msg: str):
        """Update UI on error."""
        self.update_status(f'<span size="large" foreground="red" weight="bold">错误: {error_msg}</span>')
        self.update_progress(0.0, "失败")
        self.append_log(f"\n{'='*60}\n")
        self.append_log(f"✗ 执行失败: {error_msg}\n")
        self.append_log(f"{'='*60}\n")
        self.append_log("\n请查看上方日志了解详细错误信息\n")
        self.append_log("您可以：\n")
        self.append_log("• 点击「返回」返回上一步重新配置\n")
        self.append_log("• 点击「重试」重新执行\n")
        self.append_log("• 点击「退出」关闭安装程序\n")
        
        # Show back, start (retry), and exit buttons
        self.show_buttons(back=True, cancel=False, exit=True, start=True)
        
        # Update start button label to "重试"
        if self.start_btn:
            child = self.start_btn.get_child()
            if isinstance(child, Gtk.Box):
                label_widget = None
                widget = child.get_first_child()
                while widget:
                    if isinstance(widget, Gtk.Label):
                        label_widget = widget
                        break
                    widget = widget.get_next_sibling()
                if label_widget:
                    label_widget.set_text("重试")
        
        return False
    
    def on_continue_clicked(self, button):
        """
        Handle continue button click after successful execution.
        Override to implement navigation to next page.
        """
        pass

