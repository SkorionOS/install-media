"""
Installation progress page
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import subprocess
import threading

from ...config import config


def create_install_page(app):
    """
    Create installation progress page
    
    Args:
        app: Main application instance
    
    Returns:
        Gtk.Box: Installation page widget
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
    box.set_halign(Gtk.Align.CENTER)
    box.set_valign(Gtk.Align.CENTER)
    box.add_css_class("page-container")
    
    # Title with icon
    title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    title_box.set_halign(Gtk.Align.CENTER)
    
    icon = Gtk.Image.new_from_icon_name("system-software-install-symbolic")
    icon.set_icon_size(Gtk.IconSize.LARGE)
    icon.set_pixel_size(config.scaled(48))
    title_box.append(icon)
    
    title = Gtk.Label()
    title.set_markup('<span size="xx-large" weight="bold">安装 SkorionOS</span>')
    title_box.append(title)
    
    box.append(title_box)
    
    # Target info
    if hasattr(app, 'install_target'):
        target_label = Gtk.Label()
        target_label.set_markup(
            f'<span size="large">版本配置: <b>{app.install_target}</b></span>'
        )
        box.append(target_label)
    
    # Progress box
    progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
    progress_box.add_css_class("info-box")
    progress_box.set_size_request(config.scaled(900), -1)
    
    # Status label
    status_label = Gtk.Label(label="准备开始安装...")
    status_label.set_wrap(True)
    progress_box.append(status_label)
    app.install_status_label = status_label
    
    # Progress bar
    progress_bar = Gtk.ProgressBar()
    progress_bar.set_show_text(True)
    progress_box.append(progress_bar)
    app.install_progress_bar = progress_bar
    
    # Log view (scrollable)
    scroll = Gtk.ScrolledWindow()
    scroll.set_size_request(config.scaled(900), config.scaled(300))
    
    log_view = Gtk.TextView()
    log_view.set_editable(False)
    log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    log_view.set_monospace(True)
    log_view.add_css_class("log-view")
    
    buffer = log_view.get_buffer()
    app.install_log_buffer = buffer
    
    scroll.set_child(log_view)
    progress_box.append(scroll)
    
    box.append(progress_box)
    
    # Buttons
    btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    btn_box.set_halign(Gtk.Align.CENTER)
    
    # Cancel button (only visible before installation starts)
    cancel_btn = Gtk.Button(label="取消")
    cancel_btn.set_icon_name("process-stop-symbolic")
    cancel_btn.add_css_class("nav-button")
    cancel_btn.connect("clicked", lambda b: app.go_back())
    btn_box.append(cancel_btn)
    app.install_cancel_btn = cancel_btn
    
    # Start button
    start_btn = Gtk.Button(label="开始安装")
    start_btn.set_icon_name("media-playback-start-symbolic")
    start_btn.add_css_class("nav-button")
    start_btn.add_css_class("suggested-action")
    start_btn.connect("clicked", lambda b: _start_installation(app))
    btn_box.append(start_btn)
    app.install_start_btn = start_btn
    
    # Finish button (hidden initially)
    finish_btn = Gtk.Button(label="完成")
    finish_btn.set_icon_name("object-select-symbolic")
    finish_btn.add_css_class("nav-button")
    finish_btn.add_css_class("suggested-action")
    finish_btn.set_visible(False)
    finish_btn.connect("clicked", lambda b: _on_install_complete(app))
    btn_box.append(finish_btn)
    app.install_finish_btn = finish_btn
    
    box.append(btn_box)
    
    return box


def _start_installation(app):
    """Start the installation process"""
    print("[INSTALL] Starting installation...")
    
    # Disable start and cancel buttons
    app.install_start_btn.set_sensitive(False)
    app.install_cancel_btn.set_sensitive(False)
    
    # Update status
    app.install_status_label.set_text("正在安装...")
    app.install_progress_bar.set_fraction(0.0)
    app.install_progress_bar.set_text("0%")
    
    # Clear log
    app.install_log_buffer.set_text("")
    
    # Start installation in background thread
    def install_thread():
        try:
            _run_installation(app)
        except Exception as e:
            print(f"[INSTALL] Error: {e}")
            GLib.idle_add(lambda: _on_install_error(app, str(e)))
    
    thread = threading.Thread(target=install_thread)
    thread.daemon = True
    thread.start()


def _run_installation(app):
    """Run the actual installation (placeholder)"""
    # Get target
    target = getattr(app, 'install_target', 'stable:gnome')
    
    _append_log(app, f"[INFO] Target version: {target}\n")
    _append_log(app, "[INFO] This is a PoC version - installation is simulated\n")
    _append_log(app, "[INFO] In production, this would call /root/install.sh\n\n")
    
    # Simulate installation steps
    steps = [
        (0.2, "检查系统环境..."),
        (0.4, "准备安装文件..."),
        (0.6, "下载系统镜像..."),
        (0.8, "安装系统文件..."),
        (1.0, "配置系统..."),
    ]
    
    import time
    for progress, message in steps:
        time.sleep(2)  # Simulate work
        _append_log(app, f"[STEP] {message}\n")
        GLib.idle_add(lambda p=progress, m=message: _update_progress(app, p, m))
    
    # Installation complete
    GLib.idle_add(lambda: _on_install_success(app))


def _update_progress(app, fraction, message):
    """Update progress bar and status"""
    app.install_progress_bar.set_fraction(fraction)
    app.install_progress_bar.set_text(f"{int(fraction * 100)}%")
    app.install_status_label.set_text(message)


def _append_log(app, text):
    """Append text to log buffer (thread-safe)"""
    def append():
        end_iter = app.install_log_buffer.get_end_iter()
        app.install_log_buffer.insert(end_iter, text)
    
    GLib.idle_add(append)


def _on_install_success(app):
    """Handle successful installation"""
    print("[INSTALL] Installation completed successfully")
    
    app.install_status_label.set_text("安装完成！")
    app.install_progress_bar.set_fraction(1.0)
    app.install_progress_bar.set_text("100%")
    
    _append_log(app, "\n[SUCCESS] Installation completed!\n")
    _append_log(app, "[INFO] You can now reboot the system\n")
    
    # Show finish button
    app.install_start_btn.set_visible(False)
    app.install_cancel_btn.set_visible(False)
    app.install_finish_btn.set_visible(True)


def _on_install_error(app, error_msg):
    """Handle installation error"""
    print(f"[INSTALL] Installation failed: {error_msg}")
    
    app.install_status_label.set_markup(
        f'<span foreground="red">安装失败: {error_msg}</span>'
    )
    
    _append_log(app, f"\n[ERROR] {error_msg}\n")
    
    # Re-enable buttons
    app.install_start_btn.set_sensitive(True)
    app.install_cancel_btn.set_sensitive(True)


def _on_install_complete(app):
    """Handle completion (close or reboot)"""
    print("[INSTALL] Exiting installer")
    
    # In production, this would offer to reboot
    # For now, just close the window
    app.close()

