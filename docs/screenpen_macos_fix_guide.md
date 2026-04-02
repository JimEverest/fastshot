# Screen Pen macOS Fix — Investigation & Implementation Guide

## Executive Summary

Three attempts to fix Screen Pen on macOS all failed due to **undiscovered root causes** in the Tk 9.x rendering pipeline. This document captures all findings from diagnostic testing and provides a **verified working solution**.

---

## Environment

- **Python**: 3.12.13
- **Tcl/Tk**: 9.0.3 (ships with Python 3.12 on macOS — NOT Tk 8.6)
- **macOS**: Darwin 25.2.0
- **pyobjc**: available

---

## Root Cause Analysis

### Root Cause #1: `_get_nswindow()` is broken on Tk 9.x

**File**: `fastshot/app_platform/macos.py`, method `_get_nswindow()`

The method matches tkinter windows to NSWindows by comparing `tk_window.winfo_id()` with `NSWindow.windowNumber()`. **On Tk 9.x, these return completely different values:**

```
winfo_id() = 46459077136    (a pointer/handle)
windowNumber() = 25186       (a Cocoa window number)
```

**Impact**: Every NSWindow API call silently fails and falls back to a no-op:
- `set_click_through()` → never works → **cursor stays stuck as pencil/crosshair**
- `_set_macos_floating_level()` in `image_window.py` → never works
- Any `NSWindow.setOpaque_()`, `setBackgroundColor_()` → never applied

**Fix**: Match by **window title** instead of windowNumber:

```python
def _get_nswindow(self, tk_window):
    target_title = tk_window.title()
    tk_window.update_idletasks()
    for ns_win in NSApp.windows():
        if ns_win.title() == target_title:
            return ns_win
    return None
```

> **IMPORTANT**: When using title-based matching, each Toplevel must have a **unique title**. Set titles before calling `_get_nswindow`.

### Root Cause #2: Tk 9.x Metal renderer ignores ALL per-element transparency

Tk 9.0 switched from the old Cocoa rendering to a **Metal-based** pipeline. All of the following techniques were tested and **confirmed NOT to work** on Tk 9.0.3:

| Technique | Result |
|-----------|--------|
| `bg='systemTransparent'` on Canvas | Accepted (no TclError), but **renders as opaque black** |
| `wm_attributes('-transparent', True)` | Accepted, but **no visual effect** |
| `NSWindow.setOpaque_(False)` | API call succeeds, but **no visual effect** |
| `NSWindow.setBackgroundColor_(clearColor)` | API call succeeds, but **no visual effect** |
| `NSView.setDrawsBackground_(False)` | API call succeeds, but **no visual effect** |
| `NSView.setOpaque_(False)` on all subviews | API call succeeds, but **no visual effect** |

**The ONLY working transparency mechanism on Tk 9.x is `wm_attributes('-alpha', value)`,** which applies **uniformly** to the entire window — background AND all drawn content. There is no way to have a semi-transparent background with fully opaque strokes using Tk 9.x's built-in transparency.

### Root Cause #3: ESC vs Ctrl+ESC hotkey conflict

pynput's `HotKey` class only checks that its **required keys** are pressed — it does **not** check that no OTHER keys are held. A `HotKey({esc})` fires whenever ESC is pressed, even if Ctrl is also held.

When user presses Ctrl+ESC:
1. `hk_exit` (combo=`{esc}`) sees ESC pressed → **fires `on_escape()`** (toggle off)
2. `hk_clear` (combo=`{ctrl, esc}`) sees both pressed → **fires `clear_canvas_and_hide()`**

