"""
Partition adjustment page - for dual boot when free space is insufficient
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from ...config import config
from ..components.base import BasePage, UIComponents
from ...backend.disk_utils import list_shrinkable_partitions


class PartitionAdjustPage(BasePage):
    """Partition adjustment page for dual boot space management."""
    
    def __init__(self, app):
        super().__init__(app)
        self.selected_partition = None
        self.selected_operation = 'shrink'  # 'shrink' or 'delete'
        self.selected_size = 100  # Default 100GB
        
        # References
        self.partition_buttons = []
        self.shrink_btn = None
        self.delete_btn = None
        self.size_buttons = []
    
    def create_title(self) -> Gtk.Widget:
        """Create title with icon."""
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(15))
        title_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic")
        icon.set_pixel_size(config.scaled(48))
        title_box.append(icon)
        
        title = Gtk.Label()
        title.set_markup('<span size="xx-large" weight="bold">磁盘空间不足</span>')
        title_box.append(title)
        
        return title_box
    
    def populate_content(self, content_box: Gtk.Box):
        """Populate content with partition selection and operation options."""
        # Description (more compact)
        desc = Gtk.Label()
        desc.set_markup(
            f'磁盘 <b>/dev/{self.app.selected_disk}</b> 没有足够的未分配空间（需要 >= {config.min_disk_size}GB）。'
            '请选择一个分区进行操作以释放空间：'
        )
        desc.set_wrap(True)
        desc.set_justify(Gtk.Justification.CENTER)
        desc.set_margin_bottom(config.scaled(10))
        content_box.append(desc)
        
        # Scan for shrinkable partitions
        disk = self.app.selected_disk
        partitions = list_shrinkable_partitions(disk)
        
        if not partitions:
            error_label = Gtk.Label()
            error_label.set_markup(
                '<span size="large" foreground="red">没有找到可以操作的分区</span>\n'
                f'<span size="small">需要 >= {config.min_disk_size}GB 的 ntfs/ext4/btrfs 分区</span>'
            )
            error_label.set_justify(Gtk.Justification.CENTER)
            content_box.append(error_label)
            return
        
        # All three sections in horizontal layout
        all_row = self._create_all_horizontal(partitions)
        content_box.append(all_row)
    
    def _create_all_horizontal(self, partitions):
        """Create all three sections in horizontal layout."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(10))
        row.set_halign(Gtk.Align.CENTER)
        
        # Left: Partition selection
        partition_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(5))
        
        # Title
        partition_title = Gtk.Label()
        partition_title.set_markup('<span weight="bold">选择分区：</span>')
        partition_title.set_xalign(0.5)
        partition_section.append(partition_title)
        
        # Scrolled window for partition list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(config.scaled(120))
        scrolled.set_max_content_height(config.scaled(250))
        scrolled.set_size_request(config.scaled(240), -1)
        scrolled.set_propagate_natural_height(True)
        
        # Partition list
        list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(5))
        list_container.add_css_class("info-box")
        
        first_btn = None
        for partition in partitions:
            btn = UIComponents.create_selection_button(
                group=first_btn,
                title=partition['path'],
                description=f'{partition["fstype"]} | {partition["size_gb"]}GB',
                orientation=Gtk.Orientation.VERTICAL
            )
            
            if first_btn is None:
                first_btn = btn
                btn.set_active(True)
                self.selected_partition = partition
            
            # Store partition info
            btn.partition_info = partition
            btn.connect("toggled", lambda b: self._on_partition_selected(b))
            
            self.partition_buttons.append(btn)
            list_container.append(btn)
        
        scrolled.set_child(list_container)
        partition_section.append(scrolled)
        row.append(partition_section)
        
        # Middle: Operation selection
        operation_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(5))
        
        # Title
        op_title = Gtk.Label()
        op_title.set_markup('<span weight="bold">选择操作：</span>')
        op_title.set_xalign(0.5)
        operation_section.append(op_title)
        
        # Operation buttons container
        ops_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(5))
        ops_container.add_css_class("info-box")
        ops_container.set_size_request(config.scaled(200), -1)
        
        # Shrink option
        self.shrink_btn = UIComponents.create_selection_button(
            group=None,
            title="缩小分区",
            description="保留数据，释放空间",
            orientation=Gtk.Orientation.VERTICAL
        )
        self.shrink_btn.set_active(True)
        self.shrink_btn.connect("toggled", lambda b: self._on_operation_changed('shrink') if b.get_active() else None)
        ops_container.append(self.shrink_btn)
        
        # Delete option
        self.delete_btn = UIComponents.create_selection_button(
            group=self.shrink_btn,
            title="删除整个分区",
            description="⚠️ 危险！删除数据",
            orientation=Gtk.Orientation.VERTICAL
        )
        self.delete_btn.connect("toggled", lambda b: self._on_operation_changed('delete') if b.get_active() else None)
        ops_container.append(self.delete_btn)
        
        operation_section.append(ops_container)
        row.append(operation_section)
        
        # Right: Size selection
        self.size_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(5))
        
        # Title
        size_title = Gtk.Label()
        size_title.set_markup('<span weight="bold">释放空间：</span>')
        size_title.set_xalign(0.5)
        self.size_section.append(size_title)
        
        # Size buttons container
        size_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(5))
        size_container.add_css_class("info-box")
        size_container.set_size_request(config.scaled(200), -1)
        
        sizes = [
            (60, '60GB', '最小推荐'),
            (100, '100GB', '推荐配置'),
            (200, '200GB', '充足空间')
        ]
        
        first_btn = None
        for size_gb, size_title_text, desc in sizes:
            btn = UIComponents.create_selection_button(
                group=first_btn,
                title=size_title_text,
                description=desc,
                orientation=Gtk.Orientation.VERTICAL
            )
            
            if first_btn is None:
                first_btn = btn
            
            # Default to 100GB
            if size_gb == 100:
                btn.set_active(True)
            
            btn.size_value = size_gb
            btn.connect("toggled", lambda b: self._on_size_selected(b) if b.get_active() else None)
            
            self.size_buttons.append(btn)
            size_container.append(btn)
        
        self.size_section.append(size_container)
        row.append(self.size_section)
        
        return row
    
    
    def populate_buttons(self, button_box: Gtk.Box):
        """Populate the button area."""
        # Back button
        back_btn = UIComponents.create_button("返回", "go-previous-symbolic")
        back_btn.connect("clicked", lambda b: self.app.go_back())
        button_box.append(back_btn)
        
        # Exit button
        exit_btn = UIComponents.create_button("退出", "application-exit-symbolic")
        exit_btn.connect("clicked", lambda b: self._on_exit())
        button_box.append(exit_btn)
        
        # Continue button
        continue_btn = UIComponents.create_button("继续", "go-next-symbolic")
        continue_btn.add_css_class("suggested-action")
        continue_btn.connect("clicked", lambda b: self._on_continue())
        button_box.append(continue_btn)
    
    def _on_partition_selected(self, button):
        """Handle partition selection."""
        if button.get_active() and hasattr(button, 'partition_info'):
            self.selected_partition = button.partition_info
            print(f"[PARTITION_ADJUST] Selected partition: {self.selected_partition['path']}")
    
    def _on_operation_changed(self, operation):
        """Handle operation change."""
        self.selected_operation = operation
        print(f"[PARTITION_ADJUST] Operation: {operation}")
        
        # Enable/disable size selection based on operation
        if hasattr(self, 'size_section'):
            self.size_section.set_sensitive(operation == 'shrink')
    
    def _on_size_selected(self, button):
        """Handle size selection."""
        if hasattr(button, 'size_value'):
            self.selected_size = button.size_value
            print(f"[PARTITION_ADJUST] Size: {self.selected_size}GB")
    
    def _on_exit(self):
        """Handle exit button."""
        from .complete import CompletePage
        print("[PARTITION_ADJUST] User requested exit")
        self.app.show_complete_page(
            CompletePage.STATUS_CANCELLED,
            "安装已取消",
            "您在分区调整页面选择了退出安装"
        )
    
    def _on_continue(self):
        """Handle continue button."""
        if not self.selected_partition:
            print("[PARTITION_ADJUST] No partition selected")
            return
        
        # Store configuration in app
        self.app.install_mode = 'dual'
        
        if self.selected_operation == 'shrink':
            self.app.dual_mode = 'shrink'
            self.app.shrink_partition = self.selected_partition['path']
            self.app.shrink_size = self.selected_size
            print(f"[PARTITION_ADJUST] Configured: shrink {self.selected_partition['path']} by {self.selected_size}GB")
        else:
            self.app.dual_mode = 'delete'
            self.app.delete_partition = self.selected_partition['path']
            print(f"[PARTITION_ADJUST] Configured: delete {self.selected_partition['path']}")
        
        # Go to confirm page
        self.app.show_page('confirm')


def create_partition_adjust_page(app):
    """Create the partition adjustment page."""
    page = PartitionAdjustPage(app)
    return page.create()

