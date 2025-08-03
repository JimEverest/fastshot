# fastshot/notes_manager.py

import json
import os
import re
import string
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any


class NotesManager:
    """Core business logic for note operations with CRUD functionality."""
    
    def __init__(self, app):
        """Initialize NotesManager with app context."""
        self.app = app
        self.notes_dir = Path.home() / ".fastshot" / "quicknotes"
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize cloud sync manager if available
        self.cloud_sync = getattr(app, 'cloud_sync', None)
        
        # Search history management
        self.search_history_file = self.notes_dir / "search_history.json"
        self.max_search_history = 50  # Maximum number of searches to remember
        self._load_search_history()
        
    def create_note(self, title: str, content: str = "", tags: List[str] = None) -> str:
        """
        Create a new note with generated short code.
        
        Args:
            title: Note title
            content: Note content (default empty)
            tags: List of tags (default empty list)
            
        Returns:
            str: Note ID if successful, None if failed
        """
        try:
            # Validate and sanitize input
            title = self._sanitize_text(title)
            content = self._sanitize_text(content)
            
            if not title.strip():
                raise ValueError("Note title cannot be empty")
            
            # Generate unique short code and note ID
            short_code = self._generate_short_code()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            note_id = f"{timestamp}_{short_code}"
            
            # Create note data structure
            note_data = {
                "id": note_id,
                "title": title.strip(),
                "content": content,
                "short_code": short_code,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "tags": tags or [],
                "metadata": {
                    "word_count": len(content.split()) if content else 0,
                    "char_count": len(content),
                    "last_editor": "user"
                }
            }
            
            # Validate note data
            if not self._validate_note_data(note_data):
                raise ValueError("Invalid note data structure")
            
            # Save note locally first (always works)
            local_path = self.notes_dir / f"{note_id}.json"
            with open(local_path, 'w', encoding='utf-8') as f:
                json.dump(note_data, f, indent=2, ensure_ascii=False)
            
            # Try to sync to cloud if available (with error recovery)
            self._sync_note_to_cloud(note_data, operation="create")
            
            print(f"Note created successfully: {note_id}")
            return note_id
            
        except Exception as e:
            print(f"Error creating note: {e}")
            return None
    
    def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a note by ID.
        
        Args:
            note_id: Note identifier
            
        Returns:
            Dict containing note data, None if not found
        """
        try:
            # Validate note ID format
            if not self._validate_note_id(note_id):
                raise ValueError(f"Invalid note ID format: {note_id}")
            
            # Try to load from local storage first
            local_path = self.notes_dir / f"{note_id}.json"
            if local_path.exists():
                with open(local_path, 'r', encoding='utf-8') as f:
                    note_data = json.load(f)
                
                # Validate loaded data
                if self._validate_note_data(note_data):
                    return note_data
                else:
                    print(f"Warning: Invalid note data structure for {note_id}")
                    return None
            
            print(f"Note not found: {note_id}")
            return None
            
        except Exception as e:
            print(f"Error retrieving note {note_id}: {e}")
            return None
    
    def update_note(self, note_id: str, title: str = None, content: str = None, tags: List[str] = None) -> bool:
        """
        Update an existing note.
        
        Args:
            note_id: Note identifier
            title: New title (optional)
            content: New content (optional)
            tags: New tags list (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get existing note
            note_data = self.get_note(note_id)
            if not note_data:
                print(f"Cannot update: note not found {note_id}")
                return False
            
            # Update fields if provided
            if title is not None:
                title = self._sanitize_text(title)
                if not title.strip():
                    raise ValueError("Note title cannot be empty")
                note_data["title"] = title.strip()
            
            if content is not None:
                content = self._sanitize_text(content)
                note_data["content"] = content
                # Update metadata
                note_data["metadata"]["word_count"] = len(content.split()) if content else 0
                note_data["metadata"]["char_count"] = len(content)
            
            if tags is not None:
                note_data["tags"] = tags
            
            # Update timestamp
            note_data["updated_at"] = datetime.now().isoformat()
            
            # Validate updated data
            if not self._validate_note_data(note_data):
                raise ValueError("Invalid note data structure after update")
            
            # Save updated note locally first
            local_path = self.notes_dir / f"{note_id}.json"
            with open(local_path, 'w', encoding='utf-8') as f:
                json.dump(note_data, f, indent=2, ensure_ascii=False)
            
            # Try to sync to cloud if available (with error recovery)
            self._sync_note_to_cloud(note_data, operation="update")
            
            print(f"Note updated successfully: {note_id}")
            return True
            
        except Exception as e:
            print(f"Error updating note {note_id}: {e}")
            return False
    
    def delete_note(self, note_id: str) -> bool:
        """
        Delete a note by ID.
        
        Args:
            note_id: Note identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate note ID format
            if not self._validate_note_id(note_id):
                raise ValueError(f"Invalid note ID format: {note_id}")
            
            # Check if note exists and get note data for cloud sync
            local_path = self.notes_dir / f"{note_id}.json"
            if not local_path.exists():
                print(f"Cannot delete: note not found {note_id}")
                return False
            
            # Get note data before deletion for cloud sync
            note_data = self.get_note(note_id)
            
            # Delete local file first
            local_path.unlink()
            
            # Try to sync deletion to cloud if available (with error recovery)
            if note_data:
                self._sync_note_to_cloud(note_data, operation="delete")
            
            print(f"Note deleted successfully: {note_id}")
            return True
            
        except Exception as e:
            print(f"Error deleting note {note_id}: {e}")
            return False
    
    def list_notes(self, page: int = 1, per_page: int = 15) -> Dict[str, Any]:
        """
        List notes with pagination.
        
        Args:
            page: Page number (1-based)
            per_page: Items per page
            
        Returns:
            Dict containing notes list and pagination info
        """
        try:
            # Performance optimization: Use cached index if available (same as search_notes)
            if hasattr(self.app, 'notes_cache'):
                cache_manager = self.app.notes_cache
                cached_index = cache_manager.get_cached_index()
                cached_notes = cached_index.get("notes", [])
                
                # If cache has notes, use them for the list
                if cached_notes:
                    print(f"DEBUG: Using cached index with {len(cached_notes)} notes for list_notes")
                    notes = cached_notes.copy()
                else:
                    print("DEBUG: Cache is empty, falling back to local files")
                    notes = self._load_notes_from_local_files()
            else:
                print("DEBUG: No cache manager available, using local files only")
                notes = self._load_notes_from_local_files()
            
            # Sort by updated_at (most recent first)
            notes.sort(key=lambda x: x["updated_at"], reverse=True)
            
            # Calculate pagination
            total_notes = len(notes)
            total_pages = (total_notes + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            
            # Get page data
            page_notes = notes[start_idx:end_idx]
            
            return {
                "notes": page_notes,
                "pagination": {
                    "current_page": page,
                    "per_page": per_page,
                    "total_notes": total_notes,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
            
        except Exception as e:
            print(f"Error listing notes: {e}")
            return {
                "notes": [],
                "pagination": {
                    "current_page": 1,
                    "per_page": per_page,
                    "total_notes": 0,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False
                }
            }    

    def search_notes(self, query: str, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Search notes by title and short code using fuzzy matching with performance optimizations.
        
        Args:
            query: Search query
            use_cache: Whether to use cached index for search (default True)
            
        Returns:
            List of matching notes with search metadata
        """
        try:
            if not query.strip():
                return []
            
            query = query.lower().strip()
            
            # Add to search history
            self.add_to_search_history(query)
            
            # Performance optimization: Use cached index if available
            if use_cache and hasattr(self.app, 'notes_cache'):
                cache_manager = self.app.notes_cache
                cached_index = cache_manager.get_cached_index()
                all_notes = cached_index.get("notes", [])
                
                # If cache is empty or invalid, fall back to local files
                if not all_notes:
                    all_notes = self.list_notes(page=1, per_page=10000)["notes"]
            else:
                # Get all notes from local files
                all_notes = self.list_notes(page=1, per_page=10000)["notes"]
            
            # Search and score matches with enhanced ranking
            matches = []
            query_words = query.split()
            
            for note in all_notes:
                score = 0
                match_details = {
                    "title_matches": [],
                    "short_code_matches": [],
                    "tag_matches": [],
                    "match_type": []
                }
                
                # Short code matching (highest priority)
                short_code = note.get("short_code", "")
                if query.upper() == short_code:
                    score += 100
                    match_details["short_code_matches"].append({"text": short_code, "type": "exact"})
                    match_details["match_type"].append("short_code_exact")
                elif query.upper() in short_code:
                    score += 50
                    match_details["short_code_matches"].append({"text": short_code, "type": "partial"})
                    match_details["match_type"].append("short_code_partial")
                
                # Title matching with word-level scoring
                title = note.get("title", "")
                title_lower = title.lower()
                
                # Exact title match
                if query == title_lower:
                    score += 80
                    match_details["title_matches"].append({"text": title, "type": "exact"})
                    match_details["match_type"].append("title_exact")
                # Phrase match in title
                elif query in title_lower:
                    score += 40
                    match_details["title_matches"].append({"text": title, "type": "phrase"})
                    match_details["match_type"].append("title_phrase")
                else:
                    # Word-level matching
                    word_matches = 0
                    for word in query_words:
                        if word in title_lower:
                            word_matches += 1
                            match_details["title_matches"].append({"text": word, "type": "word"})
                    
                    if word_matches > 0:
                        # Score based on percentage of words matched
                        word_score = (word_matches / len(query_words)) * 30
                        score += word_score
                        match_details["match_type"].append("title_words")
                    
                    # Fuzzy matching as fallback
                    elif self._fuzzy_match(query, title_lower):
                        score += 15
                        match_details["title_matches"].append({"text": title, "type": "fuzzy"})
                        match_details["match_type"].append("title_fuzzy")
                
                # Tag matching
                tags = note.get("tags", [])
                for tag in tags:
                    tag_lower = tag.lower()
                    if query in tag_lower:
                        score += 25
                        match_details["tag_matches"].append({"text": tag, "type": "partial"})
                        match_details["match_type"].append("tag_partial")
                    else:
                        # Word-level tag matching
                        for word in query_words:
                            if word in tag_lower:
                                score += 10
                                match_details["tag_matches"].append({"text": tag, "type": "word"})
                                match_details["match_type"].append("tag_word")
                                break
                
                # Boost score for recent notes (recency bonus)
                try:
                    updated_at = note.get("updated_at", "")
                    if updated_at:
                        updated_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                        now = datetime.now(timezone.utc)
                        days_old = (now - updated_time).days
                        
                        # Boost recent notes (within 7 days)
                        if days_old <= 7:
                            recency_bonus = max(0, 10 - days_old)
                            score += recency_bonus
                except Exception:
                    pass  # Skip recency bonus if date parsing fails
                
                if score > 0:
                    note_match = note.copy()
                    note_match["search_score"] = score
                    note_match["search_details"] = match_details
                    matches.append(note_match)
            
            # Sort by score (highest first), then by updated_at for ties
            matches.sort(key=lambda x: (x["search_score"], x.get("updated_at", "")), reverse=True)
            
            # Update search history with result count
            self.add_to_search_history(query, len(matches))
            
            return matches
            
        except Exception as e:
            print(f"Error searching notes: {e}")
            return []
    
    def generate_short_code(self) -> str:
        """
        Generate a unique 4-character alphanumeric short code.
        
        Returns:
            str: Unique short code
        """
        return self._generate_short_code()
    
    def get_public_url(self, note_id: str) -> Optional[str]:
        """
        Get public URL for a note (placeholder for cloud sync integration).
        
        Args:
            note_id: Note identifier
            
        Returns:
            str: Public URL if available, None otherwise
        """
        # This will be implemented in task 3 when cloud sync is added
        print(f"Public URL generation not yet implemented for note: {note_id}")
        return None
    
    def _generate_short_code(self) -> str:
        """Generate a unique 4-character alphanumeric code."""
        # Use uppercase letters and digits for better readability
        chars = string.ascii_uppercase + string.digits
        
        # Generate codes until we find a unique one
        max_attempts = 100
        for _ in range(max_attempts):
            code = ''.join(random.choices(chars, k=4))
            
            # Check if code is already in use
            if not self._is_short_code_used(code):
                return code
        
        # Fallback: use timestamp-based code if all random attempts fail
        timestamp = datetime.now().strftime("%M%S")
        return f"N{timestamp[0:3]}"
    
    def _is_short_code_used(self, short_code: str) -> bool:
        """Check if a short code is already in use."""
        try:
            note_files = list(self.notes_dir.glob("*.json"))
            
            for note_file in note_files:
                try:
                    with open(note_file, 'r', encoding='utf-8') as f:
                        note_data = json.load(f)
                    
                    if note_data.get("short_code") == short_code:
                        return True
                except Exception:
                    continue
            
            return False
            
        except Exception:
            return False
    
    def _sanitize_text(self, text: str) -> str:
        """Sanitize text input by removing dangerous characters."""
        if not isinstance(text, str):
            return ""
        
        # Remove null bytes and control characters except newlines and tabs
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Limit length to prevent excessive memory usage
        max_length = 10000  # 10KB limit for content
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized
    
    def _validate_note_data(self, note_data: Dict[str, Any]) -> bool:
        """Validate note data structure."""
        try:
            required_fields = ["id", "title", "content", "short_code", "created_at", "updated_at", "tags", "metadata"]
            
            # Check required fields exist
            for field in required_fields:
                if field not in note_data:
                    print(f"Missing required field: {field}")
                    return False
            
            # Validate field types
            if not isinstance(note_data["title"], str) or not note_data["title"].strip():
                print("Invalid title: must be non-empty string")
                return False
            
            if not isinstance(note_data["content"], str):
                print("Invalid content: must be string")
                return False
            
            if not isinstance(note_data["short_code"], str) or len(note_data["short_code"]) != 4:
                print("Invalid short_code: must be 4-character string")
                return False
            
            if not isinstance(note_data["tags"], list):
                print("Invalid tags: must be list")
                return False
            
            if not isinstance(note_data["metadata"], dict):
                print("Invalid metadata: must be dict")
                return False
            
            # Validate note ID format
            if not self._validate_note_id(note_data["id"]):
                print(f"Invalid note ID format: {note_data['id']}")
                return False
            
            # Validate timestamps
            try:
                datetime.fromisoformat(note_data["created_at"])
                datetime.fromisoformat(note_data["updated_at"])
            except ValueError:
                print("Invalid timestamp format")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating note data: {e}")
            return False
    
    def _validate_note_id(self, note_id: str) -> bool:
        """Validate note ID format (YYYYMMDD_HHMMSS_XXXX)."""
        if not isinstance(note_id, str):
            return False
        
        # Expected format: 20250801_123456_ABCD
        pattern = r'^\d{8}_\d{6}_[A-Z0-9]{4}$'
        return bool(re.match(pattern, note_id))
    
    def _load_notes_from_local_files(self) -> List[Dict[str, Any]]:
        """Load notes from local files (fallback when cache is not available)."""
        notes = []
        try:
            # Get all note files
            note_files = list(self.notes_dir.glob("*.json"))
            
            # Load and validate notes
            for note_file in note_files:
                try:
                    with open(note_file, 'r', encoding='utf-8') as f:
                        note_data = json.load(f)
                    
                    if self._validate_note_data(note_data):
                        # Extract essential info for listing
                        note_info = {
                            "id": note_data["id"],
                            "title": note_data["title"],
                            "short_code": note_data["short_code"],
                            "created_at": note_data["created_at"],
                            "updated_at": note_data["updated_at"],
                            "tags": note_data["tags"],
                            "word_count": note_data["metadata"]["word_count"]
                        }
                        notes.append(note_info)
                except Exception as e:
                    print(f"Error loading note {note_file.name}: {e}")
                    continue
        except Exception as e:
            print(f"Error loading notes from local files: {e}")
        
        return notes
    
    def _fuzzy_match(self, query: str, text: str) -> bool:
        """Simple fuzzy matching for search."""
        # Simple implementation: check if most characters of query are in text
        if len(query) <= 2:
            return query in text
        
        # For longer queries, check if at least 70% of characters match
        matches = sum(1 for char in query if char in text)
        return matches >= len(query) * 0.7
    
    def _load_search_history(self):
        """Load search history from file."""
        try:
            if self.search_history_file.exists():
                with open(self.search_history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.search_history = data.get("searches", [])
            else:
                self.search_history = []
        except Exception as e:
            print(f"Error loading search history: {e}")
            self.search_history = []
    
    def _save_search_history(self):
        """Save search history to file."""
        try:
            history_data = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "searches": self.search_history
            }
            with open(self.search_history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving search history: {e}")
    
    def add_to_search_history(self, query: str, result_count: int = 0):
        """Add a search query to history."""
        if not query.strip():
            return
        
        query = query.strip()
        
        # Remove existing entry if it exists
        self.search_history = [h for h in self.search_history if h.get("query") != query]
        
        # Add new entry at the beginning
        search_entry = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "result_count": result_count
        }
        self.search_history.insert(0, search_entry)
        
        # Limit history size
        if len(self.search_history) > self.max_search_history:
            self.search_history = self.search_history[:self.max_search_history]
        
        # Save to file
        self._save_search_history()
    
    def get_search_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent search history."""
        return self.search_history[:limit]
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status information for debugging."""
        try:
            status = {
                "local_notes_count": 0,
                "cached_notes_count": 0,
                "cache_available": False,
                "cloud_sync_available": bool(self.cloud_sync),
                "sync_health": "unknown",
                "last_error": None
            }
            
            # Count local notes
            try:
                local_notes = self._load_notes_from_local_files()
                status["local_notes_count"] = len(local_notes)
            except Exception as e:
                status["last_error"] = f"Error counting local notes: {e}"
            
            # Check cache status
            if hasattr(self.app, 'notes_cache'):
                status["cache_available"] = True
                try:
                    cache_manager = self.app.notes_cache
                    cached_index = cache_manager.get_cached_index()
                    status["cached_notes_count"] = len(cached_index.get("notes", []))
                    
                    # Check if cache is valid
                    if cache_manager.validate_cache():
                        status["sync_health"] = "healthy"
                    else:
                        status["sync_health"] = "cache_invalid"
                        status["last_error"] = "Cache validation failed"
                        
                except Exception as e:
                    status["sync_health"] = "cache_error"
                    status["last_error"] = f"Cache error: {e}"
            
            # Test cloud connectivity if available
            if self.cloud_sync:
                try:
                    # Simple test - try to list notes (doesn't download)
                    cloud_notes = self.cloud_sync.list_notes_in_cloud()
                    if isinstance(cloud_notes, list):
                        status["cloud_notes_count"] = len(cloud_notes)
                        if status["sync_health"] == "healthy":
                            status["sync_health"] = "healthy"
                    else:
                        status["sync_health"] = "cloud_error"
                        status["last_error"] = "Cloud connectivity test failed"
                except Exception as e:
                    status["sync_health"] = "failed"
                    status["last_error"] = f"Cloud sync error: {e}"
            
            return status
            
        except Exception as e:
            return {
                "error": f"Failed to get sync status: {e}",
                "sync_health": "error"
            }
    
    def clear_search_history(self):
        """Clear all search history."""
        self.search_history = []
        self._save_search_history()
    
    def get_search_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """Get search suggestions based on history and partial query."""
        if not partial_query.strip():
            # Return recent searches if no partial query
            return [h["query"] for h in self.search_history[:limit]]
        
        partial_lower = partial_query.lower()
        suggestions = []
        
        # Find matching queries from history
        for entry in self.search_history:
            query = entry["query"]
            if partial_lower in query.lower() and query not in suggestions:
                suggestions.append(query)
                if len(suggestions) >= limit:
                    break
        
        return suggestions
    
    def _sync_note_to_cloud(self, note_data: Dict[str, Any], operation: str = "create") -> bool:
        """
        Sync note to cloud with error handling and recovery.
        
        Args:
            note_data: Note data to sync
            operation: Operation type ("create", "update", "delete")
            
        Returns:
            bool: True if successful, False if failed (but local operation still succeeded)
        """
        if not self.cloud_sync:
            # Cloud sync not available - graceful degradation
            print(f"Cloud sync not available for {operation} operation on note {note_data.get('id', 'unknown')}")
            return False
        
        try:
            # Attempt cloud sync based on operation
            if operation == "create" or operation == "update":
                success = self.cloud_sync.save_note_to_cloud(note_data)
                if success:
                    # Update overall index
                    self.cloud_sync.update_notes_overall_index()
                    print(f"Note {operation} synced to cloud: {note_data['id']}")
                    return True
                else:
                    print(f"Failed to sync note {operation} to cloud: {note_data['id']}")
                    return False
            
            elif operation == "delete":
                success = self.cloud_sync.delete_note_from_cloud(note_data['id'])
                if success:
                    # Update overall index
                    self.cloud_sync.update_notes_overall_index()
                    print(f"Note deletion synced to cloud: {note_data['id']}")
                    return True
                else:
                    print(f"Failed to sync note deletion to cloud: {note_data['id']}")
                    return False
            
        except Exception as e:
            # Network or other cloud sync errors - log but don't fail local operation
            print(f"Cloud sync error during {operation} for note {note_data.get('id', 'unknown')}: {e}")
            
            # Store failed sync for retry later (could be implemented)
            self._store_failed_sync(note_data, operation, str(e))
            
            return False
    
    def _store_failed_sync(self, note_data: Dict[str, Any], operation: str, error: str):
        """
        Store failed sync operations for later retry.
        
        Args:
            note_data: Note data that failed to sync
            operation: Operation type
            error: Error message
        """
        try:
            failed_syncs_file = self.notes_dir / "failed_syncs.json"
            
            # Load existing failed syncs
            failed_syncs = []
            if failed_syncs_file.exists():
                try:
                    with open(failed_syncs_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        failed_syncs = data.get("failed_syncs", [])
                except Exception:
                    failed_syncs = []
            
            # Add new failed sync
            failed_sync = {
                "note_id": note_data.get("id", "unknown"),
                "operation": operation,
                "error": error,
                "timestamp": datetime.now().isoformat(),
                "note_data": note_data,
                "retry_count": 0
            }
            
            failed_syncs.append(failed_sync)
            
            # Limit failed syncs to prevent unbounded growth
            if len(failed_syncs) > 100:
                failed_syncs = failed_syncs[-100:]
            
            # Save failed syncs
            failed_syncs_data = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "failed_syncs": failed_syncs
            }
            
            with open(failed_syncs_file, 'w', encoding='utf-8') as f:
                json.dump(failed_syncs_data, f, indent=2, ensure_ascii=False)
            
            print(f"Stored failed sync for later retry: {note_data.get('id', 'unknown')}")
            
        except Exception as e:
            print(f"Error storing failed sync: {e}")
    
    def retry_failed_syncs(self) -> Dict[str, Any]:
        """
        Retry failed sync operations.
        
        Returns:
            Dict with retry results
        """
        try:
            failed_syncs_file = self.notes_dir / "failed_syncs.json"
            
            if not failed_syncs_file.exists():
                return {"retried": 0, "succeeded": 0, "failed": 0}
            
            # Load failed syncs
            with open(failed_syncs_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                failed_syncs = data.get("failed_syncs", [])
            
            if not failed_syncs:
                return {"retried": 0, "succeeded": 0, "failed": 0}
            
            retried = 0
            succeeded = 0
            still_failed = []
            
            for failed_sync in failed_syncs:
                # Skip if too many retries
                if failed_sync.get("retry_count", 0) >= 3:
                    still_failed.append(failed_sync)
                    continue
                
                retried += 1
                note_data = failed_sync["note_data"]
                operation = failed_sync["operation"]
                
                # Attempt retry
                success = self._sync_note_to_cloud(note_data, operation)
                
                if success:
                    succeeded += 1
                    print(f"Retry successful for {operation} on note {note_data.get('id', 'unknown')}")
                else:
                    # Increment retry count and keep for next attempt
                    failed_sync["retry_count"] = failed_sync.get("retry_count", 0) + 1
                    failed_sync["last_retry"] = datetime.now().isoformat()
                    still_failed.append(failed_sync)
            
            # Update failed syncs file with remaining failures
            if still_failed:
                failed_syncs_data = {
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat(),
                    "failed_syncs": still_failed
                }
                
                with open(failed_syncs_file, 'w', encoding='utf-8') as f:
                    json.dump(failed_syncs_data, f, indent=2, ensure_ascii=False)
            else:
                # No more failed syncs, remove file
                failed_syncs_file.unlink()
            
            failed_count = len(still_failed)
            
            print(f"Sync retry completed: {retried} retried, {succeeded} succeeded, {failed_count} still failed")
            
            return {
                "retried": retried,
                "succeeded": succeeded,
                "failed": failed_count,
                "remaining_failures": still_failed
            }
            
        except Exception as e:
            print(f"Error retrying failed syncs: {e}")
            return {"retried": 0, "succeeded": 0, "failed": 0, "error": str(e)}
    
    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get current sync status and health information.
        
        Returns:
            Dict with sync status information
        """
        try:
            status = {
                "cloud_sync_available": self.cloud_sync is not None,
                "cloud_sync_enabled": False,
                "last_sync_attempt": None,
                "failed_syncs_count": 0,
                "sync_health": "unknown"
            }
            
            if self.cloud_sync:
                # Check if cloud sync is enabled
                status["cloud_sync_enabled"] = getattr(self.cloud_sync, 'cloud_sync_enabled', False)
                
                # Test cloud connectivity
                try:
                    # Simple connectivity test
                    test_result = self.cloud_sync.load_notes_overall_index()
                    if test_result is not None:
                        status["sync_health"] = "healthy"
                        status["last_sync_attempt"] = datetime.now().isoformat()
                    else:
                        status["sync_health"] = "degraded"
                except Exception as e:
                    status["sync_health"] = "failed"
                    status["last_error"] = str(e)
            
            # Check for failed syncs
            failed_syncs_file = self.notes_dir / "failed_syncs.json"
            if failed_syncs_file.exists():
                try:
                    with open(failed_syncs_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        failed_syncs = data.get("failed_syncs", [])
                        status["failed_syncs_count"] = len(failed_syncs)
                except Exception:
                    pass
            
            return status
            
        except Exception as e:
            return {
                "cloud_sync_available": False,
                "error": str(e),
                "sync_health": "error"
            }