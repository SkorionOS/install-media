"""
Disk selection page (placeholder)
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from ...config import config


def create_disk_page(app):
    """
    Create disk selection page (placeholder)
    
    Args:
        app: Main application instance
    
    Returns:
        Gtk.Box: Disk page widget
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
    box.set_halign(Gtk.Align.CENTER)
    box.set_valign(Gtk.Align.CENTER)
    box.add_css_class("page-container")
    
    # Icon
    icon = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic")
    icon.set_icon_size(Gtk.IconSize.LARGE)
    icon.set_pixel_size(config.scaled(96))
    box.append(icon)
    
    # Title
    title = Gtk.Label()
    title.set_markup('<span size="xx-large" weight="bold">磁盘选择</span>')
    box.append(title)
    
    # Subtitle
    subtitle = Gtk.Label()
    subtitle.set_markup('<span size="large" foreground="#aaa">此页面正在开发中</span>')
    box.append(subtitle)
    
    # Info box
    info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    info_box.add_css_class("info-box")
    info_box.set_size_request(config.scaled(600), -1)
    
    features = [
        "• 检测系统磁盘",
        "• 选择安装目标",
        "• 分区方案配置",
        "• 安全检查"
    ]
    
    for feature in features:
        label = Gtk.Label(label=feature)
        label.set_xalign(0)
        info_box.append(label)
    
    box.append(info_box)
    
    # Navigation buttons
    btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    btn_box.set_halign(Gtk.Align.CENTER)
    
    back_btn = Gtk.Button(label="返回")
    back_btn.set_icon_name("go-previous-symbolic")
    back_btn.add_css_class("nav-button")
    back_btn.connect("clicked", lambda b: app.go_back())
    btn_box.append(back_btn)
    
    # Restart button
    restart_btn = Gtk.Button(label="重新开始")
    restart_btn.set_icon_name("view-refresh-symbolic")
    restart_btn.add_css_class("nav-button")
    restart_btn.connect("clicked", lambda b: app.restart_wizard())
    btn_box.append(restart_btn)
    
    box.append(btn_box)
    
    return box

