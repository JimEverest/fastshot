# fastshot/quick_notes_ui.py

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import customtkinter as ctk
from typing import Dict, List, Optional, Any
import threading
import time
from datetime import datetime


class QuickNotesUI:
    """Quick Notes UI with split-pane layout for note management."""
    
    def __init__(self, app):
        """Initialize Quick Notes UI with app context."""
        self.app = app
        self.window = None
        self.is_visible = False
        
        # UI components
        self.notes_list_frame = None
        self.editor_frame = None
        self.search_var = None
        self.notes_tree = None
        self.editor_text = None
        self.title_entry = None
        
        # Data management
        self.current_note_id = None
        self.current_page = 1
        self.per_page = 15
        self.search_query = ""
        self.notes_data = []
        self.filtered_notes = []
        self._note_id_map = {}  # Initialize note ID mapping
        
        # Get managers from app
        self.notes_manager = getattr(app, 'notes_manager', None)
        self.cache_manager = getattr(app, 'notes_cache', None)
        
        if not self.notes_manager:
            print("Warning: NotesManager not found in app")
        if not self.cache_manager:
            print("Warning: NotesCacheManager not found in app")
    
    def show_window(self):
        """Show the Quick Notes window."""
        try:
            print("DEBUG: show_window() called")
            
            # Check if window exists and is valid
            window_exists = False
            if self.window:
                try:
                    # Try to access window properties to verify it's still valid
                    self.window.winfo_exists()
                    self.window.winfo_viewable()
                    window_exists = True
                    print("DEBUG: Window exists and is valid")
                except:
                    # Window object exists but is destroyed, clean it up
                    print("DEBUG: Window object exists but is destroyed, cleaning up")
                    self.window = None
                    self.is_visible = False
            
            if window_exists:
                # Window exists, just bring to front
                print("DEBUG: Bringing existing window to front")
                self.window.lift()
                self.window.focus_force()
                self.window.deiconify()  # Make sure it's not minimized
                return
            
            # Create new window
            print("DEBUG: Creating new window")
            self._create_window()
            print("DEBUG: Window created, loading notes list")
            self._load_notes_list()
            print("DEBUG: Notes list loaded, setting visible flag")
            self.is_visible = True
            print("DEBUG: show_window() completed successfully")
        except Exception as e:
            print(f"ERROR in show_window(): {e}")
            import traceback
            traceback.print_exc()
    
    def hide_window(self):
        """Hide the Quick Notes window."""
        if self.window and self.window.winfo_exists():
            self.window.withdraw()
            self.is_visible = False
    
    def toggle_window(self):
        """Toggle Quick Notes window visibility."""
        if self.is_visible and self.window and self.window.winfo_exists():
            self.hide_window()
        else:
            self.show_window()
    
    def _create_window(self):
        """Create the main Quick Notes window."""
        self.window = ctk.CTkToplevel()
        self.window.title("Quick Notes")
        self.window.geometry("1000x700")
        self.window.minsize(800, 500)
        
        # Configure window properties
        self.window.attributes('-topmost', True)
        self.window.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        # Create main UI
        self._create_ui()
    
    def _create_ui(self):
        """Create the main UI layout."""
        # Main container with padding
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create split pane layout
        paned_window = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=5)
        paned_window.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Left pane - Notes list
        self._create_notes_list_pane(paned_window)
        
        # Right pane - Editor
        self._create_editor_pane(paned_window)
        
        # Add panes to PanedWindow
        paned_window.add(self.notes_list_frame, minsize=300)
        paned_window.add(self.editor_frame, minsize=400)
        
        # Set initial pane sizes (40% left, 60% right)
        self.window.after(100, lambda: paned_window.sash_place(0, 400, 0))
    
    def _create_notes_list_pane(self, parent):
        """Create the notes list pane."""
        self.notes_list_frame = ctk.CTkFrame(parent)
        
        # Search section
        search_frame = ctk.CTkFrame(self.notes_list_frame)
        search_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(search_frame, text="Search:").pack(side="left", padx=(5, 5))
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search_changed)
        self.search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var, placeholder_text="Search by name or short code...")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        # Bind events for search suggestions
        self.search_entry.bind("<KeyPress>", self._on_search_key_press)
        self.search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self._on_search_focus_out)
        
        # Clear search button
        clear_btn = ctk.CTkButton(search_frame, text="Clear", width=60, command=self._clear_search)
        clear_btn.pack(side="right", padx=(5, 5))
        
        # Search history button
        history_btn = ctk.CTkButton(search_frame, text="History", width=60, command=self._show_search_history)
        history_btn.pack(side="right", padx=(5, 5))
        
        # Search suggestions dropdown (initially hidden)
        self.suggestions_frame = None
        
        # Notes list with scrollbar
        list_frame = ctk.CTkFrame(self.notes_list_frame)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create Treeview for notes list
        columns = ("title", "short_code", "created", "updated", "actions")
        self.notes_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        self.notes_tree.heading("title", text="Title")
        self.notes_tree.heading("short_code", text="Code")
        self.notes_tree.heading("created", text="Created")
        self.notes_tree.heading("updated", text="Updated")
        self.notes_tree.heading("actions", text="Actions")
        
        # Set column widths
        self.notes_tree.column("title", width=150, minwidth=100)
        self.notes_tree.column("short_code", width=60, minwidth=50)
        self.notes_tree.column("created", width=80, minwidth=70)
        self.notes_tree.column("updated", width=80, minwidth=70)
        self.notes_tree.column("actions", width=80, minwidth=70)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.notes_tree.yview)
        self.notes_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack treeview and scrollbar
        self.notes_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind selection event
        self.notes_tree.bind("<<TreeviewSelect>>", self._on_note_selected)
        self.notes_tree.bind("<Double-1>", self._on_note_double_click)
        
        # Pagination controls
        pagination_frame = ctk.CTkFrame(self.notes_list_frame)
        pagination_frame.pack(fill="x", padx=10, pady=5)
        
        self.prev_btn = ctk.CTkButton(pagination_frame, text="Previous", width=80, command=self._prev_page)
        self.prev_btn.pack(side="left", padx=5)
        
        self.page_label = ctk.CTkLabel(pagination_frame, text="Page 1 of 1")
        self.page_label.pack(side="left", expand=True)
        
        self.next_btn = ctk.CTkButton(pagination_frame, text="Next", width=80, command=self._next_page)
        self.next_btn.pack(side="right", padx=5)
        
        # Action buttons
        actions_frame = ctk.CTkFrame(self.notes_list_frame)
        actions_frame.pack(fill="x", padx=10, pady=(5, 10))
        
        new_btn = ctk.CTkButton(actions_frame, text="New Note", command=self._create_new_note)
        new_btn.pack(side="left", padx=5)
        
        delete_btn = ctk.CTkButton(actions_frame, text="Delete", fg_color="red", command=self._delete_selected_note)
        delete_btn.pack(side="left", padx=5)
        
        cache_status_btn = ctk.CTkButton(actions_frame, text="Cache Status", command=self._show_cache_status)
        cache_status_btn.pack(side="right", padx=5)
        
        sync_btn = ctk.CTkButton(actions_frame, text="Force Sync", command=self._force_sync)
        sync_btn.pack(side="right", padx=5)
        
        rebuild_btn = ctk.CTkButton(actions_frame, text="Rebuild Index", command=self._rebuild_index)
        rebuild_btn.pack(side="right", padx=5)
    
    def _create_editor_pane(self, parent):
        """Create the editor pane."""
        self.editor_frame = ctk.CTkFrame(parent)
        
        # Title section
        title_frame = ctk.CTkFrame(self.editor_frame)
        title_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(title_frame, text="Title:").pack(side="left", padx=(5, 5))
        
        self.title_entry = ctk.CTkEntry(title_frame, placeholder_text="Enter note title...")
        self.title_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        # Note info
        self.info_label = ctk.CTkLabel(title_frame, text="", font=("Arial", 10))
        self.info_label.pack(side="right", padx=(5, 5))
        
        # Editor section
        editor_container = ctk.CTkFrame(self.editor_frame)
        editor_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Text editor with scrollbar
        text_frame = tk.Frame(editor_container)
        text_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.editor_text = tk.Text(text_frame, wrap=tk.WORD, font=("Consolas", 11))
        editor_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.editor_text.yview)
        self.editor_text.configure(yscrollcommand=editor_scrollbar.set)
        
        self.editor_text.pack(side="left", fill="both", expand=True)
        editor_scrollbar.pack(side="right", fill="y")
        
        # Editor action buttons
        editor_actions_frame = ctk.CTkFrame(self.editor_frame)
        editor_actions_frame.pack(fill="x", padx=10, pady=(5, 10))
        
        save_btn = ctk.CTkButton(editor_actions_frame, text="Save Note", fg_color="green", command=self._save_current_note)
        save_btn.pack(side="left", padx=5)
        
        url_btn = ctk.CTkButton(editor_actions_frame, text="Get Public URL", command=self._get_public_url)
        url_btn.pack(side="left", padx=5)
        
        # Status label
        self.status_label = ctk.CTkLabel(editor_actions_frame, text="Ready", font=("Arial", 10))
        self.status_label.pack(side="right", padx=5)
    
    def _load_notes_list(self):
        """Load notes list from cache or notes manager."""
        if not self.notes_manager:
            print("NotesManager not available")
            return
        
        try:
            # Get notes from manager with pagination
            result = self.notes_manager.list_notes(page=self.current_page, per_page=self.per_page)
            self.notes_data = result.get("notes", [])
            pagination = result.get("pagination", {})
            
            # Apply search filter if active
            if self.search_query:
                self._apply_search_filter()
            else:
                self.filtered_notes = self.notes_data.copy()
            
            # Update UI
            self._update_notes_tree()
            self._update_pagination_controls(pagination)
            
            # Load most recent note if no note is currently selected
            if not self.current_note_id and self.filtered_notes:
                self._load_note_content(self.filtered_notes[0]["id"])
            
        except Exception as e:
            print(f"Error loading notes list: {e}")
            self._show_status(f"Error loading notes: {e}", error=True)
    
    def _update_notes_tree(self):
        """Update the notes tree view with current data."""
        # Clear existing items
        for item in self.notes_tree.get_children():
            self.notes_tree.delete(item)
        
        # Clear the note ID mapping
        if not hasattr(self, '_note_id_map'):
            self._note_id_map = {}
        self._note_id_map.clear()
        
        # Add notes to tree
        for note in self.filtered_notes:
            # Format dates for display
            created_date = self._format_date(note.get("created_at", ""))
            updated_date = self._format_date(note.get("updated_at", ""))
            
            # Insert note into tree
            item_id = self.notes_tree.insert("", "end", values=(
                note.get("title", "Untitled")[:30],  # Truncate long titles
                note.get("short_code", ""),
                created_date,
                updated_date,
                "📋 🗑️"  # Action icons
            ))
            
            # Store note ID in mapping dictionary
            self._note_id_map[item_id] = note.get("id", "")
    
    def _format_date(self, date_str: str) -> str:
        """Format ISO date string for display."""
        try:
            if not date_str:
                return ""
            
            # Parse ISO format date
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            
            # Format for display (MM/DD HH:MM)
            return dt.strftime("%m/%d %H:%M")
        except Exception:
            return date_str[:10] if date_str else ""
    
    def _update_pagination_controls(self, pagination: Dict):
        """Update pagination controls based on pagination info."""
        current_page = pagination.get("current_page", 1)
        total_pages = pagination.get("total_pages", 1)
        total_notes = pagination.get("total_notes", 0)
        
        # Update page label
        self.page_label.configure(text=f"Page {current_page} of {total_pages} ({total_notes} notes)")
        
        # Update button states
        self.prev_btn.configure(state="normal" if pagination.get("has_prev", False) else "disabled")
        self.next_btn.configure(state="normal" if pagination.get("has_next", False) else "disabled")
    
    def _on_search_changed(self, *args):
        """Handle search query changes."""
        query = self.search_var.get().strip()
        
        # Debounce search to avoid too many calls
        if hasattr(self, '_search_timer'):
            self.window.after_cancel(self._search_timer)
        
        self._search_timer = self.window.after(300, lambda: self._perform_search(query))
    
    def _perform_search(self, query: str):
        """Perform search with the given query."""
        self.search_query = query
        
        if not query:
            # No search query, show all notes
            self.filtered_notes = self.notes_data.copy()
        else:
            # Use notes manager search functionality
            if self.notes_manager:
                search_results = self.notes_manager.search_notes(query)
                self.filtered_notes = search_results
            else:
                # Fallback: simple local search
                self._apply_search_filter()
        
        # Update tree view
        self._update_notes_tree()
        
        # Update status
        if query:
            self._show_status(f"Found {len(self.filtered_notes)} notes matching '{query}'")
        else:
            self._show_status("Showing all notes")
    
    def _apply_search_filter(self):
        """Apply search filter to current notes data."""
        if not self.search_query:
            self.filtered_notes = self.notes_data.copy()
            return
        
        query_lower = self.search_query.lower()
        self.filtered_notes = []
        
        for note in self.notes_data:
            # Search in title and short code
            title_match = query_lower in note.get("title", "").lower()
            code_match = query_lower in note.get("short_code", "").lower()
            
            if title_match or code_match:
                self.filtered_notes.append(note)
    
    def _clear_search(self):
        """Clear search query and show all notes."""
        self.search_var.set("")
        self.search_query = ""
        self.filtered_notes = self.notes_data.copy()
        self._update_notes_tree()
        self._show_status("Showing all notes")
    
    def _on_note_selected(self, event):
        """Handle note selection in the tree."""
        selection = self.notes_tree.selection()
        if not selection:
            return
        
        # Get selected item
        item = selection[0]
        
        # Ensure _note_id_map exists
        if not hasattr(self, '_note_id_map'):
            self._note_id_map = {}
        
        # Get note ID from mapping dictionary
        if item in self._note_id_map:
            note_id = self._note_id_map[item]
            if note_id and note_id != self.current_note_id:
                self._load_note_content(note_id)
    
    def _on_note_double_click(self, event):
        """Handle double-click on note (focus on editor)."""
        self.editor_text.focus_set()
    
    def _load_note_content(self, note_id: str):
        """Load note content into the editor."""
        if not self.notes_manager:
            return
        
        try:
            note_data = self.notes_manager.get_note(note_id)
            if not note_data:
                self._show_status(f"Note not found: {note_id}", error=True)
                return
            
            # Update editor with note content
            self.current_note_id = note_id
            self.title_entry.delete(0, tk.END)
            self.title_entry.insert(0, note_data.get("title", ""))
            
            self.editor_text.delete("1.0", tk.END)
            self.editor_text.insert("1.0", note_data.get("content", ""))
            
            # Update info label
            created = self._format_date(note_data.get("created_at", ""))
            updated = self._format_date(note_data.get("updated_at", ""))
            word_count = note_data.get("metadata", {}).get("word_count", 0)
            
            info_text = f"Code: {note_data.get('short_code', '')} | Created: {created} | Updated: {updated} | Words: {word_count}"
            self.info_label.configure(text=info_text)
            
            self._show_status(f"Loaded note: {note_data.get('title', 'Untitled')}")
            
        except Exception as e:
            print(f"Error loading note content: {e}")
            self._show_status(f"Error loading note: {e}", error=True)
    
    def _create_new_note(self):
        """Create a new note."""
        if not self.notes_manager:
            messagebox.showerror("Error", "Notes manager not available")
            return
        
        # Get title from user
        title = simpledialog.askstring("New Note", "Enter note title:", parent=self.window)
        if not title or not title.strip():
            return
        
        try:
            # Create new note
            note_id = self.notes_manager.create_note(title.strip())
            if note_id:
                # Refresh notes list
                self._load_notes_list()
                
                # Load the new note in editor
                self._load_note_content(note_id)
                
                # Focus on editor for immediate editing
                self.editor_text.focus_set()
                
                self._show_status(f"Created new note: {title}")
            else:
                self._show_status("Failed to create note", error=True)
                
        except Exception as e:
            print(f"Error creating note: {e}")
            self._show_status(f"Error creating note: {e}", error=True)
    
    def _save_current_note(self):
        """Save the currently edited note."""
        if not self.current_note_id or not self.notes_manager:
            messagebox.showwarning("Warning", "No note selected or notes manager not available")
            return
        
        try:
            # Get current content
            title = self.title_entry.get().strip()
            content = self.editor_text.get("1.0", tk.END).strip()
            
            if not title:
                messagebox.showerror("Error", "Note title cannot be empty")
                return
            
            # Update note
            success = self.notes_manager.update_note(self.current_note_id, title=title, content=content)
            
            if success:
                # Refresh notes list to show updated info
                self._load_notes_list()
                
                # Reload note to update info display
                self._load_note_content(self.current_note_id)
                
                self._show_status("Note saved successfully")
            else:
                self._show_status("Failed to save note", error=True)
                
        except Exception as e:
            print(f"Error saving note: {e}")
            self._show_status(f"Error saving note: {e}", error=True)
    
    def _delete_selected_note(self):
        """Delete the selected note."""
        selection = self.notes_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "No note selected")
            return
        
        # Get selected note
        item = selection[0]
        
        # Ensure _note_id_map exists
        if not hasattr(self, '_note_id_map'):
            self._note_id_map = {}
        
        # Get note ID from mapping dictionary
        if item not in self._note_id_map:
            messagebox.showwarning("Warning", "Cannot find note ID for selected item")
            return
        
        note_id = self._note_id_map[item]
        if not note_id or not self.notes_manager:
            return
        
        # Get note title for confirmation
        note_data = self.notes_manager.get_note(note_id)
        note_title = note_data.get("title", "Unknown") if note_data else "Unknown"
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the note '{note_title}'?", parent=self.window):
            return
        
        try:
            # Delete note
            success = self.notes_manager.delete_note(note_id)
            
            if success:
                # Clear editor if this was the current note
                if note_id == self.current_note_id:
                    self._clear_editor()
                
                # Refresh notes list
                self._load_notes_list()
                
                self._show_status(f"Deleted note: {note_title}")
            else:
                self._show_status("Failed to delete note", error=True)
                
        except Exception as e:
            print(f"Error deleting note: {e}")
            self._show_status(f"Error deleting note: {e}", error=True)
    
    def _get_public_url(self):
        """Get public URL for the current note."""
        if not self.current_note_id or not self.notes_manager:
            messagebox.showwarning("Warning", "No note selected or notes manager not available")
            return
        
        try:
            url = self.notes_manager.get_public_url(self.current_note_id)
            if url:
                # Copy to clipboard
                self.window.clipboard_clear()
                self.window.clipboard_append(url)
                self._show_status("Public URL copied to clipboard")
                messagebox.showinfo("Public URL", f"URL copied to clipboard:\n{url}", parent=self.window)
            else:
                self._show_status("Public URL not available", error=True)
                
        except Exception as e:
            print(f"Error getting public URL: {e}")
            self._show_status(f"Error getting public URL: {e}", error=True)
    
    def _force_sync(self):
        """Force sync with cloud storage - download overall index from cloud."""
        if not self.cache_manager:
            messagebox.showerror("Error", "Cache manager not available")
            return
        
        # Get cloud sync manager from app
        cloud_sync = getattr(self.app, 'cloud_sync', None)
        if not cloud_sync:
            # Graceful degradation - show warning but allow offline operation
            result = messagebox.askyesno("Cloud Sync Unavailable", 
                                       "Cloud sync is not available. Would you like to continue working offline?\n\n"
                                       "Your notes will be saved locally and can be synced later when cloud is available.",
                                       parent=self.window)
            if result:
                self._show_status("Working in offline mode - notes saved locally only", error=False)
            return
        
        # Show progress dialog
        progress_dialog = self._create_progress_dialog("Force Sync", "Downloading notes index from cloud...")
        
        def sync_worker():
            try:
                # Update progress
                self._update_progress(progress_dialog, 20, "Connecting to cloud storage...")
                
                # Test cloud connectivity first
                sync_status = self.notes_manager.get_sync_status() if self.notes_manager else {"sync_health": "unknown"}
                
                if sync_status.get("sync_health") == "failed":
                    error_msg = f"Cloud connectivity test failed: {sync_status.get('last_error', 'Unknown error')}"
                    self._update_progress(progress_dialog, -1, error_msg)
                    
                    # Offer to work offline
                    self.window.after(0, lambda: self._offer_offline_mode("Cloud connectivity failed"))
                    return
                
                # Load overall index from cloud
                cloud_index = cloud_sync.load_notes_overall_index()
                
                if cloud_index is None:
                    self._update_progress(progress_dialog, -1, "Failed to download index from cloud")
                    
                    # Offer to work offline
                    self.window.after(0, lambda: self._offer_offline_mode("Failed to download notes index"))
                    return
                
                self._update_progress(progress_dialog, 60, "Updating local cache...")
                
                # Update local cache with cloud index
                self.cache_manager.update_cache_index(cloud_index)
                
                self._update_progress(progress_dialog, 90, "Refreshing notes list...")
                
                # Refresh the UI on main thread
                self.window.after(0, self._refresh_after_sync)
                
                self._update_progress(progress_dialog, 100, "Force sync completed successfully")
                
                # Close progress dialog after delay
                self.window.after(2000, lambda: self._close_progress_dialog(progress_dialog))
                
            except Exception as e:
                error_msg = f"Force sync failed: {str(e)}"
                print(error_msg)
                self._update_progress(progress_dialog, -1, error_msg)
                
                # Offer to work offline
                self.window.after(0, lambda: self._offer_offline_mode(f"Sync error: {str(e)}"))
                
                # Close progress dialog after delay
                self.window.after(3000, lambda: self._close_progress_dialog(progress_dialog))
        
        # Start sync in background thread
        sync_thread = threading.Thread(target=sync_worker, daemon=True)
        sync_thread.start()
    
    def _rebuild_index(self):
        """Rebuild notes index from cloud - reconstruct from all cloud notes."""
        if not self.cache_manager:
            messagebox.showerror("Error", "Cache manager not available")
            return
        
        # Get cloud sync manager from app
        cloud_sync = getattr(self.app, 'cloud_sync', None)
        if not cloud_sync:
            messagebox.showerror("Error", "Cloud sync not available")
            return
        
        # Confirm rebuild operation
        if not messagebox.askyesno("Confirm Rebuild", 
                                   "This will rebuild the notes index by downloading all notes from cloud. This may take some time. Continue?", 
                                   parent=self.window):
            return
        
        # Show progress dialog
        progress_dialog = self._create_progress_dialog("Rebuild Index", "Rebuilding notes index from cloud...")
        
        def rebuild_worker():
            try:
                # Update progress
                self._update_progress(progress_dialog, 10, "Connecting to cloud storage...")
                
                # Rebuild index in cloud
                result = cloud_sync.rebuild_notes_index()
                
                if not result.get("success", False):
                    error_msg = result.get("error", "Unknown error during rebuild")
                    self._update_progress(progress_dialog, -1, f"Rebuild failed: {error_msg}")
                    return
                
                self._update_progress(progress_dialog, 60, "Downloading rebuilt index...")
                
                # Load the rebuilt index from cloud
                cloud_index = cloud_sync.load_notes_overall_index()
                
                if cloud_index is None:
                    self._update_progress(progress_dialog, -1, "Failed to download rebuilt index")
                    return
                
                self._update_progress(progress_dialog, 80, "Updating local cache...")
                
                # Update local cache with rebuilt index
                self.cache_manager.update_cache_index(cloud_index)
                
                self._update_progress(progress_dialog, 95, "Refreshing notes list...")
                
                # Refresh the UI on main thread
                self.window.after(0, self._refresh_after_sync)
                
                total_notes = result.get("total_notes", 0)
                success_msg = f"Index rebuilt successfully with {total_notes} notes"
                self._update_progress(progress_dialog, 100, success_msg)
                
                # Close progress dialog after delay
                self.window.after(3000, lambda: self._close_progress_dialog(progress_dialog))
                
            except Exception as e:
                error_msg = f"Rebuild failed: {str(e)}"
                print(error_msg)
                self._update_progress(progress_dialog, -1, error_msg)
                # Close progress dialog after delay
                self.window.after(3000, lambda: self._close_progress_dialog(progress_dialog))
        
        # Start rebuild in background thread
        rebuild_thread = threading.Thread(target=rebuild_worker, daemon=True)
        rebuild_thread.start()
    
    def _create_progress_dialog(self, title: str, initial_message: str):
        """Create a progress dialog for long-running operations."""
        progress_window = ctk.CTkToplevel(self.window)
        progress_window.title(title)
        progress_window.geometry("400x150")
        progress_window.resizable(False, False)
        progress_window.attributes('-topmost', True)
        progress_window.transient(self.window)
        
        # Center the dialog
        progress_window.grab_set()
        
        # Progress frame
        progress_frame = ctk.CTkFrame(progress_window)
        progress_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Status label
        status_label = ctk.CTkLabel(progress_frame, text=initial_message, wraplength=350)
        status_label.pack(pady=(10, 15))
        
        # Progress bar
        progress_bar = ctk.CTkProgressBar(progress_frame, width=300)
        progress_bar.pack(pady=(0, 10))
        progress_bar.set(0)
        
        # Cancel button (initially disabled)
        cancel_btn = ctk.CTkButton(progress_frame, text="Cancel", state="disabled", width=100)
        cancel_btn.pack(pady=(10, 0))
        
        # Store references in the window object
        progress_window.status_label = status_label
        progress_window.progress_bar = progress_bar
        progress_window.cancel_btn = cancel_btn
        progress_window.cancelled = False
        
        return progress_window
    
    def _update_progress(self, progress_dialog, percent: int, message: str):
        """Update progress dialog with new progress and message."""
        if not progress_dialog or not progress_dialog.winfo_exists():
            return
        
        def update_ui():
            try:
                if percent < 0:
                    # Error state
                    progress_dialog.status_label.configure(text=f"Error: {message}", text_color="red")
                    progress_dialog.progress_bar.set(0)
                    progress_dialog.cancel_btn.configure(text="Close", state="normal")
                elif percent >= 100:
                    # Completed state
                    progress_dialog.status_label.configure(text=message, text_color="green")
                    progress_dialog.progress_bar.set(1.0)
                    progress_dialog.cancel_btn.configure(text="Close", state="normal")
                else:
                    # In progress
                    progress_dialog.status_label.configure(text=message, text_color="white")
                    progress_dialog.progress_bar.set(percent / 100.0)
            except Exception as e:
                print(f"Error updating progress dialog: {e}")
        
        # Schedule UI update on main thread
        if progress_dialog.winfo_exists():
            progress_dialog.after(0, update_ui)
    
    def _close_progress_dialog(self, progress_dialog):
        """Close the progress dialog."""
        try:
            if progress_dialog and progress_dialog.winfo_exists():
                progress_dialog.grab_release()
                progress_dialog.destroy()
        except Exception as e:
            print(f"Error closing progress dialog: {e}")
    
    def _refresh_after_sync(self):
        """Refresh the UI after sync operations."""
        try:
            # Reset to first page and reload notes list
            self.current_page = 1
            self._load_notes_list()
            
            # Clear current selection to force refresh
            self.current_note_id = None
            
            # Show success message
            self._show_status("Notes list refreshed from cache")
            
        except Exception as e:
            print(f"Error refreshing after sync: {e}")
            self._show_status(f"Error refreshing: {e}", error=True)
    
    def _show_cache_status(self):
        """Show cache status dialog with statistics and validation results."""
        if not self.cache_manager:
            messagebox.showerror("Error", "Cache manager not available")
            return
        
        try:
            # Get cache statistics
            cache_stats = self.cache_manager.get_cache_stats()
            
            # Create status dialog
            status_window = ctk.CTkToplevel(self.window)
            status_window.title("Cache Status")
            status_window.geometry("500x400")
            status_window.resizable(True, True)
            status_window.attributes('-topmost', True)
            status_window.transient(self.window)
            
            # Main frame with scrollable content
            main_frame = ctk.CTkScrollableFrame(status_window)
            main_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            # Title
            title_label = ctk.CTkLabel(main_frame, text="Notes Cache Status", font=("Arial", 16, "bold"))
            title_label.pack(pady=(0, 20))
            
            # Cache summary
            summary_frame = ctk.CTkFrame(main_frame)
            summary_frame.pack(fill="x", pady=(0, 15))
            
            ctk.CTkLabel(summary_frame, text="Cache Summary", font=("Arial", 14, "bold")).pack(pady=(10, 5))
            
            # Cache status info
            cache_status = cache_stats.get('cache_status', {})
            total_notes = cache_stats.get('total_notes', 0)
            cache_size_mb = cache_status.get('cache_size_mb', 0)
            is_valid = cache_status.get('is_valid', False)
            index_exists = cache_status.get('index_exists', False)
            
            status_text = f"Total Notes: {total_notes}\n"
            status_text += f"Cache Size: {cache_size_mb} MB\n"
            status_text += f"Index File Exists: {'Yes' if index_exists else 'No'}\n"
            status_text += f"Cache Valid: {'Yes' if is_valid else 'No'}"
            
            status_info = ctk.CTkLabel(summary_frame, text=status_text, justify="left")
            status_info.pack(pady=(5, 10), padx=10)
            
            # Last sync info
            sync_frame = ctk.CTkFrame(main_frame)
            sync_frame.pack(fill="x", pady=(0, 15))
            
            ctk.CTkLabel(sync_frame, text="Synchronization", font=("Arial", 14, "bold")).pack(pady=(10, 5))
            
            last_sync = cache_stats.get('last_sync')
            if last_sync:
                try:
                    sync_dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                    sync_display = sync_dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    sync_display = last_sync
            else:
                sync_display = "Never"
            
            sync_text = f"Last Sync: {sync_display}"
            sync_info = ctk.CTkLabel(sync_frame, text=sync_text, justify="left")
            sync_info.pack(pady=(5, 10), padx=10)
            
            # Integrity check info
            integrity_frame = ctk.CTkFrame(main_frame)
            integrity_frame.pack(fill="x", pady=(0, 15))
            
            ctk.CTkLabel(integrity_frame, text="Integrity Check", font=("Arial", 14, "bold")).pack(pady=(10, 5))
            
            integrity_check = cache_stats.get('integrity_check', {})
            last_validated = integrity_check.get('last_validated')
            if last_validated:
                try:
                    validated_dt = datetime.fromisoformat(last_validated.replace('Z', '+00:00'))
                    validated_display = validated_dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    validated_display = last_validated
            else:
                validated_display = "Never"
            
            integrity_status = integrity_check.get('status', 'unknown')
            checksum = integrity_check.get('checksum', 'None')
            
            integrity_text = f"Last Validated: {validated_display}\n"
            integrity_text += f"Status: {integrity_status}\n"
            integrity_text += f"Checksum: {checksum[:20]}..." if len(checksum) > 20 else f"Checksum: {checksum}"
            
            integrity_info = ctk.CTkLabel(integrity_frame, text=integrity_text, justify="left")
            integrity_info.pack(pady=(5, 10), padx=10)
            
            # Action buttons
            actions_frame = ctk.CTkFrame(main_frame)
            actions_frame.pack(fill="x", pady=(15, 0))
            
            ctk.CTkLabel(actions_frame, text="Actions", font=("Arial", 14, "bold")).pack(pady=(10, 5))
            
            buttons_frame = ctk.CTkFrame(actions_frame)
            buttons_frame.pack(pady=(5, 10))
            
            validate_btn = ctk.CTkButton(buttons_frame, text="Validate Cache", 
                                       command=lambda: self._validate_cache_from_status(status_window))
            validate_btn.pack(side="left", padx=5)
            
            clear_btn = ctk.CTkButton(buttons_frame, text="Clear Cache", fg_color="red",
                                    command=lambda: self._clear_cache_from_status(status_window))
            clear_btn.pack(side="left", padx=5)
            
            refresh_btn = ctk.CTkButton(buttons_frame, text="Refresh Status",
                                      command=lambda: self._refresh_cache_status(status_window))
            refresh_btn.pack(side="left", padx=5)
            
            # Close button
            close_btn = ctk.CTkButton(main_frame, text="Close", command=status_window.destroy)
            close_btn.pack(pady=(20, 0))
            
        except Exception as e:
            print(f"Error showing cache status: {e}")
            messagebox.showerror("Error", f"Failed to show cache status: {e}")
    
    def _validate_cache_from_status(self, status_window):
        """Validate cache from status dialog."""
        try:
            is_valid = self.cache_manager.validate_cache()
            if is_valid:
                messagebox.showinfo("Validation Result", "Cache validation successful!", parent=status_window)
            else:
                messagebox.showwarning("Validation Result", "Cache validation failed. Consider clearing cache.", parent=status_window)
            
            # Refresh status display
            self._refresh_cache_status(status_window)
            
        except Exception as e:
            messagebox.showerror("Error", f"Cache validation failed: {e}", parent=status_window)
    
    def _clear_cache_from_status(self, status_window):
        """Clear cache from status dialog."""
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear the cache? This will remove all cached data.", parent=status_window):
            try:
                self.cache_manager.clear_cache()
                messagebox.showinfo("Cache Cleared", "Cache cleared successfully!", parent=status_window)
                
                # Refresh status display
                self._refresh_cache_status(status_window)
                
                # Refresh notes list
                self._load_notes_list()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear cache: {e}", parent=status_window)
    
    def _refresh_cache_status(self, status_window):
        """Refresh cache status display."""
        try:
            # Close current status window and open new one
            status_window.destroy()
            self._show_cache_status()
        except Exception as e:
            print(f"Error refreshing cache status: {e}")
    
    def _prev_page(self):
        """Go to previous page."""
        if self.current_page > 1:
            self.current_page -= 1
            self._load_notes_list()
    
    def _next_page(self):
        """Go to next page."""
        self.current_page += 1
        self._load_notes_list()
    
    def _clear_editor(self):
        """Clear the editor content."""
        self.current_note_id = None
        self.title_entry.delete(0, tk.END)
        self.editor_text.delete("1.0", tk.END)
        self.info_label.configure(text="")
        self._show_status("Editor cleared")
    
    def _show_status(self, message: str, error: bool = False):
        """Show status message."""
        if error:
            self.status_label.configure(text=f"Error: {message}", text_color="red")
        else:
            self.status_label.configure(text=message, text_color="white")
        
        # Clear status after 5 seconds
        self.window.after(5000, lambda: self.status_label.configure(text="Ready", text_color="white"))
    
    def _on_window_close(self):
        """Handle window close event."""
        # When user clicks X, properly clean up the window reference
        if self.window:
            self.window.destroy()
            self.window = None
        self.is_visible = False
    
    def _on_search_key_press(self, event):
        """Handle key press events in search entry."""
        if event.keysym == "Down":
            # Show search suggestions
            self._show_search_suggestions()
        elif event.keysym == "Escape":
            # Hide suggestions
            self._hide_search_suggestions()
    
    def _on_search_focus_in(self, event):
        """Handle search entry focus in."""
        # Show recent searches when focused
        if not self.search_var.get().strip():
            self._show_search_suggestions()
    
    def _on_search_focus_out(self, event):
        """Handle search entry focus out."""
        # Hide suggestions after a delay to allow clicking
        self.window.after(200, self._hide_search_suggestions)
    
    def _show_search_suggestions(self):
        """Show search suggestions dropdown."""
        if not self.notes_manager:
            return
        
        # Get suggestions based on current input
        current_query = self.search_var.get().strip()
        suggestions = self.notes_manager.get_search_suggestions(current_query, limit=8)
        
        if not suggestions:
            self._hide_search_suggestions()
            return
        
        # Create suggestions frame if it doesn't exist
        if self.suggestions_frame is None:
            self.suggestions_frame = ctk.CTkFrame(self.notes_list_frame)
        
        # Clear existing suggestions
        for widget in self.suggestions_frame.winfo_children():
            widget.destroy()
        
        # Add suggestion buttons
        for suggestion in suggestions:
            btn = ctk.CTkButton(
                self.suggestions_frame,
                text=suggestion,
                height=25,
                command=lambda s=suggestion: self._select_suggestion(s)
            )
            btn.pack(fill="x", padx=2, pady=1)
        
        # Position suggestions frame below search entry
        self.suggestions_frame.place(
            in_=self.search_entry,
            x=0,
            y=self.search_entry.winfo_height(),
            width=self.search_entry.winfo_width()
        )
        
        # Bring to front
        self.suggestions_frame.lift()
    
    def _hide_search_suggestions(self):
        """Hide search suggestions dropdown."""
        if self.suggestions_frame:
            self.suggestions_frame.place_forget()
    
    def _select_suggestion(self, suggestion: str):
        """Select a search suggestion."""
        self.search_var.set(suggestion)
        self._hide_search_suggestions()
        self.search_entry.focus_set()
    
    def _show_search_history(self):
        """Show search history dialog."""
        if not self.notes_manager:
            messagebox.showerror("Error", "Notes manager not available")
            return
        
        # Create history dialog
        history_dialog = ctk.CTkToplevel(self.window)
        history_dialog.title("Search History")
        history_dialog.geometry("400x500")
        history_dialog.resizable(True, True)
        history_dialog.attributes('-topmost', True)
        history_dialog.transient(self.window)
        history_dialog.grab_set()
        
        # Main frame
        main_frame = ctk.CTkFrame(history_dialog)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title_label = ctk.CTkLabel(main_frame, text="Recent Searches", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        # History list frame
        list_frame = ctk.CTkFrame(main_frame)
        list_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Scrollable frame for history items
        history_scroll = ctk.CTkScrollableFrame(list_frame)
        history_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Get search history
        history = self.notes_manager.get_search_history(limit=50)
        
        if not history:
            no_history_label = ctk.CTkLabel(history_scroll, text="No search history available")
            no_history_label.pack(pady=20)
        else:
            for entry in history:
                query = entry.get("query", "")
                timestamp = entry.get("timestamp", "")
                result_count = entry.get("result_count", 0)
                
                # Format timestamp
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%m/%d %H:%M")
                except:
                    time_str = timestamp[:16] if timestamp else ""
                
                # Create history item frame
                item_frame = ctk.CTkFrame(history_scroll)
                item_frame.pack(fill="x", pady=2)
                
                # Query button (clickable)
                query_btn = ctk.CTkButton(
                    item_frame,
                    text=query,
                    anchor="w",
                    command=lambda q=query: self._use_history_query(q, history_dialog)
                )
                query_btn.pack(side="left", fill="x", expand=True, padx=5, pady=5)
                
                # Info label
                info_text = f"{time_str} ({result_count} results)"
                info_label = ctk.CTkLabel(item_frame, text=info_text, font=("Arial", 10))
                info_label.pack(side="right", padx=5, pady=5)
        
        # Action buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(fill="x")
        
        clear_btn = ctk.CTkButton(
            button_frame,
            text="Clear History",
            fg_color="red",
            command=lambda: self._clear_search_history(history_dialog)
        )
        clear_btn.pack(side="left", padx=5, pady=5)
        
        close_btn = ctk.CTkButton(
            button_frame,
            text="Close",
            command=history_dialog.destroy
        )
        close_btn.pack(side="right", padx=5, pady=5)
    
    def _use_history_query(self, query: str, dialog):
        """Use a query from search history."""
        self.search_var.set(query)
        dialog.destroy()
        self.search_entry.focus_set()
    
    def _clear_search_history(self, dialog):
        """Clear search history."""
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all search history?", parent=dialog):
            if self.notes_manager:
                self.notes_manager.clear_search_history()
                dialog.destroy()
                messagebox.showinfo("History Cleared", "Search history has been cleared.", parent=self.window)
    
    def _update_notes_tree_with_highlighting(self):
        """Update the notes tree view with search highlighting."""
        # Clear existing items
        for item in self.notes_tree.get_children():
            self.notes_tree.delete(item)
        
        # Configure highlighting tags
        self.notes_tree.tag_configure("highlight", background="yellow", foreground="black")
        
        # Add notes to tree with highlighting
        for note in self.filtered_notes:
            # Format dates for display
            created_date = self._format_date(note.get("created_at", ""))
            updated_date = self._format_date(note.get("updated_at", ""))
            
            # Get title with highlighting
            title = note.get("title", "Untitled")
            display_title = self._highlight_text(title, self.search_query)[:30]
            
            # Get short code with highlighting
            short_code = note.get("short_code", "")
            display_code = self._highlight_text(short_code, self.search_query)
            
            # Insert note into tree
            item_id = self.notes_tree.insert("", "end", values=(
                display_title,
                display_code,
                created_date,
                updated_date,
                "📋 🗑️"  # Action icons
            ))
            
            # Store note ID in mapping dictionary
            self._note_id_map[item_id] = note.get("id", "")
            
            # Apply highlighting if this note has search matches
            if hasattr(note, 'search_details') and note.get('search_details'):
                self.notes_tree.set(item_id, tags=("highlight",))
    
    def _highlight_text(self, text: str, query: str) -> str:
        """Add highlighting markers to text for search matches."""
        if not query or not text:
            return text
        
        # Simple highlighting - in a real implementation, you might use
        # more sophisticated text highlighting with tkinter tags
        query_lower = query.lower()
        text_lower = text.lower()
        
        if query_lower in text_lower:
            # For now, just return the text with a marker
            # In a full implementation, you'd use tkinter text tags
            return f"★ {text}"
        
        return text
    
    def _update_notes_tree(self):
        """Update the notes tree view with current data and highlighting."""
        if self.search_query:
            self._update_notes_tree_with_highlighting()
        else:
            # Use original method for non-search results
            self._update_notes_tree_original()
    
    def _update_notes_tree_original(self):
        """Original update method without highlighting."""
        # Clear existing items
        for item in self.notes_tree.get_children():
            self.notes_tree.delete(item)
        
        # Add notes to tree
        for note in self.filtered_notes:
            # Format dates for display
            created_date = self._format_date(note.get("created_at", ""))
            updated_date = self._format_date(note.get("updated_at", ""))
            
            # Insert note into tree
            item_id = self.notes_tree.insert("", "end", values=(
                note.get("title", "Untitled")[:30],  # Truncate long titles
                note.get("short_code", ""),
                created_date,
                updated_date,
                "📋 🗑️"  # Action icons
            ))
            
            # Store note ID in mapping dictionary
            self._note_id_map[item_id] = note.get("id", "")
    
    def _show_status(self, message: str, error: bool = False):
        """Show status message in the status label."""
        if hasattr(self, 'status_label') and self.status_label:
            color = "red" if error else "green"
            self.status_label.configure(text=message, text_color=color)
            
            # Clear status after 5 seconds
            if hasattr(self, '_status_timer'):
                self.window.after_cancel(self._status_timer)
            self._status_timer = self.window.after(5000, lambda: self.status_label.configure(text="Ready", text_color="white"))
    
    def _clear_editor(self):
        """Clear the editor content."""
        self.current_note_id = None
        self.title_entry.delete(0, tk.END)
        self.editor_text.delete("1.0", tk.END)
        self.info_label.configure(text="")
    
    def _on_window_close(self):
        """Handle window close event."""
        self.hide_window()
    
    def _prev_page(self):
        """Go to previous page."""
        if self.current_page > 1:
            self.current_page -= 1
            self._load_notes_list()
    
    def _next_page(self):
        """Go to next page."""
        self.current_page += 1
        self._load_notes_list()
    
    def _show_cache_status(self):
        """Show cache status dialog."""
        if not self.cache_manager:
            messagebox.showerror("Error", "Cache manager not available")
            return
        
        try:
            stats = self.cache_manager.get_cache_stats()
            
            # Create status dialog
            status_dialog = ctk.CTkToplevel(self.window)
            status_dialog.title("Cache Status")
            status_dialog.geometry("500x400")
            status_dialog.resizable(True, True)
            status_dialog.attributes('-topmost', True)
            status_dialog.transient(self.window)
            status_dialog.grab_set()
            
            # Main frame
            main_frame = ctk.CTkFrame(status_dialog)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Title
            title_label = ctk.CTkLabel(main_frame, text="Notes Cache Status", font=("Arial", 16, "bold"))
            title_label.pack(pady=(0, 10))
            
            # Status text
            status_text = ctk.CTkTextbox(main_frame)
            status_text.pack(fill="both", expand=True, pady=(0, 10))
            
            # Format status information
            status_info = f"""Cache Statistics:
• Total Notes: {stats.get('total_notes', 0)}
• Cache Size: {stats.get('cache_status', {}).get('cache_size_mb', 0)} MB
• Last Sync: {stats.get('last_sync', 'Never')}
• Cache Valid: {stats.get('cache_status', {}).get('is_valid', False)}
• Index Exists: {stats.get('cache_status', {}).get('index_exists', False)}

Integrity Check:
• Last Validated: {stats.get('integrity_check', {}).get('last_validated', 'Never')}
• Status: {stats.get('integrity_check', {}).get('status', 'Unknown')}
• Checksum: {stats.get('integrity_check', {}).get('checksum', 'None')[:20]}...

Cache Paths:
• Cache Directory: {stats.get('cache_paths', {}).get('cache_dir', 'Unknown')}
• Index File: {stats.get('cache_paths', {}).get('overall_notes_index_file', 'Unknown')}
"""
            
            status_text.insert("1.0", status_info)
            status_text.configure(state="disabled")
            
            # Close button
            close_btn = ctk.CTkButton(main_frame, text="Close", command=status_dialog.destroy)
            close_btn.pack(pady=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get cache status: {e}", parent=self.window)
    
    def _refresh_after_sync(self):
        """Refresh UI after sync operation."""
        try:
            self._load_notes_list()
            self._show_status("Sync completed successfully")
        except Exception as e:
            self._show_status(f"Error refreshing after sync: {e}", error=True)
    
    def _update_progress(self, progress_dialog, percentage: int, message: str):
        """Update progress dialog."""
        try:
            if not progress_dialog or not progress_dialog.winfo_exists():
                return
            
            # Find progress components
            progress_frame = progress_dialog.winfo_children()[0]
            status_label = progress_frame.winfo_children()[0]
            progress_bar = progress_frame.winfo_children()[1]
            
            # Update status message
            status_label.configure(text=message)
            
            # Update progress bar
            if percentage >= 0:
                progress_bar.set(percentage / 100.0)
            else:
                # Error state - set to red or indeterminate
                progress_bar.set(0)
            
        except Exception as e:
            print(f"Error updating progress: {e}")
    
    def _close_progress_dialog(self, progress_dialog):
        """Close progress dialog."""
        try:
            if progress_dialog and progress_dialog.winfo_exists():
                progress_dialog.destroy()
        except Exception as e:
            print(f"Error closing progress dialog: {e}")
    
    def _offer_offline_mode(self, error_message: str):
        """Offer to work in offline mode when cloud sync fails."""
        result = messagebox.askyesno("Cloud Sync Failed", 
                                   f"{error_message}\n\n"
                                   "Would you like to continue working offline?\n\n"
                                   "Your notes will be saved locally and can be synced later when cloud is available.",
                                   parent=self.window)
        if result:
            self._show_status("Working in offline mode - notes saved locally only", error=False)
            # Try to retry failed syncs if any exist
            if self.notes_manager:
                retry_result = self.notes_manager.retry_failed_syncs()
                if retry_result.get("retried", 0) > 0:
                    self._show_status(f"Retried {retry_result['retried']} failed syncs, {retry_result['succeeded']} succeeded")
    
    def _refresh_after_sync(self):
        """Refresh UI after sync operations."""
        try:
            # Reload notes list
            self._load_notes_list()
            
            # Show sync status
            if self.notes_manager:
                sync_status = self.notes_manager.get_sync_status()
                if sync_status.get("sync_health") == "healthy":
                    self._show_status("Sync completed successfully")
                else:
                    self._show_status(f"Sync completed with issues: {sync_status.get('sync_health', 'unknown')}")
            
        except Exception as e:
            print(f"Error refreshing after sync: {e}")
            self._show_status(f"Error refreshing: {e}", error=True)
    
    def _clear_editor(self):
        """Clear the editor content."""
        self.current_note_id = None
        self.title_entry.delete(0, tk.END)
        self.editor_text.delete("1.0", tk.END)
        self.info_label.configure(text="")
        self._show_status("Editor cleared")
    
    def _show_status(self, message: str, error: bool = False):
        """Show status message in the status label."""
        if hasattr(self, 'status_label') and self.status_label:
            color = "red" if error else "green"
            self.status_label.configure(text=message, text_color=color)
            
            # Clear status after 5 seconds
            if hasattr(self, 'window') and self.window:
                self.window.after(5000, lambda: self.status_label.configure(text="Ready", text_color="white"))
    
    def _on_window_close(self):
        """Handle window close event."""
        self.hide_window()
    
    def _prev_page(self):
        """Go to previous page."""
        if self.current_page > 1:
            self.current_page -= 1
            self._load_notes_list()
    
    def _next_page(self):
        """Go to next page."""
        self.current_page += 1
        self._load_notes_list()
    
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
    
    def _show_search_history(self):
        """Show search history dialog."""
        if not self.notes_manager:
            return
        
        try:
            history = self.notes_manager.get_search_history(limit=20)
            if not history:
                messagebox.showinfo("Search History", "No search history available.", parent=self.window)
                return
            
            # Create history dialog
            history_dialog = ctk.CTkToplevel(self.window)
            history_dialog.title("Search History")
            history_dialog.geometry("400x300")
            history_dialog.transient(self.window)
            history_dialog.grab_set()
            
            # History list
            history_frame = ctk.CTkFrame(history_dialog)
            history_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            ctk.CTkLabel(history_frame, text="Recent Searches:", font=("Arial", 12, "bold")).pack(pady=(0, 10))
            
            # Create listbox for history
            history_listbox = tk.Listbox(history_frame, height=15)
            history_listbox.pack(fill="both", expand=True)
            
            # Populate history
            for entry in history:
                query = entry.get("query", "")
                result_count = entry.get("result_count", 0)
                timestamp = entry.get("timestamp", "")
                
                # Format timestamp
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%m/%d %H:%M")
                except:
                    time_str = timestamp[:16] if timestamp else ""
                
                display_text = f"{query} ({result_count} results) - {time_str}"
                history_listbox.insert(tk.END, display_text)
            
            # Buttons
            button_frame = ctk.CTkFrame(history_dialog)
            button_frame.pack(fill="x", padx=10, pady=(0, 10))
            
            def use_selected():
                selection = history_listbox.curselection()
                if selection:
                    selected_entry = history[selection[0]]
                    self.search_var.set(selected_entry["query"])
                    history_dialog.destroy()
            
            def clear_history():
                if messagebox.askyesno("Clear History", "Are you sure you want to clear all search history?", parent=history_dialog):
                    self.notes_manager.clear_search_history()
                    history_dialog.destroy()
            
            ctk.CTkButton(button_frame, text="Use Selected", command=use_selected).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Clear History", command=clear_history).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Close", command=history_dialog.destroy).pack(side="right", padx=5)
            
            # Bind double-click to use selected
            history_listbox.bind("<Double-1>", lambda e: use_selected())
            
        except Exception as e:
            print(f"Error showing search history: {e}")
            messagebox.showerror("Error", f"Failed to show search history: {e}", parent=self.window)
    
    def _show_cache_status(self):
        """Show cache status dialog."""
        if not self.cache_manager:
            messagebox.showerror("Error", "Cache manager not available")
            return
        
        try:
            # Get cache statistics
            stats = self.cache_manager.get_cache_stats()
            
            # Create status dialog
            status_dialog = ctk.CTkToplevel(self.window)
            status_dialog.title("Cache Status")
            status_dialog.geometry("500x400")
            status_dialog.transient(self.window)
            status_dialog.grab_set()
            
            # Status content
            status_frame = ctk.CTkFrame(status_dialog)
            status_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            ctk.CTkLabel(status_frame, text="Cache Status", font=("Arial", 14, "bold")).pack(pady=(0, 10))
            
            # Create text widget for status info
            status_text = tk.Text(status_frame, height=20, width=60, wrap=tk.WORD)
            status_scrollbar = ttk.Scrollbar(status_frame, orient="vertical", command=status_text.yview)
            status_text.configure(yscrollcommand=status_scrollbar.set)
            
            status_text.pack(side="left", fill="both", expand=True)
            status_scrollbar.pack(side="right", fill="y")
            
            # Format status information
            status_info = f"""Cache Information:
Version: {stats.get('version', 'Unknown')}
Last Sync: {stats.get('last_sync', 'Never')}
Cache Size: {stats.get('cache_size_mb', 0):.2f} MB
Total Notes: {stats.get('total_notes', 0)}
Actual Notes Count: {stats.get('actual_notes_count', 0)}

Cache Status:
Index Exists: {stats.get('cache_status', {}).get('index_exists', False)}
Is Valid: {stats.get('cache_status', {}).get('is_valid', False)}

Integrity Check:
Last Validated: {stats.get('integrity_check', {}).get('last_validated', 'Never')}
Status: {stats.get('integrity_check', {}).get('status', 'Unknown')}
Checksum: {stats.get('integrity_check', {}).get('checksum', 'None')[:20]}...

Cache Paths:
Cache Directory: {stats.get('cache_paths', {}).get('cache_dir', 'Unknown')}
Index File: {stats.get('cache_paths', {}).get('overall_notes_index_file', 'Unknown')}
"""
            
            # Add sync status if available
            if self.notes_manager:
                sync_status = self.notes_manager.get_sync_status()
                status_info += f"""
Sync Status:
Cloud Sync Available: {sync_status.get('cloud_sync_available', False)}
Cloud Sync Enabled: {sync_status.get('cloud_sync_enabled', False)}
Sync Health: {sync_status.get('sync_health', 'Unknown')}
Failed Syncs: {sync_status.get('failed_syncs_count', 0)}
Last Sync Attempt: {sync_status.get('last_sync_attempt', 'Never')}
"""
                
                if 'last_error' in sync_status:
                    status_info += f"Last Error: {sync_status['last_error']}\n"
            
            status_text.insert("1.0", status_info)
            status_text.configure(state="disabled")
            
            # Buttons
            button_frame = ctk.CTkFrame(status_dialog)
            button_frame.pack(fill="x", padx=10, pady=(0, 10))
            
            def refresh_status():
                # Refresh and update display
                new_stats = self.cache_manager.get_cache_stats()
                status_text.configure(state="normal")
                status_text.delete("1.0", tk.END)
                # Recreate status info with new stats
                # (simplified for brevity)
                status_text.insert("1.0", f"Refreshed at {datetime.now().strftime('%H:%M:%S')}\n\n" + status_info)
                status_text.configure(state="disabled")
            
            def validate_cache():
                is_valid = self.cache_manager.validate_cache()
                result_msg = "Cache is valid ✅" if is_valid else "Cache validation failed ❌"
                messagebox.showinfo("Cache Validation", result_msg, parent=status_dialog)
                refresh_status()
            
            def clear_cache():
                if messagebox.askyesno("Clear Cache", "Are you sure you want to clear the cache?", parent=status_dialog):
                    self.cache_manager.clear_cache()
                    messagebox.showinfo("Cache Cleared", "Cache has been cleared successfully.", parent=status_dialog)
                    refresh_status()
            
            ctk.CTkButton(button_frame, text="Refresh", command=refresh_status).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Validate", command=validate_cache).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Clear Cache", command=clear_cache).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Close", command=status_dialog.destroy).pack(side="right", padx=5)
            
        except Exception as e:
            print(f"Error showing cache status: {e}")
            messagebox.showerror("Error", f"Failed to show cache status: {e}", parent=self.window)
    
    def _create_progress_dialog(self, title: str, initial_message: str):
        """Create a progress dialog for long-running operations."""
        progress_window = ctk.CTkToplevel(self.window)
        progress_window.title(title)
        progress_window.geometry("400x150")
        progress_window.resizable(False, False)
        progress_window.attributes('-topmost', True)
        progress_window.transient(self.window)
        
        # Center the dialog
        progress_window.grab_set()
        
        # Progress frame
        progress_frame = ctk.CTkFrame(progress_window)
        progress_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Progress label
        progress_label = ctk.CTkLabel(progress_frame, text=initial_message, wraplength=350)
        progress_label.pack(pady=(0, 10))
        
        # Progress bar
        progress_bar = ctk.CTkProgressBar(progress_frame, width=350)
        progress_bar.pack(pady=(0, 10))
        progress_bar.set(0)
        
        # Cancel button (optional)
        cancel_btn = ctk.CTkButton(progress_frame, text="Cancel", width=100)
        cancel_btn.pack()
        
        # Store references for updates
        progress_window.progress_label = progress_label
        progress_window.progress_bar = progress_bar
        progress_window.cancel_btn = cancel_btn
        
        return progress_window
    
    def _update_progress(self, progress_dialog, percentage: int, message: str):
        """Update progress dialog."""
        if not progress_dialog or not progress_dialog.winfo_exists():
            return
        
        try:
            progress_dialog.progress_label.configure(text=message)
            
            if percentage >= 0:
                progress_dialog.progress_bar.set(percentage / 100.0)
            else:
                # Error state - make progress bar red
                progress_dialog.progress_bar.configure(progress_color="red")
                progress_dialog.progress_bar.set(1.0)
        except Exception as e:
            print(f"Error updating progress: {e}")
    
    def _close_progress_dialog(self, progress_dialog):
        """Close progress dialog."""
        try:
            if progress_dialog and progress_dialog.winfo_exists():
                progress_dialog.destroy()
        except Exception as e:
            print(f"Error closing progress dialog: {e}")