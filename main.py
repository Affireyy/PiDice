import os
import json
import tkinter as tk
import pygame
from PIL import Image, ImageTk, ImageDraw
from mutagen.mp3 import MP3
import re
import time
from datetime import datetime
import random
import subprocess
from gpiozero import Button as GPIOButton

MUSIC_END = pygame.USEREVENT + 1

try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo

# --- Configuration & Styling ---
BG = "#2B2B2B"
FG = "#FF8200"


def natural_sort(l):
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


# --- Custom UI Components ---

class CustomPopup(tk.Toplevel):
    def __init__(self, parent, title, message):
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(bg=FG, padx=2, pady=2)

        w, h = 400, 200
        x = (parent.winfo_screenwidth() // 2) - (w // 2)
        y = (parent.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        inner = tk.Frame(self, bg=BG)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text=title, font=("Courier", 14, "bold"), bg=BG, fg=FG).pack(pady=10)
        tk.Label(inner, text=message, font=("Courier", 11), bg=BG, fg="white", wraplength=350).pack(pady=10)

        self.btn = tk.Button(inner, text="[ OK ]", font=("Courier", 12, "bold"),
                             bg=FG, fg=BG, bd=0, command=self.destroy)
        self.btn.pack(pady=20)

        self.focus_set()
        self.bind("<Return>", lambda e: self.destroy())
        self.bind("<KP_Enter>", lambda e: self.destroy())
        self.grab_set()


class TopBar(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=FG, height=30)
        self.ctrl = controller
        self.pack_propagate(False)

        self.lbl_time = tk.Label(self, font=("Courier", 12, "bold"), bg=FG, fg=BG)
        self.lbl_time.pack(side="left", padx=20)

        self.lbl_stats = tk.Label(self, font=("Courier", 10, "bold"), bg=FG, fg=BG)
        self.lbl_stats.pack(side="right", padx=20)

        self.update_bar()

    def update_bar(self):
        try:
            tz = zoneinfo.ZoneInfo("Europe/Stockholm")
            now = datetime.now(tz)
            t_str = now.strftime("%H:%M:%S")
        except:
            t_str = time.strftime("%H:%M:%S")

        self.lbl_time.config(text=t_str)

        try:
            import psutil
            cpu = psutil.cpu_percent()
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                temp = int(f.read()) / 1000
            self.lbl_stats.config(text=f"CPU: {cpu}% | TEMP: {temp:.1f}°C")
        except:
            self.lbl_stats.config(text="STATS ERROR")

        self.after(1000, self.update_bar)


# --- Screens ---

class MP3Menu(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.view_mode = "playlists"
        self.playlists = []
        self.cur_idx = 0
        self.sel_folder = ""
        self.canvas = None
        self.btns = []
        self.visible_count = 10
        self.songs = []
        self.after_id = None
        self.p_scroll_pos = 0
        self.s_scroll_pos = 0
        self.scroll_dir = 1
        self.wait_ticks = 0
        self.MAX_CHARS = 28
        self.TICK_SPEED = 150
        self.PAUSE_TICKS = 13

    def refresh(self):
        if self.after_id:
            self.after_cancel(self.after_id)
        for widget in self.winfo_children():
            widget.destroy()
        if self.view_mode == "playlists":
            self.show_playlists()
        else:
            self.show_songs_view()

    def show_playlists(self):
        path = "/home/dietpi/pidice/MP3s/"
        try:
            self.playlists = natural_sort([d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))])
        except:
            self.playlists = []
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, width=self.ctrl.screen_w, height=self.ctrl.screen_h)
        self.canvas.pack(fill="both", expand=True)
        self.draw_coverflow()

    def draw_coverflow(self):
        self.canvas.delete("all")
        if not self.playlists: return
        cx, cy = self.ctrl.screen_w // 2, (self.ctrl.screen_h // 2) - 60
        indices = [(self.cur_idx - 1) % len(self.playlists), self.cur_idx, (self.cur_idx + 1) % len(self.playlists)]
        for i, idx in enumerate(indices):
            folder = self.playlists[idx]
            sf = self.ctrl.screen_w / 800
            size = (int(300 * sf), int(300 * sf)) if i == 1 else (int(200 * sf), int(200 * sf))
            off = int(250 * sf)
            x = cx if i == 1 else (cx - off if i == 0 else cx + off)
            p = os.path.join("/home/dietpi/pidice/MP3s/", folder, "cover.png")

            cache_key = (p, size)
            if cache_key in self.ctrl.img_cache:
                photo = self.ctrl.img_cache[cache_key]
            else:
                try:
                    img = Image.open(p) if os.path.exists(p) else Image.new('RGB', size, color='#111')
                    img = img.resize(size, Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.ctrl.img_cache[cache_key] = photo
                except:
                    continue
            self.canvas.create_image(x, cy, image=photo)
        self.canvas.create_text(cx, cy + int(210 * sf), text=self.playlists[self.cur_idx].upper(),
                                font=("Courier", int(20 * sf), "bold"), fill=FG)

    def show_songs_view(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        cover_p = os.path.join("/home/dietpi/pidice/MP3s/", self.sel_folder, "cover.png")
        size = (300, 300)
        try:
            img = Image.open(cover_p) if os.path.exists(cover_p) else Image.new('RGB', size, color='#111')
            img = img.resize(size, Image.Resampling.LANCZOS)
            self.song_view_photo = ImageTk.PhotoImage(img)
            tk.Label(self, image=self.song_view_photo, bg=BG).grid(row=0, column=0, padx=20)
        except:
            pass

        right_container = tk.Frame(self, bg=BG)
        right_container.grid(row=0, column=1, sticky="nsew", padx=(10, 20))
        right_container.grid_columnconfigure(0, weight=1)
        right_container.grid_rowconfigure(0, weight=1)
        right_container.grid_rowconfigure(self.visible_count + 2, weight=1)

        self.p_name_lbl = tk.Label(right_container, text="", font=("Courier", 16, "bold underline"), bg=BG, fg=FG,
                                    anchor="w")
        self.p_name_lbl.grid(row=1, column=0, pady=(0, 10), sticky="ew")

        path = os.path.join("/home/dietpi/pidice/MP3s/", self.sel_folder)
        try:
            self.songs = natural_sort([f for f in os.listdir(path) if f.endswith(".mp3")])
        except:
            self.songs = []

        self.btns = []
        for i in range(self.visible_count):
            lbl = tk.Label(right_container, text="", font=("Courier", 14, "bold"), bg=BG, fg=FG, anchor="w", padx=10,
                            width=self.MAX_CHARS)
            lbl.grid(row=i + 2, column=0, pady=1, sticky="w")
            self.btns.append(lbl)
        self.update_list_display()
        self.scroll_loop()

    def update_list_display(self):
        start_idx = max(0, min(self.cur_idx - self.visible_count // 2, len(self.songs) - self.visible_count))
        self.s_scroll_pos, self.scroll_dir, self.wait_ticks = 0, 1, self.PAUSE_TICKS
        for i in range(self.visible_count):
            actual_idx = start_idx + i
            if actual_idx < len(self.songs):
                song_name = self.songs[actual_idx].replace(".mp3", "").upper()
                if actual_idx == self.cur_idx:
                    self.btns[i].config(text=song_name[:self.MAX_CHARS], bg=FG, fg=BG)
                else:
                    self.btns[i].config(text=song_name[:self.MAX_CHARS], bg=BG, fg=FG)
            else:
                self.btns[i].config(text="", bg=BG)

    def scroll_loop(self):
        p_full = self.sel_folder.upper()
        if len(p_full) > 22:
            self.p_scroll_pos = (self.p_scroll_pos + 1) % (len(p_full) + 5)
            start = max(0, self.p_scroll_pos)
            self.p_name_lbl.config(text=p_full[start:start + 22])
        else:
            self.p_name_lbl.config(text=p_full)
        if self.songs:
            s_full = self.songs[self.cur_idx].replace(".mp3", "").upper()
            if len(s_full) > self.MAX_CHARS:
                if self.wait_ticks > 0:
                    self.wait_ticks -= 1
                else:
                    self.s_scroll_pos += self.scroll_dir
                    max_scroll = len(s_full) - self.MAX_CHARS
                    if self.s_scroll_pos >= max_scroll:
                        self.s_scroll_pos, self.scroll_dir, self.wait_ticks = max_scroll, -1, self.PAUSE_TICKS
                    elif self.s_scroll_pos <= 0:
                        self.s_scroll_pos, self.scroll_dir, self.wait_ticks = 0, 1, self.PAUSE_TICKS
                display_text = s_full[self.s_scroll_pos: self.s_scroll_pos + self.MAX_CHARS]
                start_win = max(0, min(self.cur_idx - self.visible_count // 2, len(self.songs) - self.visible_count))
                idx_on_screen = self.cur_idx - start_win
                if 0 <= idx_on_screen < self.visible_count:
                    self.btns[idx_on_screen].config(text=display_text)
        self.after_id = self.after(self.TICK_SPEED, self.scroll_loop)

    def move(self, d, is_vertical=False):
        if self.view_mode == "playlists":
            if is_vertical:
                if d < 0:  # Up
                    self.ctrl.show_frame("SettingsMenu")
                else:  # Down
                    self.ctrl.show_frame("NowPlaying")
            elif self.playlists:
                self.cur_idx = (self.cur_idx + d) % len(self.playlists)
                self.draw_coverflow()
        else:
            if not is_vertical:
                self.view_mode = "playlists"
                self.refresh()
            elif self.songs:
                self.cur_idx = (self.cur_idx + d) % len(self.songs)
                self.update_list_display()

    def select(self):
        if self.view_mode == "playlists" and self.playlists:
            self.sel_folder = self.playlists[self.cur_idx]
            self.view_mode = "songs"
            self.cur_idx = 0
            self.refresh()
        elif self.view_mode == "songs" and self.songs:
            path = os.path.join("/home/dietpi/pidice/MP3s/", self.sel_folder)
            # Match the App.play_track(playlist, index, path, increment) signature
            self.ctrl.play_track(self.songs, self.cur_idx, path, increment=False)


class NowPlaying(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx = 1

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self.cover_label = tk.Label(self, bg=BG)
        self.cover_label.grid(row=0, column=0, padx=(0, 15), sticky="nw")

        self.info = tk.Frame(self, bg=BG)
        self.info.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        self.info.grid_rowconfigure((0, 1, 2, 3), weight=0)

        self.title = tk.Label(self.info, text="SONG NAME", font=("Courier", 18, "bold"),
                              bg=BG, fg=FG, wraplength=400, justify="left", anchor="w")
        self.title.grid(row=0, column=0, columnspan=2, sticky="sw", pady=(5, 1))

        self.p_can = tk.Canvas(self.info, width=320, height=12, bg="#111", highlightthickness=0)
        self.p_can.grid(row=1, column=0, sticky="w", pady=1)
        self.p_bar = self.p_can.create_rectangle(0, 0, 0, 12, fill=FG)

        self.t_lbl = tk.Label(self.info, text="0:00/0:00", font=("Courier", 11), bg=BG, fg=FG)
        self.t_lbl.grid(row=1, column=1, sticky="w", padx=5)

        self.v_can = tk.Canvas(self.info, width=320, height=12, bg="#111", highlightthickness=0)
        self.v_can.grid(row=2, column=0, sticky="w", pady=1)
        self.v_bar = self.v_can.create_rectangle(0, 0, 0, 12, fill=FG)

        self.v_lbl = tk.Label(self.info, text="100%", font=("Courier", 11), bg=BG, fg=FG)
        self.v_lbl.grid(row=2, column=1, sticky="w", padx=5)

        self.btn_f = tk.Frame(self.info, bg=BG)
        self.btn_f.grid(row=3, column=0, columnspan=2, sticky="nw", pady=(10, 0))

        self.btns = []
        self.btn_data = [
            {"icon": "⏮", "cmd": self.prev},
            {"icon": "▶", "cmd": self.toggle},
            {"icon": "⏭", "cmd": self.next},
            {"icon": "🔁", "cmd": self.toggle_repeat}
        ]

        for i, data in enumerate(self.btn_data):
            btn = tk.Label(self.btn_f, text=data["icon"], font=("Courier", 22, "bold"),
                           bg=BG, fg=FG, width=3, pady=3, highlightthickness=2, highlightbackground=FG)
            btn.grid(row=0, column=i, padx=6)
            self.btns.append(btn)

    def move(self, d, is_vertical=False):
        if is_vertical:
            # UP/DOWN = VOLUME PRESETS
            # We use -d because GPIO 'Up' sends -1, and we want to go 'up' the list
            self.ctrl.adjust_volume(-d)
        else:
            # LEFT/RIGHT = BUTTON NAVIGATION
            new_idx = self.cur_idx + d
            if new_idx < 0 or new_idx >= len(self.btns):
                # Edge reached: Go back to Menu
                self.ctrl.show_frame("MP3Menu")
            else:
                self.cur_idx = new_idx
                self.update_visuals()

    def update_vol_bar(self):
        vol_val = self.ctrl.vol_presets[self.ctrl.vol_idx]
        self.v_can.coords(self.v_bar, 0, 0, (vol_val / 100.0) * 320, 12)
        self.v_lbl.config(text=f"{vol_val}%")

    def select(self):
        self.btn_data[self.cur_idx]["cmd"]()

    def refresh(self):
        if not self.ctrl.playlist: return
        song_file = self.ctrl.playlist[self.ctrl.idx]
        self.title.config(text=song_file.replace(".mp3", "").upper())

        img_p = os.path.join(self.ctrl.path, "cover.png")
        if os.path.exists(img_p):
            try:
                img = Image.open(img_p).resize((360, 360), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.cover_label.config(image=photo)
                self.cover_label.image = photo
            except:
                pass

        self.update_vol_bar()
        self.update_visuals()
        self.update_ui_loop()

    def update_visuals(self):
        icon = "▶" if self.ctrl.is_paused else "⏸"
        self.btns[1].config(text=icon)
        for i, btn in enumerate(self.btns):
            if i == self.cur_idx:
                btn.config(bg=FG, fg=BG)
            elif i == 3 and self.ctrl.repeat_state:
                btn.config(bg=FG, fg=BG)
            else:
                btn.config(bg=BG, fg=FG)

    def update_ui_loop(self):
        if self.ctrl.current_screen != "NowPlaying": return
        if pygame.mixer.music.get_busy() or self.ctrl.is_paused:
            try:
                path = os.path.join(self.ctrl.path, self.ctrl.playlist[self.ctrl.idx])
                total = MP3(path).info.length
                curr = pygame.mixer.music.get_pos() / 1000.0
                if curr < 0: curr = 0
                self.p_can.coords(self.p_bar, 0, 0, min(1.0, curr / total) * 320, 12)
                self.t_lbl.config(
                    text=f"{int(curr // 60)}:{int(curr % 60):02d}/{int(total // 60)}:{int(total % 60):02d}")
            except:
                pass
        self.after(1000, self.update_ui_loop)

    def toggle(self):
        if self.ctrl.is_paused:
            pygame.mixer.music.unpause(); self.ctrl.is_paused = False
        else:
            pygame.mixer.music.pause(); self.ctrl.is_paused = True
        self.update_visuals()

    def toggle_repeat(self):
        self.ctrl.repeat_state = not self.ctrl.repeat_state
        self.update_visuals()

    def next(self):
        n = (self.ctrl.idx + 1) % len(self.ctrl.playlist)
        self.ctrl.play_track(self.ctrl.playlist, n, self.ctrl.path)

    def prev(self):
        n = (self.ctrl.idx - 1) % len(self.ctrl.playlist)
        self.ctrl.play_track(self.ctrl.playlist, n, self.ctrl.path)


class SettingsMenu(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx = 0
        self.btns = []
        self.bt_mode = "INPUT"
        self.menu_container = tk.Frame(self, bg=BG)
        self.menu_container.pack(fill="both", expand=True, pady=10)

    def refresh(self):
        self.show_main_settings()

    def clear_menu(self):
        for widget in self.menu_container.winfo_children():
            widget.destroy()
        self.btns, self.cur_idx = [], 0

    def show_main_settings(self):
        self.clear_menu()
        opts = [
            ("⚙ SYSTEM", self.show_system),
            ("🔊 AUDIO", self.show_audio),
            ("🔄 NETWORK", self.show_network_bt),
            ("⬅ BACK", lambda: self.ctrl.show_frame("MP3Menu"))
        ]
        self.build_btns(opts)

    def show_audio(self):
        self.clear_menu()
        devices = self.ctrl.get_system_outputs()
        current = getattr(self.ctrl, 'audio_output', '3.5mm Jack')
        opts = []
        for d in devices:
            label = f"● {d}" if d == current else f"○ {d}"
            opts.append((label, lambda dev=d: self.select_audio_device(dev)))
        opts.append(("⬅ BACK", self.show_main_settings))
        self.build_btns(opts)

    def select_audio_device(self, device):
        self.ctrl.audio_output = device
        self.ctrl.save_settings()
        self.show_audio()

    def show_network_bt(self):
        self.clear_menu()
        opts = [(f"BT MODE: {self.bt_mode}", self.toggle_bt_mode)]
        if self.bt_mode == "OUTPUT":
            devs = self.ctrl.get_bt_devices()
            for name, mac in devs:
                opts.append((f"PAIR: {name}", lambda m=mac: self.connect_bt(m)))
        else:
            opts.append(("STATUS: DISCOVERABLE", lambda: None))
        opts.append(("⬅ BACK", self.show_main_settings))
        self.build_btns(opts)

    def toggle_bt_mode(self):
        self.bt_mode = "OUTPUT" if self.bt_mode == "INPUT" else "INPUT"
        self.ctrl.set_bt_mode(self.bt_mode)
        self.show_network_bt()

    def connect_bt(self, mac):
        if mac:
            subprocess.run(["bluetoothctl", "pair", mac])
            subprocess.run(["bluetoothctl", "connect", mac])
            self.show_network_bt()

    def show_system(self):
        self.clear_menu()
        s_idx = self.ctrl.sleep_idx
        s_opts = self.ctrl.sleep_opts
        opts = [
            (f"SLEEP: {s_opts[s_idx]}", self.cycle_sl),
            ("REBOOT", lambda: os.system("sudo reboot")),
            ("SHUTDOWN", lambda: os.system("sudo poweroff")),
            ("⬅ BACK", self.show_main_settings)
        ]
        self.build_btns(opts)

    def build_btns(self, opts):
        for text, cmd in opts:
            b = tk.Button(self.menu_container, text=text, font=("Courier", 14, "bold"),
                          bg=BG, fg=FG, activebackground=BG, activeforeground=FG,
                          bd=0, command=cmd, height=1)
            b.pack(pady=4, fill="x", padx=60)
            self.btns.append(b)
        if self.btns: self.update_visuals()

    def cycle_sl(self):
        self.ctrl.sleep_idx = (self.ctrl.sleep_idx + 1) % len(self.ctrl.sleep_opts)
        self.ctrl.save_settings(); self.show_system()

    def move(self, d, is_vertical=True):
        if is_vertical and self.btns:
            self.cur_idx = (self.cur_idx + d) % len(self.btns)
            self.update_visuals()

    def select(self):
        if self.btns: self.after(10, self.btns[self.cur_idx].invoke)

    def update_visuals(self):
        for i, b in enumerate(self.btns):
            if i == self.cur_idx: b.config(bg=FG, fg=BG)
            else: b.config(bg=BG, fg=FG)


class NetworkBLEMenu(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx = 0
        self.btns = []
        self.menu_container = tk.Frame(self, bg=BG)
        self.menu_container.pack(fill="both", expand=True, pady=10)

    def refresh(self):
        self.show_main_network()

    def clear_menu(self):
        for widget in self.menu_container.winfo_children():
            widget.destroy()
        self.btns, self.cur_idx = [], 0

    def show_main_network(self):
        self.clear_menu()
        opts = [
            ("🔵 BLE PAIRING", self.start_ble_mode),
            ("⬅ BACK", lambda: self.ctrl.show_frame("SettingsMenu"))
        ]
        self.build_btns(opts)

    def start_ble_mode(self):
        self.ctrl.show_temporary_status("BLE SEARCHING...")
        # Placeholder for your specific BLE pairing logic
        pass

    def build_btns(self, opts):
        for text, cmd in opts:
            b = tk.Button(self.menu_container, text=text, font=("Courier", 14, "bold"),
                          bg=BG, fg=FG, activebackground=BG, activeforeground=FG,
                          bd=0, command=cmd, height=1)
            b.pack(pady=10, fill="x", padx=60)
            self.btns.append(b)
        self.update_visuals()

    def move(self, d, is_vertical=True):
        """Unified move command for GPIO and Keyboard"""
        if is_vertical:
            if self.btns:
                self.cur_idx = (self.cur_idx + d) % len(self.btns)
                self.update_visuals()
        else:
            # Horizontal (Left) logic: trigger back
            if d < 0:
                for i, b in enumerate(self.btns):
                    if "BACK" in b.cget("text"):
                        self.cur_idx = i
                        self.select()
                        break

    def select(self):
        if self.btns:
            self.btns[self.cur_idx].invoke()

    def update_visuals(self):
        for i, b in enumerate(self.btns):
            if i == self.cur_idx:
                b.config(bg=FG, fg=BG, activebackground=FG, activeforeground=BG)
            else:
                b.config(bg=BG, fg=FG, activebackground=BG, activeforeground=FG)

    def set_screen_state(self, on=True):
        """Turns the physical backlight on or off."""
        try:
            # Common path for Raspberry Pi/DSI screens
            path = "/sys/class/backlight/10-0045/bl_power"  # Standard for many DSI displays
            if not os.path.exists(path):
                path = "/sys/class/backlight/rpi_backlight/bl_power"

            val = "0" if on else "1"  # 0 is ON, 1 is OFF for bl_power
            with open(path, "w") as f:
                f.write(val)
        except Exception as e:
            # Fallback for HDMI or screens that support vcgencmd
            state = "1" if on else "0"
            os.system(f"vcgencmd display_power {state}")

    def reset_sleep_timer(self, event=None):
        """Resets the countdown every time a button is pressed."""
        self.last_input_time = time.time()
        if not self.screen_on:
            self.screen_on = True
            self.set_screen_state(True)

    def check_sleep_timer(self):
        """Background loop to check if we should dim the screen."""
        if self.sleep_idx > 0:  # If not "OFF"
            # Map "15S", "30S", "1M" etc to seconds
            times = {"15S": 15, "30S": 30, "1M": 60, "2M": 120}
            limit = times.get(self.sleep_opts[self.sleep_idx], 999)

            if time.time() - self.last_input_time > limit and self.screen_on:
                self.screen_on = False
                self.set_screen_state(False)

        self.after(1000, self.check_sleep_timer)

    def set_screen_state(self, on=True):
        """Fallback screen control for systems with no /sys/class/backlight/"""
        try:
            state = "1" if on else "0"
            # Primary method: vcgencmd (Works on most DietPi/Pi setups)
            os.system(f"vcgencmd display_power {state}")

            # Secondary method: xset (Forces X11 to blank/unblank the screen)
            # This is a safety net if vcgencmd doesn't trigger the backlight
            x_state = "on" if on else "off"
            os.system(f"DISPLAY=:0 xset dpms force {x_state}")
        except Exception as e:
            print(f"Screen Toggle Error: {e}")

            class BluetoothMenu(tk.Frame):
                def __init__(self, parent, controller):
                    super().__init__(parent, bg=BG)
                    self.ctrl = controller
                    self.mode = "INPUT"  # Starts as Receiver
                    self.devices = []
                    self.cur_idx = 0
                    self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
                    self.canvas.pack(fill="both", expand=True)

                def refresh(self):
                    self.draw_ui()

                def draw_ui(self):
                    self.canvas.delete("all")
                    cx = self.ctrl.screen_w // 2

                    # Mode Toggle Button
                    color = FG if self.cur_idx == 0 else "#444"
                    self.canvas.create_rectangle(cx - 100, 50, cx + 100, 100, outline=color, width=2)
                    self.canvas.create_text(cx, 75, text=f"MODE: {self.mode}", fill=FG, font=("Courier", 16))

                    if self.mode == "OUTPUT":
                        self.canvas.create_text(cx, 130, text="--- AVAILABLE DEVICES ---", fill=FG,
                                                font=("Courier", 12))
                        for i, dev in enumerate(self.devices):
                            y = 170 + (i * 40)
                            text_color = BG if (i + 1) == self.cur_idx else FG
                            bg_color = FG if (i + 1) == self.cur_idx else BG

                            if (i + 1) == self.cur_idx:
                                self.canvas.create_rectangle(100, y - 15, 700, y + 15, fill=FG)

                            self.canvas.create_text(cx, y, text=dev['name'], fill=text_color, font=("Courier", 14))
                    else:
                        self.canvas.create_text(cx, 240, text="PI IS DISCOVERABLE", fill=FG,
                                                font=("Courier", 20, "bold"))
                        self.canvas.create_text(cx, 280, text="Connect from your phone", fill=FG, font=("Courier", 14))

                def move(self, d, is_vertical=True):
                    limit = len(self.devices) if self.mode == "OUTPUT" else 0
                    self.cur_idx = (self.cur_idx + d) % (limit + 1)
                    self.draw_ui()

                def select(self):
                    if self.cur_idx == 0:
                        # Toggle Mode
                        self.mode = "OUTPUT" if self.mode == "INPUT" else "INPUT"
                        if self.mode == "OUTPUT":
                            self.devices = self.ctrl.get_bluetooth_devices()
                        self.ctrl.set_bluetooth_mode(self.mode.lower())
                    else:
                        # Pair with selected device
                        dev = self.devices[self.cur_idx - 1]
                        subprocess.run(["bluetoothctl", "pair", dev['mac']])
                        subprocess.run(["bluetoothctl", "connect", dev['mac']])
                    self.draw_ui()

# --- App Engine ---

MUSIC_END = pygame.USEREVENT + 1


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        try:
            pygame.mixer.pre_init(44100, -16, 2, 4096)
            pygame.init()
            pygame.mixer.music.set_endevent(MUSIC_END)
        except Exception as e:
            print(f"Mixer Init Error: {e}")

        self.title("PiDice MP3")
        self.attributes('-fullscreen', True)
        self.config(cursor="none", bg=BG)

        self.update_idletasks()
        self.screen_w = self.winfo_screenwidth()
        self.screen_h = self.winfo_screenheight()
        self.img_cache = {}

        self.vol_presets = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        self.vol_idx = 10
        self.vol_level = self.vol_presets[self.vol_idx] / 100.0

        self.playlist, self.idx, self.path = [], 0, ""
        self.repeat_state = False
        self.is_paused = False
        self.current_screen = None
        self.audio_output = "3.5mm Jack"
        self.fps_cap = 30
        self.resolution_mode = "800x480"

        self._switching = False
        self._processing_event = False

        self.sleep_idx = 0
        self.sleep_opts = ["OFF", "15S", "30S", "1M", "2M"]
        self.last_input_time = time.time()
        self.screen_on = True

        self.settings_file = os.path.join(os.path.dirname(__file__), "settings.json")
        self.load_settings()

        from __main__ import TopBar
        self.top_bar = TopBar(self, self)
        self.top_bar.pack(side="top", fill="x")

        self.container = tk.Frame(self, bg=BG)
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (MP3Menu, SettingsMenu, NowPlaying):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.setup_gpio()
        self.bind_all("<Key>", self.handle_keys)
        self.check_pygame_events()
        self.check_sleep_timer()

        self.set_screen_state(True)
        self.show_frame("MP3Menu")

    def get_bt_devices(self):
        try:
            subprocess.run(["bluetoothctl", "scan", "on"], timeout=2, capture_output=True)
            result = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True)
            devices = []
            for line in result.stdout.split('\n'):
                if "Device" in line:
                    parts = line.split(' ', 2)
                    devices.append((parts[2], parts[1]))
            return devices if devices else [("No Devices Found", "")]
        except:
            return [("Scan Error", "")]

    def get_system_outputs(self):
        try:
            result = subprocess.run(["aplay", "-l"], capture_output=True, text=True)
            outputs = ["3.5mm Jack"]
            for line in result.stdout.split('\n'):
                if "card" in line and "device" in line:
                    name = line.split('[')[1].split(']')[0] if '[' in line else "Hardware Output"
                    outputs.append(name)
            return list(dict.fromkeys(outputs))
        except:
            return ["3.5mm Jack"]

    def set_bt_mode(self, mode):
        if mode == "INPUT":
            os.system("sudo hciconfig hci0 class 0x20041C")
            subprocess.run(["bluetoothctl", "discoverable", "on"])
            subprocess.run(["bluetoothctl", "pairable", "on"])
        else:
            os.system("sudo hciconfig hci0 class 0x000100")
            subprocess.run(["bluetoothctl", "discoverable", "off"])

    def play_track(self, playlist, index, path, increment=False):
        self.playlist = playlist
        self.path = path
        if increment:
            next_idx = self.idx + 1
            if next_idx < len(self.playlist):
                self.idx = next_idx
            else:
                if self.repeat_state:
                    self.idx = 0
                else:
                    pygame.mixer.music.stop()
                    self._switching = self._processing_event = False
                    return
        else:
            self.idx = index
        try:
            pygame.mixer.music.set_endevent(0)
            track_file = os.path.join(self.path, self.playlist[self.idx])
            pygame.mixer.music.stop()
            pygame.mixer.music.load(track_file)
            pygame.mixer.music.set_volume(self.vol_level)
            pygame.mixer.music.play()
            pygame.mixer.music.set_endevent(MUSIC_END)
            self.is_paused = False
            self._switching = self._processing_event = False
            self.reset_sleep_timer()
            if self.current_screen == "NowPlaying":
                self.frames["NowPlaying"].refresh()
            else:
                self.show_frame("NowPlaying")
        except Exception as e:
            self._switching = self._processing_event = False
            print(f"Playback Error: {e}")

    def check_pygame_events(self):
        for event in pygame.event.get():
            if event.type == MUSIC_END:
                if self._processing_event or self.is_paused: continue
                if self.playlist:
                    self._processing_event = True
                    self._switching = True
                    self.after(200, lambda: self.play_track(self.playlist, self.idx, self.path, increment=True))
        self.after(100, self.check_pygame_events)

    def handle_keys(self, event):
        self.reset_sleep_timer()
        if self.current_screen not in self.frames: return
        f = self.frames[self.current_screen]
        key = event.keysym
        if key in ("Up", "8"):
            f.move(-1, True)
        elif key in ("Down", "2"):
            f.move(1, True)
        elif key in ("Left", "4"):
            f.move(-1, False)
        elif key in ("Right", "6"):
            f.move(1, False)
        elif key in ("Return", "5", "space"):
            f.select()
        elif key in ("s", "S"):
            self.show_frame("SettingsMenu")

    def show_frame(self, cont):
        self.current_screen = cont
        frame = self.frames[cont]
        frame.tkraise()
        if hasattr(frame, 'refresh'): self.after(20, frame.refresh)

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    d = json.load(f)
                    self.vol_idx = d.get("vol_idx", 10)
                    self.repeat_state = d.get("repeat", False)
                    self.sleep_idx = d.get("sleep_idx", 0)
                    self.audio_output = d.get("audio_output", "3.5mm Jack")
                    self.fps_cap = d.get("fps_cap", 30)
                    self.resolution_mode = d.get("resolution_mode", "800x480")
            except:
                pass

    def save_settings(self):
        try:
            data = {"vol_idx": self.vol_idx, "repeat": self.repeat_state,
                    "sleep_idx": self.sleep_idx, "audio_output": self.audio_output,
                    "fps_cap": self.fps_cap, "resolution_mode": self.resolution_mode}
            with open(self.settings_file, "w") as f:
                json.dump(data, f)
        except:
            pass

    def set_screen_state(self, on=True):
        state = "1" if on else "0"
        os.system(f"vcgencmd display_power {state}")

    def reset_sleep_timer(self):
        self.last_input_time = time.time()
        if not self.screen_on:
            self.screen_on = True
            self.set_screen_state(True)

    def check_sleep_timer(self):
        if self.sleep_idx > 0:
            times = {"15S": 15, "30S": 30, "1M": 60, "2M": 120}
            limit = times.get(self.sleep_opts[self.sleep_idx], 999)
            if time.time() - self.last_input_time > limit and self.screen_on:
                self.screen_on = False
                self.set_screen_state(False)
        self.after(1000, self.check_sleep_timer)

    def setup_gpio(self):
        try:
            pins = {22: "Up", 27: "Down", 17: "Left", 23: "Right", 24: "Return"}
            self.physical_buttons = []
            for pin, key in pins.items():
                btn = GPIOButton(pin, bounce_time=0.05)
                btn.when_pressed = lambda k=key: self.handle_keys(type('obj', (object,), {'keysym': k}))
                self.physical_buttons.append(btn)
        except:
            pass


if __name__ == "__main__":
    app = App();
    app.mainloop()