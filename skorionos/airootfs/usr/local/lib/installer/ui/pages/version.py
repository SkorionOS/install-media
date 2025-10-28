"""
Version selection page (Channel, Desktop, NVIDIA driver)
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from ...config import config


def create_version_page(app):
    """
    Create version selection page
    
    Args:
        app: Main application instance
    
    Returns:
        Gtk.Box: Version page widget
    """
    # Main box with less spacing
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_halign(Gtk.Align.FILL)
    box.set_valign(Gtk.Align.FILL)
    box.set_margin_start(config.scaled(40))
    box.set_margin_end(config.scaled(40))
    box.set_margin_top(config.scaled(20))
    box.set_margin_bottom(config.scaled(20))
    
    # Title with icon
    title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    title_box.set_halign(Gtk.Align.CENTER)
    
    version_icon = Gtk.Image.new_from_icon_name("view-list-symbolic")
    version_icon.set_icon_size(Gtk.IconSize.LARGE)
    version_icon.set_pixel_size(config.scaled(48))
    title_box.append(version_icon)
    
    title = Gtk.Label()
    title.set_markup('<span size="x-large" weight="bold">版本选择</span>')
    title_box.append(title)
    
    box.append(title_box)
    
    # Selection container - horizontal layout for better space usage
    selection_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
    selection_box.set_halign(Gtk.Align.CENTER)
    selection_box.set_margin_top(config.scaled(10))
    
    # Initialize selections if not exist
    if not hasattr(app, 'version_selections'):
        app.version_selections = {
            'channel': 'stable',
            'desktop': 'gnome',
            'nvidia': False
        }
    
    # Section 1: Channel selection (vertical card)
    channel_section = _create_compact_section(
        "版本通道",
        [
            ('stable', '稳定版', '推荐日常使用'),
            ('testing', '测试版', '较新功能'),
            ('unstable', '不稳定版', '开发测试')
        ],
        app.version_selections['channel'],
        lambda value: _on_selection_changed(app, 'channel', value)
    )
    selection_box.append(channel_section)
    
    # Section 2: Desktop selection (vertical card)
    desktop_section = _create_compact_section(
        "桌面环境",
        [
            ('gnome', 'GNOME', '默认推荐'),
            ('kde', 'KDE Plasma', '类似 Steam Deck')
        ],
        app.version_selections['desktop'],
        lambda value: _on_selection_changed(app, 'desktop', value)
    )
    selection_box.append(desktop_section)
    
    # Section 3: NVIDIA driver selection (vertical card)
    nvidia_section = _create_compact_section(
        "NVIDIA 驱动",
        [
            (False, '标准版', '开源驱动'),
            (True, 'NV 版', '含 NVIDIA 专有驱动')
        ],
        app.version_selections['nvidia'],
        lambda value: _on_selection_changed(app, 'nvidia', value)
    )
    selection_box.append(nvidia_section)
    
    box.append(selection_box)
    
    # Show selected configuration - compact
    config_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    config_box.set_halign(Gtk.Align.CENTER)
    config_box.set_margin_top(config.scaled(10))
    
    config_label = Gtk.Label()
    target = _build_target(app.version_selections)
    config_label.set_markup(f'<span size="large">当前配置: <b>{target}</b></span>')
    app.config_label = config_label
    config_box.append(config_label)
    
    box.append(config_box)
    
    # Navigation buttons
    btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    btn_box.set_halign(Gtk.Align.CENTER)
    
    back_btn = Gtk.Button(label="返回")
    back_btn.set_icon_name("go-previous-symbolic")
    back_btn.add_css_class("nav-button")
    back_btn.connect("clicked", lambda b: app.go_back())
    btn_box.append(back_btn)
    
    # Continue button
    continue_btn = Gtk.Button(label="继续安装")
    continue_btn.set_icon_name("go-next-symbolic")
    continue_btn.add_css_class("nav-button")
    continue_btn.add_css_class("suggested-action")
    continue_btn.connect("clicked", lambda b: _on_continue(app))
    btn_box.append(continue_btn)
    
    box.append(btn_box)
    
    return box


def _create_compact_section(title, options, current_value, on_change_callback):
    """
    Create a compact selection section (card style)
    
    Args:
        title: Section title
        options: List of (value, label, description) tuples
        current_value: Currently selected value
        on_change_callback: Callback function(value)
    
    Returns:
        Gtk.Box: Selection section widget
    """
    # Card container
    section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
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
        # Option container
        option_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        # Radio button
        if first_btn is None:
            btn = Gtk.CheckButton(label=label)
            first_btn = btn
        else:
            btn = Gtk.CheckButton(label=label)
            btn.set_group(first_btn)
        
        # Set active if current value
        if value == current_value:
            btn.set_active(True)
        
        # Connect signal
        btn.connect("toggled", lambda b, v=value: on_change_callback(v) if b.get_active() else None)
        
        option_box.append(btn)
        
        # Description - small, grey, indented
        desc_label = Gtk.Label(label=description)
        desc_label.set_xalign(0)
        desc_label.set_margin_start(config.scaled(25))
        desc_label.set_wrap(True)
        desc_label.set_max_width_chars(20)
        desc_label.add_css_class("dim-label")
        desc_label.set_markup(f'<span size="small" foreground="#888">{description}</span>')
        option_box.append(desc_label)
        
        section.append(option_box)
    
    return section


def _on_selection_changed(app, key, value):
    """Handle selection change"""
    print(f"[VERSION] {key} = {value}")
    app.version_selections[key] = value
    
    # Update config label
    if hasattr(app, 'config_label'):
        target = _build_target(app.version_selections)
        app.config_label.set_markup(
            f'<span foreground="#aaa">当前配置: <b>{target}</b></span>'
        )


def _build_target(selections):
    """Build TARGET string from selections"""
    channel = selections['channel']
    desktop = selections['desktop']
    nvidia = selections['nvidia']
    
    if nvidia:
        return f"{channel}:{desktop}-nv"
    else:
        return f"{channel}:{desktop}"


def _on_continue(app):
    """Handle continue button"""
    target = _build_target(app.version_selections)
    print(f"[VERSION] Selected target: {target}")
    
    # Store target for installation
    app.install_target = target
    
    # Go to installation page (page 3)
    app.show_page(3)

