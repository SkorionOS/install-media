"""
Virtual keyboard for password/text input
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from ..config import config


class VirtualKeyboard:
    """Virtual on-screen keyboard with letter and symbol modes"""
    
    def __init__(self, entry, dialog=None):
        """
        Initialize virtual keyboard
        
        Args:
            entry: Gtk.Entry widget to receive input
            dialog: Optional dialog to handle Enter key
        """
        self.entry = entry
        self.dialog = dialog
        
        # Keyboard state
        self.shift = False
        self.caps_lock = False
        self.symbol_mode = False  # False = letters, True = symbols
        self.letter_btns = []  # Track letter buttons for case updates
        
        # Button sizing
        self.key_size = config.scaled(48)
        self.key_height = config.scaled(48)
        self.key_spacing = config.scaled(4)
        
        # Create keyboards
        self.letter_keyboard = self._create_letter_keyboard()
        self.symbol_keyboard = self._create_symbol_keyboard()
        
        # Container
        self.container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.key_spacing)
        self.container.set_halign(Gtk.Align.CENTER)
        self.container.append(self.letter_keyboard)
    
    def get_widget(self):
        """Get the keyboard container widget"""
        return self.container
    
    def _create_letter_keyboard(self):
        """Create letter keyboard layout"""
        keyboard = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.key_spacing)
        keyboard.set_halign(Gtk.Align.CENTER)
        
        # Keyboard layout: (label, units, action)
        layout = [
            # Row 1: Numbers + Backspace
            [
                ('1', 1), ('2', 1), ('3', 1), ('4', 1), ('5', 1),
                ('6', 1), ('7', 1), ('8', 1), ('9', 1), ('0', 1),
                ('←', 2, 'backspace'),
            ],
            # Row 2: Q-P
            [
                ('', 0.5),
                ('q', 1), ('w', 1), ('e', 1), ('r', 1), ('t', 1),
                ('y', 1), ('u', 1), ('i', 1), ('o', 1), ('p', 1), ('|', 1)
            ],
            # Row 3: Caps + A-L + Enter
            [
                ('⇪', 1, 'caps'),
                ('a', 1), ('s', 1), ('d', 1), ('f', 1), ('g', 1),
                ('h', 1), ('j', 1), ('k', 1), ('l', 1),
                ('↵', -1, 'enter')
            ],
            # Row 4: Shift + Z-M + symbols
            [
                ('⇧', 1.5, 'shift'),
                ('z', 1), ('x', 1), ('c', 1), ('v', 1),
                ('b', 1), ('n', 1), ('m', 1),
                ('<', 1), ('>', 1), ('/', -1),
            ],
            # Row 5: Symbol + Space + Clear
            [
                ('?123', -1, 'symbol'),
                ('空格', 6, 'space'),
                ('清空', -1, 'clear'),
            ],
        ]
        
        return self._build_keyboard_from_layout(layout)
    
    def _create_symbol_keyboard(self):
        """Create symbol keyboard layout"""
        keyboard = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.key_spacing)
        keyboard.set_halign(Gtk.Align.CENTER)
        
        # Symbol keyboard layout
        layout = [
            # Row 1: Symbols + Backspace
            [
                ('!', 1), ('@', 1), ('#', 1), ('$', 1), ('%', 1),
                ('^', 1), ('&', 1), ('*', 1), ('(', 1), (')', 1),
                ('←', 2, 'backspace'),
            ],
            # Row 2: More symbols
            [
                ('', 0.5),
                ('+', 1), ('=', 1), ('<', 1), ('>', 1), ('?', 1),
                ('/', 1), ('\\', 1), ('|', 1), ('_', 1), ('-', 1),
            ],
            # Row 3: Even more symbols
            [
                ('', 1),
                (':', 1), (';', 1), ("'", 1), ('"', 1), (',', 1),
                ('.', 1), ('[', 1), (']', 1), ('{', 1), ('}', 1),
            ],
            # Row 4: Special symbols + Backspace
            [
                ('', 0.5),
                ('~', 1), ('`', 1), ('€', 1), ('£', 1), ('¥', 1),
                ('§', 1), ('©', 1), ('®', 1), ('™', 1),
                ('←', -1, 'backspace'),
            ],
            # Row 5: ABC + Space + Clear
            [
                ('ABC', -1, 'letter'),
                ('空格', 6, 'space'),
                ('清空', -1, 'clear'),
            ],
        ]
        
        return self._build_keyboard_from_layout(layout, is_symbol=True)
    
    def _build_keyboard_from_layout(self, layout, is_symbol=False):
        """Build keyboard widget from layout definition"""
        keyboard = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.key_spacing)
        keyboard.set_halign(Gtk.Align.CENTER)
        
        for row_layout in layout:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=self.key_spacing)
            
            for item in row_layout:
                label = item[0]
                units = item[1]
                action = item[2] if len(item) > 2 else None
                
                # Handle spacers
                if label == '' or label is None:
                    spacer = Gtk.Box()
                    if units > 0:
                        spacer_width = int(self.key_size * units + self.key_spacing * (units - 1))
                        spacer.set_size_request(spacer_width, self.key_height)
                    row.append(spacer)
                    continue
                
                # Create button
                btn = Gtk.Button(label=label)
                btn.add_css_class("keyboard-key")
                
                # Set button size
                if units == -1:
                    btn.set_hexpand(True)
                    btn.set_size_request(-1, self.key_height)
                else:
                    width = int(self.key_size * units + self.key_spacing * (units - 1))
                    btn.set_size_request(width, self.key_height)
                
                # Connect actions
                if action == 'backspace':
                    btn.connect("clicked", lambda b: self._on_backspace())
                elif action == 'caps':
                    self.caps_btn = btn
                    btn.connect("clicked", lambda b: self._on_caps())
                elif action == 'shift':
                    self.shift_btn = btn
                    btn.connect("clicked", lambda b: self._on_shift())
                elif action == 'enter':
                    if self.dialog:
                        btn.connect("clicked", lambda b: self.dialog.response(Gtk.ResponseType.OK))
                elif action == 'symbol':
                    btn.connect("clicked", lambda b: self._switch_mode())
                elif action == 'letter':
                    btn.connect("clicked", lambda b: self._switch_mode())
                elif action == 'space':
                    btn.connect("clicked", lambda b: self._on_key(' '))
                elif action == 'clear':
                    btn.connect("clicked", lambda b: self.entry.set_text(""))
                else:
                    # Regular key
                    btn.char = label
                    btn.connect("clicked", lambda b, l=label: self._on_key(l))
                    if not is_symbol and label.isalpha():
                        self.letter_btns.append(btn)
                
                row.append(btn)
            
            keyboard.append(row)
        
        return keyboard
    
    def _switch_mode(self):
        """Switch between letter and symbol keyboard"""
        self.symbol_mode = not self.symbol_mode
        
        # Remove current keyboard
        child = self.container.get_first_child()
        if child:
            self.container.remove(child)
        
        # Add the other keyboard
        if self.symbol_mode:
            self.container.append(self.symbol_keyboard)
        else:
            self.container.append(self.letter_keyboard)
    
    def _on_key(self, char):
        """Handle key press"""
        current = self.entry.get_text()
        # Apply shift or caps lock for letters
        if (self.shift or self.caps_lock) and char.isalpha():
            char = char.upper()
        self.entry.set_text(current + char)
        # Reset shift after letter input (but not caps lock)
        if self.shift and char.isalpha():
            self._on_shift()
    
    def _on_backspace(self):
        """Handle backspace"""
        current = self.entry.get_text()
        if current:
            self.entry.set_text(current[:-1])
    
    def _on_shift(self):
        """Toggle shift state"""
        self.shift = not self.shift
        
        if self.shift:
            self.shift_btn.add_css_class("suggested-action")
        else:
            self.shift_btn.remove_css_class("suggested-action")
        
        self._update_letter_case()
    
    def _on_caps(self):
        """Toggle caps lock state"""
        self.caps_lock = not self.caps_lock
        
        if self.caps_lock:
            self.caps_btn.add_css_class("suggested-action")
        else:
            self.caps_btn.remove_css_class("suggested-action")
        
        self._update_letter_case()
    
    def _update_letter_case(self):
        """Update all letter buttons based on shift/caps state"""
        for btn in self.letter_btns:
            current_label = btn.get_label()
            if self.shift or self.caps_lock:
                btn.set_label(current_label.upper())
            else:
                btn.set_label(current_label.lower())

