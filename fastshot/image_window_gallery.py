# fastshot/image_window_gallery.py

import math
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw
from typing import List, Set, Dict, Callable, Optional, Any
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SessionGroup:
    """A named sub-session within the gallery, holding specific image indices."""
    name: str
    indices: List[int]           # orig_idx values (indices into app.windows)
    collapsed: bool = False


# ---------------------------------------------------------------------------
# ThumbnailButton
# ---------------------------------------------------------------------------

class ThumbnailButton(tk.Frame):
    """A clickable thumbnail with checkbox overlay, stage icon, and right-click."""

    THUMB_W = 200
    THUMB_H = 150

    def __init__(self, parent, image: Image.Image, index: int,
                 on_stage: bool = True,
                 on_toggle=None, on_double_click=None,
                 on_stage_toggle=None,
                 on_right_click=None):
        super().__init__(parent, bg="#2a2a2a", bd=2, relief="flat",
                         highlightthickness=2, highlightbackground="#2a2a2a")
        self.index = index
        self.is_selected = False
        self.on_stage = on_stage   # whether this image is on-stage (shown on desktop)
        self.on_toggle = on_toggle
        self.on_double_click = on_double_click
        self.on_stage_toggle = on_stage_toggle
        self.on_right_click = on_right_click

        # Thumbnail image
        thumb = self._make_thumbnail(image)
        self._photo = ImageTk.PhotoImage(thumb)

        # Checkbox icons (selection)
        self._check_off = ImageTk.PhotoImage(self._make_checkbox(False))
        self._check_on = ImageTk.PhotoImage(self._make_checkbox(True))

        # Stage icons: red eye = on-stage, gray closed eye = off-stage
        self._stage_on = ImageTk.PhotoImage(self._make_stage_icon(True))
        self._stage_off = ImageTk.PhotoImage(self._make_stage_icon(False))

        # --- widgets ---
        self._img_label = tk.Label(self, image=self._photo, bg="#2a2a2a")
        self._img_label.pack(padx=4, pady=4)

        # Checkbox in top-right corner
        self._cb_label = tk.Label(self._img_label, image=self._check_off,
                                  bg="#2a2a2a", cursor="hand2")
        self._cb_label.place(relx=1.0, rely=0.0, anchor="ne", x=-4, y=4)

        # Stage icon in top-left corner
        self._stage_label = tk.Label(
            self._img_label,
            image=self._stage_on if self.on_stage else self._stage_off,
            bg="#2a2a2a", cursor="hand2")
        self._stage_label.place(relx=0.0, rely=0.0, anchor="nw", x=4, y=4)

        # Bind click events
        self._cb_label.bind("<Button-1>", self._on_checkbox_click)
        self._stage_label.bind("<Button-1>", self._on_stage_click)
        for w in (self, self._img_label):
            w.bind("<Button-1>", self._on_body_click)
        for w in (self, self._img_label):
            w.bind("<Double-Button-1>", self._on_dbl_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
        # Right-click
        for w in (self, self._img_label):
            w.bind("<Button-3>", self._on_right_click_event)
            w.bind("<Button-2>", self._on_right_click_event)
            w.bind("<Control-Button-1>", self._on_right_click_event)

        # Apply initial visual state (border, bg)
        self._apply_visual()

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
    def _make_stage_icon(on_stage: bool) -> Image.Image:
        """Draw eye icon. Red open eye = on-stage, gray closed eye = off-stage."""
        sz = 22
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        cx, cy = sz // 2, sz // 2
        if on_stage:
            # Red open eye — on-stage
            color = (255, 60, 60, 240)
            d.ellipse([3, 6, sz - 4, sz - 6], outline=color, width=2)
            d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=color)
        else:
            # Gray closed eye — off-stage
            color = (120, 120, 120, 160)
            d.line([(3, cy), (sz - 4, cy)], fill=color, width=2)
            d.arc([3, cy - 4, sz - 4, cy + 6], start=0, end=180, fill=color, width=2)
        return img

    # --- state ---
    def set_selected(self, val: bool):
        self.is_selected = val
        self._apply_visual()

    def set_on_stage(self, val: bool):
        self.on_stage = val
        self._stage_label.configure(image=self._stage_on if val else self._stage_off)
        border_color = "#e63946" if val else self._get_bg()
        self.configure(highlightbackground=border_color)

    def _get_bg(self):
        return "#f0d060" if self.is_selected else "#2a2a2a"

    def _apply_visual(self):
        bg = self._get_bg()
        self._cb_label.configure(
            image=self._check_on if self.is_selected else self._check_off,
            bg=bg)
        self.configure(bg=bg)
        self._img_label.configure(bg=bg)
        self._stage_label.configure(bg=bg)
        border_color = "#e63946" if self.on_stage else bg
        self.configure(highlightbackground=border_color, highlightthickness=2)

    # --- events ---
    def _on_checkbox_click(self, event=None):
        self.is_selected = not self.is_selected
        self._apply_visual()
        if self.on_toggle:
            self.on_toggle(self.index)
        return "break"

    def _on_stage_click(self, event=None):
        self.on_stage = not self.on_stage
        self._stage_label.configure(image=self._stage_on if self.on_stage else self._stage_off)
        if self.on_stage_toggle:
            self.on_stage_toggle(self.index, self.on_stage)
        return "break"

    def _on_body_click(self, _event=None):
        self.is_selected = not self.is_selected
        self._apply_visual()
        if self.on_toggle:
            self.on_toggle(self.index)

    def _on_dbl_click(self, _event=None):
        if self.on_double_click:
            self.on_double_click(self.index)

    def _on_right_click_event(self, event):
        if self.on_right_click:
            self.on_right_click(self.index, event)
        return "break"

    def _on_enter(self, _event=None):
        if not self.is_selected:
            bg = "#3a3a3a"
            self.configure(bg=bg)
            self._img_label.configure(bg=bg)
            self._cb_label.configure(bg=bg)
            self._stage_label.configure(bg=bg)
        self.configure(highlightbackground="#6ca6e0")

    def _on_leave(self, _event=None):
        bg = self._get_bg()
        self.configure(bg=bg)
        self._img_label.configure(bg=bg)
        self._cb_label.configure(bg=bg)
        self._stage_label.configure(bg=bg)
        border_color = "#e63946" if self.on_stage else bg
        self.configure(highlightbackground=border_color)


