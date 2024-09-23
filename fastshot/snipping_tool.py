import tkinter as tk
from PIL import Image
import mss
import mss.tools
import io

class SnippingTool:
    def __init__(self, root, monitors, on_screenshot):
        self.root = root
        self.monitors = monitors
        self.on_screenshot = on_screenshot
        self.overlays = []
        self.canvases = []
        self.rects = []

    def start_snipping(self):
        self.snipping = True
        self.overlays = []
        self.canvases = []
        self.rects = []

        for monitor in self.monitors:
            overlay = tk.Toplevel(self.root)
            overlay.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")
            overlay.configure(bg='blue')
            overlay.attributes('-alpha', 0.3)
            overlay.bind('<Escape>', self.exit_snipping)

            canvas = tk.Canvas(overlay, cursor="cross")
            canvas.pack(fill=tk.BOTH, expand=tk.TRUE)
            canvas.bind('<ButtonPress-1>', self.on_mouse_down)
            canvas.bind('<B1-Motion>', self.on_mouse_drag)
            canvas.bind('<ButtonRelease-1>', self.on_mouse_up)

            self.overlays.append(overlay)
            self.canvases.append(canvas)
            self.rects.append(None)

        self.root.update_idletasks()
        self.root.update()

        self.start_x = self.start_y = self.end_x = self.end_y = 0

    def exit_snipping(self, event=None):
        self.snipping = False
        for overlay in self.overlays:
            overlay.destroy()

    def on_mouse_down(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        for i in range(len(self.rects)):
            self.rects[i] = None

    def on_mouse_drag(self, event):
        for i, canvas in enumerate(self.canvases):
            if self.rects[i]:
                canvas.delete(self.rects[i])
            self.rects[i] = canvas.create_rectangle(
                self.start_x - canvas.winfo_rootx(),
                self.start_y - canvas.winfo_rooty(),
                event.x_root - canvas.winfo_rootx(),
                event.y_root - canvas.winfo_rooty(),
                outline='red'
            )

    def on_mouse_up(self, event):
        self.end_x = event.x_root
        self.end_y = event.y_root
        self.take_screenshot()
        self.exit_snipping()

    def take_screenshot(self):
        x1 = min(self.start_x, self.end_x)
        y1 = min(self.start_y, self.end_y)
        x2 = max(self.start_x, self.end_x)
        y2 = max(self.start_y, self.end_y)

        for overlay in self.overlays:
            overlay.withdraw()

        with mss.mss() as sct:
            monitor = {
                "top": y1,
                "left": x1,
                "width": x2 - x1,
                "height": y2 - y1
            }
            screenshot = sct.grab(monitor)
            img = mss.tools.to_png(screenshot.rgb, screenshot.size)

        for overlay in self.overlays:
            overlay.deiconify()

        img = Image.open(io.BytesIO(img))
        img = img.convert('RGB')
        self.on_screenshot(img)

