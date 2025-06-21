# fastshot/session_manager.py

import json
import os
import pickle
import base64
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
from PIL import Image
import io

class SessionManager:
    """Manages saving and loading of FastShot sessions."""
    
    def __init__(self, app):
        self.app = app
        self.session_dir = Path.home() / ".fastshot" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
    
    def save_session_with_dialog(self):
        """Shows dialog to get notes and saves the current session."""
        try:
            # Get optional notes from user
            notes = simpledialog.askstring(
                "Save Session", 
                "Enter optional notes for this session:",
                initialvalue=""
            )
            
            # User cancelled
            if notes is None:
                return
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            if notes.strip():
                # Sanitize notes for filename
                safe_notes = "".join(c for c in notes if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_notes = safe_notes.replace(' ', '_')[:50]  # Limit length
                filename = f"{timestamp}_{safe_notes}.fastshot"
            else:
                filename = f"{timestamp}_session.fastshot"
            
            filepath = self.session_dir / filename
            
            # Save the session
            if self.save_session(filepath):
                messagebox.showinfo("Success", f"Session saved as:\n{filename}")
                print(f"Session saved: {filepath}")
            else:
                messagebox.showerror("Error", "Failed to save session.")
                
        except Exception as e:
            print(f"Error in save_session_with_dialog: {e}")
            messagebox.showerror("Error", f"Failed to save session: {str(e)}")
    
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
            # Get window geometry
            window.img_window.update_idletasks()
            x = window.img_window.winfo_x()
            y = window.img_window.winfo_y()
            width = window.img_window.winfo_width()
            height = window.img_window.winfo_height()
            
            # Serialize the current image (with annotations)
            image_data = self.serialize_image(window.img_label.zoomed_image)
            
            # Serialize the original image
            original_image_data = self.serialize_image(window.img_label.original_image)
            
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
                "is_hidden": window.is_hidden,
                "window_id": id(window)  # For debugging
            }
            
            return window_data
            
        except Exception as e:
            print(f"Error serializing window: {e}")
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
                session_data = json.load(f)
            
            # Validate session data
            if not self.validate_session_data(session_data):
                print("Invalid session data format")
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