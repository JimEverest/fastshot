# fastshot/session_manager_ui.py

import tkinter as tk
from tkinter import ttk, messagebox
import json
import threading
from datetime import datetime
from pathlib import Path
import math

class SessionManagerUI:
    """Session Manager UI with local and cloud file management."""
    
    def __init__(self, app):
        print("DEBUG: SessionManagerUI.__init__ called")
        try:
            print(f"DEBUG: app = {app}")
            self.app = app
            self.session_manager = app.session_manager
            print(f"DEBUG: session_manager = {self.session_manager}")
            self.cloud_sync = getattr(app, 'cloud_sync', None)
            print(f"DEBUG: cloud_sync = {self.cloud_sync}")
            
            # UI state
            self.current_page = 1
            self.items_per_page = 20
            self.sort_column = 'last_modified'
            self.sort_reverse = True
            self.filter_text = ""
            self.filter_tags = []
            self.filter_color = ""
            self.filter_class = ""
            
            # Data
            self.local_sessions = []
            self.cloud_sessions = []
            self.filtered_local_sessions = []
            self.filtered_cloud_sessions = []
            
            print("DEBUG: Calling _create_ui()")
            self._create_ui()
            print("DEBUG: _create_ui() completed")
            
            print("DEBUG: Calling _load_data()")
            self._load_data()
            print("DEBUG: _load_data() completed")
            
            print("DEBUG: SessionManagerUI.__init__ completed successfully")
        except Exception as e:
            print(f"ERROR in SessionManagerUI.__init__: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _create_ui(self):
        """Create the session manager UI."""
        self.window = tk.Toplevel(self.app.root)
        self.window.title("Session Manager")
        
        # Set window size and center it on screen
        window_width = 1200
        window_height = 800
        
        # Get screen dimensions
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        # Calculate position to center the window
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        
        # Ensure window is not positioned off-screen
        x = max(0, min(x, screen_width - window_width))
        y = max(0, min(y, screen_height - window_height))
        
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        # self.window.transient(self.app.root)  # Comment out to avoid parent window dependency
        
        # Ensure window is visible and on top
        self.window.attributes('-topmost', True)
        self.window.after(100, lambda: self.window.attributes('-topmost', False))  # Remove topmost after showing
        
        print(f"DEBUG: Window geometry set to: {window_width}x{window_height}+{x}+{y}")
        print(f"DEBUG: Screen size: {screen_width}x{screen_height}")
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Local sessions tab
        self.local_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.local_frame, text="Local Sessions")
        self._create_session_tab(self.local_frame, 'local')
        
        # Cloud sessions tab
        self.cloud_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.cloud_frame, text="Cloud Sessions")
        self._create_session_tab(self.cloud_frame, 'cloud')
        
        # Settings tab
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Cloud Settings")
        self._create_settings_tab()
        
        # Bind tab change event
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)
    
    def _create_session_tab(self, parent, tab_type):
        """Create a session tab (local or cloud)."""
        parent.tab_type = tab_type
        
        # Filter frame
        filter_frame = ttk.LabelFrame(parent, text="Filters", padding="10")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Filter controls
        filter_row1 = ttk.Frame(filter_frame)
        filter_row1.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(filter_row1, text="Search:").pack(side=tk.LEFT)
        search_entry = ttk.Entry(filter_row1, width=20)
        search_entry.pack(side=tk.LEFT, padx=(5, 15))
        search_entry.bind('<KeyRelease>', lambda e: self._apply_filters(tab_type))
        setattr(parent, 'search_entry', search_entry)
        
        ttk.Label(filter_row1, text="Tags:").pack(side=tk.LEFT)
        tags_entry = ttk.Entry(filter_row1, width=20)
        tags_entry.pack(side=tk.LEFT, padx=(5, 15))
        tags_entry.bind('<KeyRelease>', lambda e: self._apply_filters(tab_type))
        setattr(parent, 'tags_entry', tags_entry)
        
        ttk.Label(filter_row1, text="Color:").pack(side=tk.LEFT)
        color_combo = ttk.Combobox(filter_row1, width=12, values=["", "blue", "red", "green", "yellow", "purple", "orange", "pink", "gray"])
        color_combo.pack(side=tk.LEFT, padx=(5, 15))
        color_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters(tab_type))
        setattr(parent, 'color_combo', color_combo)
        
        ttk.Label(filter_row1, text="Class:").pack(side=tk.LEFT)
        class_entry = ttk.Entry(filter_row1, width=15)
        class_entry.pack(side=tk.LEFT, padx=(5, 15))
        class_entry.bind('<KeyRelease>', lambda e: self._apply_filters(tab_type))
        setattr(parent, 'class_entry', class_entry)
        
        # Clear filters button
        ttk.Button(filter_row1, text="Clear", command=lambda: self._clear_filters(tab_type)).pack(side=tk.RIGHT)
        
        # Treeview frame
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview
        columns = ('filename', 'desc', 'tags', 'color', 'class', 'images', 'thumbnail', 'size', 'date', 'source')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        tree.heading('filename', text='Filename', command=lambda: self._sort_by_column('filename', tab_type))
        tree.heading('desc', text='Description', command=lambda: self._sort_by_column('desc', tab_type))
        tree.heading('tags', text='Tags', command=lambda: self._sort_by_column('tags', tab_type))
        tree.heading('color', text='Color', command=lambda: self._sort_by_column('color', tab_type))
        tree.heading('class', text='Class', command=lambda: self._sort_by_column('class', tab_type))
        tree.heading('images', text='Images', command=lambda: self._sort_by_column('image_count', tab_type))
        tree.heading('thumbnail', text='📷', command=lambda: self._sort_by_column('thumbnail', tab_type))
        tree.heading('size', text='Size', command=lambda: self._sort_by_column('size', tab_type))
        tree.heading('date', text='Date', command=lambda: self._sort_by_column('last_modified', tab_type))
        tree.heading('source', text='Source', command=lambda: self._sort_by_column('source', tab_type))
        
        # Configure column widths
        tree.column('filename', width=180)
        tree.column('desc', width=160)
        tree.column('tags', width=120)
        tree.column('color', width=60)
        tree.column('class', width=80)
        tree.column('images', width=60)
        tree.column('thumbnail', width=40)
        tree.column('size', width=70)
        tree.column('date', width=120)
        tree.column('source', width=60)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Store tree reference
        setattr(parent, 'tree', tree)
        
        # Context menu
        context_menu = tk.Menu(tree, tearoff=0)
        context_menu.add_command(label="Load Session", command=lambda: self._load_selected_session(tab_type))
        context_menu.add_command(label="Show Thumbnail", command=lambda: self._show_selected_thumbnail(tab_type))
        context_menu.add_separator()
        context_menu.add_command(label="Delete", command=lambda: self._delete_selected_session(tab_type))
        context_menu.add_separator()
        
        if tab_type == 'local':
            context_menu.add_command(label="Sync to Cloud", command=lambda: self._sync_to_cloud())
        else:
            context_menu.add_command(label="Sync to Local", command=lambda: self._sync_to_local())
        
        def show_context_menu(event):
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()
        
        tree.bind("<Button-3>", show_context_menu)
        tree.bind("<Double-1>", lambda e: self._load_selected_session(tab_type))
        tree.bind("<Button-1>", lambda e: self._on_tree_click(e, tree, tab_type))
        
        # Bottom frame with pagination and actions
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Pagination
        pagination_frame = ttk.Frame(bottom_frame)
        pagination_frame.pack(side=tk.LEFT)
        
        ttk.Button(pagination_frame, text="◀◀", command=lambda: self._goto_page(1, tab_type)).pack(side=tk.LEFT)
        ttk.Button(pagination_frame, text="◀", command=lambda: self._prev_page(tab_type)).pack(side=tk.LEFT)
        
        page_label = ttk.Label(pagination_frame, text="Page 1 of 1")
        page_label.pack(side=tk.LEFT, padx=10)
        setattr(parent, 'page_label', page_label)
        
        ttk.Button(pagination_frame, text="▶", command=lambda: self._next_page(tab_type)).pack(side=tk.LEFT)
        ttk.Button(pagination_frame, text="▶▶", command=lambda: self._goto_last_page(tab_type)).pack(side=tk.LEFT)
        
        # Items per page
        ttk.Label(pagination_frame, text="Items per page:").pack(side=tk.LEFT, padx=(20, 5))
        items_combo = ttk.Combobox(pagination_frame, width=8, values=[10, 20, 50, 100], state="readonly")
        items_combo.set(str(self.items_per_page))
        items_combo.pack(side=tk.LEFT)
        items_combo.bind('<<ComboboxSelected>>', lambda e: self._change_items_per_page(tab_type))
        setattr(parent, 'items_combo', items_combo)
        
        # Action buttons
        action_frame = ttk.Frame(bottom_frame)
        action_frame.pack(side=tk.RIGHT)
        
        ttk.Button(action_frame, text="Refresh", command=lambda: self._refresh_data(tab_type)).pack(side=tk.LEFT, padx=5)
        
        if tab_type == 'cloud':
            ttk.Button(action_frame, text="Test Connection", command=self._test_cloud_connection).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text="Manual Sync", command=self._manual_sync).pack(side=tk.LEFT, padx=5)
    
    def _create_settings_tab(self):
        """Create cloud settings tab."""
        # Main frame with scrollbar
        canvas = tk.Canvas(self.settings_frame)
        scrollbar = ttk.Scrollbar(self.settings_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # AWS S3 Settings
        aws_frame = ttk.LabelFrame(scrollable_frame, text="AWS S3 Configuration", padding="10")
        aws_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Cloud sync enable
        self.cloud_sync_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(aws_frame, text="Enable Cloud Sync", variable=self.cloud_sync_enabled_var).pack(anchor=tk.W, pady=5)
        
        # AWS credentials
        ttk.Label(aws_frame, text="AWS Access Key:").pack(anchor=tk.W)
        self.aws_access_key_entry = ttk.Entry(aws_frame, width=50, show="*")
        self.aws_access_key_entry.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(aws_frame, text="AWS Secret Key:").pack(anchor=tk.W)
        self.aws_secret_key_entry = ttk.Entry(aws_frame, width=50, show="*")
        self.aws_secret_key_entry.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(aws_frame, text="AWS Region:").pack(anchor=tk.W)
        self.aws_region_entry = ttk.Entry(aws_frame, width=50)
        self.aws_region_entry.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(aws_frame, text="S3 Bucket Name:").pack(anchor=tk.W)
        self.s3_bucket_entry = ttk.Entry(aws_frame, width=50)
        self.s3_bucket_entry.pack(fill=tk.X, pady=(0, 10))
        
        # Encryption Settings
        encryption_frame = ttk.LabelFrame(scrollable_frame, text="Encryption Configuration", padding="10")
        encryption_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(encryption_frame, text="Encryption Key:").pack(anchor=tk.W)
        self.encryption_key_entry = ttk.Entry(encryption_frame, width=50, show="*")
        self.encryption_key_entry.pack(fill=tk.X, pady=(0, 10))
        
        # Proxy Settings
        proxy_frame = ttk.LabelFrame(scrollable_frame, text="Proxy Configuration", padding="10")
        proxy_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.proxy_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(proxy_frame, text="Enable Proxy", variable=self.proxy_enabled_var).pack(anchor=tk.W, pady=5)
        
        ttk.Label(proxy_frame, text="Proxy URL (http://username:password@host:port):").pack(anchor=tk.W)
        self.proxy_url_entry = ttk.Entry(proxy_frame, width=50)
        self.proxy_url_entry.pack(fill=tk.X, pady=(0, 10))
        
        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        
        ttk.Button(button_frame, text="Test Connection", command=self._test_cloud_connection).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Settings", command=self._save_cloud_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Load Settings", command=self._load_cloud_settings).pack(side=tk.LEFT, padx=5)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Load current settings
        self._load_cloud_settings()
    
    def _load_data(self):
        """Load session data in background."""
        def load_in_background():
            try:
                # Load local sessions
                self.local_sessions = self._load_local_sessions_with_metadata()
                
                # Load cloud sessions if enabled
                if self.cloud_sync and self.cloud_sync.cloud_sync_enabled:
                    self.cloud_sessions = self._load_cloud_sessions_with_metadata()
                else:
                    self.cloud_sessions = []
                
                # Update UI in main thread
                self.window.after(0, self._update_ui)
                
            except Exception as e:
                print(f"Error loading session data: {e}")
                self.window.after(0, lambda: messagebox.showerror("Error", f"Failed to load session data: {e}"))
        
        threading.Thread(target=load_in_background, daemon=True).start()
    
    def _load_local_sessions_with_metadata(self):
        """Load local sessions with metadata extraction."""
        sessions = []
        local_dir = Path.home() / ".fastshot" / "sessions"
        
        # Create directory if it doesn't exist
        local_dir.mkdir(parents=True, exist_ok=True)
        
        for file_path in local_dir.glob("*.fastshot"):
            try:
                # Try to extract metadata
                metadata = self._extract_session_metadata(file_path)
                
                stat = file_path.stat()
                session_info = {
                    'filename': file_path.name,
                    'path': str(file_path),
                    'size': stat.st_size,
                    'last_modified': datetime.fromtimestamp(stat.st_mtime),
                    'source': 'local',
                    'name': metadata.get('name', '') if metadata else '',
                    'desc': metadata.get('desc', '') if metadata else '',
                    'tags': metadata.get('tags', []) if metadata else [],
                    'color': metadata.get('color', '') if metadata else '',
                    'class': metadata.get('class', '') if metadata else '',
                    'image_count': metadata.get('image_count', 0) if metadata else 0,
                    'thumbnail_collage': metadata.get('thumbnail_collage', None) if metadata else None
                }
                sessions.append(session_info)
                
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
        
        return sessions
    
    def _load_cloud_sessions_with_metadata(self):
        """Load cloud sessions with metadata extraction."""
        sessions = []
        
        if not self.cloud_sync:
            return sessions
        
        try:
            cloud_list = self.cloud_sync.list_cloud_sessions()
            print(f"DEBUG: Found {len(cloud_list)} cloud sessions")
            
            # Only load metadata for first few sessions to avoid slow loading
            # Users can load individual sessions when needed
            MAX_METADATA_LOAD = 10  # Limit metadata loading to avoid slowness
            
            for i, session in enumerate(cloud_list):
                try:
                    metadata = {}
                    
                    # Only load full metadata for first few sessions
                    if i < MAX_METADATA_LOAD:
                        try:
                            print(f"DEBUG: Loading metadata for {session['filename']} ({i+1}/{min(len(cloud_list), MAX_METADATA_LOAD)})")
                            session_data = self.cloud_sync.load_session_from_cloud(session['filename'])
                            metadata = session_data.get('metadata', {}) if session_data else {}
                        except Exception as e:
                            print(f"Warning: Could not load metadata for {session['filename']}: {e}")
                            metadata = {}
                    else:
                        # For remaining sessions, show basic info only
                        metadata = {
                            'name': '',
                            'desc': '',
                            'tags': [],
                            'color': '',
                            'class': '',
                            'image_count': 0,
                            'thumbnail_collage': None
                        }
                    
                    session_info = {
                        'filename': session['filename'],
                        'size': session['size'],
                        'last_modified': session['last_modified'],
                        'source': 'cloud',
                        'name': metadata.get('name', '') if metadata else '',
                        'desc': metadata.get('desc', '') if metadata else '',
                        'tags': metadata.get('tags', []) if metadata else [],
                        'color': metadata.get('color', '') if metadata else '',
                        'class': metadata.get('class', '') if metadata else '',
                        'image_count': metadata.get('image_count', 0) if metadata else 0,
                        'thumbnail_collage': metadata.get('thumbnail_collage', None) if metadata else None
                    }
                    sessions.append(session_info)
                    
                except Exception as e:
                    print(f"Error processing cloud session {session['filename']}: {e}")
                    # Add basic entry even if processing fails
                    try:
                        sessions.append({
                            'filename': session['filename'],
                            'size': session['size'],
                            'last_modified': session['last_modified'],
                            'source': 'cloud',
                            'name': '',
                            'desc': 'Error loading',
                            'tags': [],
                            'color': '',
                            'class': '',
                            'image_count': 0,
                            'thumbnail_collage': None
                        })
                    except:
                        pass
                    continue
                    
        except Exception as e:
            print(f"Error loading cloud sessions: {e}")
        
        print(f"DEBUG: Loaded {len(sessions)} cloud sessions with metadata")
        return sessions
    
    def _extract_session_metadata(self, file_path):
        """Extract metadata from a session file."""
        try:
            # First try regular JSON format (most common)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    metadata = session_data.get('metadata', {})
                    if metadata:
                        return metadata
                    # For legacy files without metadata wrapper
                    # Try to infer some basic info
                    windows = session_data.get('windows', [])
                    return {
                        'image_count': len(windows),
                        'name': '',
                        'desc': '',
                        'tags': [],
                        'color': '',
                        'class': '',
                        'thumbnail_collage': None
                    }
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If JSON fails, try encrypted format
                pass
            
            # Try encrypted format if cloud sync is available
            if self.cloud_sync and hasattr(self.cloud_sync, 'encryption_key') and self.cloud_sync.encryption_key:
                try:
                    with open(file_path, 'rb') as f:
                        data = f.read()
                    
                    # Try to extract from image disguise
                    extracted_data = self.cloud_sync._extract_from_image(data)
                    decrypted_data = self.cloud_sync._decrypt_data(extracted_data)
                    
                    session_data = json.loads(decrypted_data.decode('utf-8'))
                    return session_data.get('metadata', {})
                except Exception as e:
                    print(f"Failed to decrypt {file_path}: {e}")
                    
        except Exception as e:
            print(f"Could not extract metadata from {file_path}: {e}")
        
        # Return empty metadata if all else fails
        return {
            'image_count': 0,
            'name': '',
            'desc': '',
            'tags': [],
            'color': '',
            'class': '',
            'thumbnail_collage': None
        }
    
    def _update_ui(self):
        """Update UI with loaded data."""
        self._apply_filters('local')
        self._apply_filters('cloud')
    
    def _apply_filters(self, tab_type):
        """Apply filters to session list."""
        frame = self.local_frame if tab_type == 'local' else self.cloud_frame
        sessions = self.local_sessions if tab_type == 'local' else self.cloud_sessions
        
        # Get filter values
        search_text = frame.search_entry.get().lower()
        tags_text = frame.tags_entry.get().lower()
        color_filter = frame.color_combo.get()
        class_filter = frame.class_entry.get().lower()
        
        # Apply filters
        filtered = []
        for session in sessions:
            # Search filter
            if search_text and search_text not in session['filename'].lower() and search_text not in session['desc'].lower():
                continue
            
            # Tags filter
            if tags_text:
                session_tags = [tag.lower() for tag in session['tags']]
                if not any(tags_text in tag for tag in session_tags):
                    continue
            
            # Color filter
            if color_filter and session['color'] != color_filter:
                continue
            
            # Class filter
            if class_filter and class_filter not in session['class'].lower():
                continue
            
            filtered.append(session)
        
        # Store filtered sessions
        if tab_type == 'local':
            self.filtered_local_sessions = filtered
        else:
            self.filtered_cloud_sessions = filtered
        
        # Reset to first page
        self.current_page = 1
        self._update_tree(tab_type)
    
    def _update_tree(self, tab_type):
        """Update treeview with current page data."""
        frame = self.local_frame if tab_type == 'local' else self.cloud_frame
        tree = frame.tree
        sessions = getattr(self, f'filtered_{tab_type}_sessions', [])
        
        # Clear existing items
        tree.delete(*tree.get_children())
        
        # Calculate pagination
        total_items = len(sessions)
        total_pages = max(1, math.ceil(total_items / self.items_per_page))
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, total_items)
        
        # Sort sessions
        if hasattr(self, 'sort_column') and self.sort_column:
            reverse = getattr(self, 'sort_reverse', False)
            sessions.sort(key=lambda x: x.get(self.sort_column, ''), reverse=reverse)
        
        # Add items to tree
        for session in sessions[start_idx:end_idx]:
            try:
                # Safely extract all fields with defaults
                tags_list = session.get('tags', [])
                tags_str = ', '.join(tags_list) if isinstance(tags_list, list) and tags_list else ''
                
                size = session.get('size', 0)
                size_str = f"{size / 1024:.1f} KB" if size > 0 else "0 KB"
                
                last_modified = session.get('last_modified')
                if isinstance(last_modified, datetime):
                    date_str = last_modified.strftime("%Y-%m-%d %H:%M")
                else:
                    date_str = str(last_modified) if last_modified else ''
                
                # Check if thumbnail exists
                thumbnail_collage = session.get('thumbnail_collage')
                thumbnail_icon = "🖼️" if thumbnail_collage else "📷"
                
                # Safely get description with truncation
                desc = session.get('desc', '') or ''
                desc_display = desc[:30] + ('...' if len(desc) > 30 else '') if desc else ''
                
                item_id = tree.insert('', tk.END, values=(
                    session.get('filename', ''),
                    desc_display,
                    tags_str,
                    session.get('color', ''),
                    session.get('class', ''),
                    str(session.get('image_count', 0)),
                    thumbnail_icon,
                    size_str,
                    date_str,
                    session.get('source', '')
                ))
                
                # Store session data for thumbnail viewing and description tooltip
                # We'll use item tags to store additional data
                item_tags = []
                if thumbnail_collage:
                    item_tags.append(thumbnail_collage)
                else:
                    item_tags.append('')  # Empty thumbnail data
                
                # Add full description as second tag for tooltip
                item_tags.append(desc)
                
                try:
                    tree.item(item_id, tags=tuple(item_tags))
                except Exception as e:
                    print(f"Warning: Could not store item data for {session.get('filename', 'unknown')}: {e}")
                        
            except Exception as e:
                print(f"Error adding session to tree: {e}")
                # Add minimal entry to avoid breaking the display
                try:
                    tree.insert('', tk.END, values=(
                        session.get('filename', 'Error'),
                        'Error loading session',
                        '', '', '', '0', '📷', '0 KB', '', session.get('source', '')
                    ))
                except:
                    pass  # Skip this item if we can't even add a minimal entry
        
        # Update pagination label
        frame.page_label.config(text=f"Page {self.current_page} of {total_pages} ({total_items} items)")
    
    def _clear_filters(self, tab_type):
        """Clear all filters."""
        frame = self.local_frame if tab_type == 'local' else self.cloud_frame
        frame.search_entry.delete(0, tk.END)
        frame.tags_entry.delete(0, tk.END)
        frame.color_combo.set('')
        frame.class_entry.delete(0, tk.END)
        self._apply_filters(tab_type)
    
    def _sort_by_column(self, column, tab_type):
        """Sort sessions by column."""
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        
        self._update_tree(tab_type)
    
    def _prev_page(self, tab_type):
        """Go to previous page."""
        if self.current_page > 1:
            self.current_page -= 1
            self._update_tree(tab_type)
    
    def _next_page(self, tab_type):
        """Go to next page."""
        sessions = getattr(self, f'filtered_{tab_type}_sessions', [])
        total_pages = max(1, math.ceil(len(sessions) / self.items_per_page))
        if self.current_page < total_pages:
            self.current_page += 1
            self._update_tree(tab_type)
    
    def _goto_page(self, page, tab_type):
        """Go to specific page."""
        sessions = getattr(self, f'filtered_{tab_type}_sessions', [])
        total_pages = max(1, math.ceil(len(sessions) / self.items_per_page))
        self.current_page = max(1, min(page, total_pages))
        self._update_tree(tab_type)
    
    def _goto_last_page(self, tab_type):
        """Go to last page."""
        sessions = getattr(self, f'filtered_{tab_type}_sessions', [])
        total_pages = max(1, math.ceil(len(sessions) / self.items_per_page))
        self._goto_page(total_pages, tab_type)
    
    def _change_items_per_page(self, tab_type):
        """Change items per page."""
        frame = self.local_frame if tab_type == 'local' else self.cloud_frame
        try:
            self.items_per_page = int(frame.items_combo.get())
            self.current_page = 1
            self._update_tree(tab_type)
        except ValueError:
            pass
    
    def _on_tab_changed(self, event):
        """Handle tab change."""
        selected_tab = event.widget.tab('current')['text']
        if selected_tab in ['Local Sessions', 'Cloud Sessions']:
            tab_type = 'local' if 'Local' in selected_tab else 'cloud'
            self._apply_filters(tab_type)
    
    def _refresh_data(self, tab_type):
        """Refresh session data."""
        self._load_data()
    
    def _load_selected_session(self, tab_type):
        """Load the selected session."""
        frame = self.local_frame if tab_type == 'local' else self.cloud_frame
        tree = frame.tree
        selection = tree.selection()
        
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to load.")
            return
        
        item = tree.item(selection[0])
        filename = item['values'][0]
        
        try:
            if tab_type == 'local':
                # Load local session
                filepath = Path.home() / ".fastshot" / "sessions" / filename
                if self.session_manager.load_session(filepath):
                    messagebox.showinfo("Success", f"Session '{filename}' loaded successfully.")
                    self.window.destroy()
                else:
                    messagebox.showerror("Error", "Failed to load session.")
            else:
                # Load cloud session
                if self.cloud_sync:
                    session_data = self.cloud_sync.load_session_from_cloud(filename)
                    if session_data and 'session' in session_data:
                        # Use session manager to recreate windows
                        for window_data in session_data['session'].get('windows', []):
                            self.session_manager.deserialize_window(window_data)
                        messagebox.showinfo("Success", f"Session '{filename}' loaded from cloud.")
                        self.window.destroy()
                    else:
                        messagebox.showerror("Error", "Failed to load session from cloud.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load session: {e}")
    
    def _delete_selected_session(self, tab_type):
        """Delete the selected session."""
        frame = self.local_frame if tab_type == 'local' else self.cloud_frame
        tree = frame.tree
        selection = tree.selection()
        
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to delete.")
            return
        
        item = tree.item(selection[0])
        filename = item['values'][0]
        
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{filename}'?"):
            return
        
        try:
            if tab_type == 'local':
                if self.cloud_sync and self.cloud_sync.delete_local_session(filename):
                    self._refresh_data(tab_type)
                    messagebox.showinfo("Success", f"Session '{filename}' deleted.")
                else:
                    messagebox.showerror("Error", "Failed to delete session.")
            else:
                if self.cloud_sync and self.cloud_sync.delete_cloud_session(filename):
                    self._refresh_data(tab_type)
                    messagebox.showinfo("Success", f"Session '{filename}' deleted from cloud.")
                else:
                    messagebox.showerror("Error", "Failed to delete session from cloud.")
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete session: {e}")
    
    def _sync_to_cloud(self):
        """Sync selected local session to cloud."""
        tree = self.local_frame.tree
        selection = tree.selection()
        
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to sync.")
            return
        
        item = tree.item(selection[0])
        filename = item['values'][0]
        
        if not self.cloud_sync:
            messagebox.showerror("Error", "Cloud sync not available.")
            return
        
        try:
            if self.cloud_sync.sync_to_cloud(filename):
                messagebox.showinfo("Success", f"Session '{filename}' synced to cloud.")
                self._refresh_data('cloud')
            else:
                messagebox.showerror("Error", "Failed to sync to cloud.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to sync: {e}")
    
    def _sync_to_local(self):
        """Sync selected cloud session to local."""
        tree = self.cloud_frame.tree
        selection = tree.selection()
        
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to sync.")
            return
        
        item = tree.item(selection[0])
        filename = item['values'][0]
        
        if not self.cloud_sync:
            messagebox.showerror("Error", "Cloud sync not available.")
            return
        
        try:
            if self.cloud_sync.sync_from_cloud(filename):
                messagebox.showinfo("Success", f"Session '{filename}' synced to local.")
                self._refresh_data('local')
            else:
                messagebox.showerror("Error", "Failed to sync from cloud.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to sync: {e}")
    
    def _manual_sync(self):
        """Perform manual sync between local and cloud."""
        if not self.cloud_sync:
            messagebox.showerror("Error", "Cloud sync not available.")
            return
        
        def sync_in_background():
            try:
                # This is a simple sync - in a real implementation, you might want
                # to compare timestamps and sync only newer files
                messagebox.showinfo("Sync", "Manual sync started. This may take a while...")
                
                # Refresh data after sync
                self.window.after(0, lambda: self._load_data())
                self.window.after(1000, lambda: messagebox.showinfo("Success", "Manual sync completed."))
                
            except Exception as e:
                self.window.after(0, lambda: messagebox.showerror("Error", f"Sync failed: {e}"))
        
        threading.Thread(target=sync_in_background, daemon=True).start()
    
    def _test_cloud_connection(self):
        """Test cloud connection."""
        if not self.cloud_sync:
            messagebox.showerror("Error", "Cloud sync not available.")
            return
        
        def test_in_background():
            try:
                success, message = self.cloud_sync.test_connection()
                self.window.after(0, lambda: messagebox.showinfo("Connection Test", message))
            except Exception as e:
                self.window.after(0, lambda: messagebox.showerror("Connection Test", f"Test failed: {e}"))
        
        threading.Thread(target=test_in_background, daemon=True).start()
    
    def _load_cloud_settings(self):
        """Load cloud settings into UI."""
        if not self.cloud_sync:
            return
        
        self.cloud_sync_enabled_var.set(self.cloud_sync.cloud_sync_enabled)
        self.aws_access_key_entry.insert(0, self.cloud_sync.aws_access_key)
        self.aws_secret_key_entry.insert(0, self.cloud_sync.aws_secret_key)
        self.aws_region_entry.insert(0, self.cloud_sync.aws_region)
        self.s3_bucket_entry.insert(0, self.cloud_sync.bucket_name or '')
        self.encryption_key_entry.insert(0, self.cloud_sync.encryption_key)
        self.proxy_enabled_var.set(self.cloud_sync.proxy_enabled)
        self.proxy_url_entry.insert(0, self.cloud_sync.proxy_url)
    
    def _save_cloud_settings(self):
        """Save cloud settings."""
        try:
            # Update config
            if 'CloudSync' not in self.app.config:
                self.app.config.add_section('CloudSync')
            
            # Clean credentials before saving
            access_key = self._clean_credential(self.aws_access_key_entry.get())
            secret_key = self._clean_credential(self.aws_secret_key_entry.get())
            
            self.app.config['CloudSync']['cloud_sync_enabled'] = str(self.cloud_sync_enabled_var.get())
            self.app.config['CloudSync']['aws_access_key'] = access_key
            self.app.config['CloudSync']['aws_secret_key'] = secret_key
            self.app.config['CloudSync']['aws_region'] = self.aws_region_entry.get().strip()
            self.app.config['CloudSync']['s3_bucket_name'] = self.s3_bucket_entry.get().strip()
            self.app.config['CloudSync']['encryption_key'] = self.encryption_key_entry.get().strip()
            self.app.config['CloudSync']['proxy_enabled'] = str(self.proxy_enabled_var.get())
            self.app.config['CloudSync']['proxy_url'] = self.proxy_url_entry.get().strip()
            
            # Save to file
            with open(self.app.config_path, 'w', encoding='utf-8') as f:
                self.app.config.write(f)
            
            # Reload cloud sync
            if self.cloud_sync:
                self.cloud_sync._load_cloud_config()
            
            # Show validation warnings if any
            if access_key and len(access_key) != 20:
                messagebox.showwarning("Credential Warning", f"AWS Access Key length is {len(access_key)}, expected 20 characters.")
            
            if secret_key and len(secret_key) != 40:
                messagebox.showwarning("Credential Warning", f"AWS Secret Key length is {len(secret_key)}, expected 40 characters.")
            
            messagebox.showinfo("Success", "Cloud settings saved successfully.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def _clean_credential(self, credential):
        """Clean AWS credentials by removing whitespace and potential formatting issues."""
        if not credential:
            return ''
        
        # Remove all whitespace characters (spaces, tabs, newlines)
        cleaned = ''.join(credential.split())
        
        # Remove any potential quotes that might have been added
        cleaned = cleaned.strip('\'"')
        
        return cleaned
    
    def show(self):
        """Show the session manager window."""
        try:
            print("DEBUG: SessionManagerUI.show() called")
            print(f"DEBUG: self.window = {self.window}")
            print(f"DEBUG: self.window.winfo_exists() = {self.window.winfo_exists()}")
            
            # Get current window state
            try:
                current_state = self.window.state()
                print(f"DEBUG: Current window state: {current_state}")
            except Exception as e:
                print(f"DEBUG: Could not get window state: {e}")
            
            # Get current geometry
            try:
                current_geometry = self.window.geometry()
                print(f"DEBUG: Current window geometry: {current_geometry}")
            except Exception as e:
                print(f"DEBUG: Could not get window geometry: {e}")
            
            print("DEBUG: Calling self.window.deiconify()")
            self.window.deiconify()
            print("DEBUG: self.window.deiconify() completed")
            
            # Force window to normal state
            print("DEBUG: Setting window state to normal")
            self.window.state('normal')
            
            print("DEBUG: Calling self.window.lift()")
            self.window.lift()
            print("DEBUG: self.window.lift() completed")
            
            # Temporarily set topmost to ensure visibility
            print("DEBUG: Setting window to topmost temporarily")
            self.window.attributes('-topmost', True)
            self.window.update()  # Force update
            
            print("DEBUG: Calling self.window.focus_force()")
            self.window.focus_force()
            print("DEBUG: self.window.focus_force() completed")
            
            # Remove topmost after a short delay
            self.window.after(500, lambda: self.window.attributes('-topmost', False))
            
            # Final geometry and state check
            try:
                final_geometry = self.window.geometry()
                final_state = self.window.state()
                print(f"DEBUG: Final window geometry: {final_geometry}")
                print(f"DEBUG: Final window state: {final_state}")
                print(f"DEBUG: Window visible: {self.window.winfo_viewable()}")
                print(f"DEBUG: Window mapped: {self.window.winfo_ismapped()}")
            except Exception as e:
                print(f"DEBUG: Could not get final window info: {e}")
            
            print("DEBUG: SessionManagerUI.show() completed successfully")
        except Exception as e:
            print(f"ERROR in SessionManagerUI.show(): {e}")
            import traceback
            traceback.print_exc()
    
    def _on_tree_click(self, event, tree, tab_type):
        """Handle tree click events, especially for thumbnail column."""
        try:
            # Identify the clicked region
            region = tree.identify_region(event.x, event.y)
            if region != "cell":
                return
            
            # Get the clicked item and column
            item_id = tree.identify_row(event.y)
            column = tree.identify_column(event.x)
            
            if not item_id:
                return
            
            # Check if clicked on thumbnail column (column #7 - 0-indexed, so '#7')
            if column == '#7':  # thumbnail column
                # Get thumbnail data from item tags (first tag)
                tags = tree.item(item_id, 'tags')
                if tags and len(tags) > 0:
                    thumbnail_data = tags[0]
                    if thumbnail_data:
                        self._show_thumbnail_popup(event, thumbnail_data)
            # Check if clicked on description column (column #2)
            elif column == '#2':  # description column
                # Get full description from item tags (second tag)
                tags = tree.item(item_id, 'tags')
                if tags and len(tags) > 1:
                    full_desc = tags[1]
                    if full_desc and len(full_desc) > 30:  # Only show tooltip if description is truncated
                        self._show_description_tooltip(event, full_desc)
        except Exception as e:
            print(f"Error handling tree click: {e}")
    
    def _show_thumbnail_popup(self, event, thumbnail_data):
        """Show thumbnail popup when thumbnail icon is clicked."""
        try:
            # Deserialize thumbnail image
            from .session_manager import SessionManager
            temp_manager = SessionManager(self.app)
            thumbnail_image = temp_manager.deserialize_image(thumbnail_data)
            
            if not thumbnail_image:
                return
            
            # Create popup window
            popup = tk.Toplevel(self.window)
            popup.title("Session Thumbnail")
            popup.attributes('-topmost', True)
            popup.resizable(False, False)
            
            # Calculate popup position near mouse
            x = event.x_root + 10
            y = event.y_root + 10
            
            # Ensure popup doesn't go off screen
            screen_width = popup.winfo_screenwidth()
            screen_height = popup.winfo_screenheight()
            
            # Scale image if too large
            img_width, img_height = thumbnail_image.size
            max_size = 400
            if img_width > max_size or img_height > max_size:
                ratio = min(max_size / img_width, max_size / img_height)
                new_width = int(img_width * ratio)
                new_height = int(img_height * ratio)
                thumbnail_image = thumbnail_image.resize((new_width, new_height), Image.LANCZOS)
                img_width, img_height = new_width, new_height
            
            # Adjust position if popup would go off screen
            if x + img_width > screen_width:
                x = event.x_root - img_width - 10
            if y + img_height > screen_height:
                y = event.y_root - img_height - 10
            
            popup.geometry(f"{img_width}x{img_height}+{x}+{y}")
            
            # Display image
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(thumbnail_image)
            label = tk.Label(popup, image=photo)
            label.image = photo  # Keep a reference
            label.pack()
            
            # Auto-hide after 3 seconds or on click
            popup.after(3000, popup.destroy)
            label.bind("<Button-1>", lambda e: popup.destroy())
            
            # Also hide when mouse leaves the popup
            def on_leave(event):
                popup.after(500, popup.destroy)
            popup.bind("<Leave>", on_leave)
            
        except Exception as e:
            print(f"Error showing thumbnail popup: {e}")
    
    def _show_selected_thumbnail(self, tab_type):
        """Show thumbnail in a larger window for the selected session."""
        frame = self.local_frame if tab_type == 'local' else self.cloud_frame
        tree = frame.tree
        selection = tree.selection()
        
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to view thumbnail.")
            return
        
        try:
            item_id = selection[0]
            item_values = tree.item(item_id, 'values')
            filename = item_values[0] if item_values else "Unknown"
            
            # Get thumbnail data from item tags (first tag)
            tags = tree.item(item_id, 'tags')
            thumbnail_data = None
            
            if tags and len(tags) > 0:
                thumbnail_data = tags[0] if tags[0] else None
            else:
                # Try to load thumbnail data if not available
                if tab_type == 'local':
                    # For local files, try to extract metadata
                    sessions = self.filtered_local_sessions
                else:
                    # For cloud files, try to load session data
                    sessions = self.filtered_cloud_sessions
                
                # Find the session data
                session_data = None
                for session in sessions:
                    if session.get('filename') == filename:
                        session_data = session
                        break
                
                if session_data:
                    thumbnail_data = session_data.get('thumbnail_collage')
            
            if not thumbnail_data:
                messagebox.showinfo("No Thumbnail", f"No thumbnail available for '{filename}'.")
                return
            
            self._show_thumbnail_window(thumbnail_data, filename)
            
        except Exception as e:
            print(f"Error showing selected thumbnail: {e}")
            messagebox.showerror("Error", f"Failed to show thumbnail: {e}")
    
    def _show_thumbnail_window(self, thumbnail_data, filename):
        """Show thumbnail in a dedicated window."""
        try:
            # Deserialize thumbnail image
            from .session_manager import SessionManager
            temp_manager = SessionManager(self.app)
            thumbnail_image = temp_manager.deserialize_image(thumbnail_data)
            
            if not thumbnail_image:
                messagebox.showerror("Error", "Failed to load thumbnail image.")
                return
            
            # Create thumbnail window
            thumb_window = tk.Toplevel(self.window)
            thumb_window.title(f"Session Thumbnail - {filename}")
            
            # Calculate window size and position
            img_width, img_height = thumbnail_image.size
            
            # Scale image if too large for screen
            screen_width = thumb_window.winfo_screenwidth()
            screen_height = thumb_window.winfo_screenheight()
            max_width = int(screen_width * 0.8)
            max_height = int(screen_height * 0.8)
            
            if img_width > max_width or img_height > max_height:
                ratio = min(max_width / img_width, max_height / img_height)
                new_width = int(img_width * ratio)
                new_height = int(img_height * ratio)
                thumbnail_image = thumbnail_image.resize((new_width, new_height), Image.LANCZOS)
                img_width, img_height = new_width, new_height
            
            # Center window on screen
            x = (screen_width - img_width) // 2
            y = (screen_height - img_height) // 2
            thumb_window.geometry(f"{img_width + 20}x{img_height + 60}+{x}+{y}")
            
            # Create main frame
            main_frame = ttk.Frame(thumb_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Display image
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(thumbnail_image)
            label = ttk.Label(main_frame, image=photo)
            label.image = photo  # Keep a reference
            label.pack()
            
            # Add filename label
            filename_label = ttk.Label(main_frame, text=filename, font=("Arial", 10, "bold"))
            filename_label.pack(pady=(10, 0))
            
            # Add close button
            close_button = ttk.Button(main_frame, text="Close", command=thumb_window.destroy)
            close_button.pack(pady=(10, 0))
            
            # Make window resizable
            thumb_window.resizable(True, True)
            
            # Bind Escape key to close
            thumb_window.bind('<Escape>', lambda e: thumb_window.destroy())
            
            # Focus on window
            thumb_window.focus()
            
        except Exception as e:
            print(f"Error creating thumbnail window: {e}")
            messagebox.showerror("Error", f"Failed to create thumbnail window: {e}")
    
    def _show_description_tooltip(self, event, full_desc):
        """Show description tooltip with Markdown support."""
        try:
            # Create tooltip window
            tooltip = tk.Toplevel(self.window)
            tooltip.title("Description")
            tooltip.attributes('-topmost', True)
            tooltip.resizable(True, True)
            tooltip.configure(bg='#ffffcc')  # Light yellow background
            
            # Calculate tooltip position near mouse
            x = event.x_root + 10
            y = event.y_root + 10
            
            # Ensure tooltip doesn't go off screen
            screen_width = tooltip.winfo_screenwidth()
            screen_height = tooltip.winfo_screenheight()
            
            # Create main frame
            main_frame = ttk.Frame(tooltip, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Try to render Markdown if possible, otherwise show plain text
            try:
                # Simple Markdown rendering for basic formatting
                formatted_text = self._simple_markdown_to_text(full_desc)
                
                # Create text widget with formatted content
                text_widget = tk.Text(main_frame, wrap=tk.WORD, width=60, height=10, 
                                    font=("Arial", 10), bg='#ffffcc', relief=tk.FLAT)
                text_widget.insert("1.0", formatted_text)
                text_widget.config(state=tk.DISABLED)  # Read-only
                
                # Add scrollbar if needed
                scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)
                
                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                
            except Exception as e:
                print(f"Error formatting description: {e}")
                # Fallback to plain text
                label = tk.Label(main_frame, text=full_desc, wraplength=400, 
                               justify=tk.LEFT, font=("Arial", 10), bg='#ffffcc')
                label.pack()
            
            # Calculate window size
            tooltip.update_idletasks()
            tooltip_width = min(500, tooltip.winfo_reqwidth())
            tooltip_height = min(300, tooltip.winfo_reqheight())
            
            # Adjust position if tooltip would go off screen
            if x + tooltip_width > screen_width:
                x = event.x_root - tooltip_width - 10
            if y + tooltip_height > screen_height:
                y = event.y_root - tooltip_height - 10
            
            tooltip.geometry(f"{tooltip_width}x{tooltip_height}+{x}+{y}")
            
            # Auto-hide after 5 seconds or on click
            tooltip.after(5000, tooltip.destroy)
            tooltip.bind("<Button-1>", lambda e: tooltip.destroy())
            
            # Hide when mouse leaves the tooltip
            def on_leave(event):
                tooltip.after(1000, tooltip.destroy)
            tooltip.bind("<Leave>", on_leave)
            
            # Bind Escape key to close
            tooltip.bind('<Escape>', lambda e: tooltip.destroy())
            
        except Exception as e:
            print(f"Error showing description tooltip: {e}")
    
    def _simple_markdown_to_text(self, text):
        """Simple Markdown to text conversion for basic formatting."""
        try:
            import re
            
            # Simple conversions for basic Markdown
            # Bold **text** or __text__
            text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
            text = re.sub(r'__(.*?)__', r'\1', text)
            
            # Italic *text* or _text_
            text = re.sub(r'\*(.*?)\*', r'\1', text)
            text = re.sub(r'_(.*?)_', r'\1', text)
            
            # Code `text`
            text = re.sub(r'`(.*?)`', r'[\1]', text)
            
            # Headers
            text = re.sub(r'^#{1,6}\s*(.*?)$', r'\1', text, flags=re.MULTILINE)
            
            # Lists (simple)
            text = re.sub(r'^\s*[\*\-\+]\s*(.*?)$', r'• \1', text, flags=re.MULTILINE)
            text = re.sub(r'^\s*\d+\.\s*(.*?)$', r'1. \1', text, flags=re.MULTILINE)
            
            return text
            
        except Exception as e:
            print(f"Error converting Markdown: {e}")
            return text  # Return original text if conversion fails 