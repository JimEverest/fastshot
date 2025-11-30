# Additional methods to add to QuickNotesUI class

def _check_sync_status_on_show(self):
    """Check sync status when window is shown."""
    try:
        print("DEBUG: Checking sync status on window show...")
        
        # This will trigger a background sync status check
        # and refresh the UI to show updated status
        if self.notes_manager:
            # Refresh the notes list which will trigger status check
            self._load_notes_list()
            self._show_status("Sync status updated")
        
    except Exception as e:
        print(f"Error checking sync status: {e}")
        self._show_status("Error checking sync status", error=True)

def _refresh_after_sync(self):
    """Refresh UI after sync operation."""
    try:
        # Reload notes list to show updated sync status
        self._load_notes_list()
        self._show_status("Notes list refreshed after sync")
    except Exception as e:
        print(f"Error refreshing after sync: {e}")

def _on_window_close(self):
    """Handle window close event."""
    self.hide_window()

def _show_status(self, message: str, error: bool = False):
    """Show status message in the status label."""
    if hasattr(self, 'status_label') and self.status_label:
        self.status_label.configure(text=message)
        if error:
            # Could add error styling here
            print(f"ERROR: {message}")
        else:
            print(f"STATUS: {message}")

def _clear_editor(self):
    """Clear the editor content."""
    if self.title_entry:
        self.title_entry.delete(0, tk.END)
    if self.editor_text:
        self.editor_text.delete("1.0", tk.END)
    if self.info_label:
        self.info_label.configure(text="")
    self.current_note_id = None

def _prev_page(self):
    """Go to previous page."""
    if self.current_page > 1:
        self.current_page -= 1
        self._load_notes_list()

def _next_page(self):
    """Go to next page."""
    self.current_page += 1
    self._load_notes_list()

def _show_search_history(self):
    """Show search history dialog."""
    if not self.notes_manager:
        return
    
    try:
        history = self.notes_manager.get_search_history(10)
        if not history:
            messagebox.showinfo("Search History", "No search history available.", parent=self.window)
            return
        
        # Create a simple dialog to show history
        history_text = "Recent searches:\n\n"
        for i, entry in enumerate(history, 1):
            query = entry.get("query", "")
            count = entry.get("result_count", 0)
            history_text += f"{i}. '{query}' ({count} results)\n"
        
        messagebox.showinfo("Search History", history_text, parent=self.window)
        
    except Exception as e:
        print(f"Error showing search history: {e}")

def _on_search_key_press(self, event):
    """Handle key press in search entry."""
    # Could implement search suggestions here
    pass

def _on_search_focus_in(self, event):
    """Handle search entry focus in."""
    # Could show search suggestions here
    pass

def _on_search_focus_out(self, event):
    """Handle search entry focus out."""
    # Could hide search suggestions here
    pass

def _show_cache_status(self):
    """Show cache status dialog."""
    if not self.cache_manager:
        messagebox.showerror("Error", "Cache manager not available", parent=self.window)
        return
    
    try:
        cache_stats = self.cache_manager.get_cache_stats()
        
        # Format cache status information
        status_text = "=========== Cache Status: ============\n"
        status_text += "Cache Information:\n"
        status_text += f"Version: {cache_stats.get('version', 'Unknown')}\n"
        status_text += f"Last Sync: {cache_stats.get('last_sync', 'Never')}\n"
        status_text += f"Cache Size: {cache_stats.get('cache_size_mb', 0):.2f} MB\n"
        status_text += f"Total Notes: {cache_stats.get('total_notes', 0)}\n"
        status_text += f"Actual Notes Count: {cache_stats.get('actual_notes_count', 0)}\n"
        
        status_text += "\nCache Status:\n"
        cache_status = cache_stats.get('cache_status', {})
        status_text += f"Index Exists: {cache_status.get('index_exists', False)}\n"
        status_text += f"Is Valid: {cache_status.get('is_valid', False)}\n"
        
        status_text += "\nIntegrity Check:\n"
        integrity = cache_stats.get('integrity_check', {})
        status_text += f"Last Validated: {integrity.get('last_validated', 'Never')}\n"
        status_text += f"Status: {integrity.get('status', 'Unknown')}\n"
        status_text += f"Checksum: {integrity.get('checksum', 'None')[:20]}...\n"
        
        status_text += "\nCache Paths:\n"
        paths = cache_stats.get('cache_paths', {})
        status_text += f"Cache Directory: {paths.get('cache_dir', 'Unknown')}\n"
        status_text += f"Index File: {paths.get('overall_notes_index_file', 'Unknown')}\n"
        
        # Add sync status if available
        if self.notes_manager:
            sync_status = self.notes_manager.get_sync_status()
            status_text += "\nSync Status:\n"
            status_text += f"Cloud Sync Available: {sync_status.get('cloud_sync_available', False)}\n"
            status_text += f"Cloud Sync Enabled: {sync_status.get('cloud_sync_enabled', False)}\n"
            status_text += f"Sync Health: {sync_status.get('sync_health', 'Unknown')}\n"
            status_text += f"Failed Syncs: {sync_status.get('failed_syncs', 0)}\n"
            status_text += f"Last Sync Attempt: {sync_status.get('last_sync_attempt', 'Never')}\n"
        
        # Show in a scrollable dialog
        dialog = tk.Toplevel(self.window)
        dialog.title("Cache Status")
        dialog.geometry("600x500")
        dialog.transient(self.window)
        dialog.grab_set()
        
        # Create text widget with scrollbar
        text_frame = tk.Frame(dialog)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("Consolas", 10))
        scrollbar = tk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        text_widget.insert("1.0", status_text)
        text_widget.configure(state="disabled")
        
        # Close button
        close_btn = tk.Button(dialog, text="Close", command=dialog.destroy)
        close_btn.pack(pady=5)
        
    except Exception as e:
        print(f"Error showing cache status: {e}")
        messagebox.showerror("Error", f"Failed to get cache status: {e}", parent=self.window)

