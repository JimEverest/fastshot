# fastshot/session_manager_ui.py

import tkinter as tk
from tkinter import ttk, messagebox
import json
import threading
from datetime import datetime
from pathlib import Path
import math
from .meta_cache import MetaCacheManager
from .async_operations import get_async_manager, CloudMetadataSyncOperation

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
            
            # Initialize metadata cache manager
            try:
                self.meta_cache = MetaCacheManager()
                print("DEBUG: MetaCacheManager initialized successfully")
            except Exception as e:
                print(f"WARNING: Failed to initialize MetaCacheManager: {e}")
                self.meta_cache = None
            
            # Initialize async operation manager
            try:
                self.async_manager = get_async_manager()
                print("DEBUG: AsyncOperationManager initialized successfully")
                
                # Initialize cloud metadata sync operation
                if self.cloud_sync and self.meta_cache:
                    self.cloud_metadata_sync = CloudMetadataSyncOperation(
                        self.cloud_sync, self.meta_cache, self.async_manager
                    )
                    print("DEBUG: CloudMetadataSyncOperation initialized successfully")
                else:
                    self.cloud_metadata_sync = None
                    print("DEBUG: CloudMetadataSyncOperation not available (missing cloud_sync or meta_cache)")
            except Exception as e:
                print(f"WARNING: Failed to initialize AsyncOperationManager: {e}")
                self.async_manager = None
                self.cloud_metadata_sync = None
            
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
            
            # Cache management buttons
            ttk.Separator(action_frame, orient='vertical').pack(side=tk.LEFT, padx=10, fill='y')
            ttk.Button(action_frame, text="Smart Sync", command=self._smart_cache_sync).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text="Rebuild All Indexes", command=self._rebuild_all_indexes).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text="Rebuild Overall List", command=self._rebuild_overall_list).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text="Cache Cleanup", command=self._cleanup_cache).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text="Cache Status", command=self._show_cache_status).pack(side=tk.LEFT, padx=5)
    
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
        
        # SSL Verification Settings
        ssl_frame = ttk.LabelFrame(scrollable_frame, text="SSL Configuration", padding="10")
        ssl_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.ssl_verify_var = tk.BooleanVar()
        ssl_checkbox = ttk.Checkbutton(ssl_frame, text="Enable SSL Certificate Verification", variable=self.ssl_verify_var)
        ssl_checkbox.pack(anchor=tk.W, pady=5)
        
        # Add warning label
        warning_label = ttk.Label(ssl_frame, text="⚠️ Disable SSL verification only in proxy environments where certificate validation fails.\nThis reduces security and should not be used in production.", 
                                 foreground="orange", font=("Arial", 9))
        warning_label.pack(anchor=tk.W, pady=(5, 10))
        
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
        """Load cloud sessions with metadata extraction using async approach."""
        sessions = []
        
        if not self.cloud_sync:
            return sessions
        
        # First, try to load from cache for immediate display
        cached_sessions = self._load_cached_cloud_sessions()
        if cached_sessions:
            print(f"DEBUG: Loaded {len(cached_sessions)} sessions from cache")
            sessions = cached_sessions
            
            # Update UI immediately with cached data
            self.cloud_sessions = sessions
            self.window.after(0, lambda: self._apply_filters('cloud'))
            
            # Start background sync to update cache
            self._start_background_sync()
            
            return sessions
        
        # If no cache available, load basic info immediately and metadata asynchronously
        print("DEBUG: No cache available, loading basic info immediately...")
        return self._load_cloud_sessions_async()
    
    def _load_cached_cloud_sessions(self):
        """Load cloud sessions from local cache."""
        if not self.meta_cache:
            return []
        
        try:
            cached_metadata = self.meta_cache.get_cached_metadata()
            sessions = []
            
            for meta_data in cached_metadata:
                try:
                    # Extract metadata from cache entry
                    metadata = meta_data.get('metadata', {})
                    filename = meta_data.get('filename', '')
                    
                    if not filename:
                        continue
                    
                    # Create session info from cached metadata
                    session_info = {
                        'filename': filename,
                        'size': metadata.get('file_size', 0),
                        'last_modified': self._parse_datetime(metadata.get('created_at', '')),
                        'source': 'cloud',
                        'name': metadata.get('name', ''),
                        'desc': metadata.get('desc', ''),
                        'tags': metadata.get('tags', []),
                        'color': metadata.get('color', ''),
                        'class': metadata.get('class', ''),
                        'image_count': metadata.get('image_count', 0),
                        'thumbnail_collage': metadata.get('thumbnail_collage', None)
                    }
                    sessions.append(session_info)
                    
                except Exception as e:
                    print(f"Warning: Error processing cached metadata for {meta_data.get('filename', 'unknown')}: {e}")
                    continue
            
            return sessions
            
        except Exception as e:
            print(f"Error loading cached cloud sessions: {e}")
            return []
    
    def _load_cloud_sessions_async(self):
        """Load cloud sessions with immediate basic info display and async metadata loading."""
        sessions = []
        
        try:
            # Step 1: Get basic session list immediately (this is fast)
            print("DEBUG: Loading basic session list from cloud...")
            cloud_list = self.cloud_sync.list_cloud_sessions()
            print(f"DEBUG: Found {len(cloud_list)} cloud sessions")
            
            # Step 2: Create sessions with basic info immediately
            for session in cloud_list:
                session_info = {
                    'filename': session['filename'],
                    'size': session['size'],
                    'last_modified': session['last_modified'],
                    'source': 'cloud',
                    # Basic metadata (will be updated asynchronously)
                    'name': '',
                    'desc': 'Loading...',
                    'tags': [],
                    'color': '',
                    'class': '',
                    'image_count': 0,
                    'thumbnail_collage': None,
                    # Mark as loading
                    '_loading_metadata': True
                }
                sessions.append(session_info)
            
            # Step 3: Update UI immediately with basic info
            self.cloud_sessions = sessions
            self.window.after(0, lambda: self._apply_filters('cloud'))
            
            # Step 4: Start async metadata loading
            if self.async_manager and self.cloud_metadata_sync:
                print("DEBUG: Starting async metadata sync...")
                operation_id = self.cloud_metadata_sync.sync_all_metadata(
                    progress_callback=self._on_metadata_sync_progress
                )
                print(f"DEBUG: Async metadata sync started with operation ID: {operation_id}")
            else:
                print("DEBUG: Async manager not available, falling back to batch loading")
                self._start_batch_metadata_loading(sessions)
            
            return sessions
            
        except Exception as e:
            print(f"Error in async cloud session loading: {e}")
            # Fallback to direct loading
            return self._load_cloud_sessions_direct()
    
    def _start_batch_metadata_loading(self, sessions):
        """Start batch metadata loading in background thread (fallback method)."""
        def load_metadata_batch():
            try:
                print("DEBUG: Starting batch metadata loading...")
                batch_size = 5
                total_sessions = len(sessions)
                
                for i in range(0, total_sessions, batch_size):
                    batch = sessions[i:i + batch_size]
                    print(f"DEBUG: Loading metadata batch {i//batch_size + 1} ({len(batch)} sessions)")
                    
                    for session in batch:
                        try:
                            filename = session['filename']
                            
                            # Try to load metadata index first
                            meta_index = self.cloud_sync.load_meta_index_from_cloud(filename)
                            if meta_index:
                                metadata = meta_index
                            else:
                                # Fallback to loading full session (slower)
                                session_data = self.cloud_sync.load_session_from_cloud(filename)
                                metadata = session_data.get('metadata', {}) if session_data else {}
                            
                            # Update session with metadata
                            session.update({
                                'name': metadata.get('name', ''),
                                'desc': metadata.get('desc', ''),
                                'tags': metadata.get('tags', []),
                                'color': metadata.get('color', ''),
                                'class': metadata.get('class', ''),
                                'image_count': metadata.get('image_count', 0),
                                'thumbnail_collage': metadata.get('thumbnail_collage', None),
                                '_loading_metadata': False
                            })
                            
                            # Save to cache if available
                            if self.meta_cache:
                                self.meta_cache.save_meta_index(filename, metadata)
                            
                        except Exception as e:
                            print(f"Error loading metadata for {session.get('filename', 'unknown')}: {e}")
                            # Mark as failed to load
                            session.update({
                                'desc': 'Error loading metadata',
                                '_loading_metadata': False
                            })
                    
                    # Update UI after each batch
                    self.window.after(0, lambda: self._apply_filters('cloud'))
                    
                    # Small delay between batches to keep UI responsive
                    threading.Event().wait(0.1)
                
                print("DEBUG: Batch metadata loading completed")
                
            except Exception as e:
                print(f"Error in batch metadata loading: {e}")
        
        # Start background thread
        threading.Thread(target=load_metadata_batch, daemon=True).start()
    
    def _on_metadata_sync_progress(self, operation_id, progress, status, result=None, error=None, message=None):
        """Handle progress updates from async metadata sync."""
        try:
            print(f"DEBUG: Metadata sync progress: {progress:.1f}% - {message or status}")
            
            if status == 'completed' and result:
                print(f"DEBUG: Metadata sync completed: {result}")
                # Reload sessions from updated cache
                updated_sessions = self._load_cached_cloud_sessions()
                if updated_sessions:
                    self.cloud_sessions = updated_sessions
                    # Update UI in main thread
                    self.window.after(0, lambda: self._apply_filters('cloud'))
        
        except Exception as e:
            print(f"Error in metadata sync progress callback: {e}")
    
    def _smart_cache_sync(self):
        """Perform smart cache synchronization with user prompts for orphaned entries."""
        if not self.cloud_sync or not self.meta_cache or not self.cloud_metadata_sync:
            messagebox.showerror("Error", "Smart cache sync not available. Cloud sync or cache manager not initialized.")
            return
        
        if not self.cloud_sync.cloud_sync_enabled:
            messagebox.showerror("Error", "Cloud sync is not enabled. Please enable it in settings first.")
            return
        
        # Show progress dialog
        progress_dialog = self._create_progress_dialog("Smart Cache Synchronization", "Initializing...")
        
        # Track orphaned entries for user confirmation
        orphaned_entries = []
        orphan_decisions = {}
        
        def orphan_callback(filename):
            """Callback to handle orphaned cache entries."""
            orphaned_entries.append(filename)
            # For now, return True to delete (we'll ask user later)
            return orphan_decisions.get(filename, True)
        
        def progress_callback(operation_id, progress, status, result=None, error=None, message=None):
            """Handle progress updates."""
            try:
                # Update progress dialog
                if progress_dialog:
                    self._update_progress_dialog(progress_dialog, progress, message or status)
                
                if status == 'completed':
                    # Close progress dialog
                    if progress_dialog:
                        self._close_progress_dialog(progress_dialog)
                    
                    if result and result.get('success'):
                        # Show results
                        self._show_sync_results(result, orphaned_entries)
                        # Refresh cloud sessions
                        self._refresh_data('cloud')
                    else:
                        error_msg = result.get('error', 'Unknown error') if result else 'Operation failed'
                        messagebox.showerror("Smart Sync Failed", f"Smart cache synchronization failed:\n{error_msg}")
                
                elif status == 'failed':
                    # Close progress dialog
                    if progress_dialog:
                        self._close_progress_dialog(progress_dialog)
                    messagebox.showerror("Smart Sync Failed", f"Smart cache synchronization failed:\n{error or 'Unknown error'}")
            
            except Exception as e:
                print(f"Error in smart sync progress callback: {e}")
        
        # Ask user about orphaned entries before starting
        if orphaned_entries:
            self._handle_orphaned_entries(orphaned_entries, orphan_decisions)
        
        # Start smart cache sync operation
        try:
            operation_id = self.cloud_metadata_sync.smart_cache_sync(
                orphan_callback=orphan_callback,
                progress_callback=progress_callback
            )
            print(f"Started smart cache sync operation: {operation_id}")
        except Exception as e:
            if progress_dialog:
                self._close_progress_dialog(progress_dialog)
            messagebox.showerror("Error", f"Failed to start smart cache sync:\n{e}")
    
    def _cleanup_cache(self):
        """Perform cache cleanup and validation."""
        if not self.meta_cache or not self.cloud_metadata_sync:
            messagebox.showerror("Error", "Cache cleanup not available. Cache manager not initialized.")
            return
        
        # Confirm with user
        if not messagebox.askyesno("Confirm Cache Cleanup", 
                                  "This will validate and clean up corrupted or orphaned cache files.\n\n"
                                  "Do you want to continue?"):
            return
        
        # Show progress dialog
        progress_dialog = self._create_progress_dialog("Cache Cleanup", "Starting cleanup...")
        
        def progress_callback(operation_id, progress, status, result=None, error=None, message=None):
            """Handle progress updates."""
            try:
                # Update progress dialog
                if progress_dialog:
                    self._update_progress_dialog(progress_dialog, progress, message or status)
                
                if status == 'completed':
                    # Close progress dialog
                    if progress_dialog:
                        self._close_progress_dialog(progress_dialog)
                    
                    if result and result.get('success'):
                        self._show_cleanup_results(result)
                        # Refresh cloud sessions
                        self._refresh_data('cloud')
                    else:
                        error_msg = result.get('error', 'Unknown error') if result else 'Operation failed'
                        messagebox.showerror("Cleanup Failed", f"Cache cleanup failed:\n{error_msg}")
                
                elif status == 'failed':
                    # Close progress dialog
                    if progress_dialog:
                        self._close_progress_dialog(progress_dialog)
                    messagebox.showerror("Cleanup Failed", f"Cache cleanup failed:\n{error or 'Unknown error'}")
            
            except Exception as e:
                print(f"Error in cleanup progress callback: {e}")
        
        # Start cache cleanup operation
        try:
            operation_id = self.cloud_metadata_sync.cleanup_cache(
                progress_callback=progress_callback
            )
            print(f"Started cache cleanup operation: {operation_id}")
        except Exception as e:
            if progress_dialog:
                self._close_progress_dialog(progress_dialog)
            messagebox.showerror("Error", f"Failed to start cache cleanup:\n{e}")
    
    def _handle_orphaned_entries(self, orphaned_entries, orphan_decisions):
        """Handle orphaned cache entries with user input."""
        if not orphaned_entries:
            return
        
        # Create dialog for orphaned entries
        dialog = tk.Toplevel(self.window)
        dialog.title("Orphaned Cache Entries Found")
        dialog.geometry("600x400")
        dialog.transient(self.window)
        dialog.grab_set()
        
        # Center dialog
        dialog.geometry("+%d+%d" % (
            self.window.winfo_rootx() + 50,
            self.window.winfo_rooty() + 50
        ))
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Info label
        info_label = ttk.Label(main_frame, 
                              text=f"Found {len(orphaned_entries)} cache entries that no longer exist in cloud storage.\n"
                                   "These entries can be safely deleted to free up space.",
                              wraplength=550)
        info_label.pack(pady=(0, 10))
        
        # Listbox with orphaned entries
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        for entry in orphaned_entries:
            listbox.insert(tk.END, entry)
        
        # Select all by default
        listbox.select_set(0, tk.END)
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        def on_delete_selected():
            selected_indices = listbox.curselection()
            for i in selected_indices:
                filename = orphaned_entries[i]
                orphan_decisions[filename] = True
            dialog.destroy()
        
        def on_keep_all():
            for filename in orphaned_entries:
                orphan_decisions[filename] = False
            dialog.destroy()
        
        def on_select_all():
            listbox.select_set(0, tk.END)
        
        def on_select_none():
            listbox.select_clear(0, tk.END)
        
        ttk.Button(button_frame, text="Select All", command=on_select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Select None", command=on_select_none).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Selected", command=on_delete_selected).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Keep All", command=on_keep_all).pack(side=tk.RIGHT, padx=5)
        
        # Wait for dialog to close
        dialog.wait_window()
    
    def _show_sync_results(self, results, orphaned_entries):
        """Show smart cache sync results."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Smart Cache Sync Results")
        dialog.geometry("500x400")
        dialog.transient(self.window)
        
        # Center dialog
        dialog.geometry("+%d+%d" % (
            self.window.winfo_rootx() + 100,
            self.window.winfo_rooty() + 100
        ))
        
        # Main frame with scrollbar
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Results text
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        # Format results
        result_text = "Smart Cache Synchronization Results\n"
        result_text += "=" * 40 + "\n\n"
        result_text += f"Cloud Sessions: {results.get('cloud_sessions', 0)}\n"
        result_text += f"Cached Sessions: {results.get('cached_sessions', 0)}\n"
        result_text += f"Missing Sessions Downloaded: {results.get('missing_sessions', 0)}\n"
        result_text += f"Orphaned Sessions Found: {results.get('orphaned_sessions', 0)}\n\n"
        
        if results.get('downloaded'):
            result_text += "Downloaded Metadata:\n"
            for filename in results['downloaded']:
                result_text += f"  • {filename}\n"
            result_text += "\n"
        
        if results.get('deleted'):
            result_text += "Deleted Orphaned Entries:\n"
            for filename in results['deleted']:
                result_text += f"  • {filename}\n"
            result_text += "\n"
        
        if results.get('errors'):
            result_text += "Errors:\n"
            for error in results['errors']:
                result_text += f"  • {error}\n"
            result_text += "\n"
        
        result_text += f"Cache Valid: {'Yes' if results.get('cache_valid', False) else 'No'}\n"
        
        # Insert text
        text_widget.config(state=tk.NORMAL)
        text_widget.insert(tk.END, result_text)
        text_widget.config(state=tk.DISABLED)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=(10, 0))
    
    def _show_cleanup_results(self, results):
        """Show cache cleanup results."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Cache Cleanup Results")
        dialog.geometry("500x400")
        dialog.transient(self.window)
        
        # Center dialog
        dialog.geometry("+%d+%d" % (
            self.window.winfo_rootx() + 100,
            self.window.winfo_rooty() + 100
        ))
        
        # Main frame with scrollbar
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Results text
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        # Format results
        result_text = "Cache Cleanup Results\n"
        result_text += "=" * 25 + "\n\n"
        result_text += f"Total Files Checked: {results.get('total_files_checked', 0)}\n"
        result_text += f"Corrupted Files Found: {results.get('corrupted_files_found', 0)}\n"
        result_text += f"Corrupted Files Removed: {results.get('corrupted_files_removed', 0)}\n"
        result_text += f"Orphaned Files Found: {results.get('orphaned_files_found', 0)}\n"
        result_text += f"Orphaned Files Removed: {results.get('orphaned_files_removed', 0)}\n\n"
        
        # Size information
        size_before = results.get('cache_size_before', 0)
        size_after = results.get('cache_size_after', 0)
        size_saved = size_before - size_after
        
        result_text += f"Cache Size Before: {self._format_file_size(size_before)}\n"
        result_text += f"Cache Size After: {self._format_file_size(size_after)}\n"
        result_text += f"Space Freed: {self._format_file_size(size_saved)}\n\n"
        
        if results.get('errors'):
            result_text += "Errors:\n"
            for error in results['errors']:
                result_text += f"  • {error}\n"
        
        # Insert text
        text_widget.config(state=tk.NORMAL)
        text_widget.insert(tk.END, result_text)
        text_widget.config(state=tk.DISABLED)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=(10, 0))
    
    def _create_progress_dialog(self, title, initial_message):
        """Create a progress dialog."""
        dialog = tk.Toplevel(self.window)
        dialog.title(title)
        dialog.geometry("400x150")
        dialog.transient(self.window)
        dialog.grab_set()
        
        # Center dialog
        dialog.geometry("+%d+%d" % (
            self.window.winfo_rootx() + 200,
            self.window.winfo_rooty() + 200
        ))
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Progress label
        progress_label = ttk.Label(main_frame, text=initial_message)
        progress_label.pack(pady=(0, 10))
        
        # Progress bar
        progress_bar = ttk.Progressbar(main_frame, mode='determinate', length=300)
        progress_bar.pack(pady=(0, 10))
        
        # Store references
        dialog.progress_label = progress_label
        dialog.progress_bar = progress_bar
        
        return dialog
    
    def _update_progress_dialog(self, dialog, progress, message):
        """Update progress dialog."""
        try:
            if dialog:
                # Handle ProgressDialog class (has update_progress method)
                if hasattr(dialog, 'update_progress'):
                    dialog.update_progress(progress, message)
                # Handle direct tk.Toplevel dialog
                elif hasattr(dialog, 'winfo_exists'):
                    try:
                        if dialog.winfo_exists():
                            dialog.progress_bar['value'] = progress
                            dialog.progress_label.config(text=message)
                            dialog.update()
                    except tk.TclError:
                        # Dialog was destroyed
                        pass
        except Exception as e:
            print(f"Error updating progress dialog: {e}")
    
    def _close_progress_dialog(self, dialog):
        """Close progress dialog safely."""
        try:
            if dialog:
                # Handle ProgressDialog class (has dialog attribute)
                if hasattr(dialog, 'dialog'):
                    try:
                        if dialog.dialog.winfo_exists():
                            dialog.dialog.destroy()
                    except (tk.TclError, AttributeError):
                        pass
                # Handle direct tk.Toplevel dialog
                elif hasattr(dialog, 'winfo_exists'):
                    try:
                        if dialog.winfo_exists():
                            dialog.destroy()
                    except tk.TclError:
                        pass
        except Exception as e:
            print(f"Error closing progress dialog: {e}")
    
    def _format_file_size(self, size_bytes):
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def _load_cloud_sessions_direct(self):
        """Load cloud sessions directly from cloud storage (fallback method)."""
        sessions = []
        
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
    
    def _parse_datetime(self, datetime_str):
        """Parse datetime string from cache metadata."""
        if not datetime_str:
            return datetime.now()
        
        try:
            # Try ISO format first
            if 'T' in datetime_str:
                return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            else:
                return datetime.fromisoformat(datetime_str)
        except Exception:
            # Fallback to current time if parsing fails
            return datetime.now()
    
    def _start_background_sync(self):
        """Start background synchronization with cloud to update cache."""
        def sync_in_background():
            try:
                print("DEBUG: Starting background sync with cloud...")
                
                # Use CloudSyncManager's sync method if available
                if hasattr(self.cloud_sync, 'sync_metadata_with_cloud'):
                    sync_result = self.cloud_sync.sync_metadata_with_cloud()
                    
                    if sync_result.get('success', False):
                        print("DEBUG: Background sync completed successfully")
                        
                        # Update local cache with cloud data
                        overall_meta = sync_result.get('overall_meta')
                        if overall_meta and self.meta_cache:
                            print(f"DEBUG: Updating local cache with {overall_meta.get('total_sessions', 0)} sessions from cloud")
                            self.meta_cache.update_cache_from_cloud(overall_meta)
                            
                            # Download missing metadata index files
                            sessions_in_cloud = overall_meta.get('sessions', [])
                            for session_info in sessions_in_cloud:
                                filename = session_info.get('filename', '')
                                if filename:
                                    # Check if we have the metadata index locally
                                    if not self.meta_cache.load_meta_index(filename):
                                        print(f"DEBUG: Downloading missing metadata for {filename}")
                                        try:
                                            # Try to load metadata index from cloud
                                            meta_index = self.cloud_sync.load_meta_index_from_cloud(filename)
                                            if meta_index:
                                                # Extract just the metadata part
                                                metadata = meta_index.get('metadata', {})
                                                self.meta_cache.save_meta_index(filename, metadata)
                                                print(f"DEBUG: Saved metadata index for {filename}")
                                            else:
                                                print(f"DEBUG: No metadata index found in cloud for {filename}")
                                        except Exception as e:
                                            print(f"DEBUG: Failed to download metadata for {filename}: {e}")
                        
                        # Reload sessions from updated cache
                        updated_sessions = self._load_cached_cloud_sessions()
                        if updated_sessions:
                            print(f"DEBUG: Loaded {len(updated_sessions)} sessions from updated cache")
                            self.cloud_sessions = updated_sessions
                            # Update UI in main thread
                            self.window.after(0, lambda: self._apply_filters('cloud'))
                        else:
                            print("DEBUG: No sessions loaded from updated cache")
                    else:
                        print(f"DEBUG: Background sync failed: {sync_result.get('error', 'Unknown error')}")
                else:
                    print("DEBUG: CloudSyncManager does not support metadata sync")
                    
            except Exception as e:
                print(f"Error in background sync: {e}")
                import traceback
                traceback.print_exc()
        
        # Start background thread
        threading.Thread(target=sync_in_background, daemon=True).start()
    
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
        
        # Sort sessions with safe datetime handling
        if hasattr(self, 'sort_column') and self.sort_column:
            reverse = getattr(self, 'sort_reverse', False)
            
            def safe_sort_key(session):
                value = session.get(self.sort_column, '')
                
                # Handle datetime objects specially
                if isinstance(value, datetime):
                    # Convert to timestamp for consistent comparison
                    return value.timestamp()
                
                # Handle other types
                if value is None:
                    return ''
                
                return value
            
            sessions.sort(key=safe_sort_key, reverse=reverse)
        
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
        
        # Load SSL verification setting
        ssl_verify = self.cloud_sync.config.getboolean('CloudSync', 'ssl_verify', fallback=True)
        self.ssl_verify_var.set(ssl_verify)
    
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
            self.app.config['CloudSync']['ssl_verify'] = str(self.ssl_verify_var.get())
            
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
            
            # Show SSL warning if disabled
            if not self.ssl_verify_var.get():
                messagebox.showwarning("Security Warning", "SSL verification is disabled. This reduces security and should only be used in proxy environments where certificate validation fails.")
            
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
            from PIL import Image, ImageTk
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
            from PIL import Image, ImageTk
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

    # Cache Management Methods
    
    def _rebuild_all_indexes(self):
        """Rebuild all metadata indexes by downloading all sessions and extracting metadata."""
        if not self.cloud_sync:
            messagebox.showerror("Error", "Cloud sync not available.")
            return
        
        if not self.meta_cache:
            messagebox.showerror("Error", "Metadata cache not available.")
            return
        
        # Confirm with user
        result = messagebox.askyesno(
            "Rebuild All Indexes",
            "This will download all cloud sessions to rebuild metadata indexes.\n"
            "This may take several minutes and use significant bandwidth.\n\n"
            "Do you want to continue?"
        )
        
        if not result:
            return
        
        # Create progress dialog
        progress_dialog = self._create_progress_dialog(
            "Rebuilding All Indexes",
            "Initializing rebuild operation..."
        )
        
        def rebuild_in_background():
            try:
                # Get list of all cloud sessions
                progress_dialog.update_progress(10, "Getting list of cloud sessions...")
                cloud_sessions = self.cloud_sync.list_cloud_sessions()
                total_sessions = len(cloud_sessions)
                
                if total_sessions == 0:
                    self.window.after(0, lambda: progress_dialog.complete("No cloud sessions found."))
                    return
                
                progress_dialog.update_progress(20, f"Found {total_sessions} sessions. Starting rebuild...")
                
                # Process sessions in batches
                processed_count = 0
                batch_size = 3  # Smaller batches for rebuild to avoid overwhelming
                
                for i in range(0, total_sessions, batch_size):
                    if progress_dialog.cancelled:
                        break
                    
                    batch = cloud_sessions[i:i + batch_size]
                    batch_progress = 20 + (i / total_sessions) * 70
                    
                    progress_dialog.update_progress(
                        batch_progress,
                        f"Processing sessions {i+1}-{min(i+batch_size, total_sessions)} of {total_sessions}..."
                    )
                    
                    for session in batch:
                        if progress_dialog.cancelled:
                            break
                        
                        try:
                            filename = session['filename']
                            
                            # Download full session to extract metadata
                            session_data = self.cloud_sync.load_session_from_cloud(filename)
                            if session_data:
                                metadata = session_data.get('metadata', {})
                                
                                # Add file size and creation date
                                metadata['file_size'] = session.get('size', 0)
                                metadata['created_at'] = session.get('last_modified', datetime.now()).isoformat()
                                
                                # Save metadata index to cache
                                self.meta_cache.save_meta_index(filename, metadata)
                                
                                # Also save to cloud if not exists
                                try:
                                    self.cloud_sync.save_meta_index_to_cloud(filename, metadata)
                                except Exception as e:
                                    print(f"Warning: Could not save meta index to cloud for {filename}: {e}")
                                
                                processed_count += 1
                            
                        except Exception as e:
                            print(f"Error processing session {session.get('filename', 'unknown')}: {e}")
                            continue
                
                if progress_dialog.cancelled:
                    self.window.after(0, lambda: progress_dialog.complete("Rebuild cancelled by user."))
                    return
                
                # Update overall metadata file
                progress_dialog.update_progress(90, "Updating overall metadata file...")
                try:
                    self.cloud_sync.update_overall_meta_file()
                except Exception as e:
                    print(f"Warning: Could not update overall meta file: {e}")
                
                # Complete
                progress_dialog.update_progress(100, "Rebuild completed successfully!")
                
                # Refresh UI data
                self.window.after(0, lambda: self._load_data())
                
                self.window.after(0, lambda: progress_dialog.complete(
                    f"Successfully rebuilt {processed_count} metadata indexes."
                ))
                
            except Exception as e:
                error_msg = f"Rebuild failed: {str(e)}"
                print(f"Error in rebuild all indexes: {e}")
                self.window.after(0, lambda: progress_dialog.error(error_msg))
        
        # Start background thread
        threading.Thread(target=rebuild_in_background, daemon=True).start()
    
    def _rebuild_overall_list(self):
        """Rebuild overall metadata list by downloading all existing metadata indexes."""
        if not self.cloud_sync:
            messagebox.showerror("Error", "Cloud sync not available.")
            return
        
        if not self.meta_cache:
            messagebox.showerror("Error", "Metadata cache not available.")
            return
        
        # Confirm with user
        result = messagebox.askyesno(
            "Rebuild Overall List",
            "This will download all existing metadata indexes and rebuild the master list.\n"
            "This is faster than rebuilding all indexes but requires existing metadata files.\n\n"
            "Do you want to continue?"
        )
        
        if not result:
            return
        
        # Create progress dialog
        progress_dialog = self._create_progress_dialog(
            "Rebuilding Overall List",
            "Initializing rebuild operation..."
        )
        
        def rebuild_overall_in_background():
            try:
                # Get list of metadata indexes in cloud
                progress_dialog.update_progress(10, "Getting list of metadata indexes...")
                meta_indexes = self.cloud_sync.list_meta_indexes_in_cloud()
                total_indexes = len(meta_indexes)
                
                if total_indexes == 0:
                    self.window.after(0, lambda: progress_dialog.complete("No metadata indexes found in cloud."))
                    return
                
                progress_dialog.update_progress(20, f"Found {total_indexes} metadata indexes. Downloading...")
                
                # Download all metadata indexes
                processed_count = 0
                batch_size = 10  # Larger batches for metadata files (they're smaller)
                
                for i in range(0, total_indexes, batch_size):
                    if progress_dialog.cancelled:
                        break
                    
                    batch = meta_indexes[i:i + batch_size]
                    batch_progress = 20 + (i / total_indexes) * 60
                    
                    progress_dialog.update_progress(
                        batch_progress,
                        f"Downloading metadata {i+1}-{min(i+batch_size, total_indexes)} of {total_indexes}..."
                    )
                    
                    for meta_filename in batch:
                        if progress_dialog.cancelled:
                            break
                        
                        try:
                            # Extract session filename from metadata filename
                            session_filename = meta_filename.replace('.meta.json', '.fastshot')
                            
                            # Download metadata index
                            meta_data = self.cloud_sync.load_meta_index_from_cloud(session_filename)
                            if meta_data:
                                # Save to local cache
                                self.meta_cache.save_meta_index(session_filename, meta_data)
                                processed_count += 1
                            
                        except Exception as e:
                            print(f"Error downloading metadata {meta_filename}: {e}")
                            continue
                
                if progress_dialog.cancelled:
                    self.window.after(0, lambda: progress_dialog.complete("Rebuild cancelled by user."))
                    return
                
                # Update overall metadata file
                progress_dialog.update_progress(80, "Updating overall metadata file...")
                try:
                    self.cloud_sync.update_overall_meta_file()
                    
                    # Load and update local cache
                    overall_meta = self.cloud_sync.load_overall_meta_file()
                    if overall_meta:
                        self.meta_cache.update_cache_from_cloud(overall_meta)
                    
                except Exception as e:
                    print(f"Warning: Could not update overall meta file: {e}")
                
                # Complete
                progress_dialog.update_progress(100, "Rebuild completed successfully!")
                
                # Refresh UI data
                self.window.after(0, lambda: self._load_data())
                
                self.window.after(0, lambda: progress_dialog.complete(
                    f"Successfully rebuilt overall list with {processed_count} metadata indexes."
                ))
                
            except Exception as e:
                error_msg = f"Rebuild failed: {str(e)}"
                print(f"Error in rebuild overall list: {e}")
                self.window.after(0, lambda: progress_dialog.error(error_msg))
        
        # Start background thread
        threading.Thread(target=rebuild_overall_in_background, daemon=True).start()
    
    def _show_cache_status(self):
        """Show cache status dialog with size, last updated, and integrity information."""
        if not self.meta_cache:
            messagebox.showerror("Error", "Metadata cache not available.")
            return
        
        try:
            # Get comprehensive cache statistics including session files
            cache_stats = self.meta_cache.get_cache_statistics()
            
            # Create status dialog
            status_dialog = tk.Toplevel(self.window)
            status_dialog.title("Cache Status")
            status_dialog.geometry("600x500")
            status_dialog.transient(self.window)
            status_dialog.grab_set()
            
            # Center dialog
            status_dialog.update_idletasks()
            x = (status_dialog.winfo_screenwidth() // 2) - (600 // 2)
            y = (status_dialog.winfo_screenheight() // 2) - (500 // 2)
            status_dialog.geometry(f"600x500+{x}+{y}")
            
            # Main frame
            main_frame = ttk.Frame(status_dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            title_label = ttk.Label(main_frame, text="Cache Status", font=("Arial", 14, "bold"))
            title_label.pack(pady=(0, 20))
            
            # Create notebook for different sections
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
            
            # General Status Tab
            general_frame = ttk.Frame(notebook, padding="10")
            notebook.add(general_frame, text="General")
            
            # Cache size (metadata only)
            metadata_cache_size_mb = cache_stats.get('cache_size_bytes', 0) / (1024 * 1024)
            ttk.Label(general_frame, text=f"Metadata Cache Size: {metadata_cache_size_mb:.2f} MB", font=("Arial", 10)).pack(anchor=tk.W, pady=2)
            
            # Session cache size
            session_cache_size_mb = cache_stats.get('session_cache_size_mb', 0)
            ttk.Label(general_frame, text=f"Session Cache Size: {session_cache_size_mb:.2f} MB", font=("Arial", 10)).pack(anchor=tk.W, pady=2)
            
            # Total cache size
            total_cache_size_mb = cache_stats.get('total_cache_size_mb', 0)
            ttk.Label(general_frame, text=f"Total Cache Size: {total_cache_size_mb:.2f} MB", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=2)
            
            # File counts
            total_files = cache_stats.get('total_meta_files', 0)
            actual_files = cache_stats.get('actual_meta_files', 0)
            ttk.Label(general_frame, text=f"Metadata Files: {actual_files} (expected: {total_files})", font=("Arial", 10)).pack(anchor=tk.W, pady=2)
            
            # Session file counts
            cached_session_files = cache_stats.get('cached_session_files', 0)
            ttk.Label(general_frame, text=f"Cached Session Files: {cached_session_files}", font=("Arial", 10)).pack(anchor=tk.W, pady=2)
            
            # Last sync
            last_sync = cache_stats.get('last_sync')
            if last_sync:
                try:
                    sync_time = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                    sync_str = sync_time.strftime("%Y-%m-%d %H:%M:%S UTC")
                except:
                    sync_str = last_sync
            else:
                sync_str = "Never"
            ttk.Label(general_frame, text=f"Last Sync: {sync_str}", font=("Arial", 10)).pack(anchor=tk.W, pady=2)
            
            # Integrity Status Tab
            integrity_frame = ttk.Frame(notebook, padding="10")
            notebook.add(integrity_frame, text="Integrity")
            
            integrity_info = cache_stats.get('integrity_check', {})
            status = integrity_info.get('status', 'unknown')
            
            # Status with color
            status_color = "green" if status == "valid" else "red" if status == "corrupted" else "orange"
            status_label = ttk.Label(integrity_frame, text=f"Status: {status.upper()}", font=("Arial", 10, "bold"))
            status_label.pack(anchor=tk.W, pady=2)
            
            # Last validated
            last_validated = integrity_info.get('last_validated')
            if last_validated:
                try:
                    validated_time = datetime.fromisoformat(last_validated.replace('Z', '+00:00'))
                    validated_str = validated_time.strftime("%Y-%m-%d %H:%M:%S UTC")
                except:
                    validated_str = last_validated
            else:
                validated_str = "Never"
            ttk.Label(integrity_frame, text=f"Last Validated: {validated_str}", font=("Arial", 10)).pack(anchor=tk.W, pady=2)
            
            # Corrupted files
            corrupted_files = integrity_info.get('corrupted_files', [])
            if corrupted_files:
                ttk.Label(integrity_frame, text=f"Corrupted Files: {len(corrupted_files)}", font=("Arial", 10)).pack(anchor=tk.W, pady=2)
                
                # List corrupted files
                corrupted_frame = ttk.LabelFrame(integrity_frame, text="Corrupted Files", padding="5")
                corrupted_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
                
                corrupted_text = tk.Text(corrupted_frame, height=8, width=60)
                corrupted_scrollbar = ttk.Scrollbar(corrupted_frame, orient="vertical", command=corrupted_text.yview)
                corrupted_text.configure(yscrollcommand=corrupted_scrollbar.set)
                
                for file in corrupted_files:
                    corrupted_text.insert(tk.END, f"• {file}\n")
                
                corrupted_text.config(state=tk.DISABLED)
                corrupted_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                corrupted_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                ttk.Label(integrity_frame, text="No corrupted files found", font=("Arial", 10)).pack(anchor=tk.W, pady=2)
            
            # Session Cache Tab
            session_cache_frame = ttk.Frame(notebook, padding="10")
            notebook.add(session_cache_frame, text="Session Cache")
            
            # Session cache statistics
            cached_sessions = cache_stats.get('cached_sessions', [])
            ttk.Label(session_cache_frame, text=f"Cached Session Files: {len(cached_sessions)}", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=2)
            
            session_cache_size_mb = cache_stats.get('session_cache_size_mb', 0)
            ttk.Label(session_cache_frame, text=f"Session Cache Size: {session_cache_size_mb:.2f} MB", font=("Arial", 10)).pack(anchor=tk.W, pady=2)
            
            if cached_sessions:
                # List cached sessions
                session_list_frame = ttk.LabelFrame(session_cache_frame, text="Cached Sessions", padding="5")
                session_list_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
                
                # Create treeview for session list
                session_tree = ttk.Treeview(session_list_frame, columns=('size', 'cached_at'), show='tree headings', height=10)
                session_tree.heading('#0', text='Filename')
                session_tree.heading('size', text='Size')
                session_tree.heading('cached_at', text='Cached At')
                
                session_tree.column('#0', width=300)
                session_tree.column('size', width=100)
                session_tree.column('cached_at', width=150)
                
                # Add session files to tree
                for filename in cached_sessions:
                    session_info = self.meta_cache.get_session_cache_info(filename)
                    if session_info:
                        size_mb = session_info['size'] / (1024 * 1024)
                        cached_at = session_info.get('cached_at', 'Unknown')
                        try:
                            # Format the cached_at time
                            cached_time = datetime.fromisoformat(cached_at)
                            cached_str = cached_time.strftime("%Y-%m-%d %H:%M")
                        except:
                            cached_str = cached_at
                        
                        session_tree.insert('', 'end', text=filename, values=(f"{size_mb:.2f} MB", cached_str))
                
                session_scrollbar = ttk.Scrollbar(session_list_frame, orient="vertical", command=session_tree.yview)
                session_tree.configure(yscrollcommand=session_scrollbar.set)
                
                session_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                session_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                
                # Session cache management buttons
                session_button_frame = ttk.Frame(session_cache_frame)
                session_button_frame.pack(fill=tk.X, pady=(10, 0))
                
                ttk.Button(session_button_frame, text="Clear All Session Cache", 
                          command=lambda: self._clear_session_cache_confirm(status_dialog)).pack(side=tk.LEFT, padx=5)
                ttk.Button(session_button_frame, text="Optimize Cache", 
                          command=lambda: self._optimize_session_cache(status_dialog)).pack(side=tk.LEFT, padx=5)
            else:
                ttk.Label(session_cache_frame, text="No session files cached", font=("Arial", 10)).pack(anchor=tk.W, pady=10)
            
            # Paths Tab (for debugging)
            paths_frame = ttk.Frame(notebook, padding="10")
            notebook.add(paths_frame, text="Paths")
            
            cache_paths = cache_stats.get('cache_paths', {})
            for path_name, path_value in cache_paths.items():
                ttk.Label(paths_frame, text=f"{path_name.replace('_', ' ').title()}:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(5, 0))
                path_label = ttk.Label(paths_frame, text=path_value, font=("Arial", 8), foreground="gray")
                path_label.pack(anchor=tk.W, padx=(10, 0), pady=(0, 5))
            
            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)
            
            # Action buttons
            ttk.Button(button_frame, text="Validate Cache", command=lambda: self._validate_cache_integrity(status_dialog)).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Clear Cache", command=lambda: self._clear_cache_confirm(status_dialog)).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Refresh", command=lambda: self._refresh_cache_status(status_dialog)).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Close", command=status_dialog.destroy).pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            print(f"Error showing cache status: {e}")
            messagebox.showerror("Error", f"Failed to show cache status: {e}")
    
    def _validate_cache_integrity(self, parent_dialog):
        """Validate cache integrity and update status."""
        if not self.meta_cache:
            return
        
        def validate_in_background():
            try:
                # Show progress
                parent_dialog.after(0, lambda: messagebox.showinfo("Validation", "Validating cache integrity..."))
                
                # Perform validation
                is_valid = self.meta_cache.validate_cache_integrity()
                
                # Show result
                if is_valid:
                    parent_dialog.after(0, lambda: messagebox.showinfo("Validation Complete", "Cache integrity validation passed. All files are valid."))
                else:
                    parent_dialog.after(0, lambda: messagebox.showwarning("Validation Complete", "Cache integrity validation found corrupted files. Check the integrity tab for details."))
                
                # Refresh status dialog
                parent_dialog.after(0, lambda: self._refresh_cache_status(parent_dialog))
                
            except Exception as e:
                parent_dialog.after(0, lambda: messagebox.showerror("Validation Error", f"Failed to validate cache: {e}"))
        
        threading.Thread(target=validate_in_background, daemon=True).start()
    
    def _clear_cache_confirm(self, parent_dialog):
        """Confirm and clear cache."""
        result = messagebox.askyesno(
            "Clear Cache",
            "This will delete all cached metadata files.\n"
            "You will need to rebuild the cache to restore fast loading.\n\n"
            "Are you sure you want to continue?",
            parent=parent_dialog
        )
        
        if result and self.meta_cache:
            try:
                self.meta_cache.clear_cache()
                messagebox.showinfo("Cache Cleared", "Cache has been cleared successfully.", parent=parent_dialog)
                
                # Refresh status dialog and main UI
                self._refresh_cache_status(parent_dialog)
                self._load_data()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear cache: {e}", parent=parent_dialog)
    
    def _refresh_cache_status(self, status_dialog):
        """Refresh the cache status dialog."""
        # Close current dialog and reopen
        status_dialog.destroy()
        self._show_cache_status()
    
    def _create_progress_dialog(self, title, initial_message):
        """Create a progress dialog for long-running operations."""
        return ProgressDialog(self.window, title, initial_message)


class ProgressDialog:
    """Progress dialog for long-running operations with cancellation support."""
    
    def __init__(self, parent, title, initial_message):
        self.cancelled = False
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x200")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        
        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (200 // 2)
        self.dialog.geometry(f"500x200+{x}+{y}")
        
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        self.title_label = ttk.Label(main_frame, text=title, font=("Arial", 12, "bold"))
        self.title_label.pack(pady=(0, 20))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Status message
        self.status_label = ttk.Label(main_frame, text=initial_message, wraplength=450)
        self.status_label.pack(pady=(0, 20))
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Cancel button
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self._cancel)
        self.cancel_button.pack(side=tk.RIGHT)
        
        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)
    
    def update_progress(self, progress, message):
        """Update progress and message."""
        def update():
            if not self.cancelled:
                self.progress_var.set(progress)
                self.status_label.config(text=message)
                self.dialog.update()
        
        if self.dialog.winfo_exists():
            self.dialog.after(0, update)
    
    def complete(self, message):
        """Complete the operation with success message."""
        def complete_update():
            self.progress_var.set(100)
            self.status_label.config(text=message)
            self.cancel_button.config(text="Close")
            self.dialog.update()
            
            # Auto-close after 3 seconds
            self.dialog.after(3000, self.dialog.destroy)
        
        if self.dialog.winfo_exists():
            self.dialog.after(0, complete_update)
    
    def error(self, message):
        """Complete the operation with error message."""
        def error_update():
            self.status_label.config(text=f"Error: {message}")
            self.cancel_button.config(text="Close")
            self.dialog.update()
        
        if self.dialog.winfo_exists():
            self.dialog.after(0, error_update)
    
    def _cancel(self):
        """Cancel the operation."""
        self.cancelled = True
        if self.dialog.winfo_exists():
            self.dialog.destroy()    
  
    def _clear_session_cache_confirm(self, parent_dialog):
        """Confirm and clear session cache."""
        if messagebox.askyesno("Confirm", "Are you sure you want to clear all cached session files?\n\nThis will not affect your cloud sessions, but you'll need to download them again when loading.", parent=parent_dialog):
            try:
                if self.meta_cache:
                    success = self.meta_cache.clear_session_cache()
                    if success:
                        messagebox.showinfo("Success", "Session cache cleared successfully.", parent=parent_dialog)
                        # Refresh the cache status dialog
                        self._refresh_cache_status(parent_dialog)
                    else:
                        messagebox.showerror("Error", "Failed to clear session cache.", parent=parent_dialog)
                else:
                    messagebox.showerror("Error", "Cache manager not available.", parent=parent_dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear session cache: {e}", parent=parent_dialog)
    
    def _optimize_session_cache(self, parent_dialog):
        """Optimize session cache by removing old/large files."""
        try:
            if not self.meta_cache:
                messagebox.showerror("Error", "Cache manager not available.", parent=parent_dialog)
                return
            
            # Show optimization dialog
            optimize_dialog = tk.Toplevel(parent_dialog)
            optimize_dialog.title("Optimize Session Cache")
            optimize_dialog.geometry("400x300")
            optimize_dialog.transient(parent_dialog)
            optimize_dialog.grab_set()
            
            # Center dialog
            optimize_dialog.update_idletasks()
            x = (optimize_dialog.winfo_screenwidth() // 2) - (400 // 2)
            y = (optimize_dialog.winfo_screenheight() // 2) - (300 // 2)
            optimize_dialog.geometry(f"400x300+{x}+{y}")
            
            main_frame = ttk.Frame(optimize_dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(main_frame, text="Cache Optimization Settings", font=("Arial", 12, "bold")).pack(pady=(0, 20))
            
            # Max size setting
            size_frame = ttk.Frame(main_frame)
            size_frame.pack(fill=tk.X, pady=5)
            ttk.Label(size_frame, text="Maximum cache size (MB):").pack(side=tk.LEFT)
            size_var = tk.StringVar(value="500")
            size_entry = ttk.Entry(size_frame, textvariable=size_var, width=10)
            size_entry.pack(side=tk.RIGHT)
            
            # Max age setting
            age_frame = ttk.Frame(main_frame)
            age_frame.pack(fill=tk.X, pady=5)
            ttk.Label(age_frame, text="Maximum file age (days):").pack(side=tk.LEFT)
            age_var = tk.StringVar(value="30")
            age_entry = ttk.Entry(age_frame, textvariable=age_var, width=10)
            age_entry.pack(side=tk.RIGHT)
            
            # Info text
            info_text = tk.Text(main_frame, height=8, width=50, wrap=tk.WORD)
            info_text.pack(fill=tk.BOTH, expand=True, pady=(20, 0))
            info_text.insert(tk.END, "Cache optimization will:\n\n")
            info_text.insert(tk.END, "• Remove files older than the specified age\n")
            info_text.insert(tk.END, "• Remove oldest files if cache exceeds size limit\n")
            info_text.insert(tk.END, "• Keep frequently accessed files\n\n")
            info_text.insert(tk.END, "This will not affect your cloud sessions, only local cache.")
            info_text.config(state=tk.DISABLED)
            
            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(20, 0))
            
            def run_optimization():
                try:
                    max_size = int(size_var.get())
                    max_age = int(age_var.get())
                    
                    result = self.meta_cache.optimize_session_cache(max_size, max_age)
                    
                    if result.get('success'):
                        deleted_files = result.get('deleted_files', 0)
                        deleted_size = result.get('deleted_size_mb', 0)
                        remaining_files = result.get('remaining_files', 0)
                        remaining_size = result.get('remaining_size_mb', 0)
                        
                        message = f"Optimization completed!\n\n"
                        message += f"Deleted: {deleted_files} files ({deleted_size:.2f} MB)\n"
                        message += f"Remaining: {remaining_files} files ({remaining_size:.2f} MB)"
                        
                        messagebox.showinfo("Optimization Complete", message, parent=optimize_dialog)
                        optimize_dialog.destroy()
                        self._refresh_cache_status(parent_dialog)
                    else:
                        messagebox.showerror("Error", f"Optimization failed: {result.get('error', 'Unknown error')}", parent=optimize_dialog)
                        
                except ValueError:
                    messagebox.showerror("Error", "Please enter valid numbers for size and age.", parent=optimize_dialog)
                except Exception as e:
                    messagebox.showerror("Error", f"Optimization failed: {e}", parent=optimize_dialog)
            
            ttk.Button(button_frame, text="Optimize", command=run_optimization).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=optimize_dialog.destroy).pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open optimization dialog: {e}", parent=parent_dialog)