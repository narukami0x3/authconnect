import sys
import os
import winreg
import threading
import time
import tkinter as tk
from tkinter import messagebox
import requests
from PIL import Image, ImageDraw
import pystray

CHECK_URL = "http://connectivitycheck.gstatic.com/generate_204"
LOGIN_URL = "http://192.168.12.254:8002/index.php?zone=lan"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "AutoConnectService"

def set_startup(enable=True):
    """Adds or removes the compiled EXE path with --minimized flag to Windows Registry."""
    try:
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            exe_path = os.path.abspath(__file__)

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            # Pass --minimized argument so it starts hidden in system tray
            cmd = f'"{exe_path}" --minimized'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Registry update failed: {e}")

def create_tray_icon_image():
    image = Image.new('RGB', (64, 64), color=(76, 175, 80))
    d = ImageDraw.Draw(image)
    d.rectangle([16, 16, 48, 48], fill=(255, 255, 255))
    return image

class AutoConnectApp:
    def __init__(self, root, start_minimized=False):
        self.root = root
        self.root.title("Auto Connect")
        self.root.geometry("320x290")
        self.root.resizable(False, False)

        self.running = False
        self.tray_icon = None

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Content-Type": "application/x-www-form-urlencoded"
        })

        # UI Components
        tk.Label(root, text="Username:").pack(anchor="w", padx=20, pady=(15, 2))
        self.user_entry = tk.Entry(root, width=30)
        self.user_entry.insert(0, "")
        self.user_entry.pack(padx=20)

        tk.Label(root, text="Password:").pack(anchor="w", padx=20, pady=(10, 2))
        self.pass_entry = tk.Entry(root, show="*", width=30)
        self.pass_entry.insert(0, "")
        self.pass_entry.pack(padx=20)

        self.auto_start_var = tk.BooleanVar(value=True)
        self.auto_start_cb = tk.Checkbutton(root, text="Start with Windows (Hidden)", variable=self.auto_start_var)
        self.auto_start_cb.pack(pady=(10, 0))

        self.status_label = tk.Label(root, text="Status: Stopped", fg="red", font=("Arial", 10, "bold"))
        self.status_label.pack(pady=10)

        self.toggle_btn = tk.Button(root, text="TURN ON", bg="#4CAF50", fg="white", 
                                    font=("Arial", 11, "bold"), width=15, command=self.toggle_service)
        self.toggle_btn.pack()

        self.root.protocol('WM_DELETE_WINDOW', self.minimize_to_tray)

        # Handle launch mode
        if start_minimized:
            self.start_service()
            self.root.after(100, self.minimize_to_tray)

    def set_status(self, text, color):
        self.root.after(0, lambda: self.status_label.config(text=text, fg=color))

    def check_connection(self):
        try:
            res = self.session.get(CHECK_URL, timeout=1.0, allow_redirects=False)
            return res.status_code == 204
        except requests.RequestException:
            return False

    def send_login(self):
        payload = {
            "auth_user": self.user_entry.get(),
            "auth_pass": self.pass_entry.get(),
            "accept": "Login"
        }
        try:
            self.session.post(LOGIN_URL, data=payload, timeout=2.0)
        except requests.RequestException:
            pass

    def monitor_loop(self):
        is_connecting_attempt = False
        while self.running:
            online = self.check_connection()
            if online:
                self.set_status("Status: Connected", "green")
                is_connecting_attempt = False
                time.sleep(1)
            else:
                if not is_connecting_attempt:
                    self.set_status("Status: Reconnecting...", "orange")
                    is_connecting_attempt = True
                self.send_login()
                time.sleep(0.5)

    def start_service(self):
        set_startup(enable=self.auto_start_var.get())
        self.running = True
        self.toggle_btn.config(text="TURN OFF", bg="#f44336")
        self.user_entry.config(state="disabled")
        self.pass_entry.config(state="disabled")
        self.auto_start_cb.config(state="disabled")
        self.set_status("Status: Checking...", "orange")
        threading.Thread(target=self.monitor_loop, daemon=True).start()

    def toggle_service(self):
        if not self.running:
            if not self.user_entry.get() or not self.pass_entry.get():
                messagebox.showwarning("Warning", "Please enter credentials.")
                return
            self.start_service()
        else:
            self.running = False
            self.toggle_btn.config(text="TURN ON", bg="#4CAF50")
            self.user_entry.config(state="normal")
            self.pass_entry.config(state="normal")
            self.auto_start_cb.config(state="normal")
            self.set_status("Status: Stopped", "red")

    def show_window(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.deiconify)

    def quit_app(self, icon=None, item=None):
        self.running = False
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def minimize_to_tray(self):
        self.root.withdraw()
        menu = pystray.Menu(
            pystray.MenuItem("Show", self.show_window, default=True),
            pystray.MenuItem("Exit", self.quit_app)
        )
        self.tray_icon = pystray.Icon("AutoConnect", create_tray_icon_image(), "Auto Connect Service", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

if __name__ == "__main__":
    start_in_tray = "--minimized" in sys.argv
    root = tk.Tk()
    app = AutoConnectApp(root, start_minimized=start_in_tray)
    root.mainloop()