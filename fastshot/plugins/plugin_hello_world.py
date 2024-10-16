# plugin_hello_world.py

import tkinter as tk
from tkinter import messagebox

def run(app_context):
    """The main function that gets called when the plugin is activated."""
    # Display a Hello World message box
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("Hello Plugin", "Hello, World!")
    root.destroy()

def get_plugin_info():
    """Returns metadata about the plugin."""
    return {
        'name': 'Hello World Plugin',
        'id': 'plugin_hello_world',
        'description': 'A sample plugin that shows a Hello World message.',
        'author': 'Jim',
        'version': '1.0',
        'default_shortcut': 'esc',
        'press_times': 4,
        'enabled': True
    }
