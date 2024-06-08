from paddleocr import PaddleOCR
from PIL import Image
import win32clipboard
import tkinter as tk

class PluginOCR:
    def __init__(self):
        self.ocr_engine = PaddleOCR(use_angle_cls=True, lang='ch')

    def ocr(self, image):
        result = self.ocr_engine.ocr(image, cls=True)
        ocr_text = "\n".join([line[1][0] for res in result for line in res])
        self.copy_to_clipboard(ocr_text)
        return ocr_text

    def copy_to_clipboard(self, text):
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()

    def show_message(self, message, parent):
        label = tk.Label(parent, text=message, bg="yellow", fg="black", font=("Helvetica", 10))
        label.pack(side="bottom", fill="x")
        parent.after(3000, label.destroy)
