"""
Disk selection page for the graphical installer - COMPLETE REWRITE
Supports: repair / fresh / dual-boot installation modes
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import threading
from ...config import config
from ...backend.disk_utils import (
    list_available_disks,
    check_existing_frzr_installation,
    check_free_space,
    list_shrinkable_partitions,
    is_disk_smaller_than,
    is_disk_external
)
from ..components.base import BasePage, UIComponents
from ...logger import get_logger

logger = get_logger('disk')


class DiskPage(BasePage):
    """Disk selection page with automatic detection and mode selection."""
    
    def __init__(self, app):
        super().__init__(app)
        self.disk_list_box = None
        self.continue_btn = None
    
    def create_title(self) -> Gtk.Widget:
        """Create title with icon."""
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
        title_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic")
        icon.set_pixel_size(config.scaled(48))
        title_box.append(icon)
        
        title = UIComponents.create_title("磁盘选择")
        title_box.append(title)
        
        return title_box
    
    def populate_content(self, content_box: Gtk.Box):
        """Populate content with disk selection UI."""
        # Info text
        info = Gtk.Label()
        info.set_markup('<span>请选择要安装 SkorionOS 的磁盘</span>')
        info.set_wrap(True)
        info.set_max_width_chars(50)
        content_box.append(info)
        
        # Disk list container
        self.disk_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(10))
        self.disk_list_box.set_size_request(config.scaled(700), config.scaled(300))
        self.disk_list_box.set_valign(Gtk.Align.CENTER)
        self.disk_list_box.set_halign(Gtk.Align.CENTER)
        self.app.disk_list_box = self.disk_list_box
        
        # Show loading indicator initially (centered)
        loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(10))
        loading_box.set_valign(Gtk.Align.CENTER)
        loading_box.set_halign(Gtk.Align.CENTER)
        loading_box.set_vexpand(True)
        
        loading_spinner = Gtk.Spinner()
        loading_spinner.set_size_request(config.scaled(48), config.scaled(48))
        loading_box.append(loading_spinner)
        
        loading_label = Gtk.Label()
        loading_label.set_markup('<span size="large">正在扫描磁盘...</span>')
        loading_box.append(loading_label)
        
        self.disk_list_box.append(loading_box)
        content_box.append(self.disk_list_box)
        
        # Start spinner and disk scanning
        self.app.disk_loading_spinner = loading_spinner
        loading_spinner.start()
        
        # Scan disks in background thread to avoid blocking UI
        thread = threading.Thread(target=_scan_and_populate_disks_thread, args=(self.app,), daemon=True)
        thread.start()
    
    def populate_buttons(self, button_box: Gtk.Box):
        """Populate button area."""
        # Back button
        back_btn = UIComponents.create_button("返回", "go-previous-symbolic")
        back_btn.connect("clicked", lambda b: self.app.go_back())
        button_box.append(back_btn)
        
        # Continue button
        self.continue_btn = UIComponents.create_button("继续", "go-next-symbolic")
        self.continue_btn.add_css_class("suggested-action")
        self.continue_btn.set_sensitive(False)
        self.continue_btn.connect("clicked", lambda b: _on_continue(self.app))
        button_box.append(self.continue_btn)
        
        # Store reference for enabling later
        self.app.disk_continue_btn = self.continue_btn


def create_disk_page(app):
    """Create the disk selection page using the new page architecture."""
    page = DiskPage(app)
    return page.create()


def _scan_and_populate_disks_thread(app):
    """Scan available disks in background thread"""
    try:
        # This runs in a background thread, so UI won't freeze
        disks = list_available_disks()
        
        # Update UI in main thread
        GLib.idle_add(_update_disk_list, app, disks)
        
    except Exception as e:
        logger.exception(f"[DISK] Error scanning disks: {e}")
        print(f"[DISK] Error scanning disks: {e}")
        GLib.idle_add(_show_error, app, f"扫描磁盘失败: {str(e)}")


def _update_disk_list(app, disks):
    """Update disk list in main thread (called from background thread)"""
    if len(disks) == 0:
        _show_no_disk_error(app)
        return False
    
    # Show disk list
    _show_disk_list(app, disks)
    
    # Auto-select if only one disk
    if len(disks) == 1:
        print(f"[DISK] Auto-selecting single disk: {disks[0]['name']}")
        app.selected_disk = disks[0]['name']
        app.selected_disk_desc = disks[0]['description']
        app.disk_continue_btn.set_sensitive(True)
    
    return False


def _show_disk_list(app, disks):
    """Display disk selection list"""
    # Clear existing content
    while app.disk_list_box.get_first_child():
        app.disk_list_box.remove(app.disk_list_box.get_first_child())
    
    list_box = Gtk.ListBox()
    list_box.set_selection_mode(Gtk.SelectionMode.NONE)
    list_box.add_css_class("info-box")
    
    app.available_disks = {}
    first_button = None
    
    for disk_info in disks:
        row = Gtk.ListBoxRow()
        
        # Use unified selection button component
        from ..components.base import UIComponents
        
        btn = UIComponents.create_selection_button(
            group=first_button,
            title=f'/dev/{disk_info["name"]}',
            description=disk_info['description'],
            orientation=Gtk.Orientation.VERTICAL
        )
        
        if first_button is None:
            first_button = btn
        
        row.set_child(btn)
        list_box.append(row)
        
        # Store disk info
        app.available_disks[row] = disk_info
        
        # Connect button selection
        btn.connect("toggled", lambda b, d=disk_info: _on_disk_selected(app, b, d) if b.get_active() else None)
    
    app.disk_list_box.append(list_box)
    return False


def _on_disk_selected(app, button, disk_info):
    """Handle disk selection"""
    if button.get_active():
        app.selected_disk = disk_info['name']
        app.selected_disk_desc = disk_info['description']
        app.disk_continue_btn.set_sensitive(True)
        print(f"[DISK] Selected: {app.selected_disk}")


def _on_continue(app):
    """Handle continue button - perform safety checks then detect installation"""
    disk = app.selected_disk
    
    # Perform safety checks first
    print(f"[DISK] Performing safety checks on {disk}...")
    
    # Check 1: Disk size (must be >= config.min_disk_size)
    from ...config import config
    if is_disk_smaller_than(disk, config.min_disk_size):
        _show_disk_too_small_dialog(app, disk)
        return
    
    # Check 2: External disk warning
    if is_disk_external(disk):
        _show_external_disk_warning(app, disk)
        return
    
    # Safety checks passed, proceed with installation detection
    _continue_to_mode_selection(app, disk)


def _continue_to_mode_selection(app, disk):
    """Continue to mode selection after safety checks pass."""
    print(f"[DISK] Checking {disk} for existing frzr installation...")
    status = check_existing_frzr_installation(disk)
    print(f"[DISK] Installation status: {status}")
    
    if status == 'complete':
        # Complete installation found - go to mode selection page
        app.has_existing_installation = True
        app.show_page('mode')
    elif status == 'incomplete':
        # Incomplete remnants - show cleanup dialog
        _show_cleanup_dialog(app, disk)
    else:
        # No installation - go to mode selection page
        app.has_existing_installation = False
        app.show_page('mode')


def _show_mode_dialog_with_repair(app, disk):
    """Show installation mode dialog when existing installation is detected"""
    dialog = Gtk.Dialog(title="检测到现有安装", transient_for=app, modal=True)
    dialog.set_default_size(config.scaled(500), config.scaled(400))
    
    content = dialog.get_content_area()
    content.set_spacing(config.scaled(20))
    content.set_margin_start(config.scaled(20))
    content.set_margin_end(config.scaled(20))
    content.set_margin_top(config.scaled(20))
    content.set_margin_bottom(config.scaled(20))
    
    # Title
    title = Gtk.Label()
    title.set_markup('<span size="large" weight="bold">检测到现有 frzr 安装</span>')
    content.append(title)
    
    # Description
    desc = Gtk.Label()
    desc.set_markup(f'磁盘 <b>/dev/{disk}</b> 上已有 frzr 安装。\n请选择操作：')
    desc.set_wrap(True)
    content.append(desc)
    
    # Radio buttons for mode selection
    repair_btn = Gtk.CheckButton(label="修复安装 - 保留用户数据，修复引导和系统文件")
    fresh_btn = Gtk.CheckButton(label="重新安装 (全新) - 格式化整个磁盘")
    fresh_btn.set_group(repair_btn)
    dual_btn = Gtk.CheckButton(label="重新安装 (双系统) - 保留其他系统")
    dual_btn.set_group(repair_btn)
    
    repair_btn.set_active(True)
    
    content.append(repair_btn)
    content.append(fresh_btn)
    content.append(dual_btn)
    
    # Buttons
    btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
    btn_box.set_halign(Gtk.Align.END)
    btn_box.set_margin_top(config.scaled(20))
    
    cancel_btn = Gtk.Button(label="取消")
    cancel_btn.connect("clicked", lambda b: dialog.close())
    btn_box.append(cancel_btn)
    
    ok_btn = Gtk.Button(label="继续")
    ok_btn.add_css_class("suggested-action")
    ok_btn.connect("clicked", lambda b: _on_mode_selected(app, dialog, repair_btn, fresh_btn, dual_btn))
    btn_box.append(ok_btn)
    
    content.append(btn_box)
    
    dialog.present()


def _show_mode_dialog(app, disk):
    """Show installation mode dialog for new disk"""
    dialog = Gtk.Dialog(title="选择安装类型", transient_for=app, modal=True)
    dialog.set_default_size(config.scaled(500), config.scaled(350))
    
    content = dialog.get_content_area()
    content.set_spacing(config.scaled(20))
    content.set_margin_start(config.scaled(20))
    content.set_margin_end(config.scaled(20))
    content.set_margin_top(config.scaled(20))
    content.set_margin_bottom(config.scaled(20))
    
    # Title
    title = Gtk.Label()
    title.set_markup('<span size="large" weight="bold">选择安装类型</span>')
    content.append(title)
    
    # Radio buttons
    fresh_btn = Gtk.CheckButton(label="全新安装 - 格式化整个磁盘")
    dual_btn = Gtk.CheckButton(label="双系统安装 - 保留现有系统")
    dual_btn.set_group(fresh_btn)
    
    fresh_btn.set_active(True)
    
    content.append(fresh_btn)
    content.append(dual_btn)
    
    # Buttons
    btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
    btn_box.set_halign(Gtk.Align.END)
    btn_box.set_margin_top(config.scaled(20))
    
    cancel_btn = Gtk.Button(label="取消")
    cancel_btn.connect("clicked", lambda b: dialog.close())
    btn_box.append(cancel_btn)
    
    ok_btn = Gtk.Button(label="继续")
    ok_btn.add_css_class("suggested-action")
    ok_btn.connect("clicked", lambda b: _on_mode_selected(app, dialog, None, fresh_btn, dual_btn))
    btn_box.append(ok_btn)
    
    content.append(btn_box)
    
    dialog.present()


def _show_cleanup_dialog(app, disk):
    """Show cleanup dialog for incomplete installation"""
    dialog = Gtk.MessageDialog(
        transient_for=app,
        modal=True,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.OK_CANCEL,
        text="检测到不完整的 frzr 安装残留"
    )
    dialog.set_secondary_text(
        f"磁盘 /dev/{disk} 上有不完整的 frzr 分区。\n"
        "这可能是之前安装失败的结果。\n\n"
        "建议清理残留分区后重新安装。\n"
        "是否清理残留分区？"
    )
    
    def on_response(dialog, response):
        dialog.close()
        if response == Gtk.ResponseType.OK:
            # User confirmed cleanup - proceed with mode selection
            _show_mode_dialog(app, disk)
    
    dialog.connect("response", on_response)
    dialog.present()


def _on_mode_selected(app, dialog, repair_btn, fresh_btn, dual_btn):
    """Handle mode selection from dialog"""
    dialog.close()
    
    if repair_btn and repair_btn.get_active():
        # Repair mode
        app.install_mode = 'repair'
        print(f"[DISK] Mode selected: repair")
        app.show_page('confirm')
        
    elif fresh_btn.get_active():
        # Fresh install mode
        app.install_mode = 'fresh'
        print(f"[DISK] Mode selected: fresh")
        app.show_page('confirm')
        
    elif dual_btn.get_active():
        # Dual-boot mode - need to check free space
        print(f"[DISK] Mode selected: dual")
        _configure_dual_boot(app)


def _configure_dual_boot(app):
    """Configure dual-boot installation"""
    disk = app.selected_disk
    
    print(f"[DISK] Checking free space on {disk}...")
    free_spaces = check_free_space(disk)
    
    if free_spaces:
        # Has sufficient free space
        print(f"[DISK] Found {len(free_spaces)} free space(s): {free_spaces}")
        app.install_mode = 'dual'
        app.dual_mode = 'auto'
        app.show_page('confirm')
    else:
        # No sufficient free space - show partition adjustment dialog
        print(f"[DISK] No sufficient free space, showing partition adjustment dialog")
        _show_partition_adjustment_dialog(app)


def _show_partition_adjustment_dialog(app):
    """Show dialog for partition adjustment (shrink/delete)"""
    disk = app.selected_disk
    partitions = list_shrinkable_partitions(disk)
    
    if not partitions:
        _show_error(app, "没有找到可以操作的分区（需要 >= 55GB 的 ntfs/ext4/btrfs 分区）")
        return
    
    dialog = Gtk.Dialog(title="调整分区大小", transient_for=app, modal=True)
    dialog.set_default_size(config.scaled(600), config.scaled(500))
    
    content = dialog.get_content_area()
    content.set_spacing(config.scaled(20))
    content.set_margin_start(config.scaled(20))
    content.set_margin_end(config.scaled(20))
    content.set_margin_top(config.scaled(20))
    content.set_margin_bottom(config.scaled(20))
    
    # Title
    title = Gtk.Label()
    title.set_markup('<span size="large" weight="bold">磁盘空间不足</span>')
    content.append(title)
    
    # Description
    desc = Gtk.Label()
    desc.set_markup('磁盘没有足够的未分配空间（需要 >= 55GB）。\n请选择一个分区进行操作：')
    desc.set_wrap(True)
    content.append(desc)
    
    # Partition list
    list_box = Gtk.ListBox()
    list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
    list_box.add_css_class("info-box")
    
    for partition in partitions:
        row = Gtk.ListBoxRow()
        row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(4))
        row_box.set_margin_start(config.scaled(10))
        row_box.set_margin_end(config.scaled(10))
        row_box.set_margin_top(config.scaled(8))
        row_box.set_margin_bottom(config.scaled(8))
        
        name_label = Gtk.Label()
        name_label.set_markup(f'<b>{partition["path"]}</b>')
        name_label.set_xalign(0)
        row_box.append(name_label)
        
        info_label = Gtk.Label(label=f'{partition["fstype"]} ({partition["size_gb"]}GB)')
        info_label.set_xalign(0)
        row_box.append(info_label)
        
        row.set_child(row_box)
        row.partition_info = partition
        list_box.append(row)
    
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_size_request(config.scaled(500), config.scaled(200))
    scrolled.set_child(list_box)
    content.append(scrolled)
    
    # Operation selection
    op_label = Gtk.Label(label="选择操作：")
    op_label.set_xalign(0)
    content.append(op_label)
    
    shrink_btn = Gtk.CheckButton(label="缩小分区")
    delete_btn = Gtk.CheckButton(label="删除整个分区 (危险!)")
    delete_btn.set_group(shrink_btn)
    shrink_btn.set_active(True)
    
    content.append(shrink_btn)
    content.append(delete_btn)
    
    # Size selection (for shrink)
    size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
    size_label = Gtk.Label(label="释放空间：")
    size_box.append(size_label)
    
    size_combo = Gtk.ComboBoxText()
    size_combo.append_text("60 GB")
    size_combo.append_text("100 GB")
    size_combo.append_text("200 GB")
    size_combo.set_active(1)
    size_box.append(size_combo)
    content.append(size_box)
    
    # Enable/disable size selection based on operation
    def on_operation_changed(btn):
        size_box.set_sensitive(shrink_btn.get_active())
    
    shrink_btn.connect("toggled", on_operation_changed)
    delete_btn.connect("toggled", on_operation_changed)
    
    # Buttons
    btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
    btn_box.set_halign(Gtk.Align.END)
    btn_box.set_margin_top(config.scaled(20))
    
    cancel_btn = Gtk.Button(label="取消")
    cancel_btn.connect("clicked", lambda b: dialog.close())
    btn_box.append(cancel_btn)
    
    ok_btn = Gtk.Button(label="继续")
    ok_btn.add_css_class("suggested-action")
    ok_btn.connect("clicked", lambda b: _on_partition_operation_selected(
        app, dialog, list_box, shrink_btn, delete_btn, size_combo
    ))
    btn_box.append(ok_btn)
    
    content.append(btn_box)
    
    dialog.present()


def _on_partition_operation_selected(app, dialog, list_box, shrink_btn, delete_btn, size_combo):
    """Handle partition operation selection"""
    selected_row = list_box.get_selected_row()
    if not selected_row:
        _show_error(app, "请选择一个分区")
        return
    
    partition = selected_row.partition_info
    
    app.install_mode = 'dual'
    
    if shrink_btn.get_active():
        # Shrink partition
        size_text = size_combo.get_active_text()
        size_gb = int(size_text.split()[0])
        
        app.dual_mode = 'shrink'
        app.shrink_partition = partition['path']
        app.shrink_size = size_gb
        
        print(f"[DISK] Dual mode: shrink {partition['path']} by {size_gb}GB")
    else:
        # Delete partition
        app.dual_mode = 'delete'
        app.delete_partition = partition['path']
        
        print(f"[DISK] Dual mode: delete {partition['path']}")
    
    dialog.close()
    app.show_page('confirm')


def _show_no_disk_error(app):
    """Show error when no disks are available"""
    dialog = Gtk.MessageDialog(
        transient_for=app,
        modal=True,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        text="未找到可用磁盘"
    )
    dialog.set_secondary_text("系统未检测到任何可用的安装磁盘。")
    
    def on_response(dialog, response):
        dialog.close()
        app.close()
    
    dialog.connect("response", on_response)
    dialog.present()


def _show_error(app, message):
    """Show error dialog"""
    dialog = Gtk.MessageDialog(
        transient_for=app,
        modal=True,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        text="错误"
    )
    dialog.set_secondary_text(message)
    dialog.connect("response", lambda d, r: d.close())
    dialog.present()


def _show_disk_too_small_dialog(app, disk):
    """Show error when disk is too small"""
    from ...config import config
    
    dialog = Gtk.MessageDialog(
        transient_for=app,
        modal=True,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        text="磁盘空间不足"
    )
    dialog.set_secondary_text(
        f"磁盘 {disk} 小于 {config.min_disk_size}GB，无法安装 SkorionOS。\n\n"
        f"SkorionOS 需要至少 {config.min_disk_size}GB 的可用空间。\n"
        "请选择更大的磁盘。"
    )
    
    def on_response(dialog, response):
        dialog.close()
    
    dialog.connect("response", on_response)
    dialog.present()


def _show_external_disk_warning(app, disk):
    """Show warning when selecting external disk"""
    dialog = Gtk.MessageDialog(
        transient_for=app,
        modal=True,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.YES_NO,
        text="外部磁盘警告"
    )
    dialog.set_secondary_text(
        f"磁盘 {disk} 似乎是外部设备（USB/SD卡等）。\n\n"
        "在外部磁盘上安装可能导致：\n"
        "• 系统性能不佳\n"
        "• 启动速度缓慢\n"
        "• 磁盘易损坏或丢失\n\n"
        "强烈建议安装到内置磁盘。\n\n"
        "是否仍要继续安装到此磁盘？"
    )
    
    def on_response(dialog, response):
        dialog.close()
        if response == Gtk.ResponseType.YES:
            # User confirmed, continue with installation
            _continue_to_mode_selection(app, disk)
    
    dialog.connect("response", on_response)
    dialog.present()
