# fastshot/session_manager.py

import json
import os
import pickle
import base64
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont
import io
import math

class ThumbnailCreator:
    """Creates thumbnail collages from multiple images."""
    
    @staticmethod
    def calculate_grid_layout(num_images):
        """Calculate optimal grid layout for given number of images."""
        if num_images <= 0:
            return 1, 1
        
        # Target aspect ratio is 4:3
        target_ratio = 4 / 3
        
        # Try different grid configurations
        best_ratio_diff = float('inf')
        best_cols, best_rows = 1, 1
        
        for cols in range(1, num_images + 1):
            rows = math.ceil(num_images / cols)
            current_ratio = cols / rows
            ratio_diff = abs(current_ratio - target_ratio)
            
            if ratio_diff < best_ratio_diff:
                best_ratio_diff = ratio_diff
                best_cols, best_rows = cols, rows
        
        return best_cols, best_rows
    
    @staticmethod
    def create_thumbnail_collage(images, max_thumb_size=100):
        """Create a collage of thumbnails from multiple images."""
        if not images:
            return None
        
        num_images = len(images)
        cols, rows = ThumbnailCreator.calculate_grid_layout(num_images)
        
        # Create thumbnails for each image
        thumbnails = []
        for img in images:
            # Calculate thumbnail size maintaining aspect ratio
            img_width, img_height = img.size
            
            if img_width > img_height:
                thumb_width = max_thumb_size
                thumb_height = int((img_height / img_width) * max_thumb_size)
            else:
                thumb_height = max_thumb_size
                thumb_width = int((img_width / img_height) * max_thumb_size)
            
            thumbnail = img.resize((thumb_width, thumb_height), Image.LANCZOS)
            thumbnails.append(thumbnail)
        
        # Calculate collage dimensions
        cell_width = max_thumb_size
        cell_height = max_thumb_size
        collage_width = cols * cell_width
        collage_height = rows * cell_height
        
        # Create collage
        collage = Image.new('RGB', (collage_width, collage_height), (240, 240, 240))
        
        for i, thumb in enumerate(thumbnails):
            row = i // cols
            col = i % cols
            
            # Calculate position to center thumbnail in cell
            x_offset = (cell_width - thumb.width) // 2
            y_offset = (cell_height - thumb.height) // 2
            
            x = col * cell_width + x_offset
            y = row * cell_height + y_offset
            
            collage.paste(thumb, (x, y))
        
        return collage

