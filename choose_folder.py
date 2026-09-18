import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
path = filedialog.askdirectory(title="选择模型和缓存保存位置")
root.destroy()
print(path or "")
