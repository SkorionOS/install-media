"""
Version selection page (Install mode, Channel, Desktop, NVIDIA driver)
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
                'install_mode': 'online',  # 'online' or 'local'
                'local_file': None,        # Selected local file path
                'channel': 'stable',
                'desktop': 'gnome',
                'nvidia': False
            }
        
        self.config_label = None
        self.dynamic_content_box = None
    
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
        # Top section: Install mode + Config + Advanced options (no info-box, compact)
        top_section = self._create_top_section()
        content_box.append(top_section)
        
        # Dynamic content container (version selection)
        self.dynamic_content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=config.scaled(10)
        )
        self.dynamic_content_box.set_margin_top(config.scaled(8))
        content_box.append(self.dynamic_content_box)
        
        # Fill dynamic content based on current mode
        self._update_dynamic_content()
    
    def _create_top_section(self):
        """Create top section with install mode, config, and advanced options (no info-box)."""
        # Check if local files are available
        has_local_files = (
            hasattr(self.app, 'local_frzr_files') 
            and len(self.app.local_frzr_files) > 0
        )
        
        # Container (no info-box styling)
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(8))
        container.set_halign(Gtk.Align.CENTER)
        
        # Row 1: Install mode
        mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(15))
        
        # Title
        title = Gtk.Label()
        title.set_markup('<span weight="bold">安装方式</span>')
        title.set_xalign(0)
        title.set_size_request(config.scaled(100), -1)
        mode_row.append(title)
        
        # Buttons
        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(30))
        
        # Online option
        online_btn = Gtk.CheckButton(label="在线安装")
        online_btn.set_active(self.app.version_selections['install_mode'] == 'online')
        online_btn.connect("toggled", lambda b: self._on_install_mode_changed('online') if b.get_active() else None)
        buttons_box.append(online_btn)
        
        first_btn = online_btn
        
        # Local option (always show, but disabled if no local files)
        local_btn = Gtk.CheckButton(label="本地安装")
        local_btn.set_group(first_btn)
        if has_local_files:
            local_btn.set_active(self.app.version_selections['install_mode'] == 'local')
            local_btn.connect("toggled", lambda b: self._on_install_mode_changed('local') if b.get_active() else None)
        else:
            local_btn.set_sensitive(False)
            local_btn.set_tooltip_text("没有检测到本地安装文件")
        buttons_box.append(local_btn)
        
        mode_row.append(buttons_box)
        container.append(mode_row)
        
        # Row 2: Current config + Advanced options
        config_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(30))
        config_row.set_halign(Gtk.Align.CENTER)
        
        # Current configuration label
        self.config_label = Gtk.Label()
        target = self._build_target(self.app.version_selections)
        self.config_label.set_markup(f'当前配置: <b>{target}</b>')
        config_row.append(self.config_label)
        
        # Advanced options checkbox
        self.advanced_check = Gtk.CheckButton(label="启用高级选项")
        self.advanced_check.set_active(self.app.use_advanced_options)
        self.advanced_check.connect("toggled", self._on_advanced_toggled)
        config_row.append(self.advanced_check)
        
        container.append(config_row)
        
        return container
    
    def _on_install_mode_changed(self, mode):
        """Handle install mode change."""
        print(f"[VERSION] install_mode = {mode}")
        self.app.version_selections['install_mode'] = mode
        
        # Update dynamic content
        self._update_dynamic_content()
        
        # Update config display
        self._update_config_display()
    
    def _update_dynamic_content(self):
        """Update dynamic content based on install mode."""
        # Clear existing content
        while child := self.dynamic_content_box.get_first_child():
            self.dynamic_content_box.remove(child)
        
        mode = self.app.version_selections.get('install_mode', 'online')
        
        if mode == 'online':
            self._show_online_options()
        else:
            self._show_local_file_list()
    
    def _show_online_options(self):
        """Show online installation options (channel, desktop, NVIDIA)."""
        # Selection container - horizontal layout (reduced spacing)
        selection_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))  # 15 → 10
        selection_box.set_halign(Gtk.Align.CENTER)
        
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
        
        self.dynamic_content_box.append(selection_box)
    
    def _show_local_file_list(self):
        """Show local file selection list."""
        local_files = getattr(self.app, 'local_frzr_files', [])
        
        if not local_files:
            # No local files - show message
            message_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(10))
            message_box.set_halign(Gtk.Align.CENTER)
            
            label = Gtk.Label()
            label.set_markup(
                '<span size="large">未找到本地镜像文件</span>\n'
                '<span size="small">请插入包含安装镜像的 USB 设备</span>'
            )
            label.set_justify(Gtk.Justification.CENTER)
            message_box.append(label)
            
            self.dynamic_content_box.append(message_box)
            return
        
        # Create file selection box
        file_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(10))
        file_box.set_halign(Gtk.Align.CENTER)
        
        # Title
        title_label = Gtk.Label()
        title_label.set_markup('<span size="large" weight="bold">选择镜像文件</span>')
        file_box.append(title_label)
        
        # File list with radio buttons
        list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(5))
        list_container.add_css_class("info-box")
        list_container.set_size_request(config.scaled(600), -1)
        
        first_btn = None
        for file_info in local_files:
            # Radio button
            if first_btn is None:
                btn = Gtk.CheckButton()
                first_btn = btn
                btn.set_active(True)  # Select first by default
                self.app.version_selections['local_file'] = file_info['path']
            else:
                btn = Gtk.CheckButton()
                btn.set_group(first_btn)
            
            # File info display
            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(2))
            
            # Filename
            filename_label = Gtk.Label(label=file_info['filename'])
            filename_label.set_xalign(0)
            info_box.append(filename_label)
            
            # Details (device + size)
            details_label = Gtk.Label()
            details_label.set_markup(
                f'<span size="small" foreground="#888">'
                f'设备: {file_info["device"]} | 大小: {file_info["size"]}'
                f'</span>'
            )
            details_label.set_xalign(0)
            details_label.set_margin_start(config.scaled(15))
            info_box.append(details_label)
            
            btn.set_child(info_box)
            
            # Connect signal
            file_path = file_info['path']
            btn.connect("toggled", lambda b, p=file_path: self._on_local_file_selected(b, p))
            
            list_container.append(btn)
        
        file_box.append(list_container)
        self.dynamic_content_box.append(file_box)
    
    def _on_local_file_selected(self, button, file_path):
        """Handle local file selection."""
        if button.get_active():
            print(f"[VERSION] Selected local file: {file_path}")
            self.app.version_selections['local_file'] = file_path
            self._update_config_display()
    
    def _update_config_display(self):
        """Update configuration display label."""
        if self.config_label:
            target = self._build_target(self.app.version_selections)
            self.config_label.set_markup(f'当前配置: <b>{target}</b>')
    
    def populate_buttons(self, button_box: Gtk.Box):
        """Populate the button area."""
        # Back button
        back_btn = UIComponents.create_button("返回", "go-previous-symbolic")
        back_btn.connect("clicked", lambda b: self.app.go_back())
        button_box.append(back_btn)
        
        # Exit button (go to complete page - cancelled)
        exit_btn = UIComponents.create_button("退出", "application-exit-symbolic")
        exit_btn.connect("clicked", lambda b: self._on_exit())
        button_box.append(exit_btn)
        
        # Continue button
        continue_btn = UIComponents.create_button("开始安装", "system-software-install-symbolic")
        continue_btn.add_css_class("suggested-action")
        continue_btn.connect("clicked", lambda b: self._on_continue())
        button_box.append(continue_btn)
    
    def _create_compact_section(self, title, options, current_value, on_change_callback):
        """
        Create a compact selection section (card style) using unified components.
        
        Args:
            title: Section title
            options: List of (value, label, description) tuples
            current_value: Currently selected value
            on_change_callback: Callback function(value)
        
        Returns:
            Gtk.Box: Selection section widget
        """
        # Card container (reduced spacing)
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(5))  # 8 → 5
        section.add_css_class("info-box")
        section.set_size_request(config.scaled(220), -1)
        
        # Title
        title_label = Gtk.Label()
        title_label.set_markup(f'<span weight="bold">{title}</span>')
        title_label.set_xalign(0.5)
        section.append(title_label)
        
        # Separator (reduced margins)
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(config.scaled(3))  # 5 → 3
        separator.set_margin_bottom(config.scaled(3))  # 5 → 3
        section.append(separator)
        
        # Radio buttons using unified component
        first_btn = None
        for value, label, description in options:
            # Use unified UIComponents.create_selection_button for consistent styling
            btn = UIComponents.create_selection_button(
                group=first_btn,
                title=label,
                description=description,
                orientation=Gtk.Orientation.VERTICAL
            )
            
            if first_btn is None:
                first_btn = btn
            
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
        self._update_config_display()
    
    def _build_target(self, selections):
        """Build TARGET string from selections."""
        mode = selections.get('install_mode', 'online')
        
        if mode == 'local':
            # Local installation - show filename
            local_file = selections.get('local_file')
            if local_file:
                import os
                filename = os.path.basename(local_file)
                return f"本地镜像: {filename}"
            else:
                return "本地安装 (未选择文件)"
        else:
            # Online installation - show channel:desktop configuration
            channel = selections['channel']
            desktop = selections['desktop']
            nvidia = selections['nvidia']
            
            if nvidia:
                return f"{channel}:{desktop}-nv"
            else:
                return f"{channel}:{desktop}"
    
    def _on_advanced_toggled(self, checkbox):
        """Handle advanced options toggle."""
        self.app.use_advanced_options = checkbox.get_active()
        print(f"[VERSION] Advanced options: {self.app.use_advanced_options}")
    
    def _on_exit(self):
        """Handle exit button - go to complete page with CANCELLED status."""
        from .complete import CompletePage
        print("[VERSION] User requested exit")
        self.app.show_complete_page(
            CompletePage.STATUS_CANCELLED,
            "安装已取消",
            "您在版本选择页面选择了退出安装"
        )
    
    def _on_continue(self):
        """Handle continue button."""
        target = self._build_target(self.app.version_selections)
        print(f"[VERSION] Selected target: {target}")
        
        # Store target for installation
        self.app.install_target = target
        
        # Check if advanced options enabled
        if self.app.use_advanced_options:
            # Go to advanced options page
            self.app.show_page('advanced')
        else:
            # Go directly to installation page
            self.app.show_page('install')


def create_version_page(app):
    """Create the version selection page using the new page architecture."""
    page = VersionPage(app)
    return page.create()