def _rebuild_index(self):
    """Rebuild notes index from cloud."""
    if not self.notes_manager:
        messagebox.showerror("Error", "Notes manager not available", parent=self.window)
        return
    
    # Get cloud sync manager from app
    cloud_sync = getattr(self.app, 'cloud_sync', None)
    if not cloud_sync:
        messagebox.showerror("Error", "Cloud sync not available", parent=self.window)
        return
    
    # Confirm operation
    if not messagebox.askyesno("Confirm Rebuild", 
                              "This will rebuild the notes index by downloading all notes from cloud.\n\n"
                              "This may take some time. Continue?", 
                              parent=self.window):
        return
    
    # Show progress dialog
    progress_dialog = self._create_progress_dialog("Rebuild Index", "Rebuilding notes index from cloud...")
    
    def rebuild_worker():
        try:
            self._update_progress(progress_dialog, 20, "Scanning cloud storage...")
            
            # Rebuild index
            result = cloud_sync.rebuild_notes_index()
            
            if result and result.get("success"):
                self._update_progress(progress_dialog, 80, "Updating local cache...")
                
                # Update local cache with rebuilt index
                if self.cache_manager:
                    cloud_index = cloud_sync.load_notes_overall_index()
                    if cloud_index:
                        self.cache_manager.update_cache_index(cloud_index)
                
                self._update_progress(progress_dialog, 100, "Rebuild completed successfully")
                
                # Refresh UI
                self.window.after(0, self._refresh_after_sync)
                
                # Show success message
                total_notes = result.get("total_notes", 0)
                self.window.after(0, lambda: messagebox.showinfo(
                    "Rebuild Complete", 
                    f"Successfully rebuilt index with {total_notes} notes.",
                    parent=self.window
                ))
            else:
                error_msg = result.get("error", "Unknown error") if result else "Rebuild failed"
                self._update_progress(progress_dialog, -1, f"Rebuild failed: {error_msg}")
                
                self.window.after(0, lambda: messagebox.showerror(
                    "Rebuild Failed", 
                    f"Failed to rebuild index: {error_msg}",
                    parent=self.window
                ))
            
            # Close progress dialog
            self.window.after(3000, lambda: self._close_progress_dialog(progress_dialog))
            
        except Exception as e:
            error_msg = f"Rebuild error: {str(e)}"
            print(error_msg)
            self._update_progress(progress_dialog, -1, error_msg)
            
            self.window.after(0, lambda: messagebox.showerror(
                "Rebuild Error", 
                error_msg,
                parent=self.window
            ))
            
            self.window.after(3000, lambda: self._close_progress_dialog(progress_dialog))
    
    # Start rebuild in background thread
    rebuild_thread = threading.Thread(target=rebuild_worker, daemon=True)
    rebuild_thread.start()

def _create_progress_dialog(self, title: str, message: str):
    """Create a progress dialog."""
    dialog = tk.Toplevel(self.window)
    dialog.title(title)
    dialog.geometry("400x150")
    dialog.transient(self.window)
    dialog.grab_set()
    
    # Center the dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")
    
    # Progress label
    progress_label = tk.Label(dialog, text=message, wraplength=350)
    progress_label.pack(pady=20)
    
    # Progress bar
    progress_bar = ttk.Progressbar(dialog, mode='indeterminate')
    progress_bar.pack(pady=10, padx=20, fill="x")
    progress_bar.start()
    
    # Store references
    dialog.progress_label = progress_label
    dialog.progress_bar = progress_bar
    
    return dialog

def _update_progress(self, dialog, progress: int, message: str):
    """Update progress dialog."""
    if not dialog or not dialog.winfo_exists():
        return
    
    try:
        dialog.progress_label.configure(text=message)
        
        if progress < 0:
            # Error state
            dialog.progress_bar.configure(mode='determinate', value=0)
            dialog.progress_bar.stop()
        elif progress >= 100:
            # Complete state
            dialog.progress_bar.configure(mode='determinate', value=100)
            dialog.progress_bar.stop()
        else:
            # Progress state
            dialog.progress_bar.configure(mode='determinate', value=progress)
    except Exception as e:
        print(f"Error updating progress: {e}")

def _close_progress_dialog(self, dialog):
    """Close progress dialog."""
    try:
        if dialog and dialog.winfo_exists():
            dialog.destroy()
    except Exception as e:
        print(f"Error closing progress dialog: {e}")

def _offer_offline_mode(self, error_message: str):
    """Offer to work in offline mode when cloud sync fails."""
    result = messagebox.askyesno(
        "Cloud Sync Failed", 
        f"{error_message}\n\nWould you like to continue working offline?\n\n"
        "Your notes will be saved locally and can be synced later when cloud is available.",
        parent=self.window
    )
    if result:
        self._show_status("Working in offline mode - notes saved locally only")
    return result