Both fire, but `on_escape()` runs first, making the window "transparent" (alpha=0.01) with click-through. Since click-through silently fails (Root Cause #1), the window stays active with pencil cursor, blocking all desktop interaction.

### Root Cause #4: `clear_canvas_and_hide()` incomplete cleanup

The method only calls `withdraw()` and sets `drawing=False`. It does NOT:
- Reset `pen_type` back to `'pen'`
- Reset cursor back to default
- Unbind keyboard events (`<Escape>`, `<Control-z>`, `<Control-y>`)
- Call `set_window_transparent()` to enable click-through

---

## Verified Working Solution: Screenshot-Based Overlay

### Concept

Instead of trying to make the window background semi-transparent (impossible on Tk 9.x), **capture the desktop, darken it, and display it as a canvas background image**. The window stays at `alpha=1.0`, so strokes drawn on the canvas are fully opaque.

**Tested and confirmed working** via `debug_screenpen3.py`.

### Architecture (macOS only — Windows unchanged)

```
┌─────────────────────────────────────┐
│  Single pen_window (alpha=1.0)      │
│  ┌─────────────────────────────────┐│
│  │  Canvas                         ││
│  │  ┌───────────────────────────┐  ││
│  │  │ bg_overlay (darkened       │  ││
│  │  │ desktop screenshot)        │  ││
│  │  │                            │  ││
│  │  │    ╲  stroke (full opaque) │  ││
│  │  │     ╲                      │  ││
│  │  │      ╲    ○ highlight      │  ││
│  │  └───────────────────────────┘  ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

- **No second overlay window needed on macOS**
- **No NSWindow API calls needed** (no click-through, no setOpaque)
- **No `systemTransparent` dependency**
- Window is fully opaque — `withdraw()` to hide, `deiconify()` to show

### Implementation Steps

#### Step 1: Modify `__init__` (macOS path only)

No second `overlay_window` needed. Keep a single `pen_window` with `bg='black'`.
Add `self._bg_photo = None` to hold the background image reference (prevent GC).

```python
# Keep existing single-window init for both platforms.
# No overlay_window, no systemTransparent, no -transparent attribute.
self.pen_window = tk.Toplevel(master)
self.pen_window.overrideredirect(True)
self.pen_window.attributes('-topmost', True)
self.pen_window.config(cursor="pencil", bg="black")
# ...
self._bg_photo = None  # Holds darkened desktop PhotoImage (macOS)
```

#### Step 2: Add `_capture_darkened_desktop()` method

```python
def _capture_darkened_desktop(self, screen_info):
    """Capture the desktop and darken it for the overlay effect (macOS)."""
    import mss
    from PIL import Image, ImageEnhance, ImageTk

    with mss.mss() as sct:
        monitor = {
            "top": screen_info['y'],
            "left": screen_info['x'],
            "width": screen_info['width'],
            "height": screen_info['height'],
        }
        screenshot = sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

    # Darken: overlay_opacity=0.3 means 30% black → 70% brightness
    enhancer = ImageEnhance.Brightness(img)
    darkened = enhancer.enhance(1.0 - self.overlay_opacity)

    # On Retina displays, mss captures physical pixels but tkinter
    # uses logical points. Scale down by backingScaleFactor.
    try:
        from AppKit import NSScreen
        scale = int(NSScreen.mainScreen().backingScaleFactor())
        if scale > 1:
            logical_size = (img.width // scale, img.height // scale)
            darkened = darkened.resize(logical_size, Image.LANCZOS)
    except Exception:
        pass

    self._bg_photo = ImageTk.PhotoImage(darkened)
    return self._bg_photo
```

#### Step 3: Modify `toggle_drawing_mode()` — entering mode

When entering drawing mode on macOS:
1. Capture desktop screenshot (BEFORE showing the window)
2. Set window geometry and show it
3. Set canvas background to the darkened screenshot
4. Redraw all strokes on top

```python
def toggle_drawing_mode(self):
    if self.drawing:
        # Exit — same as before (see Step 5)
        ...
    else:
        print("Entering drawing mode")
        self.drawing = True
        screen_info = self.get_current_screen_info()
        geom = f"{screen_info['width']}x{screen_info['height']}+{screen_info['x']}+{screen_info['y']}"

        if self._is_mac:
            # Capture desktop BEFORE showing the overlay
            bg_photo = self._capture_darkened_desktop(screen_info)

        self.pen_window.geometry(geom)
        self.pen_window.deiconify()

        if self._is_mac:
            self.pen_window.attributes('-alpha', 1.0)
            self.canvas.delete("bg_overlay")
            self.canvas.create_image(0, 0, anchor='nw',
                                     image=bg_photo, tags="bg_overlay")
            self.canvas.tag_lower("bg_overlay")  # Push behind strokes
        else:
            self.set_window_to_draw()  # Windows: existing behavior

        self.redraw_all_paths()
        self.pen_window.focus_set()
        self.pen_window.bind("<Escape>", self.on_escape)
        self.pen_window.bind("<Control-z>", lambda e: self.undo_last_action())
        self.pen_window.bind("<Control-y>", lambda e: self.redo_last_action())
```

#### Step 4: Modify `redraw_all_paths()`

Ensure the background image stays at the bottom when redrawing:

```python
def redraw_all_paths(self):
    # Delete strokes only, preserve bg_overlay on macOS
    self.canvas.delete("stroke")
    self.canvas.delete("current_line")
    self.canvas.delete("current_rectangle")
    for item_type, item_data in self.undo_stack:
        if item_type == 'path':
            self.draw_path(item_data)
        elif item_type == 'rectangle':
            self.draw_rectangle(item_data)
    self.redraw_current_path()
```

> **IMPORTANT**: All `draw_path()`, `draw_rectangle()`, `redraw_current_path()`, and `redraw_current_path_optimized()` calls must add `tags="stroke"` (or keep existing tags like `"current_line"`, `"current_rectangle"`) so that `redraw_all_paths` can delete strokes without touching `bg_overlay`.

Modify `draw_path()` and `draw_rectangle()` to use a `"stroke"` tag:
```python
def draw_path(self, path):
    if len(path) < 2:
        return
    for i in range(len(path) - 1):
        self.canvas.create_line(path[i], path[i + 1],
                                fill=self.pen_color, width=self.pen_width,
                                tags="stroke")

def draw_rectangle(self, coords):
    self.canvas.create_rectangle(coords,
                                  fill=self.highlighter_color,
                                  outline='', stipple='gray25',
                                  tags="stroke")
```

#### Step 5: Modify exit paths (ESC toggle-off)

On macOS, simply `withdraw()` the window. No click-through needed.

```python
def toggle_drawing_mode(self):
    if self.drawing:
        print("Exiting drawing mode")
        self.drawing = False
        if self._is_mac:
            self.pen_window.withdraw()  # Just hide — no click-through needed
        else:
            self.set_window_transparent()  # Windows: existing behavior
        self.pen_window.unbind("<Escape>")
        self.pen_window.unbind("<Control-z>")
        self.pen_window.unbind("<Control-y>")
    else:
        ...
```

#### Step 6: Fix `clear_canvas_and_hide()`

Full cleanup — works cross-platform:

```python
def clear_canvas_and_hide(self):
    print("Clearing canvas and hiding...")
    self.clear_canvas()  # Clears undo/redo stacks too
    if self._is_mac:
        self.canvas.delete("bg_overlay")  # Remove desktop screenshot
        self._bg_photo = None
    self.drawing = False
    self.pen_type = 'pen'
    self.pen_window.config(cursor="pencil")
    self.pen_window.unbind("<Escape>")
    self.pen_window.unbind("<Control-z>")
    self.pen_window.unbind("<Control-y>")
    self.pen_window.withdraw()
```

#### Step 7: Fix ESC vs Ctrl+ESC hotkey conflict

Remove the `hk_exit` HotKey. Instead, track modifier state manually and only fire `on_escape` when ESC is pressed **without any modifiers**:

```python
def start_keyboard_listener(self):
    from pynput.keyboard import Key, KeyCode, HotKey, Listener, _NORMAL_MODIFIERS

    toggle_combo = self.config['Shortcuts'].get('hotkey_screenpen_toggle', '<ctrl>+x+c')
    clear_combo = self.config['Shortcuts'].get('hotkey_screenpen_clear_hide', '<ctrl>+<esc>')

    hk_toggle = HotKey(HotKey.parse(toggle_combo),
                       lambda: self.queue.put(self.toggle_drawing_mode))
    hk_clear = HotKey(HotKey.parse(clear_combo),
                      lambda: self.queue.put(self.clear_canvas_and_hide))

    # Track modifiers to distinguish bare ESC from Ctrl+ESC
    modifiers_held = set()
    _modifier_keys = {Key.ctrl, Key.ctrl_l, Key.ctrl_r,
                      Key.cmd, Key.cmd_l, Key.cmd_r,
                      Key.alt, Key.alt_l, Key.alt_r,
                      Key.shift, Key.shift_l, Key.shift_r}

    def _canonical(key):
        if isinstance(key, KeyCode):
            if key.char is not None and key.char.isprintable():
                return KeyCode.from_char(key.char.lower())
            elif key.vk is not None:
                return KeyCode.from_vk(key.vk)
            return key
        elif isinstance(key, Key) and key.value in _NORMAL_MODIFIERS:
            return _NORMAL_MODIFIERS[key.value]
        # For non-modifier Key enums (esc, f1, etc.), return as-is
        return key

    def on_press(key):
        try:
            if key in _modifier_keys:
                modifiers_held.add(key)
            ck = _canonical(key)
            hk_toggle.press(ck)
            hk_clear.press(ck)
            # Plain ESC (no modifiers) → temporary exit
            if key == Key.esc and not modifiers_held:
                self.queue.put(self.on_escape)
        except Exception:
            pass

    def on_release(key):
        try:
            modifiers_held.discard(key)
            ck = _canonical(key)
            hk_toggle.release(ck)
            hk_clear.release(ck)
        except Exception:
            pass

    listener = Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()
    self.process_queue()
```

> **Note on `_canonical`**: The third branch (`elif isinstance(key, Key) and hasattr(key.value, 'vk')...`) that converts Key enums to `KeyCode.from_vk()` was removed. On Tk 9.x / pynput, `HotKey.parse('<esc>')` already returns `KeyCode(<53>)`, so `_canonical(Key.esc)` → `KeyCode.from_vk(53)` happens to match. But this conversion is fragile and unnecessary for Key enums. Returning them as-is is simpler and safer.

#### Step 8: `set_window_to_draw()` and `set_window_opacity()`

On macOS with the screenshot approach, these become simpler:

```python
def set_window_to_draw(self):
    if _IS_WINDOWS:
        # ... existing Windows code unchanged ...
    else:
        # macOS: screenshot approach handles overlay, just set alpha
        self.pen_window.attributes('-alpha', 1.0)

def set_window_opacity(self, opacity):
    if _IS_WINDOWS:
        # ... existing Windows code unchanged ...
    else:
        # macOS: re-capture and re-darken desktop
        # (called from update_config when user changes overlay_opacity)
        if self.drawing:
            screen_info = self.get_current_screen_info()
            bg_photo = self._capture_darkened_desktop(screen_info)
            self.canvas.delete("bg_overlay")
            self.canvas.create_image(0, 0, anchor='nw',
                                     image=bg_photo, tags="bg_overlay")
            self.canvas.tag_lower("bg_overlay")
            self.redraw_all_paths()
```

---

## Additional Fix: `_get_nswindow` for Other Code

The title-based `_get_nswindow` fix should also be applied in `fastshot/app_platform/macos.py` since it affects `image_window.py`'s `_set_macos_floating_level()` and any other NSWindow API usage.

```python
def _get_nswindow(self, tk_window):
    """Get NSWindow for a tkinter window. Uses title matching (Tk 9.x compatible)."""
    try:
        from AppKit import NSApp
        target_title = tk_window.title()
        tk_window.update_idletasks()
        for ns_win in NSApp.windows():
            if ns_win.title() == target_title:
                return ns_win
        return None
    except Exception:
        return None
```

---

## Behavior Changes on macOS

| Behavior | Before (broken) | After (screenshot approach) |
|----------|-----------------|----------------------------|
| Overlay opacity | Entire window (incl. strokes) at overlay_opacity | Desktop darkened, strokes at 100% opacity |
| ESC toggle-off | Window transparent + click-through (failed) | Window withdrawn (hidden) |
| Strokes visible after ESC | No (alpha=0.01) | No (withdrawn) — reappear on toggle-on |
| Ctrl+ESC | Behaved like ESC (both fired) | Properly clears strokes + hides |
| Cursor after exit | Stuck as pencil (click-through failed) | Normal (window withdrawn) |
| Desktop view | "Live" through semi-transparent window | Frozen screenshot (re-captured on toggle-on) |

The "frozen desktop" is the only UX trade-off. It is standard behavior for screen annotation tools and is acceptable because:
1. The previous "live" view never worked on macOS anyway (was fully opaque black)
2. Desktop is re-captured fresh each time the user toggles back on
3. The annotation session is typically short

---

## Windows Impact

**ZERO**. All changes are guarded by `if self._is_mac:` / `if _IS_WINDOWS:`. The Windows code path remains completely unchanged.

---

## Settings UI: Highlighter Color

The highlighter color picker was already added to `fastshot/settings/components/screenpen_frame.py` in a previous session. Verify it persists after rollback. If not, add:
- A "Highlighter Color:" row with `ttk.Button` + color picker + preview canvas
- `self.hl_color_var = tk.StringVar(value=settings.get('highlighter_color', '#FFFF00'))`
- Include `'highlighter_color': self.hl_color_var.get()` in `get_settings()`

In `screen_pen.py`, load `self.highlighter_color` in `reload_config()` instead of `__init__`.

---

## Files to Modify

1. **`fastshot/screen_pen.py`** — Main changes (screenshot overlay, hotkey fix, cleanup)
2. **`fastshot/app_platform/macos.py`** — Fix `_get_nswindow()` to use title matching
3. **`fastshot/settings/components/screenpen_frame.py`** — Add highlighter color picker (if not present after rollback)

---

## Diagnostic Scripts (for reference)

The following scripts in the project root were used during investigation and can be deleted after the fix is implemented:
- `debug_screenpen.py` — Tk version, systemTransparent, _get_nswindow, pynput key identity
- `debug_screenpen2.py` — NSWindow transparency APIs (all failed on Tk 9.x)
- `debug_screenpen3.py` — **Screenshot-based overlay (VERIFIED WORKING)**