# ---------------------------------------------------------------------------
# SessionHeader
# ---------------------------------------------------------------------------

class SessionHeader(tk.Frame):
    """Header bar for a named session group, spanning all columns."""

    def __init__(self, parent, group_idx: int, name: str, image_count: int,
                 collapsed: bool = False,
                 on_rename=None, on_collapse_toggle=None,
                 on_save=None, on_noting=None, on_delete=None,
                 on_toggle_stage=None,
                 on_toggle_select=None,
                 on_header_right_click=None):
        super().__init__(parent, bg="#333333", padx=10, pady=6)
        self.group_idx = group_idx
        self._on_rename = on_rename
        self._on_collapse_toggle = on_collapse_toggle
        self._on_header_right_click = on_header_right_click

        # Collapse triangle
        self._collapse_btn = tk.Label(
            self, text=" \u25BC " if not collapsed else " \u25B6 ",
            bg="#333333", fg="#aaaaaa", font=("Arial", 12),
            cursor="hand2")
        self._collapse_btn.pack(side="left")
        self._collapse_btn.bind("<Button-1>", lambda _: self._toggle())

        # Session name — double-click to rename
        self._name_var = tk.StringVar(value=name)
        self._name_label = tk.Label(
            self, textvariable=self._name_var,
            bg="#333333", fg="#ffffff", font=("Arial", 13, "bold"),
            cursor="hand2")
        self._name_label.pack(side="left", padx=(4, 8))
        self._name_label.bind("<Double-Button-1>", lambda _: self._start_rename())

        # Image count
        self._count_label = tk.Label(
            self, text=f"({image_count} images)",
            bg="#333333", fg="#888888", font=("Arial", 11))
        self._count_label.pack(side="left")

        # Action buttons (right side)
        actions = tk.Frame(self, bg="#333333")
        actions.pack(side="right")

        _is_mac = sys.platform == "darwin"

        def _small_btn(parent, text, command, bg="#555555", fg="#ffffff"):
            if _is_mac:
                btn = ttk.Button(parent, text=text, command=command,
                                 cursor="hand2")
            else:
                btn = tk.Button(parent, text=text, command=command,
                                bg=bg, fg=fg, relief="flat", padx=6, pady=2,
                                font=("Arial", 9), cursor="hand2")
            return btn

        _small_btn(actions, "Select", on_toggle_select or (lambda: None),
                   bg="#795548").pack(side="left", padx=2)
        _small_btn(actions, "Stage", on_toggle_stage or (lambda: None),
                   bg="#FF9800").pack(side="left", padx=2)
        _small_btn(actions, "Save", on_save or (lambda: None),
                   bg="#4CAF50").pack(side="left", padx=2)
        _small_btn(actions, "Noting", on_noting or (lambda: None),
                   bg="#2196F3").pack(side="left", padx=2)
        _small_btn(actions, "Delete", on_delete or (lambda: None),
                   bg="#f44336").pack(side="left", padx=2)

        # Right-click on header
        for w in (self, self._name_label, self._count_label, self._collapse_btn):
            w.bind("<Button-3>", self._on_rc)
            w.bind("<Button-2>", self._on_rc)
            w.bind("<Control-Button-1>", self._on_rc)

        # Hover effect
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_rc(self, event):
        if self._on_header_right_click:
            self._on_header_right_click(self.group_idx, event)
        return "break"

    def _toggle(self):
        if self._on_collapse_toggle:
            self._on_collapse_toggle(self.group_idx)

    def _start_rename(self):
        new_name = simpledialog.askstring(
            "Rename Session", "Enter new session name:",
            initialvalue=self._name_var.get(),
            parent=self.winfo_toplevel())
        if new_name is not None and new_name.strip():
            self._name_var.set(new_name.strip())
            if self._on_rename:
                self._on_rename(self.group_idx, new_name.strip())

    def _on_enter(self, _event=None):
        self.configure(bg="#3a3a3a")
        self._collapse_btn.configure(bg="#3a3a3a")
        self._name_label.configure(bg="#3a3a3a")
        self._count_label.configure(bg="#3a3a3a")

    def _on_leave(self, _event=None):
        self.configure(bg="#333333")
        self._collapse_btn.configure(bg="#333333")
        self._name_label.configure(bg="#333333")
        self._count_label.configure(bg="#333333")