class SessionManager:
    """Manages saving and loading of FastShot sessions."""
    
    def __init__(self, app):
        self.app = app
        self.session_dir = Path.home() / ".fastshot" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
    
    def save_session_with_dialog(self):
        """Shows enhanced dialog to get metadata and saves the current session."""
        try:
            # Check if there are any windows to save
            valid_windows = self._get_valid_windows()
            if not valid_windows:
                messagebox.showinfo("No Windows", "No image windows to save.")
                return
            
            # Use enhanced save dialog
            from .enhanced_save_dialog import EnhancedSaveDialog
            
            dialog = EnhancedSaveDialog(self.app.root, self.app)
            metadata = dialog.show()
            
            # User cancelled
            if metadata is None:
                return
            
            # Check if we should save to cloud
            if metadata.get('save_to_cloud', False) and hasattr(self.app, 'cloud_sync'):
                # Cloud save is now handled by the enhanced save dialog with progress
                # The dialog will show progress and handle the save operation
                # If we get here, the save was successful (dialog only returns on success)
                print("Cloud save completed successfully via enhanced dialog")
            else:
                # Save locally with metadata
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                name = metadata.get('name', '')
                if name.strip():
                    # Use name for filename (already sanitized in dialog)
                    safe_name = name[:50]  # Limit length
                    filename = f"{timestamp}_{safe_name}.fastshot"
                else:
                    # Fallback to description or default
                    desc = metadata.get('desc', '')
                    if desc.strip():
                        # Sanitize description for filename
                        safe_desc = "".join(c for c in desc if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        safe_desc = safe_desc.replace(' ', '_')[:50]  # Limit length
                        filename = f"{timestamp}_{safe_desc}.fastshot"
                    else:
                        filename = f"{timestamp}_session.fastshot"
                
                filepath = self.session_dir / filename
                
                # Save the session with metadata
                if self.save_session_with_metadata(filepath, metadata):
                    session_data = self._prepare_session_data()
                    image_count = len(session_data.get('windows', []))
                    messagebox.showinfo("Success", f"Session saved as:\n{filename}\n\nSaved {image_count} images")
                    print(f"Session saved: {filepath} with {image_count} images")
                else:
                    messagebox.showerror("Error", "Failed to save session.")
                
        except Exception as e:
            print(f"Error in save_session_with_dialog: {e}")
            messagebox.showerror("Error", f"Failed to save session: {str(e)}")
    
    def _get_valid_windows(self):
        """Get all valid windows that can be saved (including hidden ones)."""
        valid_windows = []
        for window in self.app.windows:
            try:
                # Check if window object exists and has required attributes
                if (hasattr(window, 'img_window') and 
                    hasattr(window, 'img_label') and 
                    hasattr(window.img_label, 'original_image')):
                    
                    # Don't require window to be visible - include hidden windows too
                    # Just check if the Tkinter window object exists
                    if window.img_window.winfo_exists():
                        valid_windows.append(window)
                    else:
                        print(f"Window {id(window)} exists but Tkinter window doesn't exist")
            except Exception as e:
                print(f"Error checking window {id(window)}: {e}")
                continue
        
        print(f"Found {len(valid_windows)} valid windows out of {len(self.app.windows)} total windows")
        return valid_windows
    
    def _prepare_session_data(self):
        """Prepare session data for saving."""
        session_data = {
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "windows": []
        }
        
        # Get all valid windows (including hidden ones)
        valid_windows = self._get_valid_windows()
        
        # Collect data from all valid image windows
        for i, window in enumerate(valid_windows):
            try:
                window_data = self.serialize_window(window, i)
                if window_data:
                    session_data["windows"].append(window_data)
                    print(f"Successfully serialized window {i}")
                else:
                    print(f"Failed to serialize window {i}")
            except Exception as e:
                print(f"Error serializing window {i}: {e}")
                continue
        
        print(f"Prepared session data with {len(session_data['windows'])} windows")
        return session_data
    
    def save_session_with_metadata(self, filepath, metadata):
        """Saves the current session with metadata to a file."""
        try:
            session_data = self._prepare_session_data()
            
            # Create thumbnail collage
            thumbnail_collage = self._create_session_thumbnail(session_data)
            thumbnail_data = None
            if thumbnail_collage:
                thumbnail_data = self.serialize_image(thumbnail_collage)
            
                            # Add enhanced metadata to session
                full_session_data = {
                    'session': session_data,
                    'metadata': {
                        'name': metadata.get('name', ''),
                        'desc': metadata.get('desc', ''),
                        'tags': metadata.get('tags', []),
                        'color': metadata.get('color', 'blue'),
                        'class': metadata.get('class', ''),
                        'created_at': datetime.now().isoformat(),
                        'filename': filepath.name,
                        'image_count': len(session_data.get('windows', [])),
                        'thumbnail_collage': thumbnail_data
                    }
                }
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(full_session_data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Error saving session with metadata: {e}")
            return False
    
    def _create_session_thumbnail(self, session_data):
        """Create a thumbnail collage from all images in the session."""
        try:
            windows = session_data.get('windows', [])
            if not windows:
                return None
            
            # Extract original images from all windows
            images = []
            for window_data in windows:
                original_image_data = window_data.get('original_image_data')
                if original_image_data:
                    image = self.deserialize_image(original_image_data)
                    if image:
                        images.append(image)
            
            if not images:
                return None
            
            # Create thumbnail collage
            collage = ThumbnailCreator.create_thumbnail_collage(images)
            return collage
            
        except Exception as e:
            print(f"Error creating session thumbnail: {e}")
            return None
    
    def load_session_with_dialog(self):
        """Shows file dialog to select and load a session."""
        try:
            # Show file dialog
            filepath = filedialog.askopenfilename(
                title="Load Session",
                initialdir=str(self.session_dir),
                filetypes=[("FastShot Sessions", "*.fastshot"), ("All Files", "*.*")]
            )
            
            if not filepath:
                return
            
            # Confirm if there are existing windows
            if self.app.windows:
                result = messagebox.askyesnocancel(
                    "Load Session",
                    f"You have {len(self.app.windows)} existing image windows.\n\n"
                    "Yes: Close existing windows and load session\n"
                    "No: Keep existing windows and add session\n"
                    "Cancel: Don't load session"
                )
                
                if result is None:  # Cancel
                    return
                elif result:  # Yes - close existing
                    self.close_all_windows()
            
            # Load the session
            if self.load_session(filepath):
                filename = os.path.basename(filepath)
                messagebox.showinfo("Success", f"Session loaded:\n{filename}")
                print(f"Session loaded: {filepath}")
            else:
                messagebox.showerror("Error", "Failed to load session.")
                
        except Exception as e:
            print(f"Error in load_session_with_dialog: {e}")
            messagebox.showerror("Error", f"Failed to load session: {str(e)}")
    
    def save_session(self, filepath):
        """Saves the current session to a file."""
        try:
            session_data = {
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "windows": []
            }
            
            # Collect data from all active image windows
            for i, window in enumerate(self.app.windows):
                if not window.img_window.winfo_exists():
                    continue
                
                try:
                    window_data = self.serialize_window(window, i)
                    if window_data:
                        session_data["windows"].append(window_data)
                except Exception as e:
                    print(f"Error serializing window {i}: {e}")
                    continue
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Error saving session: {e}")
            return False
    
    def serialize_window(self, window, index):
        """Serializes a single ImageWindow to dictionary format."""
        try:
            # Get window geometry - handle hidden windows gracefully
            try:
                if not window.is_hidden:
                    window.img_window.update_idletasks()
                x = window.img_window.winfo_x()
                y = window.img_window.winfo_y()
                width = window.img_window.winfo_width()
                height = window.img_window.winfo_height()
            except Exception as e:
                print(f"Warning: Could not get geometry for window {index}, using defaults: {e}")
                x, y, width, height = 100, 100, 300, 200
            
            # Serialize the current image (with annotations)
            image_data = self.serialize_image(window.img_label.zoomed_image)
            if not image_data:
                print(f"Warning: Failed to serialize zoomed image for window {index}")
                return None
            
            # Serialize the original image
            original_image_data = self.serialize_image(window.img_label.original_image)
            if not original_image_data:
                print(f"Error: Failed to serialize original image for window {index}")
                return None
            
            window_data = {
                "index": index,
                "geometry": {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height
                },
                "scale": getattr(window.img_label, 'scale', 1.0),
                "image_data": image_data,
                "original_image_data": original_image_data,
                "draw_history": self.serialize_draw_history(window.draw_history),
                "is_hidden": getattr(window, 'is_hidden', False),
                "window_id": id(window)  # For debugging
            }
            
            print(f"Successfully serialized window {index} (hidden: {window_data['is_hidden']})")
            return window_data
            
        except Exception as e:
            print(f"Error serializing window {index}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def serialize_image(self, image):
        """Converts PIL Image to base64 string."""
        try:
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            image_bytes = buffer.getvalue()
            return base64.b64encode(image_bytes).decode('utf-8')
        except Exception as e:
            print(f"Error serializing image: {e}")
            return None
    
    def serialize_draw_history(self, draw_history):
        """Serializes the drawing history."""
        try:
            serialized_history = []
            for item in draw_history:
                if isinstance(item, list):  # Line drawings
                    serialized_history.append({
                        "type": "lines",
                        "data": item
                    })
                elif isinstance(item, tuple) and item[0] == 'text':  # Text annotations
                    serialized_history.append({
                        "type": "text",
                        "data": {
                            "x": item[1],
                            "y": item[2], 
                            "text": item[3]
                        }
                    })
            return serialized_history
        except Exception as e:
            print(f"Error serializing draw history: {e}")
            return []
    
    def load_session(self, filepath):
        """Loads a session from a file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            
            # Handle both formats: with metadata wrapper and direct session data
            if 'session' in file_data and 'metadata' in file_data:
                # New format with metadata wrapper
                session_data = file_data['session']
                print(f"Loading session with metadata: {file_data['metadata'].get('desc', 'No description')}")
            else:
                # Legacy format - direct session data
                session_data = file_data
            
            # Validate session data
            if not self.validate_session_data(session_data):
                print("Invalid session data format")
                print(f"Session data keys: {list(session_data.keys()) if isinstance(session_data, dict) else 'Not a dict'}")
                return False
            
            # Load each window
            loaded_count = 0
            for window_data in session_data.get("windows", []):
                try:
                    if self.deserialize_window(window_data):
                        loaded_count += 1
                except Exception as e:
                    print(f"Error loading window: {e}")
                    continue
            
            print(f"Successfully loaded {loaded_count} windows from session")
            return loaded_count > 0
            
        except Exception as e:
            print(f"Error loading session: {e}")
            return False
    
    def deserialize_window(self, window_data):
        """Recreates an ImageWindow from serialized data."""
        try:
            # Deserialize original image
            original_image = self.deserialize_image(window_data["original_image_data"])
            if not original_image:
                print("Failed to deserialize original image")
                return False
            
            # Create new ImageWindow with original image
            from .image_window import ImageWindow
            window = ImageWindow(self.app, original_image, self.app.config)
            
            # Restore scale
            scale = window_data.get("scale", 1.0)
            window.img_label.scale = scale
            
            # Restore draw history
            window.draw_history = self.deserialize_draw_history(window_data.get("draw_history", []))
            
            # Apply scale to the image if it's not 1.0
            if scale != 1.0:
                new_width = int(window.img_label.original_image.width * scale)
                new_height = int(window.img_label.original_image.height * scale)
                try:
                    window.img_label.zoomed_image = window.img_label.original_image.resize((new_width, new_height), Image.LANCZOS)
                except Exception as e:
                    print(f"Error resizing image during load: {e}")
                    # Fallback to original size
                    window.img_label.scale = 1.0
                    window.img_label.zoomed_image = window.img_label.original_image.copy()
            
            # Redraw the image with annotations
            if window.draw_history or scale != 1.0:
                window.redraw_image()
            
            # Restore geometry
            geometry = window_data.get("geometry", {})
            if geometry:
                x = geometry.get("x", 100)
                y = geometry.get("y", 100)
                window.img_window.geometry(f"+{x}+{y}")
            
            # Restore visibility state
            is_hidden = window_data.get("is_hidden", False)
            if is_hidden:
                window.hide()
            
            # Add to app windows list
            self.app.windows.append(window)
            
            print(f"Restored window at ({geometry.get('x', 0)}, {geometry.get('y', 0)}) with scale {scale}")
            return True
            
        except Exception as e:
            print(f"Error deserializing window: {e}")
            return False
    
    def deserialize_image(self, image_data):
        """Converts base64 string back to PIL Image."""
        try:
            if not image_data:
                return None
            
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            return image
        except Exception as e:
            print(f"Error deserializing image: {e}")
            return None
    
    def deserialize_draw_history(self, serialized_history):
        """Recreates the drawing history from serialized data."""
        try:
            draw_history = []
            for item in serialized_history:
                if item.get("type") == "lines":
                    draw_history.append(item["data"])
                elif item.get("type") == "text":
                    text_data = item["data"]
                    draw_history.append(('text', text_data["x"], text_data["y"], text_data["text"]))
            return draw_history
        except Exception as e:
            print(f"Error deserializing draw history: {e}")
            return []
    
    def validate_session_data(self, session_data):
        """Validates the structure of session data."""
        try:
            if not isinstance(session_data, dict):
                return False
            
            if "windows" not in session_data:
                return False
            
            if not isinstance(session_data["windows"], list):
                return False
            
            return True
        except:
            return False
    
    def close_all_windows(self):
        """Closes all existing image windows."""
        try:
            for window in list(self.app.windows):
                if window.img_window.winfo_exists():
                    window.close()
            self.app.windows.clear()
        except Exception as e:
            print(f"Error closing windows: {e}")
    
    def get_session_files(self):
        """Returns a list of available session files."""
        try:
            return list(self.session_dir.glob("*.fastshot"))
        except Exception as e:
            print(f"Error getting session files: {e}")
            return [] 