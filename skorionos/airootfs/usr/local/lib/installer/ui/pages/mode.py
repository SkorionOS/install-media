"""
Installation mode selection page - shown after disk selection
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from ...config import config
from ..components.base import BasePage, UIComponents


class ModePage(BasePage):
    """Mode selection page for choosing installation type."""
    
    def __init__(self, app):
        super().__init__(app)
        self.has_existing = getattr(app, 'has_existing_installation', False)
        
        # Radio button references
        self.repair_btn = None
        self.fresh_btn = None
        self.dual_btn = None
    
    def create_title(self) -> Gtk.Widget:
        """Create title with icon."""
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.scaled(15))
        title_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("emblem-system-symbolic")
        icon.set_pixel_size(config.scaled(48))
        title_box.append(icon)
        
        title = Gtk.Label()
        if self.has_existing:
            title.set_markup('<span size="xx-large" weight="bold">检测到现有安装</span>')
        else:
            title.set_markup('<span size="xx-large" weight="bold">选择安装类型</span>')
        title_box.append(title)
        
        return title_box
    
    def populate_content(self, content_box: Gtk.Box):
        """Populate content with mode selection options."""
        # Description
        desc = Gtk.Label()
        if self.has_existing:
            desc.set_markup(f'磁盘 <b>/dev/{self.app.selected_disk}</b> 上已有 frzr 安装。\n请选择操作：')
        else:
            desc.set_markup('请选择安装方式：')
        desc.set_wrap(True)
        desc.set_justify(Gtk.Justification.CENTER)
        content_box.append(desc)
        
        # Radio buttons container with border/background like disk selection
        radio_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.scaled(15))
        radio_box.set_halign(Gtk.Align.CENTER)
        radio_box.set_margin_top(config.scaled(20))
        radio_box.add_css_class("info-box")
        
        # Create radio buttons based on existing installation
        if self.has_existing:
            # Repair option
            self.repair_btn = self._create_option_button(
                None,
                "修复安装",
                "保留用户数据，修复引导和系统文件",
                True
            )
            radio_box.append(self.repair_btn)
            
            # Fresh install option
            self.fresh_btn = self._create_option_button(
                self.repair_btn,
                "重新安装 (全新)",
                "格式化整个磁盘，删除所有数据"
            )
            radio_box.append(self.fresh_btn)
            
            # Dual boot option
            self.dual_btn = self._create_option_button(
                self.repair_btn,
                "重新安装 (双系统)",
                "保留其他系统，与现有系统共存"
            )
            radio_box.append(self.dual_btn)
            
            # Store references for backward compatibility
            self.app._mode_repair_btn = self.repair_btn
            self.app._mode_fresh_btn = self.fresh_btn
            self.app._mode_dual_btn = self.dual_btn
        else:
            # Fresh install option
            self.fresh_btn = self._create_option_button(
                None,
                "全新安装",
                "格式化整个磁盘",
                True
            )
            radio_box.append(self.fresh_btn)
            
            # Dual boot option
            self.dual_btn = self._create_option_button(
                self.fresh_btn,
                "双系统安装",
                "保留现有系统，与其他系统共存"
            )
            radio_box.append(self.dual_btn)
            
            # Store references for backward compatibility
            self.app._mode_fresh_btn = self.fresh_btn
            self.app._mode_dual_btn = self.dual_btn
        
        content_box.append(radio_box)
    
    def populate_buttons(self, button_box: Gtk.Box):
        """Populate button area."""
        # Back button
        back_btn = UIComponents.create_button("返回", "go-previous-symbolic")
        back_btn.connect("clicked", lambda b: self.app.go_back())
        button_box.append(back_btn)
        
        # Exit button (go to complete page - cancelled)
        exit_btn = UIComponents.create_button("退出", "application-exit-symbolic")
        exit_btn.connect("clicked", lambda b: self._on_exit())
        button_box.append(exit_btn)
        
        # Continue button
        continue_btn = UIComponents.create_button("继续", "go-next-symbolic")
        continue_btn.add_css_class("suggested-action")
        continue_btn.connect("clicked", lambda b: self._on_continue())
        button_box.append(continue_btn)
    
    def _create_option_button(self, group, title, description, active=False):
        """
        Create a radio button option with title and description.
        Uses the unified UIComponents.create_selection_button for consistent styling.
        
        Args:
            group: Group button (None for first button)
            title: Option title
            description: Option description
            active: Whether to set active by default
        
        Returns:
            Gtk.CheckButton: Radio button
        """
        from ..components.base import UIComponents
        
        btn = UIComponents.create_selection_button(
            group=group,
            title=title,
            description=description,
            orientation=Gtk.Orientation.VERTICAL
        )
        
        if active:
            btn.set_active(True)
        
        return btn
    
    def _on_exit(self):
        """Handle exit button - go to complete page with CANCELLED status."""
        from .complete import CompletePage
        print("[MODE] User requested exit")
        self.app.show_complete_page(
            CompletePage.STATUS_CANCELLED,
            "安装已取消",
            "您在模式选择页面选择了退出安装"
        )
    
    def _on_continue(self):
        """Handle continue button click."""
        # Determine selected mode
        if self.has_existing:
            if self.repair_btn.get_active():
                mode = 'repair'
            elif self.fresh_btn.get_active():
                mode = 'fresh'
            else:
                mode = 'dual'
        else:
            if self.fresh_btn.get_active():
                mode = 'fresh'
            else:
                mode = 'dual'
        
        self.app.install_mode = mode
        print(f"[MODE] Selected mode: {mode}")
        
        # If dual boot, configure it first
        if mode == 'dual':
            from .disk_new import _configure_dual_boot
            _configure_dual_boot(self.app)
        else:
            # Go to confirm page
            self.app.show_page('confirm')


def create_mode_page(app):
    """Create the mode selection page using the new page architecture."""
    page = ModePage(app)
    return page.create()
