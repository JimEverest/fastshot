# ask_dialog.py

import tkinter as tk
from PIL import ImageTk, Image
import threading
import time
import os
import base64
import json
import io
import customtkinter as ctk
from fastshot.gpt4o import ask

class AskDialog:
    def __init__(self, image_window=None):
        self.image_window = image_window
        self.is_minimized = False
        self.dialog_icon = None
        self.current_image = None  # To store the uploaded image
        self.image_changed = False  # Flag to check if the image has changed

        # Initialize customtkinter
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("dark-blue")

        # Create the main dialog window
        self.dialog_window = ctk.CTkToplevel()
        self.dialog_window.title("Fastshot")
        self.dialog_window.geometry("600x800")
        self.dialog_window.minsize(400, 600)
        self.dialog_window.attributes('-topmost', True)
        # Set the window icon
        self.set_window_icon()
        # Existing initialization code...
        self.resize_job = None  # Initialize a variable to hold the after job ID
        # Bind window resize event
        self.dialog_window.bind("<Configure>", self.on_window_resize)



        # Remove overrideredirect to use native window decorations
        # self.dialog_window.overrideredirect(True)

        # Disable interactions with the image window while the dialog is open
        if self.image_window:
            self.image_window.disable_interactions()
            self.image_window.is_dialog_open = True

        # Load user and AI icons
        self.user_icon = self.load_icon("user_icon.png", size=(40, 40))
        self.ai_icon = self.load_icon("ai_icon.png", size=(40, 40))

        # Initialize messages list
        self.messages = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]

        # Create the main frame
        self.create_main_frame()

        # Handle window close event
        self.dialog_window.protocol("WM_DELETE_WINDOW", self.clean_and_close)

        # Bind window resize event
        self.dialog_window.bind("<Configure>", self.on_window_resize)


    def set_window_icon(self):
        # Load the icon image
        icon_path = os.path.join(os.path.dirname(__file__), 'resources', 'title_icon.png')
        if os.path.exists(icon_path):
            # Load the image using PIL
            icon_image = Image.open(icon_path)
            # Resize the icon if necessary
            icon_image = icon_image.resize((32, 32), Image.LANCZOS)
            # Convert the image to a PhotoImage object
            self.icon_photo = ImageTk.PhotoImage(icon_image)
            # Set the window icon
            self.dialog_window.iconphoto(True, self.icon_photo)
        else:
            print(f"Icon file not found: {icon_path}")


    def create_main_frame(self):
        # Main frame
        self.main_frame = ctk.CTkFrame(self.dialog_window)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Conversation display
        self.create_conversation_display()

        # Input area
        self.create_input_area()

    def create_conversation_display(self):
        # Scrollable frame for conversation
        self.conversation_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.conversation_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_input_area(self):
        # Input frame
        self.input_frame = ctk.CTkFrame(self.main_frame)
        self.input_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)

        # Thumbnail image
        self.show_thumbnail()

        # Buttons frame
        self.buttons_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.buttons_frame.pack(side=tk.RIGHT, padx=(5, 0))

        # Submit button
        self.submit_button = ctk.CTkButton(self.buttons_frame, text="Send", command=self.on_submit_click)
        self.submit_button.pack(side=tk.TOP, pady=5)

        # Clean button
        self.clean_button = ctk.CTkButton(self.buttons_frame, text="Clean", command=self.clean_conversation)
        self.clean_button.pack(side=tk.TOP, pady=5)

        # Cancel button added below the Clean button
        self.cancel_button = ctk.CTkButton(self.buttons_frame, text="Cancel", command=self.minimize_dialog)
        self.cancel_button.pack(side=tk.TOP, pady=5)

        # Input text box with increased height
        self.user_entry = ctk.CTkTextbox(self.input_frame, height=90)
        self.user_entry.pack(fill=tk.BOTH, side=tk.LEFT, expand=True, padx=(10, 5))
        self.user_entry.bind("<Shift-Return>", self.on_submit_click)

    def show_thumbnail(self):
        # If image_window is not None and has an image, use it
        if self.image_window and hasattr(self.image_window.img_label, 'zoomed_image'):
            original_image = self.image_window.img_label.zoomed_image
            self.current_image = original_image.copy()
            self.image_changed = True  # Image has changed
        else:
            self.current_image = None
            self.image_changed = False

        if self.current_image:
            thumb_size = 50  # Thumbnail size
            thumbnail_image = self.current_image.copy()
            thumbnail_image.thumbnail((thumb_size, thumb_size), Image.LANCZOS)
            self.thumbnail_photo = ImageTk.PhotoImage(thumbnail_image)
        else:
            # Load placeholder image
            placeholder_path = os.path.join(os.path.dirname(__file__), 'resources', 'upload_placeholder.png')
            if os.path.exists(placeholder_path):
                placeholder_image = Image.open(placeholder_path)
                placeholder_image = placeholder_image.resize((50, 50), Image.LANCZOS)
                self.thumbnail_photo = ImageTk.PhotoImage(placeholder_image)
            else:
                # Create a simple placeholder if image not found
                placeholder_image = Image.new('RGBA', (50, 50), (200, 200, 200, 255))
                self.thumbnail_photo = ImageTk.PhotoImage(placeholder_image)

        # Thumbnail label
        self.thumbnail_label = ctk.CTkLabel(self.input_frame, image=self.thumbnail_photo, text="")
        self.thumbnail_label.pack(side=tk.LEFT, padx=(0, 15))
        self.thumbnail_label.bind("<Enter>", self.show_image_preview)
        self.thumbnail_label.bind("<Leave>", self.hide_image_preview)
        self.thumbnail_label.bind("<Button-1>", self.upload_image)

    def upload_image(self, event=None):
        # Open file dialog to select image
        filetypes = [("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")]
        filepath = tk.filedialog.askopenfilename(filetypes=filetypes)
        if filepath:
            self.load_uploaded_image(filepath)

    def load_uploaded_image(self, filepath):
        try:
            image = Image.open(filepath)
            self.current_image = image.copy()
            self.image_changed = True  # Image has changed

            # Update thumbnail
            thumb_size = 50  # Thumbnail size
            thumbnail_image = self.current_image.copy()
            thumbnail_image.thumbnail((thumb_size, thumb_size), Image.LANCZOS)
            self.thumbnail_photo = ImageTk.PhotoImage(thumbnail_image)
            self.thumbnail_label.configure(image=self.thumbnail_photo)
        except Exception as e:
            print(f"Error loading image: {e}")

    def show_image_preview(self, event):
        if self.current_image:
            # Show larger image preview on hover
            max_size = (400, 400)

            # Resize image for preview
            img_width, img_height = self.current_image.size
            scale = min(max_size[0]/img_width, max_size[1]/img_height)
            new_size = (int(img_width * scale), int(img_height * scale))
            display_image = self.current_image.resize(new_size, Image.LANCZOS)

            self.preview_photo = ImageTk.PhotoImage(display_image)

            self.preview_window = ctk.CTkToplevel(self.dialog_window)
            self.preview_window.overrideredirect(True)
            self.preview_window.attributes('-topmost', True)

            x = self.dialog_window.winfo_x() + self.thumbnail_label.winfo_x()
            y = self.dialog_window.winfo_y() + self.thumbnail_label.winfo_y() - new_size[1]
            self.preview_window.geometry(f"+{x}+{y}")

            preview_label = ctk.CTkLabel(self.preview_window, image=self.preview_photo, text="")
            preview_label.pack()

    def hide_image_preview(self, event):
        # Hide the image preview
        if hasattr(self, 'preview_window') and self.preview_window:
            self.preview_window.destroy()
            self.preview_window = None

    def load_icon(self, filename, size=(30, 30)):
        icon_path = os.path.join(os.path.dirname(__file__), 'resources', filename)
        if os.path.exists(icon_path):
            icon = Image.open(icon_path)
            icon = icon.resize(size, Image.LANCZOS)
            return ImageTk.PhotoImage(icon)
        else:
            print(f"Icon file not found: {icon_path}")
            return None

    def on_window_close(self):
        self.clean_and_close()

    def on_submit_click(self, event=None):
        user_input = self.user_entry.get("1.0", tk.END).strip()
        if user_input:
            self.user_entry.delete("1.0", tk.END)

            # Build user content
            user_content = ""

            # Check if image has changed or if it's the first query with an image
            if self.current_image and self.image_changed:
                user_content = {"type": "text", "text": user_input}
                buffered = io.BytesIO()
                self.current_image.save(buffered, format="JPEG")
                img_str = base64.b64encode(buffered.getvalue()).decode('ascii')
                image_content = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}}
                user_content = [user_content, image_content]
                self.image_changed = False  # Reset the flag
            else:
                user_content =  user_input

            self.messages.append({
                "role": "user",
                "content": user_content
            })

            # Append user message to UI
            self.append_message(user_content, sender='user')

            # Call the ask function
            threading.Thread(target=self.ask_dummy).start()
        return 'break'

    def append_message(self, message_content, sender='user'):
        # Create message frame
        message_frame = ctk.CTkFrame(self.conversation_frame, fg_color="transparent")
        message_frame.pack(fill=tk.X, padx=10, pady=5)

        if sender == 'user':
            anchor = 'e'
            bg_color = "#1F6AA5"
            icon_image = self.user_icon
        else:
            anchor = 'w'
            bg_color = "#2E2E2E"
            icon_image = self.ai_icon

        # Message content frame
        content_frame = ctk.CTkFrame(message_frame, fg_color="transparent")
        content_frame.pack(anchor=anchor, fill=tk.X, expand=True)

        # Icon
        if icon_image:
            icon_label = ctk.CTkLabel(content_frame, image=icon_image, text="")
            icon_label.pack(side=tk.LEFT if sender == 'assistant' else tk.RIGHT, padx=5)

        # Display message content
        if isinstance(message_content, list):
            for item in message_content:
                self.display_message_item(content_frame, item, bg_color, sender)
        else:
            self.display_message_item(content_frame, message_content, bg_color, sender)

        # Scroll to the bottom
        self.conversation_frame.update_idletasks()
        self.conversation_frame._parent_canvas.yview_moveto(1.0)

    def display_message_item(self, parent_frame, item, bg_color, sender):
        alignment = 'w' if sender == 'assistant' else 'e'
        if isinstance(item, dict) and item.get('type') == 'image_url':
            # Existing image handling code...
            if isinstance(item, dict) and item.get('type') == 'image_url':
                img_url = item.get('image_url', {}).get('url', '')
                if img_url.startswith('data:image'):
                    img_data = img_url.split(',', 1)[1]
                    image = Image.open(io.BytesIO(base64.b64decode(img_data)))
                    # Resize image to max 400px on the longest side
                    max_size = 400
                    image.thumbnail((max_size, max_size), Image.LANCZOS)
                    image_photo = ImageTk.PhotoImage(image)
                    image_label = ctk.CTkLabel(parent_frame, image=image_photo, text="")
                    image_label.image = image_photo  # Keep a reference
                    image_label.pack(side=tk.TOP, anchor=alignment, padx=5, pady=5)
        else:
            # Handle text content
            if isinstance(item, str):
                text = item
            else:
                text = item.get('text', '')

            # Calculate wraplength safely
            wraplength = self.dialog_window.winfo_width() - 150
            if wraplength <= 0:
                wraplength = 100  # Minimum wraplength

            # Create a CTkLabel
            bubble = ctk.CTkLabel(
                parent_frame,
                text=text,
                fg_color=bg_color,
                text_color="white",
                corner_radius=15,
                wraplength=wraplength,
                padx=10,
                pady=10,
                font=("Arial", 12),
                anchor='w',
                justify='left'
            )
            bubble.pack(side=tk.TOP, anchor=alignment, padx=5, pady=5, fill=tk.X, expand=True)
            # Ensure minimum height
            bubble.update_idletasks()
            current_height = bubble.winfo_height()
            if current_height < 40:
                bubble.configure(height=40)


    def on_window_resize(self, event):
        if self.resize_job is not None:
            self.dialog_window.after_cancel(self.resize_job)
        self.resize_job = self.dialog_window.after(200, self.resize_bubbles)  # Adjust delay as needed

    def resize_bubbles(self):
        self.resize_job = None  # Reset the job ID
        try:
            new_wraplength = self.dialog_window.winfo_width() - 150  # Adjust as needed
            if new_wraplength <= 0:
                new_wraplength = 100  # Set a minimum wraplength

            for widget in self.conversation_frame.winfo_children():
                content_frames = widget.winfo_children()
                for content_frame in content_frames:
                    bubbles = content_frame.winfo_children()
                    for bubble in bubbles:
                        if isinstance(bubble, ctk.CTkLabel):
                            bubble.configure(wraplength=new_wraplength)
        except Exception as e:
            print(f"Exception during resize: {e}")


    def ask_dummy(self):
        # Simulate sending messages to OpenAI GPT-4V model
        answer_content = ask(self.messages)  # Replace with actual call to GPT-4V

        # Add AI's response to messages list
        self.messages.append({
            "role": "assistant",
            "content": answer_content
        })

        # Update UI with AI's response
        self.dialog_window.after(0, self.append_message, answer_content, 'assistant')

    def minimize_dialog(self):
        # Minimize the dialog window
        self.dialog_window.withdraw()
        self.is_minimized = True

        if self.image_window:
            # Create dialog icon only if image_window is present
            self.create_dialog_icon()
            # Re-enable interactions with the image window
            self.image_window.enable_interactions()
            self.image_window.is_dialog_open = False

    def maximize_dialog(self, event=None):
        # Restore the dialog window
        self.dialog_window.deiconify()
        self.is_minimized = False
        if self.dialog_icon:
            self.dialog_icon.destroy()
            self.dialog_icon = None
        if self.image_window:
            # Disable interactions with the image window
            self.image_window.disable_interactions()
            self.image_window.is_dialog_open = True

    def create_dialog_icon(self):
        # Create an icon on the image window to restore the dialog
        if self.dialog_icon:
            self.dialog_icon.destroy()

        if not self.image_window:
            return  # Do not create dialog icon if image_window is None

        # Load the icon image
        icon_image = self.load_icon("title_icon.png", size=(30, 30))

        if icon_image:
            self.dialog_icon = ctk.CTkLabel(
                self.image_window.img_window,
                image=icon_image,
                text="",
                cursor="hand2"
            )
            # Keep a reference to prevent garbage collection
            self.dialog_icon.image = icon_image
        else:
            # If icon not found, use text
            self.dialog_icon = ctk.CTkLabel(
                self.image_window.img_window,
                text="💬",
                cursor="hand2",
                font=("Arial", 24),
                fg_color="transparent",
                text_color="white"
            )

        self.dialog_icon.place(relx=1.0, rely=0.0, anchor='ne', x=-20, y=20)
        self.dialog_icon.bind("<Button-1>", self.maximize_dialog)

    def update_dialog_icon_position(self):
        # Update the position of the dialog icon when the image window moves
        if self.dialog_icon:
            self.dialog_icon.place(relx=1.0, rely=0.0, anchor='ne', x=-20, y=20)

    def clean_conversation(self):
        # Reset messages and clear conversation display
        self.messages.clear()
        self.messages = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
        self.current_image = None
        self.image_changed = False

        # Clear conversation frame
        for widget in self.conversation_frame.winfo_children():
            widget.destroy()

    def clean_and_close(self):
        # Clean conversation and close the dialog
        self.clean_conversation()
        if self.dialog_window:
            self.dialog_window.destroy()
            self.dialog_window = None

        # Reset reference in main application
        if hasattr(self, 'image_window') and self.image_window:
            self.image_window.ask_dialog = None
            self.image_window.is_dialog_open = False
        else:
            # For global AskDialog, reset the reference
            app = self.get_main_app()
            if app:
                app.ask_dialog = None

    def get_main_app(self):
        # Utility method to get the main application instance
        try:
            return tk._default_root.app  # Assuming 'app' is set in the main Tk instance
        except AttributeError:
            return None
