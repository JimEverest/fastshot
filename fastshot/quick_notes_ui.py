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
                
                # Trigger sync status check when bringing window to front
                self._check_sync_status_on_show()
                return
            
            # Create new window
            print("DEBUG: Creating new window")
            self._create_window()
            print("DEBUG: Window created, loading notes list")
            self._load_notes_list()
            print("DEBUG: Notes list loaded, checking sync status")
            
            # Check sync status when opening window for the first time
            self._check_sync_status_on_show()
            
            print("DEBUG: Notes list loaded, setting visible flag")
            self.is_visible = True
            print("DEBUG: show_window() completed successfully")
        except Exception as e:
            print(f"ERROR in show_window(): {e}")
            import traceback
            traceback.print_exc()
    
    def _check_sync_status_on_show(self):
        """Check sync status when window is shown and invalidate cache if needed."""
        try:
            print("DEBUG: Checking sync status on window show...")
            
            if not self.notes_manager or not self.cache_manager:
                print("DEBUG: Notes manager or cache manager not available")
                return
            
            # Check if cloud sync is available
            if not hasattr(self.notes_manager, 'cloud_sync') or not self.notes_manager.cloud_sync:
                print("DEBUG: Cloud sync not available")
                self._load_notes_list()
                return
            
            # Download cloud index to compare with local cache
            try:
                cloud_index = self.notes_manager.cloud_sync.load_notes_overall_index()
                if not cloud_index:
                    print("DEBUG: No cloud index found")
                    self._load_notes_list()
                    return
                
                # Get local cached index
                local_index = self.cache_manager.get_cached_index()
                
                # Compare timestamps to see if cache is outdated
                cloud_last_updated = cloud_index.get("last_updated", "")
                local_last_updated = local_index.get("last_updated", "")
                
                print(f"DEBUG: Cloud last updated: {cloud_last_updated}")
                print(f"DEBUG: Local last updated: {local_last_updated}")
                
                # Parse timestamps for comparison
                cloud_time = self.notes_manager._parse_timestamp_to_utc(cloud_last_updated)
                local_time = self.notes_manager._parse_timestamp_to_utc(local_last_updated)
                
                if cloud_time > local_time:
                    print("DEBUG: Cloud index is newer, updating local cache")
                    # Update local cache with cloud index
                    self.cache_manager.update_cache_index(cloud_index)
                    
                    # Check if any notes need to be refreshed from cloud
                    refreshed_notes = self._refresh_outdated_notes()
                    
                    # Check if currently opened note needs refresh (only if not already refreshed)
                    self._refresh_current_note_if_outdated(refreshed_notes)
                    
                    self._show_status("Cache updated from cloud")
                else:
                    print("DEBUG: Local cache is up to date")
                    self._show_status("Cache is up to date")
                
            except Exception as e:
                print(f"DEBUG: Error comparing cloud and local indexes: {e}")
                self._show_status("Error checking cloud updates", error=True)
            
            # Refresh the notes list to show updated status
            self._load_notes_list()
            
        except Exception as e:
            print(f"Error checking sync status: {e}")
            self._show_status("Error checking sync status", error=True)
    
    def _refresh_outdated_notes(self):
        """Refresh outdated notes from cloud automatically."""
        try:
            print("DEBUG: Checking for outdated notes to refresh...")
            
            if not self.notes_manager:
                return []
            
            # Get sync status for all notes
            sync_status_dict = self.notes_manager.check_notes_sync_status()
            
            # Find notes that need refresh
            outdated_notes = []
            for note_id, status_info in sync_status_dict.items():
                if status_info.get("needs_refresh", False):
                    outdated_notes.append(note_id)
            
            refreshed_notes = []
            if outdated_notes:
                print(f"DEBUG: Found {len(outdated_notes)} outdated notes, refreshing...")
                
                # Refresh each outdated note
                for note_id in outdated_notes:
                    try:
                        success = self.notes_manager.refresh_note_from_cloud(note_id)
                        if success:
                            print(f"DEBUG: Successfully refreshed note {note_id[:8]}...")
                            refreshed_notes.append(note_id)
                        else:
                            print(f"DEBUG: Failed to refresh note {note_id[:8]}...")
                    except Exception as e:
                        print(f"DEBUG: Error refreshing note {note_id[:8]}...: {e}")
                
                self._show_status(f"Refreshed {len(refreshed_notes)} outdated notes")
            else:
                print("DEBUG: No outdated notes found")
                
            return refreshed_notes
                
        except Exception as e:
            print(f"Error refreshing outdated notes: {e}")
            return []
    
    def _refresh_current_note_if_outdated(self, refreshed_notes=None):
        """Refresh currently opened note if it's outdated."""
        try:
            if not self.current_note_id or not self.notes_manager:
                return
            
            print(f"DEBUG: Checking if current note {self.current_note_id[:8]}... needs refresh...")
            
            # If this note was already refreshed in batch, just reload the content
            if refreshed_notes and self.current_note_id in refreshed_notes:
                print(f"DEBUG: Current note {self.current_note_id[:8]}... was already refreshed, reloading content...")
                self._load_note_content(self.current_note_id)
                self._show_status("Current note updated from cloud")
                print(f"DEBUG: Successfully reloaded current note content")
                return
            
            # Get sync status for current note
            sync_status_dict = self.notes_manager.check_notes_sync_status()
            current_note_status = sync_status_dict.get(self.current_note_id, {})
            
            if current_note_status.get("needs_refresh", False):
                print(f"DEBUG: Current note {self.current_note_id[:8]}... is outdated, refreshing...")
                
                # Refresh the note from cloud
                success = self.notes_manager.refresh_note_from_cloud(self.current_note_id)
                
                if success:
                    # Reload the note content in the editor
                    self._load_note_content(self.current_note_id)
                    self._show_status("Current note updated from cloud")
                    print(f"DEBUG: Successfully refreshed and reloaded current note")
                else:
                    print(f"DEBUG: Failed to refresh current note")
                    self._show_status("Failed to update current note", error=True)
            else:
                print(f"DEBUG: Current note is up to date")
                
        except Exception as e:
            print(f"Error refreshing current note: {e}")
            self._show_status("Error updating current note", error=True)
    
    def _show_status(self, message: str, error: bool = False):
        """Show status message in the status label."""
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.configure(text=message)
            if error:
                # Could add error styling here
                print(f"ERROR: {message}")
            else:
                print(f"STATUS: {message}")
    
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
        self.window.geometry("1300x700")
        self.window.minsize(1100, 500)
        
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
        
        # Add panes to PanedWindow with specific widths
        paned_window.add(self.notes_list_frame, minsize=500, width=750)
        paned_window.add(self.editor_frame, minsize=400, width=500)
        
        # Store paned_window reference for later use
        self.paned_window = paned_window
        
        # Set initial pane sizes (750px left, 500px right) with multiple attempts
        self.window.after(50, lambda: self._set_pane_sizes())
        self.window.after(200, lambda: self._set_pane_sizes())
        self.window.after(500, lambda: self._set_pane_sizes())
        self.window.after(1000, lambda: self._set_pane_sizes())  # Additional attempt
        self.window.after(2000, lambda: self._set_pane_sizes())  # Even more attempts
        self.window.after(3000, lambda: self._set_pane_sizes())  # Final attempt
    
    def _set_pane_sizes(self):
        """Set the pane sizes to ensure left panel is 750px and right panel is 500px."""
        try:
            if hasattr(self, 'paned_window') and self.paned_window:
                # Get the current window width
                window_width = self.window.winfo_width()
                print(f"DEBUG: Window width: {window_width}")
                
                # Calculate the actual available width for panes (minus padding and sash)
                # Main frame has 10px padding on each side, paned_window has 5px padding on each side
                available_width = window_width - 30  # 10+10+5+5 padding
                print(f"DEBUG: Available width for panes: {available_width}")
                
                # Set sash position at 750px from left, but ensure it doesn't exceed available space
                sash_position = min(750, available_width - 400)  # Leave at least 400px for right pane
                
                # Use sash_place to set the divider position
                self.paned_window.sash_place(0, sash_position, 0)
                
                # Verify the position was set
                actual_position = self.paned_window.sash_coord(0)[0]
                print(f"DEBUG: Set sash position to {sash_position}, actual position: {actual_position}")
                
                # Force update the display
                self.paned_window.update_idletasks()
                
        except Exception as e:
            print(f"DEBUG: Error setting pane sizes: {e}")
    
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
        
        # Notes list with scrollbar - use standard tk.Frame for TreeView compatibility
        list_frame = tk.Frame(self.notes_list_frame)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create a container for treeview and action buttons
        tree_container = tk.Frame(list_frame)
        tree_container.pack(fill="both", expand=True)
        
        # Create Treeview for notes list (without actions column) - in the container
        columns = ("title", "short_code", "created", "updated", "status")
        self.notes_tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=15)
        
        # Configure columns
        self.notes_tree.heading("title", text="Title")
        self.notes_tree.heading("short_code", text="Code")
        self.notes_tree.heading("created", text="Created")
        self.notes_tree.heading("updated", text="Updated")
        self.notes_tree.heading("status", text="Status")
        
        # Set column widths
        self.notes_tree.column("title", width=140, minwidth=120)
        self.notes_tree.column("short_code", width=50, minwidth=40)
        self.notes_tree.column("created", width=70, minwidth=60)
        self.notes_tree.column("updated", width=70, minwidth=60)
        self.notes_tree.column("status", width=80, minwidth=70)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.notes_tree.yview)
        self.notes_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack treeview and scrollbar in the container
        self.notes_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create action buttons frame next to the treeview
        self.actions_frame = tk.Frame(tree_container, width=120)
        self.actions_frame.pack(side="right", fill="y", padx=(5, 0))
        self.actions_frame.pack_propagate(False)  # Maintain fixed width
        
        # Bind selection event
        self.notes_tree.bind("<<TreeviewSelect>>", self._on_note_selected)
        self.notes_tree.bind("<Double-1>", self._on_note_double_click)
        # Remove the problematic click handler - we'll use a different approach
        # self.notes_tree.bind("<Button-1>", self._on_tree_click)
        
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
        
        # Clear existing action buttons
        for widget in self.actions_frame.winfo_children():
            widget.destroy()
        
        # Clear the note ID mapping
        if not hasattr(self, '_note_id_map'):
            self._note_id_map = {}
        self._note_id_map.clear()
        
        # Get sync status for all notes
        sync_status_dict = {}
        if self.notes_manager:
            try:
                sync_status_dict = self.notes_manager.check_notes_sync_status()
                print(f"DEBUG: Got sync status for {len(sync_status_dict)} notes")
            except Exception as e:
                print(f"DEBUG: Error getting sync status: {e}")
        
        # Add notes to tree and create corresponding action buttons
        for i, note in enumerate(self.filtered_notes):
            note_id = note.get("id", "")
            
            # Format dates for display
            created_date = self._format_date(note.get("created_at", ""))
            updated_date = self._format_date(note.get("updated_at", ""))
            
            # Get status display - provide fallback for local notes
            status_info = sync_status_dict.get(note_id, {
                "status": "local_only", 
                "cloud_exists": False, 
                "local_exists": True
            })
            status_display = self._get_status_display(status_info)
            
            print(f"DEBUG: Note {note_id[:8]}... - Status: {status_display}")
            
            # Insert note into tree (without actions column)
            item_id = self.notes_tree.insert("", "end", values=(
                note.get("title", "Untitled")[:30],  # Truncate long titles
                note.get("short_code", ""),
                created_date,
                updated_date,
                status_display
            ))
            
            # Store note ID in mapping dictionary
            self._note_id_map[item_id] = note_id
            
            # Create action buttons for this note
            self._create_action_buttons(note_id, status_info, i)
    
    def _create_action_buttons(self, note_id: str, status_info: Dict[str, Any], row_index: int):
        """Create real button controls for each note row."""
        # Add header spacer for the first row to align with TreeView header
        if row_index == 0:
            header_spacer = tk.Frame(self.actions_frame, height=23)  # TreeView header height
            header_spacer.pack(fill="x")
            header_spacer.pack_propagate(False)
        
        # Create a frame for this row's buttons
        button_frame = tk.Frame(self.actions_frame, height=20)
        button_frame.pack(fill="x", pady=1)
        button_frame.pack_propagate(False)
        
        # Open button - always available (icon only)
        open_btn = tk.Button(button_frame, text="📖", width=3, height=1,
                            command=lambda: self._handle_action_open(note_id),
                            relief="flat", borderwidth=0)
        open_btn.pack(side="left", padx=1)
        
        # Refresh button - available if cloud version exists (icon only)
        if status_info.get("cloud_exists", False):
            refresh_btn = tk.Button(button_frame, text="🔄", width=3, height=1,
                                   command=lambda: self._handle_action_refresh(note_id),
                                   relief="flat", borderwidth=0)
        else:
            refresh_btn = tk.Button(button_frame, text="⚫", width=3, height=1,
                                   state="disabled", relief="flat", borderwidth=0)
        refresh_btn.pack(side="left", padx=1)
        
        # Public URL button - available if cloud version exists (icon only)
        if status_info.get("cloud_exists", False):
            url_btn = tk.Button(button_frame, text="🔗", width=3, height=1,
                               command=lambda: self._handle_action_public_url(note_id),
                               relief="flat", borderwidth=0)
        else:
            url_btn = tk.Button(button_frame, text="⚫", width=3, height=1,
                               state="disabled", relief="flat", borderwidth=0)
        url_btn.pack(side="left", padx=1)
        
        # Delete button - always available (icon only)
        delete_btn = tk.Button(button_frame, text="🗑️", width=3, height=1,
                              command=lambda: self._handle_action_delete(note_id),
                              relief="flat", borderwidth=0, fg="red")
        delete_btn.pack(side="left", padx=1)
    
    def _get_status_display(self, status_info: Dict[str, Any]) -> str:
        """Get status display text for a note."""
        if not status_info:
            return "�?Unknown"
        
        status = status_info.get("status", "unknown")
        
        status_map = {
            "new": "🆕 New",
            "updated": "🔴 Outdated",  # Changed to show outdated status in red
            "current": "✅Current",
            "local_only": "📱 Local",
            "syncing": "⏳Syncing",
            "unknown": "❓Unknown"
        }
        
        return status_map.get(status, "�?Unknown")
    
    def _create_actions_display(self, note_id: str, status_info: Dict[str, Any]) -> str:
        """Create actions display for a note with proper button labels."""
        actions = []
        
        # Open button - always available
        actions.append("📖")
        
        # Refresh button - available if cloud version exists
        if status_info.get("cloud_exists", False):
            actions.append("🔄")
        else:
            actions.append("�?Refresh")  # Disabled
        
        # Public URL button - available if cloud version exists
        if status_info.get("cloud_exists", False):
            actions.append("🔗 URL")
        else:
            actions.append("�?URL")  # Disabled
        
        # Delete button - always available
        actions.append("🗑�?Delete")
        
        # Use wider spacing for better click targets
        return "     ".join(actions)
    
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
    
    def _clear_editor(self):
        """Clear the editor content."""
        if self.title_entry:
            self.title_entry.delete(0, tk.END)
        if self.editor_text:
            self.editor_text.delete("1.0", tk.END)
        if self.info_label:
            self.info_label.configure(text="")
        self.current_note_id = Nonelf.editor_text.delete("1.0", tk.END)
        if self.info_label:
            self.info_label.configure(text="")
        self.current_note_id = None
    
    def _on_tree_click(self, event):
        """Handle clicks on the tree view, including action buttons."""
        try:
            # Get the item and column that was clicked
            item = self.notes_tree.identify_row(event.y)
            column = self.notes_tree.identify_column(event.x)
            
            if not item or column != "#6":  # Column #6 is the actions column
                return
            
            # Get note ID from mapping
            if not hasattr(self, '_note_id_map') or item not in self._note_id_map:
                return
            
            note_id = self._note_id_map[item]
            if not note_id:
                return
            
            # Get the actions text to determine which action was clicked
            actions_text = self.notes_tree.item(item, "values")[5]  # Actions column
            
            # Calculate which action was clicked based on x position within the column
            column_x = self.notes_tree.bbox(item, column)[0] if self.notes_tree.bbox(item, column) else 0
            relative_x = event.x - column_x
            
            # Rough estimation of action button positions
            # Actions are: "📖 Open | 🔄 Refresh | 🔗 URL | 🗑�?Delete"
            # Get actual column width for better accuracy
            bbox = self.notes_tree.bbox(item, column)
            if bbox:
                column_width = bbox[2]
                action_width = column_width // 4  # More accurate width per action
            else:
                action_width = 30  # Fallback width
            
            if relative_x < action_width:
                self._handle_action_open(note_id)
            elif relative_x < action_width * 2:
                self._handle_action_refresh(note_id)
            elif relative_x < action_width * 3:
                self._handle_action_public_url(note_id)
            else:
                self._handle_action_delete(note_id)
                
        except Exception as e:
            print(f"Error handling tree click: {e}")
    
    def _handle_action_open(self, note_id: str):
        """Handle open action for a note."""
        try:
            self._load_note_content(note_id)
            self._show_status(f"Opened note: {note_id[:8]}...")
        except Exception as e:
            print(f"Error opening note: {e}")
            self._show_status("Error opening note", error=True)
    
    def _handle_action_refresh(self, note_id: str):
        """Handle refresh action for a note - download from cloud."""
        try:
            if not self.notes_manager:
                self._show_status("Notes manager not available", error=True)
                return
            
            # Check if note exists in cloud
            sync_status = self.notes_manager.check_notes_sync_status()
            note_status = sync_status.get(note_id, {})
            
            if not note_status.get("cloud_exists", False):
                self._show_status("Note not available in cloud", error=True)
                return
            
            # Force refresh from cloud
            success = self.notes_manager.refresh_note_from_cloud(note_id)
            
            if success:
                # Refresh the UI
                self._load_notes_list()
                
                # If this is the current note, reload it
                if note_id == self.current_note_id:
                    self._load_note_content(note_id)
                
                self._show_status(f"Refreshed note from cloud: {note_id[:8]}...")
            else:
                self._show_status("Failed to refresh note from cloud", error=True)
                
        except Exception as e:
            print(f"Error refreshing note: {e}")
            self._show_status("Error refreshing note", error=True)
    
    def _handle_action_public_url(self, note_id: str):
        """Handle public URL action for a note."""
        try:
            if not self.notes_manager:
                self._show_status("Notes manager not available", error=True)
                return
            
            # Check if note exists in cloud
            sync_status = self.notes_manager.check_notes_sync_status()
            note_status = sync_status.get(note_id, {})
            
            if not note_status.get("cloud_exists", False):
                self._show_status("Note not available in cloud", error=True)
                return
            
            # Get public URL
            url = self.notes_manager.get_public_url(note_id)
            
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
            self._show_status("Error getting public URL", error=True)
    
    def _handle_action_delete(self, note_id: str):
        """Handle delete action for a note."""
        try:
            if not self.notes_manager:
                self._show_status("Notes manager not available", error=True)
                return
            
            # Get note title for confirmation
            note_data = self.notes_manager.get_note(note_id)
            note_title = note_data.get("title", "Unknown") if note_data else "Unknown"
            
            # Confirm deletion
            if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the note '{note_title}'?", parent=self.window):
                return
            
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
            self._show_status("Error deleting note", error=True)

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
        pass

    def _on_search_focus_in(self, event):
        """Handle search entry focus in."""
        pass

    def _on_search_focus_out(self, event):
        """Handle search entry focus out."""
        pass

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

    def _on_window_close(self):
        """Handle window close event."""
        self.hide_window()

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
            
            # Show in a dialog
            messagebox.showinfo("Cache Status", status_text, parent=self.window)
            
        except Exception as e:
            print(f"Error showing cache status: {e}")
            messagebox.showerror("Error", f"Failed to get cache status: {e}", parent=self.window)

    def _force_sync(self):
        """Force synchronization with cloud."""
        if not self.notes_manager or not self.cache_manager:
            messagebox.showerror("Error", "Notes manager or cache manager not available", parent=self.window)
            return
        
        try:
            self._show_status("Forcing sync with cloud...")
            
            # Force download of cloud index
            if hasattr(self.notes_manager, 'cloud_sync') and self.notes_manager.cloud_sync:
                cloud_index = self.notes_manager.cloud_sync.load_notes_overall_index()
                
                if cloud_index:
                    # Update local cache with cloud index
                    self.cache_manager.update_cache_index(cloud_index)
                    
                    # Refresh the UI
                    self._load_notes_list()
                    
                    self._show_status("Force sync completed successfully")
                    messagebox.showinfo("Force Sync", "Synchronization completed successfully", parent=self.window)
                else:
                    self._show_status("No cloud index found", error=True)
                    messagebox.showwarning("Force Sync", "No cloud index found", parent=self.window)
            else:
                self._show_status("Cloud sync not available", error=True)
                messagebox.showerror("Error", "Cloud sync not available", parent=self.window)
                
        except Exception as e:
            print(f"Error during force sync: {e}")
            self._show_status("Force sync failed", error=True)
            messagebox.showerror("Error", f"Force sync failed: {e}", parent=self.window)
    
    def _rebuild_index(self):
        """Rebuild the notes index from cloud."""
        if not self.notes_manager:
            messagebox.showerror("Error", "Notes manager not available", parent=self.window)
            return
        
        # Confirm rebuild
        if not messagebox.askyesno("Confirm Rebuild", "This will rebuild the index from all cloud notes. Continue?", parent=self.window):
            return
        
        try:
            self._show_status("Rebuilding index from cloud...")
            
            # This would be implemented in the notes manager
            # For now, just show a placeholder message
            messagebox.showinfo("Rebuild Index", "Index rebuild functionality not yet implemented", parent=self.window)
            
        except Exception as e:
            print(f"Error rebuilding index: {e}")
            self._show_status("Index rebuild failed", error=True)
            messagebox.showerror("Error", f"Index rebuild failed: {e}", parent=self.window)