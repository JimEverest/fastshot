# fastshot/image_window_gallery.py

import sys
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw
from typing import List, Set, Callable, Optional, Any


class ThumbnailButton(tk.Frame):
    """A clickable thumbnail with checkbox overlay and eye icon for visibility."""

    THUMB_W = 200
    THUMB_H = 150

    def __init__(self, parent, image: Image.Image, index: int,
                 is_visible: bool = True,
                 on_toggle=None, on_double_click=None,
                 on_visibility_toggle=None):
        super().__init__(parent, bg="#2a2a2a", bd=2, relief="flat",
                         highlightthickness=2, highlightbackground="#2a2a2a")
        self.index = index
        self.is_selected = False
        self.is_visible = is_visible  # whether the source ImageWindow is visible
        self.on_toggle = on_toggle
        self.on_double_click = on_double_click
        self.on_visibility_toggle = on_visibility_toggle

        # Create thumbnail PIL image and keep PhotoImage reference
        thumb = self._make_thumbnail(image)
        self._photo = ImageTk.PhotoImage(thumb)

        # Checkbox icons (keep references)
        self._check_off = ImageTk.PhotoImage(self._make_checkbox(False))
        self._check_on = ImageTk.PhotoImage(self._make_checkbox(True))

        # Eye icons (keep references)
        self._eye_on = ImageTk.PhotoImage(self._make_eye_icon(True))
        self._eye_off = ImageTk.PhotoImage(self._make_eye_icon(False))

        # --- widgets ---
        self._img_label = tk.Label(self, image=self._photo, bg="#2a2a2a")
        self._img_label.pack(padx=4, pady=4)

        # Checkbox in top-right corner — clickable
        self._cb_label = tk.Label(self._img_label, image=self._check_off,
                                  bg="#2a2a2a", cursor="hand2")
        self._cb_label.place(relx=1.0, rely=0.0, anchor="ne", x=-4, y=4)

        # Eye icon in top-left corner — clickable
        self._eye_label = tk.Label(
            self._img_label,
            image=self._eye_on if self.is_visible else self._eye_off,
            bg="#2a2a2a", cursor="hand2")
        self._eye_label.place(relx=0.0, rely=0.0, anchor="nw", x=4, y=4)

        # Bind click events
        # Clicking checkbox toggles selection
        self._cb_label.bind("<Button-1>", self._on_checkbox_click)
        # Clicking eye toggles visibility
        self._eye_label.bind("<Button-1>", self._on_eye_click)
        # Clicking image body toggles selection
        for w in (self, self._img_label):
            w.bind("<Button-1>", self._on_body_click)
        # Double-click on image body focuses window
        for w in (self, self._img_label):
            w.bind("<Double-Button-1>", self._on_dbl_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    # --- thumbnail creation ---
    def _make_thumbnail(self, image: Image.Image) -> Image.Image:
        w, h = image.size
        scale = min(self.THUMB_W / w, self.THUMB_H / h, 1.0)
        nw, nh = int(w * scale), int(h * scale)
        thumb = image.resize((nw, nh), Image.LANCZOS)
        canvas = Image.new("RGB", (self.THUMB_W, self.THUMB_H), (42, 42, 42))
        canvas.paste(thumb, ((self.THUMB_W - nw) // 2, (self.THUMB_H - nh) // 2))
        return canvas

    @staticmethod
    def _make_checkbox(checked: bool) -> Image.Image:
        sz = 22
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([1, 1, sz - 2, sz - 2],
                     fill=(76, 175, 80, 200) if checked else (60, 60, 60, 180),
                     outline="white", width=2)
        if checked:
            d.line([(5, 11), (9, 16), (17, 6)], fill="white", width=2)
        return img

    @staticmethod
    def _make_eye_icon(visible: bool) -> Image.Image:
        """Draw a small eye icon. Open eye = red (visible), closed eye = gray (hidden)."""
        sz = 22
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        cx, cy = sz // 2, sz // 2

        if visible:
            # Red open eye — highly visible
            color = (255, 60, 60, 240)
            d.ellipse([3, 6, sz - 4, sz - 6], outline=color, width=2)
            d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=color)
        else:
            # Gray closed eye
            color = (120, 120, 120, 160)
            d.line([(3, cy), (sz - 4, cy)], fill=color, width=2)
            d.arc([3, cy - 4, sz - 4, cy + 6], start=0, end=180, fill=color, width=2)

        return img

    # --- state ---
    def set_selected(self, val: bool):
        self.is_selected = val
        self._apply_visual()

    def set_visible(self, val: bool):
        """Update the eye icon and border to reflect visibility state."""
        self.is_visible = val
        self._eye_label.configure(image=self._eye_on if val else self._eye_off)
        border_color = "#e63946" if val else self._get_bg()
        self.configure(highlightbackground=border_color)

    def _get_bg(self):
        """Get background color based on selection state."""
        return "#1a4a1a" if self.is_selected else "#2a2a2a"

    def _apply_visual(self):
        bg = self._get_bg()
        self._cb_label.configure(
            image=self._check_on if self.is_selected else self._check_off,
            bg=bg)
        self.configure(bg=bg)
        self._img_label.configure(bg=bg)
        self._eye_label.configure(bg=bg)
        # Red inner border for visible windows
        border_color = "#e63946" if self.is_visible else bg
        self.configure(highlightbackground=border_color, highlightthickness=2)

    # --- events ---
    def _on_checkbox_click(self, event=None):
        """Toggle selection when checkbox is clicked."""
        self.is_selected = not self.is_selected
        self._apply_visual()
        if self.on_toggle:
            self.on_toggle(self.index)
        return "break"  # prevent event propagation to body

    def _on_eye_click(self, event=None):
        """Toggle visibility when eye icon is clicked."""
        self.is_visible = not self.is_visible
        self._eye_label.configure(image=self._eye_on if self.is_visible else self._eye_off)
        if self.on_visibility_toggle:
            self.on_visibility_toggle(self.index, self.is_visible)
        return "break"  # prevent event propagation to body

    def _on_body_click(self, _event=None):
        """Toggle selection when thumbnail body is clicked."""
        self.is_selected = not self.is_selected
        self._apply_visual()
        if self.on_toggle:
            self.on_toggle(self.index)

    def _on_dbl_click(self, _event=None):
        if self.on_double_click:
            self.on_double_click(self.index)

    def _on_enter(self, _event=None):
        """Hover highlight — preserve icon visibility and visible border."""
        if not self.is_selected:
            bg = "#3a3a3a"
            self.configure(bg=bg)
            self._img_label.configure(bg=bg)
            self._cb_label.configure(bg=bg)
            self._eye_label.configure(bg=bg)
            # Keep red border for visible windows
            border_color = "#e63946" if self.is_visible else bg
            self.configure(highlightbackground=border_color)

    def _on_leave(self, _event=None):
        """Restore normal background — preserve icon visibility and visible border."""
        bg = self._get_bg()
        self.configure(bg=bg)
        self._img_label.configure(bg=bg)
        self._cb_label.configure(bg=bg)
        self._eye_label.configure(bg=bg)
        # Keep red border for visible windows
        border_color = "#e63946" if self.is_visible else bg
        self.configure(highlightbackground=border_color)


class ImageWindowGallery(tk.Toplevel):
    """Fullscreen gallery view of all Image Windows with selection."""

    COLS = 4

    def __init__(self, app, on_selection_change=None):
        super().__init__(app.root)
        self.app = app
        self.on_selection_change = on_selection_change
        self.thumbnail_buttons: List[ThumbnailButton] = []
        self._valid_windows: list = []   # (original_index, window) pairs
        self.window_count = 0

        # Restore persisted selection from app (if any)
        if not hasattr(app, '_gallery_selected_indices'):
            app._gallery_selected_indices = set()
        self.selected_indices: Set[int] = app._gallery_selected_indices

        self._setup_window()
        self._create_ui()
        self._load_thumbnails()

    def _setup_window(self):
        self.title("Image Window Gallery")
        self.configure(bg="#1a1a1a")
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.bind("<Escape>", lambda _: self._close_gallery())
        self.bind("<F5>", lambda _: self._refresh_gallery())
        self.focus_force()

    # ------------------------------------------------------------------ UI
    def _create_ui(self):
        # Top bar
        top = tk.Frame(self, bg="#1a1a1a")
        top.pack(fill="x", padx=20, pady=(20, 5))
        tk.Label(top, text="Image Window Gallery", font=("Arial", 22, "bold"),
                 bg="#1a1a1a", fg="#ffffff").pack(side="left")
        self._info = tk.Label(top, text="", font=("Arial", 13),
                              bg="#1a1a1a", fg="#888888")
        self._info.pack(side="left", padx=20)

        # Scrollable area
        mid = tk.Frame(self, bg="#1a1a1a")
        mid.pack(fill="both", expand=True, padx=20, pady=5)

        self._canvas = tk.Canvas(mid, bg="#1a1a1a", highlightthickness=0)
        vsb = ttk.Scrollbar(mid, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg="#1a1a1a")
        self._inner_id = self._canvas.create_window((0, 0), window=self._inner,
                                                     anchor="nw")

        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._inner.bind("<Configure>",
                         lambda _: self._canvas.configure(
                             scrollregion=self._canvas.bbox("all")))
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Toolbar
        self._create_toolbar()

    def _create_toolbar(self):
        bar = tk.Frame(self, bg="#2a2a2a", height=70)
        bar.pack(fill="x", padx=20, pady=(5, 20))
        bar.pack_propagate(False)

        # On macOS, tk.Button ignores fg/bg — use ttk with custom styles
        _is_mac = sys.platform == "darwin"

        def _btn(parent, text, command, bg="#3a3a3a", fg="#ffffff"):
            """Create a styled button that works on both macOS and Windows."""
            if _is_mac:
                style_name = f"{text.replace(' ', '')}.TButton"
                style = ttk.Style()
                style.configure(style_name, background=bg, foreground=fg,
                                padding=(10, 4), font=("Arial", 11))
                style.map(style_name,
                          background=[("active", bg)],
                          foreground=[("active", fg)])
                btn = ttk.Button(parent, text=text, command=command,
                                 style=style_name, cursor="hand2")
            else:
                btn = tk.Button(parent, text=text, command=command,
                                bg=bg, fg=fg, relief="flat", padx=10,
                                cursor="hand2")
            return btn

        # Selection controls
        left = tk.Frame(bar, bg="#2a2a2a")
        left.pack(side="left", padx=15, fill="y")
        tk.Label(left, text="Selection:", font=("Arial", 12, "bold"),
                 bg="#2a2a2a", fg="#ffffff").pack(side="left", padx=(0, 8))
        for text, cmd in [("Select All", self._select_all),
                          ("Deselect All", self._deselect_all),
                          ("Invert", self._invert_selection)]:
            _btn(left, text, cmd).pack(side="left", padx=4, pady=15)
        self._sel_label = tk.Label(left, text="Selected: 0", font=("Arial", 12),
                                   bg="#2a2a2a", fg="#4CAF50")
        self._sel_label.pack(side="left", padx=15)

        # Visibility controls
        mid_sec = tk.Frame(bar, bg="#2a2a2a")
        mid_sec.pack(side="left", padx=15, fill="y")
        tk.Label(mid_sec, text="Visibility:", font=("Arial", 12, "bold"),
                 bg="#2a2a2a", fg="#ffffff").pack(side="left", padx=(0, 8))
        self._vis_label = tk.Label(mid_sec, text="Visible: 0/0", font=("Arial", 12),
                                   bg="#2a2a2a", fg="#8BC34A")
        self._vis_label.pack(side="left", padx=(0, 8))
        for text, cmd, color in [
            ("Show Selected Only", self._show_selected_only, "#FF9800"),
            ("Show All",           self._show_all,           "#8BC34A"),
            ("Hide All",           self._hide_all,           "#9E9E9E"),
        ]:
            _btn(mid_sec, text, cmd, bg=color).pack(side="left", padx=4, pady=15)

        # Action buttons
        right = tk.Frame(bar, bg="#2a2a2a")
        right.pack(side="right", padx=15, fill="y")
        for text, cmd, color in [
            ("Close Selected", self._action_close, "#f44336"),
            ("Save Selected",  self._action_save,  "#4CAF50"),
            ("Noting Selected", self._action_noting, "#2196F3"),
        ]:
            _btn(right, text, cmd, bg=color).pack(side="left", padx=4, pady=15)
        _btn(right, "Close (ESC)", self._close_gallery, bg="#555555"
             ).pack(side="right", padx=4, pady=15)

    # --------------------------------------------------------- canvas helpers
    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._inner_id, width=event.width)

    def _on_mousewheel(self, event):
        try:
            if self._canvas.winfo_exists():
                self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except tk.TclError:
            pass

    # --------------------------------------------------------- load thumbnails
    def _load_thumbnails(self):
        for w in self._inner.winfo_children():
            w.destroy()
        self.thumbnail_buttons.clear()
        self._valid_windows.clear()

        # Collect valid windows
        for i, win in enumerate(self.app.windows):
            try:
                if (hasattr(win, 'img_window') and
                        hasattr(win, 'img_label') and
                        hasattr(win.img_label, 'original_image') and
                        win.img_window.winfo_exists()):
                    self._valid_windows.append((i, win))
            except Exception:
                continue

        self.window_count = len(self._valid_windows)
        self._info.configure(text=f"Total: {self.window_count} windows")

        # Prune persisted selection: remove indices that no longer exist
        valid_idx_set = {i for i, _ in self._valid_windows}
        self.selected_indices &= valid_idx_set

        if not self._valid_windows:
            tk.Label(self._inner,
                     text="No image windows found.\n\nTake a screenshot first (Shift+A+S)",
                     font=("Arial", 16), bg="#1a1a1a", fg="#666666"
                     ).grid(row=0, column=0, columnspan=self.COLS, pady=80)
            return

        for c in range(self.COLS):
            self._inner.grid_columnconfigure(c, weight=1)

        for seq, (orig_idx, win) in enumerate(self._valid_windows):
            r, c = divmod(seq, self.COLS)
            is_vis = not getattr(win, 'is_hidden', False)
            btn = ThumbnailButton(
                self._inner,
                win.img_label.original_image,
                orig_idx,
                is_visible=is_vis,
                on_toggle=self._on_toggle,
                on_double_click=self._on_dbl_click,
                on_visibility_toggle=self._on_visibility_toggle,
            )
            # Restore persisted selection
            if orig_idx in self.selected_indices:
                btn.set_selected(True)
            btn.grid(row=r, column=c, padx=8, pady=8)
            self.thumbnail_buttons.append(btn)

        self._update_sel_label()

    # -------------------------------------------------------- eye icon sync
    def _sync_eye_icons(self):
        """Update all eye icons to match actual window visibility."""
        for btn in self.thumbnail_buttons:
            try:
                win = self.app.windows[btn.index]
                btn.set_visible(not win.is_hidden)
            except Exception:
                pass

    # ---------------------------------------------------------- selection ops
    def _on_toggle(self, index: int):
        if index in self.selected_indices:
            self.selected_indices.discard(index)
        else:
            self.selected_indices.add(index)
        self._update_sel_label()

    def _on_dbl_click(self, index: int):
        try:
            win = self.app.windows[index]
            if win.img_window.winfo_exists():
                win.img_window.lift()
                win.img_window.focus_force()
        except Exception:
            pass

    def _on_visibility_toggle(self, index: int, visible: bool):
        """Handle visibility toggle from eye icon click."""
        try:
            win = self.app.windows[index]
            if visible:
                win.show()
                win.gallery_hidden = False
            else:
                win.hide()
                win.gallery_hidden = True
        except Exception:
            pass
        self._update_sel_label()

    def _update_sel_label(self):
        vis_count = sum(1 for _, win in self._valid_windows if not getattr(win, 'is_hidden', False))
        self._sel_label.configure(
            text=f"Selected: {len(self.selected_indices)} / {self.window_count}")
        if hasattr(self, '_vis_label'):
            self._vis_label.configure(text=f"Visible: {vis_count}/{self.window_count}")

    def _select_all(self):
        self.selected_indices.clear()
        for btn in self.thumbnail_buttons:
            btn.set_selected(True)
            self.selected_indices.add(btn.index)
        self._update_sel_label()

    def _deselect_all(self):
        self.selected_indices.clear()
        for btn in self.thumbnail_buttons:
            btn.set_selected(False)
        self._update_sel_label()

    def _invert_selection(self):
        new = set()
        for btn in self.thumbnail_buttons:
            if btn.index in self.selected_indices:
                btn.set_selected(False)
            else:
                btn.set_selected(True)
                new.add(btn.index)
        self.selected_indices = new
        self._update_sel_label()

    # --------------------------------------------------------- visibility ops
    def _show_selected_only(self):
        """Show only selected image windows, hide all others."""
        for orig_idx, win in self._valid_windows:
            try:
                if orig_idx in self.selected_indices:
                    win.show()
                    win.gallery_hidden = False
                else:
                    win.hide()
                    win.gallery_hidden = True
            except Exception:
                pass
        self._sync_eye_icons()

    def _show_all(self):
        """Show all image windows."""
        for orig_idx, win in self._valid_windows:
            try:
                win.show()
                win.gallery_hidden = False
            except Exception:
                pass
        self._sync_eye_icons()

    def _hide_all(self):
        """Hide all image windows."""
        for orig_idx, win in self._valid_windows:
            try:
                win.hide()
                win.gallery_hidden = True
            except Exception:
                pass
        self._sync_eye_icons()

    # ---------------------------------------------------------- actions
    def _action_close(self):
        if not self.selected_indices:
            return
        n = len(self.selected_indices)
        if not messagebox.askyesno("Confirm", f"Close {n} selected window(s)?",
                                   parent=self):
            return
        for idx in sorted(self.selected_indices, reverse=True):
            try:
                win = self.app.windows[idx]
                if win.img_window.winfo_exists():
                    win.close()
            except Exception:
                pass
        # Remove closed indices from persisted selection
        self.selected_indices -= set(sorted(self.selected_indices, reverse=True))
        self.after(300, self._refresh_gallery)

    def _action_save(self):
        """Open save dialog for selected windows, defaulting to Cloud."""
        if not self.selected_indices:
            return
        selected = self.get_selected_windows()
        # Close gallery first — it's fullscreen topmost and would cover the dialog
        self._cleanup()
        self.destroy()
        self.app.session_manager.save_session_with_dialog(
            selected_windows=selected,
            default_save_target='cloud',
        )

    def _action_noting(self):
        """Open save dialog for selected windows, defaulting to Notes."""
        if not self.selected_indices:
            return
        selected = self.get_selected_windows()
        # Close gallery first — it's fullscreen topmost and would cover the dialog
        self._cleanup()
        self.destroy()
        self.app.session_manager.save_session_with_dialog(
            selected_windows=selected,
            default_save_target='notes',
        )

    # ---------------------------------------------------------- misc
    def _refresh_gallery(self):
        self._load_thumbnails()

    def _cleanup(self):
        """Unbind global mousewheel before destroying the window."""
        try:
            self._canvas.unbind_all("<MouseWheel>")
        except Exception:
            pass

    def _close_gallery(self):
        # Selection is already persisted via app._gallery_selected_indices (same object)
        self._cleanup()
        self.destroy()

    def get_selected_windows(self) -> List[Any]:
        out = []
        for idx in self.selected_indices:
            try:
                win = self.app.windows[idx]
                if win.img_window.winfo_exists():
                    out.append(win)
            except Exception:
                pass
        return out
