# fastshot/enhanced_save_dialog.py

import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
import threading

class EnhancedSaveDialog:
    """Enhanced save dialog with metadata fields."""
    
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.result = None
        
        # Load saved tags and classes for auto-completion
        self.saved_tags = self._load_saved_tags()
        self.saved_classes = self._load_saved_classes()
        
        self._create_dialog()
    
    def _load_saved_tags(self):
        """Load previously used tags for auto-completion."""
        try:
            tags_file = Path.home() / ".fastshot" / "saved_tags.json"
            if tags_file.exists():
                with open(tags_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except:
            return []
    
    def _load_saved_classes(self):
        """Load previously used classes for auto-completion."""
        try:
            classes_file = Path.home() / ".fastshot" / "saved_classes.json"
            if classes_file.exists():
                with open(classes_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except:
            return []
    
    def _save_tags(self, tags):
        """Save tags for future auto-completion."""
        try:
            # Add new tags to saved list
            for tag in tags:
                if tag.strip() and tag.strip() not in self.saved_tags:
                    self.saved_tags.append(tag.strip())
            
            # Keep only last 50 tags
            self.saved_tags = self.saved_tags[-50:]
            
            tags_file = Path.home() / ".fastshot" / "saved_tags.json"
            tags_file.parent.mkdir(parents=True, exist_ok=True)
            with open(tags_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_tags, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving tags: {e}")
    
    def _save_classes(self, class_name):
        """Save class for future auto-completion."""
        try:
            if class_name.strip() and class_name.strip() not in self.saved_classes:
                self.saved_classes.append(class_name.strip())
            
            # Keep only last 30 classes
            self.saved_classes = self.saved_classes[-30:]
            
            classes_file = Path.home() / ".fastshot" / "saved_classes.json"
            classes_file.parent.mkdir(parents=True, exist_ok=True)
            with open(classes_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_classes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving classes: {e}")
    
    def _create_dialog(self):
        """Create the enhanced save dialog."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Save Session")
        self.dialog.geometry("500x600")
        self.dialog.resizable(False, False)
        # Don't use transient to avoid parent window dependency issues
        # self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Ensure window is visible and on top
        self.dialog.attributes('-topmost', True)
        self.dialog.after(100, lambda: self.dialog.attributes('-topmost', False))  # Remove topmost after showing
        
        # Center the dialog on screen
        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width // 2) - (500 // 2)
        y = (screen_height // 2) - (600 // 2)
        
        # Ensure dialog is not positioned off-screen
        x = max(0, min(x, screen_width - 500))
        y = max(0, min(y, screen_height - 600))
        
        self.dialog.geometry(f"500x600+{x}+{y}")
        
        print(f"DEBUG: Save dialog geometry set to: 500x600+{x}+{y}")
        print(f"DEBUG: Screen size: {screen_width}x{screen_height}")
        
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Save Session", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Name field (used in filename)
        ttk.Label(main_frame, text="Name (used in filename):", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.name_entry = ttk.Entry(main_frame, font=("Arial", 10))
        self.name_entry.pack(fill=tk.X, pady=(0, 15))
        
        # Description field (supports Markdown)
        desc_label_frame = ttk.Frame(main_frame)
        desc_label_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(desc_label_frame, text="Description (Markdown supported):", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        ttk.Label(desc_label_frame, text="ℹ️", font=("Arial", 8)).pack(side=tk.RIGHT)
        
        self.desc_entry = tk.Text(main_frame, height=4, wrap=tk.WORD, font=("Arial", 10))
        self.desc_entry.pack(fill=tk.X, pady=(0, 15))
        
        # Add placeholder text for description
        self.desc_entry.insert("1.0", "Enter description here...\nSupports **bold**, *italic*, `code`, etc.")
        self.desc_entry.bind('<FocusIn>', self._on_desc_focus_in)
        self.desc_entry.bind('<FocusOut>', self._on_desc_focus_out)
        
        # Tags field
        ttk.Label(main_frame, text="Tags (comma-separated):", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        # Tags frame with auto-completion
        tags_frame = ttk.Frame(main_frame)
        tags_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.tags_entry = ttk.Entry(tags_frame, font=("Arial", 10))
        self.tags_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.tags_entry.bind('<KeyRelease>', self._on_tags_keyrelease)
        
        # Tags suggestion listbox (initially hidden)
        self.tags_listbox = tk.Listbox(main_frame, height=4)
        self.tags_listbox.bind('<Double-Button-1>', self._on_tag_select)
        self.tags_listbox.bind('<Return>', self._on_tag_select)
        
        # Color field
        ttk.Label(main_frame, text="Color:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.color_var = tk.StringVar(value="blue")
        color_frame = ttk.Frame(main_frame)
        color_frame.pack(fill=tk.X, pady=(0, 15))
        
        colors = ["blue", "red", "green", "yellow", "purple", "orange", "pink", "gray"]
        self.color_combo = ttk.Combobox(color_frame, textvariable=self.color_var, values=colors, state="readonly")
        self.color_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Color preview
        self.color_preview = tk.Label(color_frame, width=3, bg=self.color_var.get())
        self.color_preview.pack(side=tk.RIGHT, padx=(10, 0))
        self.color_combo.bind('<<ComboboxSelected>>', self._update_color_preview)
        
        # Class field
        ttk.Label(main_frame, text="Class:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        class_frame = ttk.Frame(main_frame)
        class_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.class_entry = ttk.Entry(class_frame, font=("Arial", 10))
        self.class_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.class_entry.bind('<KeyRelease>', self._on_class_keyrelease)
        
        # Class suggestion listbox (initially hidden)
        self.class_listbox = tk.Listbox(main_frame, height=4)
        self.class_listbox.bind('<Double-Button-1>', self._on_class_select)
        self.class_listbox.bind('<Return>', self._on_class_select)
        
        # Cloud sync option
        self.cloud_sync_var = tk.BooleanVar()
        cloud_sync_check = ttk.Checkbutton(
            main_frame, 
            text="Save to cloud (if enabled)", 
            variable=self.cloud_sync_var
        )
        cloud_sync_check.pack(anchor=tk.W, pady=(10, 20))
        
        # Check if cloud sync is available
        if hasattr(self.app, 'cloud_sync') and self.app.cloud_sync.cloud_sync_enabled:
            self.cloud_sync_var.set(True)
        else:
            cloud_sync_check.config(state='disabled')
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(buttons_frame, text="Cancel", command=self._cancel).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(buttons_frame, text="Save", command=self._save).pack(side=tk.RIGHT)
        
        # Bind Enter and Escape keys
        self.dialog.bind('<Return>', lambda e: self._save())
        self.dialog.bind('<Escape>', lambda e: self._cancel())
        
        # Focus on name field
        self.name_entry.focus()
        
        # Update color preview
        self._update_color_preview()
    
    def _update_color_preview(self, event=None):
        """Update color preview."""
        try:
            color = self.color_var.get()
            self.color_preview.config(bg=color)
        except:
            pass
    
    def _on_desc_focus_in(self, event):
        """Handle description field focus in."""
        current_text = self.desc_entry.get("1.0", tk.END).strip()
        if current_text == "Enter description here...\nSupports **bold**, *italic*, `code`, etc.":
            self.desc_entry.delete("1.0", tk.END)
            self.desc_entry.config(fg='black')
    
    def _on_desc_focus_out(self, event):
        """Handle description field focus out."""
        current_text = self.desc_entry.get("1.0", tk.END).strip()
        if not current_text:
            self.desc_entry.insert("1.0", "Enter description here...\nSupports **bold**, *italic*, `code`, etc.")
            self.desc_entry.config(fg='gray')
    
    def _on_tags_keyrelease(self, event):
        """Handle tags auto-completion."""
        current_text = self.tags_entry.get()
        if not current_text:
            self.tags_listbox.pack_forget()
            return
        
        # Get current tag being typed
        current_tags = [tag.strip() for tag in current_text.split(',')]
        current_tag = current_tags[-1] if current_tags else ""
        
        if len(current_tag) < 2:
            self.tags_listbox.pack_forget()
            return
        
        # Filter matching tags
        matching_tags = [tag for tag in self.saved_tags 
                        if current_tag.lower() in tag.lower() and tag not in current_tags]
        
        if matching_tags:
            self.tags_listbox.delete(0, tk.END)
            for tag in matching_tags[:10]:  # Show max 10 suggestions
                self.tags_listbox.insert(tk.END, tag)
            
            if not self.tags_listbox.winfo_viewable():
                self.tags_listbox.pack(fill=tk.X, pady=(0, 10))
        else:
            self.tags_listbox.pack_forget()
    
    def _on_tag_select(self, event):
        """Handle tag selection from suggestions."""
        selection = self.tags_listbox.curselection()
        if selection:
            selected_tag = self.tags_listbox.get(selection[0])
            
            # Replace current tag with selected one
            current_text = self.tags_entry.get()
            current_tags = [tag.strip() for tag in current_text.split(',')]
            current_tags[-1] = selected_tag
            
            self.tags_entry.delete(0, tk.END)
            self.tags_entry.insert(0, ', '.join(current_tags))
            
            self.tags_listbox.pack_forget()
            self.tags_entry.focus()
    
    def _on_class_keyrelease(self, event):
        """Handle class auto-completion."""
        current_text = self.class_entry.get()
        if len(current_text) < 2:
            self.class_listbox.pack_forget()
            return
        
        # Filter matching classes
        matching_classes = [cls for cls in self.saved_classes 
                           if current_text.lower() in cls.lower()]
        
        if matching_classes:
            self.class_listbox.delete(0, tk.END)
            for cls in matching_classes[:10]:  # Show max 10 suggestions
                self.class_listbox.insert(tk.END, cls)
            
            if not self.class_listbox.winfo_viewable():
                self.class_listbox.pack(fill=tk.X, pady=(0, 10))
        else:
            self.class_listbox.pack_forget()
    
    def _on_class_select(self, event):
        """Handle class selection from suggestions."""
        selection = self.class_listbox.curselection()
        if selection:
            selected_class = self.class_listbox.get(selection[0])
            self.class_entry.delete(0, tk.END)
            self.class_entry.insert(0, selected_class)
            self.class_listbox.pack_forget()
            self.class_entry.focus()
    
    def _save(self):
        """Save the session with metadata."""
        # Get all field values
        name = self.name_entry.get().strip()
        desc = self.desc_entry.get("1.0", tk.END).strip()
        
        # Check if description is placeholder text
        if desc == "Enter description here...\nSupports **bold**, *italic*, `code`, etc.":
            desc = ""
        
        tags_text = self.tags_entry.get().strip()
        tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()] if tags_text else []
        color = self.color_var.get()
        class_name = self.class_entry.get().strip()
        save_to_cloud = self.cloud_sync_var.get()
        
        # Validate name field
        if name:
            # Sanitize name for filename use
            import re
            sanitized_name = re.sub(r'[^\w\-_\.]', '_', name)
            if sanitized_name != name:
                if not messagebox.askyesno("Name Sanitized", 
                                         f"Name contains invalid characters and will be changed to:\n'{sanitized_name}'\n\nContinue?"):
                    return
                name = sanitized_name
        
        # Validate required fields (optional - can be empty)
        if not name and not desc and not tags and not class_name:
            if not messagebox.askyesno("Empty Metadata", 
                                     "You haven't entered any metadata. Save anyway?"):
                return
        
        # Save tags and classes for auto-completion
        if tags:
            self._save_tags(tags)
        if class_name:
            self._save_classes(class_name)
        
        # Prepare result
        self.result = {
            'name': name,
            'desc': desc,
            'tags': tags,
            'color': color,
            'class': class_name,
            'save_to_cloud': save_to_cloud
        }
        
        # If saving to cloud, show progress dialog
        if save_to_cloud and hasattr(self.app, 'cloud_sync') and self.app.cloud_sync.cloud_sync_enabled:
            self._save_with_progress()
        else:
            self.dialog.destroy()
    
    def _save_with_progress(self):
        """Save with progress dialog for cloud operations."""
        # Create progress dialog
        self.progress_dialog = tk.Toplevel(self.dialog)
        self.progress_dialog.title("Saving Session")
        self.progress_dialog.geometry("400x150")
        self.progress_dialog.resizable(False, False)
        self.progress_dialog.transient(self.dialog)
        self.progress_dialog.grab_set()
        
        # Center progress dialog
        self.progress_dialog.update_idletasks()
        x = self.dialog.winfo_x() + (self.dialog.winfo_width() // 2) - 200
        y = self.dialog.winfo_y() + (self.dialog.winfo_height() // 2) - 75
        self.progress_dialog.geometry(f"400x150+{x}+{y}")
        
        # Progress dialog content
        progress_frame = ttk.Frame(self.progress_dialog, padding="20")
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        # Progress label
        self.progress_label = ttk.Label(progress_frame, text="Initializing save operation...")
        self.progress_label.pack(pady=(0, 10))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=350)
        self.progress_bar.pack(pady=(0, 10))
        
        # Cancel button
        self.cancel_button = ttk.Button(progress_frame, text="Cancel", command=self._cancel_save)
        self.cancel_button.pack()
        
        # Start save operation in background thread
        self.save_cancelled = False
        import threading
        self.save_thread = threading.Thread(target=self._perform_save_operation, daemon=True)
        self.save_thread.start()
        
        # Check progress periodically
        self._check_save_progress()
    
    def _perform_save_operation(self):
        """Perform the actual save operation in background thread."""
        try:
            # Get session data from app
            session_data = self.app.session_manager._prepare_session_data()
            
            # Save to cloud with progress callback
            filename = self.app.cloud_sync.save_session_to_cloud(
                session_data, 
                self.result, 
                progress_callback=self._update_progress
            )
            
            # Store result
            self.save_result = filename
            self.save_error = None
            
        except Exception as e:
            self.save_result = None
            self.save_error = str(e)
    
    def _update_progress(self, progress, message):
        """Update progress from background thread."""
        # Store progress info for main thread to pick up
        self.current_progress = progress
        self.current_message = message
    
    def _check_save_progress(self):
        """Check save progress and update UI (runs in main thread)."""
        if self.save_cancelled:
            return
        
        # Update progress if available
        if hasattr(self, 'current_progress') and hasattr(self, 'current_message'):
            progress = self.current_progress
            message = self.current_message
            
            if progress >= 0:
                self.progress_bar['value'] = progress
                self.progress_label.config(text=message)
            else:
                # Error occurred
                self.progress_label.config(text=f"Error: {message}")
                self.cancel_button.config(text="Close")
                return
        
        # Check if save thread is done
        if hasattr(self, 'save_thread') and not self.save_thread.is_alive():
            # Save operation completed
            if hasattr(self, 'save_result'):
                if self.save_result:
                    # Success
                    self.progress_bar['value'] = 100
                    self.progress_label.config(text="Save completed successfully!")
                    self.dialog.after(1000, self._close_progress_and_dialog)  # Close after 1 second
                else:
                    # Failed
                    error_msg = getattr(self, 'save_error', 'Unknown error')
                    self.progress_label.config(text=f"Save failed: {error_msg}")
                    self.cancel_button.config(text="Close")
            return
        
        # Continue checking
        self.dialog.after(100, self._check_save_progress)
    
    def _cancel_save(self):
        """Cancel the save operation."""
        self.save_cancelled = True
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.destroy()
        # Don't destroy main dialog, let user try again
    
    def _close_progress_and_dialog(self):
        """Close both progress dialog and main dialog after successful save."""
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.destroy()
        self.dialog.destroy()
    
    def _cancel(self):
        """Cancel the dialog."""
        self.result = None
        self.dialog.destroy()
    
    def show(self):
        """Show the dialog and return the result."""
        self.dialog.wait_window()
        return self.result 