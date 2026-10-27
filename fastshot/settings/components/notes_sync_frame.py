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
            enable_frame, text="Enable Notes Sync (LifeOS /ingest)",
            variable=self.enabled_var
        ).pack(side='left')

        # Ingest URL (back-compat: show the old wrapper_url if ingest_url unset)
        url_frame = ttk.Frame(self)
        url_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(url_frame, text="Ingest URL:").pack(side='left')
        self.url_var = tk.StringVar(
            value=settings.get('ingest_url', '') or settings.get('wrapper_url', '')
            or "https://json-validator.centralindia.cloudapp.azure.com/ingest"
        )
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=45)
        self.url_entry.pack(side='left', padx=5, fill='x', expand=True)

        # API Key (Bearer, for authentication)
        api_frame = ttk.Frame(self)
        api_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(api_frame, text="API Key (Bearer):").pack(side='left')
        self.api_var = tk.StringVar(value=settings.get('api_key', ''))
        self.api_entry = ttk.Entry(api_frame, textvariable=self.api_var, width=35, show='*')
        self.api_entry.pack(side='left', padx=5, fill='x', expand=True)
        self.show_api_btn = ttk.Button(
            api_frame, text="Show", command=lambda: self._toggle(self.api_entry, self.show_api_btn), width=8
        )
        self.show_api_btn.pack(side='left', padx=5)

        # XOR Key (envelope obfuscation = encryption_key)
        key_frame = ttk.Frame(self)
        key_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(key_frame, text="XOR Key:").pack(side='left')
        self.key_var = tk.StringVar(value=settings.get('encryption_key', ''))
        self.key_entry = ttk.Entry(key_frame, textvariable=self.key_var, width=35, show='*')
        self.key_entry.pack(side='left', padx=5, fill='x', expand=True)
        self.show_key_btn = ttk.Button(
            key_frame, text="Show", command=lambda: self._toggle(self.key_entry, self.show_key_btn), width=8
        )
        self.show_key_btn.pack(side='left', padx=5)

        # Help text
        help_text = (
            "Note:\n"
            "1. Ingest URL: the LifeOS unified endpoint, e.g.\n"
            "   https://json-validator.centralindia.cloudapp.azure.com/ingest\n"
            "2. API Key (Bearer): authenticates the request (Authorization header).\n"
            "3. XOR Key: obfuscates the payload inside the PNG envelope; must match\n"
            "   the key configured on the LifeOS server (the engine's encryption_key).\n"
            "   The API Key and the XOR Key are DIFFERENT strings (case matters).\n"
            "4. The whole capture (Markdown + images) is XOR'd and disguised as a PNG."
        )
        help_label = ttk.Label(self, text=help_text, justify='left', foreground='gray')
        help_label.pack(padx=10, pady=10, anchor='w')

    def _toggle(self, entry, btn):
        if entry['show'] == '*':
            entry['show'] = ''
            btn['text'] = 'Hide'
        else:
            entry['show'] = '*'
            btn['text'] = 'Show'

    def get_settings(self):
        return {
            'notes_sync_enabled': str(self.enabled_var.get()),
            'ingest_url': self.url_var.get().strip(),
            'api_key': self.api_var.get().strip(),
            'encryption_key': self.key_var.get().strip(),
        }
