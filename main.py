import os
import json
import tkinter as tk
import pygame
from PIL import Image, ImageTk
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
            self.ctrl.play_track(self.songs, self.cur_idx, path, force_switch=True)


class NowPlaying(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx = 1  # Default to the Play/Pause button
        self.vol_steps = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # Left side: Album Art
        self.cover_label = tk.Label(self, bg=BG)
        self.cover_label.grid(row=0, column=0, padx=(0, 15), sticky="nw")

        # Right side: Info and Controls
        self.info = tk.Frame(self, bg=BG)
        self.info.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        self.info.grid_rowconfigure((0, 1, 2, 3), weight=0)

        # Song Title
        self.title = tk.Label(self.info, text="SONG NAME", font=("Courier", 18, "bold"),
                              bg=BG, fg=FG, wraplength=400, justify="left", anchor="w")
        self.title.grid(row=0, column=0, columnspan=2, sticky="sw", pady=(5, 1))

        # Progress Bar
        self.p_can = tk.Canvas(self.info, width=320, height=12, bg="#111", highlightthickness=0)
        self.p_can.grid(row=1, column=0, sticky="w", pady=1)
        self.p_bar = self.p_can.create_rectangle(0, 0, 0, 12, fill=FG)

        self.t_lbl = tk.Label(self.info, text="0:00/0:00", font=("Courier", 11), bg=BG, fg=FG)
        self.t_lbl.grid(row=1, column=1, sticky="w", padx=5)

        # Volume Bar
        self.v_can = tk.Canvas(self.info, width=320, height=12, bg="#111", highlightthickness=0)
        self.v_can.grid(row=2, column=0, sticky="w", pady=1)
        self.v_bar = self.v_can.create_rectangle(0, 0, 0, 12, fill=FG)

        self.v_lbl = tk.Label(self.info, text="100%", font=("Courier", 11), bg=BG, fg=FG)
        self.v_lbl.grid(row=2, column=1, sticky="w", padx=5)

        # Control Buttons Frame
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

    def refresh(self):
        if not self.ctrl.playlist: return
        song_file = self.ctrl.playlist[self.ctrl.idx]
        self.title.config(text=song_file.replace(".mp3", "").upper())

        # Load Cover Art
        img_p = os.path.join(self.ctrl.path, "cover.png")
        if os.path.exists(img_p):
            try:
                img = Image.open(img_p).resize((360, 360), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.cover_label.config(image=photo, text="")
                self.cover_label.image = photo
            except:
                self.cover_label.config(image="", text="[ IMAGE ERROR ]")
        else:
            self.cover_label.config(image="", text="[ NO COVER ]")

        self.update_vol_bar()
        self.update_visuals()
        self.update_ui_loop()

    def update_visuals(self):
        """Updates the look of the control buttons based on state and selection"""
        # Update Play/Pause icon
        icon = "▶" if self.ctrl.is_paused else "⏸"
        self.btns[1].config(text=icon)

        for i, btn in enumerate(self.btns):
            if i == self.cur_idx:
                btn.config(bg=FG, fg=BG)  # Highlighted
            elif i == 3 and self.ctrl.repeat_state:
                btn.config(bg=FG, fg=BG)  # Repeat Active
            else:
                btn.config(bg=BG, fg=FG)  # Idle

    def move(self, d, is_vertical=False):
        """Unified move command for both GPIO and Keyboard"""
        if is_vertical:
            # UP/DOWN handles Volume
            self.ctrl.vol_level = max(0.0, min(1.0, self.ctrl.vol_level + (-d * 0.05)))
            pygame.mixer.music.set_volume(self.ctrl.vol_level)
            self.update_vol_bar()
        else:
            # LEFT/RIGHT handles Button Selection
            new_idx = self.cur_idx + d
            if new_idx < 0:
                # Swipe Left from the first button to go back to Menu
                self.ctrl.show_frame("MP3Menu")
            elif new_idx >= len(self.btns):
                pass  # End of buttons
            else:
                self.cur_idx = new_idx
                self.update_visuals()

    def select(self):
        """MIDDLE/RETURN executes the highlighted button's command"""
        self.btn_data[self.cur_idx]["cmd"]()

    def update_vol_bar(self):
        perc = round(self.ctrl.vol_level * 100)
        self.v_can.coords(self.v_bar, 0, 0, (perc / 100.0) * 320, 12)
        self.v_lbl.config(text=f"{perc}%")

    def update_ui_loop(self):
        """Background loop to update the seek bar and time labels"""
        if self.ctrl.current_screen != "NowPlaying": return
        if pygame.mixer.music.get_busy() or self.ctrl.is_paused:
            try:
                from mutagen.mp3 import MP3
                path = os.path.join(self.ctrl.path, self.ctrl.playlist[self.ctrl.idx])
                total = MP3(path).info.length
                curr = pygame.mixer.music.get_pos() / 1000.0

                # Check for negative pos (mixer bug sometimes)
                if curr < 0: curr = 0

                self.p_can.coords(self.p_bar, 0, 0, min(1.0, curr / total) * 320, 12)
                self.t_lbl.config(
                    text=f"{int(curr // 60)}:{int(curr % 60):02d}/{int(total // 60)}:{int(total % 60):02d}")
            except:
                pass
        self.after(1000, self.update_ui_loop)

    def toggle(self):
        if self.ctrl.is_paused:
            pygame.mixer.music.unpause()
            self.ctrl.is_paused = False
        else:
            pygame.mixer.music.pause()
            self.ctrl.is_paused = True
        self.update_visuals()

    def toggle_repeat(self):
        self.ctrl.repeat_state = not self.ctrl.repeat_state
        self.update_visuals()

    def next(self):
        next_idx = (self.ctrl.idx + 1) % len(self.ctrl.playlist)
        self.ctrl.play_track(self.ctrl.playlist, next_idx, self.ctrl.path)

    def prev(self):
        prev_idx = (self.ctrl.idx - 1) % len(self.ctrl.playlist)
        self.ctrl.play_track(self.ctrl.playlist, prev_idx, self.ctrl.path)


class SettingsMenu(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx = 0
        self.btns = []
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
            ("🔄 NETWORK", lambda: self.ctrl.show_frame("NetworkBLEMenu")),
            ("⬅ BACK", lambda: self.ctrl.show_frame("MP3Menu"))
        ]
        self.build_btns(opts)

    def show_system(self):
        self.clear_menu()

        # 1. Safely get variables
        s_idx = getattr(self.ctrl, 'sleep_idx', 0)
        s_opts = getattr(self.ctrl, 'sleep_opts', ["OFF"])
        fps = getattr(self.ctrl, 'fps_cap', 30)
        res = getattr(self.ctrl, 'resolution_mode', "800x480")
        res_label = "NATIVE" if res == "native" else "800x480"

        # 2. Define options
        # Note: We use lambda for simple calls and functions for logic
        opts = [
            (f"SLEEP: {s_opts[s_idx]}", self.cycle_sl),
            (f"FPS: {fps}", self.cycle_fps),
            (f"RES: {res_label}", self.toggle_resolution),
            ("REBOOT", lambda: os.system("sudo reboot")),
            ("SHUTDOWN", lambda: os.system("sudo poweroff")),
            ("RESTART APP", lambda: os.system("sudo systemctl restart pidice")),
            ("⬅ BACK", self.show_main_settings)
        ]

        # 3. Draw them
        self.build_btns(opts)

    def show_audio(self):
        self.clear_menu()
        audio_out = getattr(self.ctrl, 'audio_output', 'jack')
        out_mode = "3.5mm" if audio_out == "jack" else "BT"
        opts = [
            (f"OUTPUT: {out_mode}", self.toggle_output),
            ("⬅ BACK", self.show_main_settings)
        ]
        self.build_btns(opts)

    def build_btns(self, opts):
        for text, cmd in opts:
            try:
                b = tk.Button(self.menu_container, text=text, font=("Courier", 14, "bold"),
                              bg=BG, fg=FG, activebackground=BG, activeforeground=FG,
                              bd=0, command=cmd, height=1)
                b.pack(pady=6, fill="x", padx=60)
                self.btns.append(b)
            except Exception as e:
                print(f"Error building button {text}: {e}")

        if self.btns:
            self.update_visuals()

    def toggle_resolution(self):
        curr = getattr(self.ctrl, 'resolution_mode', "800x480")
        self.ctrl.resolution_mode = "800x480" if curr == "native" else "native"
        self.ctrl.save_settings()
        self.show_system()

    def toggle_output(self):
        curr = getattr(self.ctrl, 'audio_output', 'jack')
        self.ctrl.audio_output = "bt" if curr == "jack" else "jack"
        self.ctrl.save_settings()
        self.show_audio()

    def cycle_sl(self):
        curr_idx = getattr(self.ctrl, 'sleep_idx', 0)
        opts_len = len(getattr(self.ctrl, 'sleep_opts', ["OFF"]))
        self.ctrl.sleep_idx = (curr_idx + 1) % opts_len
        self.ctrl.save_settings()
        self.show_system()

    def cycle_fps(self):
        fps_opts = [5, 10, 15, 20, 25, 30]
        curr_fps = getattr(self.ctrl, 'fps_cap', 30)
        next_idx = (fps_opts.index(curr_fps) + 1) % len(fps_opts) if curr_fps in fps_opts else 0
        self.ctrl.fps_cap = fps_opts[next_idx]
        self.ctrl.save_settings()
        self.show_system()

    def move(self, d, is_vertical=True):
        if is_vertical and self.btns:
            self.cur_idx = (self.cur_idx + d) % len(self.btns)
            self.update_visuals()
        elif not is_vertical and d < 0:  # Left = Back
            # If we aren't at the main menu, go back to main menu.
            # If we are at main menu, go back to MP3.
            has_back = False
            for i, b in enumerate(self.btns):
                if "BACK" in b.cget("text"):
                    self.cur_idx = i
                    self.select()
                    has_back = True
                    break

    def select(self):
        if self.btns:
            # Use after to prevent recursion issues during menu rebuilds
            self.after(10, self.btns[self.cur_idx].invoke)

    def update_visuals(self):
        for i, b in enumerate(self.btns):
            if i == self.cur_idx:
                b.config(bg=FG, fg=BG, activebackground=FG, activeforeground=BG)
            else:
                b.config(bg=BG, fg=FG, activebackground=BG, activeforeground=FG)


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
            ("📡 WIFI STATUS", self.show_wifi_info),
            ("🔵 BLE PAIRING", self.start_ble_mode),
            ("⬅ BACK", lambda: self.ctrl.show_frame("SettingsMenu"))
        ]
        self.build_btns(opts)

    def show_wifi_info(self):
        try:
            import subprocess
            cmd = "hostname -I | cut -d' ' -f1"
            ip = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
            if not ip: ip = "NOT CONNECTED"
        except:
            ip = "ERROR"

        CustomPopup(self.ctrl, "WIFI INFO", f"IP ADDRESS:\n{ip}")

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
            print(f"Pygame Init Error: {e}")

        self.title("PiDice MP3 Player")
        self.attributes('-fullscreen', True)
        self.config(cursor="none", bg=BG)

        self.update_idletasks()
        self.screen_w = self.winfo_screenwidth()
        self.screen_h = self.winfo_screenheight()

        self.playlist = []
        self.idx = 0
        self.path = ""
        self.vol_level = 0.5
        self.repeat_state = False
        self.is_paused = False
        self.current_screen = None
        self.sleep_idx = 0
        self.audio_output = "jack"
        self.fps_cap = 30
        self.resolution_mode = "800x480"
        self.sleep_opts = ["OFF", "15S", "30S", "1M", "2M"]
        self.img_cache = {}
        self.settings_file = os.path.join(os.path.dirname(__file__), "settings.json")

        self.load_settings()

        self.top_bar = TopBar(self, self)
        self.top_bar.pack(side="top", fill="x")

        self.status_label = tk.Label(self, text="", font=("Courier", 10, "bold"), bg=BG, fg=FG)
        self.status_label.place(relx=1.0, rely=0.05, anchor="ne", x=-10)

        self.container = tk.Frame(self, bg=BG)
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (MP3Menu, SettingsMenu, NetworkBLEMenu, NowPlaying):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # GPIO & Keyboard setup
        self.setup_gpio()
        self.bind_all("<Key>", self.handle_keys)

        self.show_frame("MP3Menu")
        self.check_pygame_events()

    def setup_gpio(self):
        try:
            from gpiozero import Button as GPIOButton
            # Map GPIO to internal keysyms
            pins = {22: "Up", 27: "Down", 17: "Left", 23: "Right", 24: "Return"}
            self.physical_buttons = []
            for pin, key in pins.items():
                btn = GPIOButton(pin, bounce_time=0.05)
                # Redirect GPIO press to the unified handle_keys method
                btn.when_pressed = lambda k=key: self.handle_keys(type('obj', (object,), {'keysym': k}))
                self.physical_buttons.append(btn)
        except Exception as e:
            print(f"GPIO Error: {e}")

    def handle_keys(self, event):
        if self.current_screen not in self.frames: return
        f = self.frames[self.current_screen]
        key = event.keysym

        # Unified mapping: calls move(delta, is_vertical) or select() on the current frame
        if key in ("Up", "KP_Up", "8"):
            f.move(-1, is_vertical=True)
        elif key in ("Down", "KP_Down", "2"):
            f.move(1, is_vertical=True)
        elif key in ("Left", "KP_Left", "4"):
            f.move(-1, is_vertical=False)
        elif key in ("Right", "KP_Right", "6"):
            f.move(1, is_vertical=False)
        elif key in ("Return", "KP_Enter", "5", "space"):
            f.select()
        elif key in ("s", "S"):
            self.show_frame("SettingsMenu")

    def show_frame(self, cont):
        self.current_screen = cont
        frame = self.frames[cont]
        frame.tkraise()
        frame.focus_force()
        if hasattr(frame, 'refresh'):
            self.after(20, frame.refresh)

    def play_track(self, playlist, index, path, *args, **kwargs):
        self.playlist, self.idx, self.path = playlist, index, path
        try:
            if not pygame.mixer.get_init(): pygame.mixer.init()
            pygame.mixer.music.load(os.path.join(path, playlist[index]))
            pygame.mixer.music.set_volume(self.vol_level)
            pygame.mixer.music.play()
            self.is_paused = False
            self.show_frame("NowPlaying")
        except Exception as e:
            print(f"Playback Error: {e}")

    def check_pygame_events(self):
        for event in pygame.event.get():
            if event.type == MUSIC_END:
                if not self.is_paused and self.playlist:
                    n = self.idx if self.repeat_state else (self.idx + 1) % len(self.playlist)
                    self.play_track(self.playlist, n, self.path)
        self.after(200, self.check_pygame_events)

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    d = json.load(f)
                    self.vol_level = d.get("vol_level", 0.5)
                    self.repeat_state = d.get("repeat", False)
                    self.sleep_idx = d.get("sleep_idx", 0)
                    self.audio_output = d.get("audio_output", "jack")
                    self.fps_cap = d.get("fps_cap", 30)
                    self.resolution_mode = d.get("resolution_mode", "800x480")
            except:
                pass


if __name__ == "__main__":
    app = App();
    app.mainloop()