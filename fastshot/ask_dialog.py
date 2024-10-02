# fastshot/ask_dialog.py

import tkinter as tk
from PIL import ImageTk, Image
import threading
import time
import os
import base64
import json
import io
import customtkinter as ctk  # Import customtkinter
from fastshot.gpt4o import ask

class AskDialog:
    def __init__(self, image_window):
        self.image_window = image_window
        self.is_minimized = False
        self.dialog_icon = None

        # Initialize customtkinter
        ctk.set_appearance_mode("Dark")  # Modes: "System", "Dark", "Light"
        ctk.set_default_color_theme("dark-blue")  # Themes: "blue", "dark-blue", "green"

        # Create the main dialog window
        self.dialog_window = ctk.CTkToplevel()
        self.dialog_window.title("Ask")
        self.dialog_window.geometry("600x800")
        self.dialog_window.minsize(400, 600)
        self.dialog_window.attributes('-topmost', True)

        # Hide system window decorations
        self.dialog_window.overrideredirect(True)

        # Create custom title bar
        self.create_title_bar()

        # Disable interactions with the image window while the dialog is open
        self.image_window.disable_interactions()
        self.image_window.is_dialog_open = True

        # Load user and AI icons
        self.user_icon = self.load_icon("user_icon.png", size=(40, 40))
        self.ai_icon = self.load_icon("ai_icon.png", size=(40, 40))

        # Create the main frame
        self.create_main_frame()

        # Initialize messages list
        self.messages = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
        self.is_first_query = True  # Flag to check if it's the first query

        # Handle window close event
        self.dialog_window.protocol("WM_DELETE_WINDOW", self.clean_and_close)

    def create_title_bar(self):
        # Create custom title bar
        self.title_bar = ctk.CTkFrame(self.dialog_window, height=40)
        self.title_bar.pack(fill=tk.X)

        # Load icons for the title bar
        self.icon_image = self.load_icon("title_icon.png", size=(20, 20))
        self.minimize_icon = self.load_icon("minimize_icon.png", size=(16, 16))
        self.close_icon = self.load_icon("close_icon.png", size=(16, 16))

        # Icon label
        self.icon_label = ctk.CTkLabel(self.title_bar, image=self.icon_image, text="")
        self.icon_label.pack(side=tk.LEFT, padx=(12, 0))

        # Title label
        self.title_label = ctk.CTkLabel(
            self.title_bar,
            text="Ask Dialog",
            anchor='w',
            font=("Arial", 14)
        )
        self.title_label.pack(side=tk.LEFT, padx=(5, 0))

        # Spacer to push buttons to the right
        self.title_bar_spacer = ctk.CTkLabel(self.title_bar, text="")
        self.title_bar_spacer.pack(side=tk.LEFT, expand=True)

        # Minimize button with icon
        if self.minimize_icon:
            self.minimize_button = ctk.CTkButton(
                self.title_bar,
                image=self.minimize_icon,
                text="",
                width=30,
                height=30,
                command=self.minimize_dialog,
                fg_color="transparent",
                hover_color="#3A3A3A"
            )
        else:
            self.minimize_button = ctk.CTkButton(
                self.title_bar,
                text="_",
                width=30,
                height=30,
                command=self.minimize_dialog,
                fg_color="transparent",
                hover_color="#3A3A3A"
            )
        self.minimize_button.pack(side=tk.RIGHT, padx=(0, 5), pady=5)

        # Close button with icon
        if self.close_icon:
            self.close_button = ctk.CTkButton(
                self.title_bar,
                image=self.close_icon,
                text="",
                width=30,
                height=30,
                command=self.clean_and_close,
                fg_color="transparent",
                hover_color="#3A3A3A"
            )
        else:
            self.close_button = ctk.CTkButton(
                self.title_bar,
                text="X",
                width=30,
                height=30,
                command=self.clean_and_close,
                fg_color="transparent",
                hover_color="#3A3A3A"
            )
        self.close_button.pack(side=tk.RIGHT, padx=(0, 5), pady=5)

        # Allow dragging the window
        self.title_bar.bind("<ButtonPress-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)
        self.title_label.bind("<ButtonPress-1>", self.start_move)
        self.title_label.bind("<B1-Motion>", self.do_move)
        self.icon_label.bind("<ButtonPress-1>", self.start_move)
        self.icon_label.bind("<B1-Motion>", self.do_move)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.dialog_window.winfo_x() + deltax
        y = self.dialog_window.winfo_y() + deltay
        self.dialog_window.geometry(f"+{x}+{y}")

    def create_main_frame(self):
        # Main frame
        self.main_frame = ctk.CTkFrame(self.dialog_window)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Conversation display
        self.create_conversation_display()

        # Input area
        self.create_input_area()

        # Enable window resizing
        self.enable_resizing()

    def enable_resizing(self):
        # Bind events for resizing
        self.dialog_window.bind("<Enter>", self.track_mouse_position)
        self.dialog_window.bind("<Motion>", self.change_cursor)
        self.dialog_window.bind("<ButtonPress-1>", self.start_resize)
        self.dialog_window.bind("<B1-Motion>", self.do_resize)
        self.dialog_window.bind("<ButtonRelease-1>", self.stop_resize)
        self.resizing = False
        self.resizable = False

    def track_mouse_position(self, event):
        self.mouse_x = event.x
        self.mouse_y = event.y

    def change_cursor(self, event):
        # Determine if the cursor is near the bottom-right corner
        border_width = 10
        x = event.x
        y = event.y
        width = self.dialog_window.winfo_width()
        height = self.dialog_window.winfo_height()

        if width - border_width <= x <= width and height - border_width <= y <= height:
            self.dialog_window.config(cursor="size_nw_se")
            self.resizable = True
        else:
            self.dialog_window.config(cursor="")
            self.resizable = False

    def start_resize(self, event):
        if self.resizable:
            self.resizing = True
            self.start_x = event.x
            self.start_y = event.y
            self.start_width = self.dialog_window.winfo_width()
            self.start_height = self.dialog_window.winfo_height()
        else:
            self.start_move(event)

    def do_resize(self, event):
        if self.resizing:
            dx = event.x - self.start_x
            dy = event.y - self.start_y
            new_width = self.start_width + dx
            new_height = self.start_height + dy
            if new_width >= self.dialog_window.minsize()[0] and new_height >= self.dialog_window.minsize()[1]:
                self.dialog_window.geometry(f"{int(new_width)}x{int(new_height)}")
                self.main_frame.update_idletasks()
        else:
            self.do_move(event)

    def stop_resize(self, event):
        self.resizing = False
        self.dialog_window.config(cursor="")

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

        # Input text box with increased height
        self.user_entry = ctk.CTkTextbox(self.input_frame, height=90)
        self.user_entry.pack(fill=tk.BOTH, side=tk.LEFT, expand=True, padx=(10, 5))
        self.user_entry.bind("<Shift-Return>", self.on_submit_click)

        # Buttons frame
        self.buttons_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.buttons_frame.pack(side=tk.RIGHT, padx=(5, 0))

        # Submit button
        self.submit_button = ctk.CTkButton(self.buttons_frame, text="Send", command=self.on_submit_click)
        self.submit_button.pack(side=tk.TOP, pady=5)

        # Clean button
        self.clean_button = ctk.CTkButton(self.buttons_frame, text="Clean", command=self.clean_and_close)
        self.clean_button.pack(side=tk.TOP, pady=5)

        # Cancel button added below the Clean button
        self.cancel_button = ctk.CTkButton(self.buttons_frame, text="Cancel", command=self.minimize_dialog)
        self.cancel_button.pack(side=tk.TOP, pady=5)

    def show_thumbnail(self):
        # Load and resize the thumbnail image
        original_image = self.image_window.img_label.zoomed_image
        thumb_size = 50  # Thumbnail size

        thumbnail_image = original_image.copy()
        thumbnail_image.thumbnail((thumb_size, thumb_size), Image.LANCZOS)
        self.thumbnail_photo = ImageTk.PhotoImage(thumbnail_image)

        # Thumbnail label
        self.thumbnail_label = ctk.CTkLabel(self.input_frame, image=self.thumbnail_photo, text="")
        self.thumbnail_label.pack(side=tk.LEFT, padx=(0, 5))
        self.thumbnail_label.bind("<Enter>", self.show_image_preview)
        self.thumbnail_label.bind("<Leave>", self.hide_image_preview)

    def show_image_preview(self, event):
        # Show larger image preview on hover
        original_image = self.image_window.img_label.zoomed_image
        max_size = (400, 400)

        # Resize image for preview
        img_width, img_height = original_image.size
        scale = min(max_size[0]/img_width, max_size[1]/img_height)
        new_size = (int(img_width * scale), int(img_height * scale))
        display_image = original_image.resize(new_size, Image.LANCZOS)

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
            self.append_message(user_input, sender='user')

            # Add user's message to messages list
            if self.is_first_query:
                # First query includes text and image
                current_image = self.image_window.img_label.zoomed_image.copy()
                buffered = io.BytesIO()
                current_image.save(buffered, format="JPEG")
                img_str = base64.b64encode(buffered.getvalue()).decode('ascii')
                user_content = [
                    {"type": "text", "text": user_input},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}}
                ]
                self.is_first_query = False
            else:
                # Subsequent queries include only text
                user_content = user_input

            self.messages.append({
                "role": "user",
                "content": user_content
            })

            # Call ask_dummy function
            threading.Thread(target=self.ask_dummy).start()
        return 'break'

    def append_message(self, message, sender='user'):
        # Create message frame
        message_frame = ctk.CTkFrame(self.conversation_frame, fg_color="transparent")

        if sender == 'user':
            # User message on the right
            bubble = ctk.CTkLabel(
                message_frame,
                text=message,
                anchor='e',
                justify='right',
                bg_color="#1F6AA5",
                text_color="white",
                corner_radius=15,
                fg_color="#1F6AA5",
                padx=10,
                pady=5,
                width=400,
                wraplength=350
            )
            bubble.pack(anchor='e', pady=5)
        else:
            # AI message on the left
            bubble = ctk.CTkLabel(
                message_frame,
                text=message,
                anchor='w',
                justify='left',
                bg_color="#2E2E2E",
                text_color="white",
                corner_radius=15,
                fg_color="#2E2E2E",
                padx=10,
                pady=5,
                width=400,
                wraplength=350
            )
            bubble.pack(anchor='w', pady=5)

        message_frame.pack(fill=tk.X, padx=10)

        # Scroll to the bottom
        self.conversation_frame.update_idletasks()
        self.conversation_frame._parent_canvas.yview_moveto(1.0)

    def ask_dummy(self):
        # token = get_token() 
        # resp = ask_with_msgs(token, self.messages)
        # self.dialog_window.after(0, self.show_messages_json)
        answer_text = ask(self.messages) #"This is a simulated response from GPT-4."

        # Add AI's response to messages list
        self.messages.append({
            "role": "assistant",
            "content": answer_text
        })

        # Update UI with AI's response
        self.dialog_window.after(0, self.append_message, answer_text, 'assistant')

    def show_messages_json(self):
        # Show messages list in JSON format
        json_window = ctk.CTkToplevel(self.dialog_window)
        json_window.title("Messages JSON")
        json_window.attributes('-topmost', True)
        json_window.geometry("600x400")

        json_text = json.dumps(self.messages, indent=4)
        text_widget = ctk.CTkTextbox(json_window)
        text_widget.insert(tk.END, json_text)
        text_widget.configure(state="disabled")
        text_widget.pack(fill=tk.BOTH, expand=True)

    def minimize_dialog(self):
        # Minimize the dialog window
        self.dialog_window.withdraw()
        self.is_minimized = True
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
        # Disable interactions with the image window
        self.image_window.disable_interactions()
        self.image_window.is_dialog_open = True

    def create_dialog_icon(self):
        # Create an icon on the image window to restore the dialog
        if self.dialog_icon:
            self.dialog_icon.destroy()

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

    def clean_and_close(self):
        # Reset messages
        self.messages.clear()
        self.messages = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
        self.is_first_query = True

        if self.dialog_window:
            self.dialog_window.destroy()
            self.dialog_window = None
        if self.dialog_icon:
            self.dialog_icon.destroy()
            self.dialog_icon = None
        # Re-enable interactions with the image window
        self.image_window.enable_interactions()
        self.image_window.ask_dialog = None
        self.image_window.is_dialog_open = False