# ---------------------------------------------------------------------------
# ImageWindowGallery
# ---------------------------------------------------------------------------

class ImageWindowGallery(tk.Toplevel):
    """Fullscreen gallery view of all Image Windows with session split support."""

    COLS = 4

    def __init__(self, app, on_selection_change=None):
        super().__init__(app.root)
        self.app = app
        self.on_selection_change = on_selection_change
        self.thumbnail_buttons: List[ThumbnailButton] = []
        self._thumbnail_map: Dict[int, ThumbnailButton] = {}  # orig_idx -> btn
        self._valid_windows: list = []   # (original_index, window) pairs
        self.window_count = 0
        self._session_groups: List[SessionGroup] = []

        # Restore persisted selection from app
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

        _is_mac = sys.platform == "darwin"

        def _btn(parent, text, command, bg="#3a3a3a", fg="#ffffff"):
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

        # Stage controls
        mid_sec = tk.Frame(bar, bg="#2a2a2a")
        mid_sec.pack(side="left", padx=15, fill="y")
        tk.Label(mid_sec, text="Stage:", font=("Arial", 12, "bold"),
                 bg="#2a2a2a", fg="#ffffff").pack(side="left", padx=(0, 8))
        self._stage_label = tk.Label(mid_sec, text="On-Stage: 0/0", font=("Arial", 12),
                                     bg="#2a2a2a", fg="#8BC34A")
        self._stage_label.pack(side="left", padx=(0, 8))
        for text, cmd, color in [
            ("Stage Selected Only", self._stage_selected_only, "#FF9800"),
            ("Stage All",           self._stage_all,           "#8BC34A"),
            ("Off-Stage All",       self._offstage_all,        "#9E9E9E"),
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

    # ------------------------------------------------- session split persistence
    def _restore_splits(self):
        """Load session splits from app._gallery_session_splits and reconcile."""
        valid_idx_set = {i for i, _ in self._valid_windows}

        if not self.app._gallery_session_splits:
            all_indices = [i for i, _ in self._valid_windows]
            self._session_groups = [SessionGroup(name="Session 1", indices=all_indices)]
            return

        groups = []
        assigned = set()
        for entry in self.app._gallery_session_splits:
            name = entry.get("name", "Session")
            indices = [idx for idx in entry.get("indices", [])
                       if idx in valid_idx_set]
            collapsed = entry.get("collapsed", False)
            if indices:
                groups.append(SessionGroup(name=name, indices=indices, collapsed=collapsed))
                assigned.update(indices)

        # Unassigned windows go into the last group (or a new one)
        unassigned = [i for i, _ in self._valid_windows if i not in assigned]
        if unassigned:
            if groups:
                groups[-1].indices.extend(unassigned)
            else:
                groups.append(SessionGroup(name="Session 1", indices=unassigned))

        # Remove empty groups (keep at least one)
        groups = [g for g in groups if g.indices]
        if not groups:
            groups = [SessionGroup(name="Session 1", indices=[i for i, _ in self._valid_windows])]

        self._session_groups = groups

    def _persist_splits(self):
        """Save current session groups to app._gallery_session_splits."""
        self.app._gallery_session_splits = [
            {"name": g.name, "indices": list(g.indices), "collapsed": g.collapsed}
            for g in self._session_groups
        ]

    def _find_group_for_orig_idx(self, orig_idx: int) -> int:
        """Return the index in _session_groups that contains orig_idx."""
        for gi, group in enumerate(self._session_groups):
            if orig_idx in group.indices:
                return gi
        return 0

    # --------------------------------------------------------- load thumbnails
    def _load_thumbnails(self):
        for w in self._inner.winfo_children():
            w.destroy()
        self.thumbnail_buttons.clear()
        self._thumbnail_map.clear()
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

        # Prune persisted selection
        valid_idx_set = {i for i, _ in self._valid_windows}
        self.selected_indices &= valid_idx_set

        if not self._valid_windows:
            tk.Label(self._inner,
                     text="No image windows found.\n\nTake a screenshot first (Shift+A+S)",
                     font=("Arial", 16), bg="#1a1a1a", fg="#666666"
                     ).grid(row=0, column=0, columnspan=self.COLS, pady=80)
            return

        # Restore session splits
        self._restore_splits()

        for c in range(self.COLS):
            self._inner.grid_columnconfigure(c, weight=1)

        # Build all ThumbnailButton instances first (not yet placed)
        for orig_idx, win in self._valid_windows:
            is_on_stage = not getattr(win, 'gallery_hidden', False)
            btn = ThumbnailButton(
                self._inner,
                win.img_label.original_image,
                orig_idx,
                on_stage=is_on_stage,
                on_toggle=self._on_toggle,
                on_double_click=self._on_dbl_click,
                on_stage_toggle=self._on_stage_toggle,
                on_right_click=self._show_thumbnail_context_menu,
            )
            if orig_idx in self.selected_indices:
                btn.set_selected(True)
            self._thumbnail_map[orig_idx] = btn
            self.thumbnail_buttons.append(btn)

        # Place headers + thumbnails using session groups
        current_row = 0
        for gi, group in enumerate(self._session_groups):
            header = SessionHeader(
                self._inner,
                group_idx=gi,
                name=group.name,
                image_count=len(group.indices),
                collapsed=group.collapsed,
                on_rename=self._rename_group,
                on_collapse_toggle=self._toggle_collapse,
                on_save=lambda idx=gi: self._save_session(idx),
                on_noting=lambda idx=gi: self._noting_session(idx),
                on_delete=lambda idx=gi: self._delete_session(idx),
                on_toggle_stage=lambda idx=gi: self._toggle_session_stage(idx),
                on_toggle_select=lambda idx=gi: self._toggle_session_select(idx),
                on_header_right_click=self._show_header_context_menu,
            )
            header.grid(row=current_row, column=0, columnspan=self.COLS,
                        sticky="ew", padx=4, pady=(8, 2))
            current_row += 1

            if not group.collapsed:
                for seq, orig_idx in enumerate(group.indices):
                    btn = self._thumbnail_map.get(orig_idx)
                    if btn:
                        r = current_row + (seq // self.COLS)
                        c = seq % self.COLS
                        btn.grid(row=r, column=c, padx=8, pady=8)
                rows_used = math.ceil(len(group.indices) / self.COLS) if group.indices else 1
                current_row += rows_used
            else:
                for orig_idx in group.indices:
                    btn = self._thumbnail_map.get(orig_idx)
                    if btn:
                        btn.grid_forget()

        self._update_sel_label()

    # -------------------------------------------------------- stage icon sync
    def _sync_stage_icons(self):
        """Update all stage icons to match actual gallery_hidden state."""
        for btn in self.thumbnail_buttons:
            try:
                win = self.app.windows[btn.index]
                btn.set_on_stage(not getattr(win, 'gallery_hidden', False))
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

    def _on_stage_toggle(self, index: int, on_stage: bool):
        """Handle stage toggle from dot icon click on thumbnail."""
        try:
            win = self.app.windows[index]
            if on_stage:
                win.show()
                win.gallery_hidden = False
            else:
                win.hide()
                win.gallery_hidden = True
        except Exception:
            pass
        self._update_sel_label()

    def _update_sel_label(self):
        on_stage_count = sum(
            1 for _, win in self._valid_windows
            if not getattr(win, 'gallery_hidden', False))
        self._sel_label.configure(
            text=f"Selected: {len(self.selected_indices)} / {self.window_count}")
        if hasattr(self, '_stage_label'):
            self._stage_label.configure(text=f"On-Stage: {on_stage_count}/{self.window_count}")

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

    # ------------------------------------------------------------ stage ops
    def _stage_selected_only(self):
        """Put selected images on-stage, off-stage everything else."""
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
        self._sync_stage_icons()

    def _stage_all(self):
        """Put all images on-stage."""
        for orig_idx, win in self._valid_windows:
            try:
                win.show()
                win.gallery_hidden = False
            except Exception:
                pass
        self._sync_stage_icons()

    def _offstage_all(self):
        """Take all images off-stage."""
        for orig_idx, win in self._valid_windows:
            try:
                win.hide()
                win.gallery_hidden = True
            except Exception:
                pass
        self._sync_stage_icons()

    # ------------------------------------------------ session split operations
    def _split_after(self, orig_idx: int):
        """Split the session after the given image index."""
        gi = self._find_group_for_orig_idx(orig_idx)
        group = self._session_groups[gi]
        pos = group.indices.index(orig_idx)

        if pos == len(group.indices) - 1:
            return

        before = SessionGroup(
            name=group.name,
            indices=group.indices[:pos + 1],
            collapsed=group.collapsed,
        )
        after = SessionGroup(
            name=f"Session {len(self._session_groups) + 1}",
            indices=group.indices[pos + 1:],
        )

        self._session_groups[gi] = before
        self._session_groups.insert(gi + 1, after)
        self._persist_splits()
        self._load_thumbnails()

    def _remove_split(self, group_idx: int):
        """Merge this group with the previous one."""
        if group_idx <= 0 or group_idx >= len(self._session_groups):
            return

        prev = self._session_groups[group_idx - 1]
        curr = self._session_groups[group_idx]
        prev.indices.extend(curr.indices)
        self._session_groups.pop(group_idx)
        self._persist_splits()
        self._load_thumbnails()

    def _rename_group(self, group_idx: int, new_name: str):
        self._session_groups[group_idx].name = new_name
        self._persist_splits()

    def _toggle_collapse(self, group_idx: int):
        self._session_groups[group_idx].collapsed = not self._session_groups[group_idx].collapsed
        self._persist_splits()
        self._load_thumbnails()

    def _select_in_session(self, group_idx: int):
        group = self._session_groups[group_idx]
        for orig_idx in group.indices:
            self.selected_indices.add(orig_idx)
            btn = self._thumbnail_map.get(orig_idx)
            if btn:
                btn.set_selected(True)
        self._update_sel_label()

    def _deselect_in_session(self, group_idx: int):
        group = self._session_groups[group_idx]
        for orig_idx in group.indices:
            self.selected_indices.discard(orig_idx)
            btn = self._thumbnail_map.get(orig_idx)
            if btn:
                btn.set_selected(False)
        self._update_sel_label()

    def _toggle_session_select(self, group_idx: int):
        """Toggle: if all selected, deselect all; otherwise select all."""
        group = self._session_groups[group_idx]
        all_selected = all(idx in self.selected_indices for idx in group.indices)
        if all_selected:
            self._deselect_in_session(group_idx)
        else:
            self._select_in_session(group_idx)

    def _toggle_session_stage(self, group_idx: int):
        """Toggle: if all on-stage, take all off-stage; otherwise put all on-stage."""
        group = self._session_groups[group_idx]
        if not group.indices:
            return
        all_on_stage = True
        for orig_idx in group.indices:
            try:
                win = self.app.windows[orig_idx]
                if getattr(win, 'gallery_hidden', False):
                    all_on_stage = False
                    break
            except Exception:
                all_on_stage = False
                break

        for orig_idx in group.indices:
            try:
                win = self.app.windows[orig_idx]
                if all_on_stage:
                    win.hide()
                    win.gallery_hidden = True
                else:
                    win.show()
                    win.gallery_hidden = False
            except Exception:
                pass
        self._sync_stage_icons()
        self._update_sel_label()

    # ------------------------------------------------ per-session actions
    def _get_group_windows(self, group_idx: int) -> List[Any]:
        """Get list of valid ImageWindow objects for a session group."""
        windows = []
        for orig_idx in self._session_groups[group_idx].indices:
            try:
                win = self.app.windows[orig_idx]
                if win.img_window.winfo_exists():
                    windows.append(win)
            except Exception:
                pass
        return windows

    def _save_session(self, group_idx: int):
        windows = self._get_group_windows(group_idx)
        if not windows:
            return
        name = self._session_groups[group_idx].name
        self._cleanup()
        self.destroy()
        self.app.session_manager.save_session_with_dialog(
            selected_windows=windows,
            default_save_target='cloud',
            default_name=name,
        )

    def _noting_session(self, group_idx: int):
        windows = self._get_group_windows(group_idx)
        if not windows:
            return
        name = self._session_groups[group_idx].name
        self._cleanup()
        self.destroy()
        self.app.session_manager.save_session_with_dialog(
            selected_windows=windows,
            default_save_target='notes',
            default_name=name,
        )

    def _delete_session(self, group_idx: int):
        group = self._session_groups[group_idx]
        n = len(group.indices)
        if n == 0:
            return
        if not messagebox.askyesno(
                "Confirm", f"Delete {n} window(s) in '{group.name}'?",
                parent=self):
            return
        for orig_idx in sorted(group.indices, reverse=True):
            try:
                win = self.app.windows[orig_idx]
                if win.img_window.winfo_exists():
                    win.close()
            except Exception:
                pass
        self._session_groups.pop(group_idx)
        if not self._session_groups:
            self._session_groups = [SessionGroup(name="Session 1", indices=[])]
        self.selected_indices -= set(group.indices)
        self._persist_splits()
        self.after(300, self._refresh_gallery)

    # ------------------------------------------------ move / copy
    def _move_to_session(self, orig_idx: int, target_gi: int):
        source_gi = self._find_group_for_orig_idx(orig_idx)
        if source_gi == target_gi:
            return

        self._session_groups[source_gi].indices.remove(orig_idx)
        self._session_groups[target_gi].indices.append(orig_idx)

        if not self._session_groups[source_gi].indices and len(self._session_groups) > 1:
            self._session_groups.pop(source_gi)

        self._persist_splits()
        self._load_thumbnails()

    def _copy_to_session(self, orig_idx: int, target_gi: int):
        source_gi = self._find_group_for_orig_idx(orig_idx)
        if source_gi == target_gi:
            return

        if orig_idx not in self._session_groups[target_gi].indices:
            self._session_groups[target_gi].indices.append(orig_idx)

        self._persist_splits()
        self._load_thumbnails()

    # ------------------------------------------------ context menus
    def _show_thumbnail_context_menu(self, orig_idx: int, event):
        """Show right-click context menu for a thumbnail."""
        menu = tk.Menu(self, tearoff=0, bg="#3a3a3a", fg="#ffffff",
                       activebackground="#555555", activeforeground="#ffffff",
                       font=("Arial", 11))

        current_gi = self._find_group_for_orig_idx(orig_idx)

        menu.add_command(label="Split After This Image",
                         command=lambda: self._split_after(orig_idx))

        if len(self._session_groups) > 1:
            move_menu = tk.Menu(menu, tearoff=0, bg="#3a3a3a", fg="#ffffff",
                                activebackground="#555555", activeforeground="#ffffff",
                                font=("Arial", 11))
            copy_menu = tk.Menu(menu, tearoff=0, bg="#3a3a3a", fg="#ffffff",
                                activebackground="#555555", activeforeground="#ffffff",
                                font=("Arial", 11))

            for gi, group in enumerate(self._session_groups):
                if gi == current_gi:
                    continue
                label = group.name
                move_menu.add_command(
                    label=label,
                    command=lambda idx=orig_idx, target=gi: self._move_to_session(idx, target))
                copy_menu.add_command(
                    label=label,
                    command=lambda idx=orig_idx, target=gi: self._copy_to_session(idx, target))

            menu.add_separator()
            menu.add_cascade(label="Move to Session", menu=move_menu)
            menu.add_cascade(label="Copy to Session", menu=copy_menu)

        menu.tk_popup(event.x_root, event.y_root)

    def _show_header_context_menu(self, group_idx: int, event):
        """Show right-click context menu for a session header."""
        menu = tk.Menu(self, tearoff=0, bg="#3a3a3a", fg="#ffffff",
                       activebackground="#555555", activeforeground="#ffffff",
                       font=("Arial", 11))

        menu.add_command(label="Rename",
                         command=lambda: self._start_rename_dialog(group_idx))

        if group_idx > 0:
            menu.add_command(label="Remove Split (Merge Up)",
                             command=lambda: self._remove_split(group_idx))

        menu.add_separator()
        menu.add_command(label="Select All in Session",
                         command=lambda: self._select_in_session(group_idx))
        menu.add_command(label="Deselect All in Session",
                         command=lambda: self._deselect_in_session(group_idx))

        menu.tk_popup(event.x_root, event.y_root)

    def _start_rename_dialog(self, group_idx: int):
        new_name = simpledialog.askstring(
            "Rename Session", "Enter new session name:",
            initialvalue=self._session_groups[group_idx].name,
            parent=self)
        if new_name is not None and new_name.strip():
            self._session_groups[group_idx].name = new_name.strip()
            self._persist_splits()
            self._load_thumbnails()

    # ---------------------------------------------------------- toolbar actions
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
        self.selected_indices -= set(sorted(self.selected_indices, reverse=True))
        self.after(300, self._refresh_gallery)

    def _action_save(self):
        if not self.selected_indices:
            return
        selected = self.get_selected_windows()
        self._cleanup()
        self.destroy()
        self.app.session_manager.save_session_with_dialog(
            selected_windows=selected,
            default_save_target='cloud',
        )

    def _action_noting(self):
        if not self.selected_indices:
            return
        selected = self.get_selected_windows()
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
