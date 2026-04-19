import tkinter as tk
from tkinter import ttk


class NotesSyncFrame(ttk.Frame):
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.create_widgets()

    def create_widgets(self):
        settings = self.settings_manager.get_section('NotesSync')

        # Enable checkbox
        enable_frame = ttk.Frame(self)
        enable_frame.pack(fill='x', padx=10, pady=5)

        self.enabled_var = tk.BooleanVar(
            value=settings.get('notes_sync_enabled', 'False').lower() == 'true'
        )
        ttk.Checkbutton(
            enable_frame, text="Enable Notes Sync (Siyuan Wrapper)",
            variable=self.enabled_var
        ).pack(side='left')

        # Wrapper URL
        url_frame = ttk.Frame(self)
        url_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(url_frame, text="Wrapper URL:").pack(side='left')
        self.url_var = tk.StringVar(value=settings.get('wrapper_url', ''))
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=45)
        self.url_entry.pack(side='left', padx=5, fill='x', expand=True)

        # Encryption Key
        key_frame = ttk.Frame(self)
        key_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(key_frame, text="Encryption Key:").pack(side='left')
        self.key_var = tk.StringVar(value=settings.get('encryption_key', ''))
        self.key_entry = ttk.Entry(key_frame, textvariable=self.key_var, width=35, show='*')
        self.key_entry.pack(side='left', padx=5, fill='x', expand=True)

        self.show_key_btn = ttk.Button(
            key_frame, text="Show", command=self.toggle_key_visibility, width=8
        )
        self.show_key_btn.pack(side='left', padx=5)

        # Help text
        help_text = (
            "Note:\n"
            "1. Wrapper URL: the Siyuan Wrapper endpoint\n"
            "   e.g. http://xxxxxxx:8806/webhook/fastshot/en\n"
            "2. Encryption Key: must match the key configured in Siyuan Wrapper\n"
            "3. Session data is XOR encrypted and disguised as PNG before upload"
        )
        help_label = ttk.Label(self, text=help_text, justify='left', foreground='gray')
        help_label.pack(padx=10, pady=10, anchor='w')

    def toggle_key_visibility(self):
        if self.key_entry['show'] == '*':
            self.key_entry['show'] = ''
            self.show_key_btn['text'] = 'Hide'
        else:
            self.key_entry['show'] = '*'
            self.show_key_btn['text'] = 'Show'

    def get_settings(self):
        return {
            'notes_sync_enabled': str(self.enabled_var.get()),
            'wrapper_url': self.url_var.get().strip(),
            'encryption_key': self.key_var.get().strip(),
        }
