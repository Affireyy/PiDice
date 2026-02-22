import os
import sys
import json
import shutil
import tkinter as tk
from tkinter import messagebox
import pygame
from PIL import Image, ImageTk
from mutagen.mp3 import MP3
import re
import time
from datetime import datetime

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

    def refresh(self):
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
        cover_p = os.path.join("/home/dietpi/pidice/MP3s/", self.sel_folder, "cover.png")
        size = (350, 350)
        try:
            img = Image.open(cover_p) if os.path.exists(cover_p) else Image.new('RGB', size, color='#111')
            img = img.resize(size, Image.Resampling.LANCZOS)
            self.song_view_photo = ImageTk.PhotoImage(img)
            tk.Label(self, image=self.song_view_photo, bg=BG).grid(row=0, column=0, padx=20, pady=20)
        except:
            pass
        right_frm = tk.Frame(self, bg=BG)
        right_frm.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        tk.Label(right_frm, text=self.sel_folder.upper(), font=("Courier", 16, "bold"), bg=BG, fg=FG).pack(pady=10)
        path = os.path.join("/home/dietpi/pidice/MP3s/", self.sel_folder)
        try:
            songs = natural_sort([f for f in os.listdir(path) if f.endswith(".mp3")])
        except:
            songs = []
        self.btns = []
        for i, s in enumerate(songs):
            btn = tk.Button(right_frm, text=s.replace(".mp3", ""), font=("Courier", 11), bg=BG, fg=FG, bd=0,
                            anchor="w", command=lambda s_l=songs, idx=i, p=path: self.ctrl.play_track(s_l, idx, p,
                                                                                                      force_switch=True))
            btn.pack(pady=1, fill="x")
            self.btns.append(btn)
        back = tk.Button(right_frm, text="[ BACK ]", font=("Courier", 12, "bold"), bg=BG, fg=FG, bd=0,
                         command=self.back_to_playlists)
        back.pack(pady=15)
        self.btns.append(back)
        self.cur_idx = 0
        self.update_visuals()

    def back_to_playlists(self):
        self.view_mode = "playlists"
        self.refresh()

    def move(self, d, is_vertical=False):
        if self.view_mode == "playlists":
            if not is_vertical and self.playlists:
                self.cur_idx = (self.cur_idx + d) % len(self.playlists)
                self.draw_coverflow()
        else:
            if not is_vertical:
                self.back_to_playlists()
            elif self.btns:
                self.cur_idx = (self.cur_idx + d) % len(self.btns)
                self.update_visuals()

    def select(self):
        if self.view_mode == "playlists" and self.playlists:
            self.sel_folder = self.playlists[self.cur_idx]
            self.view_mode = "songs";
            self.refresh()
        elif self.btns:
            self.btns[self.cur_idx].invoke()

    def update_visuals(self):
        for i, b in enumerate(self.btns):
            b.config(bg=FG if i == self.cur_idx else BG, fg=BG if i == self.cur_idx else FG)


class NowPlaying(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx = 1
        self.grid_columnconfigure((0, 1), weight=1)
        self.cover_label = tk.Label(self, bg=BG)
        self.cover_label.grid(row=0, column=0, sticky="nsew", padx=20)
        self.info = tk.Frame(self, bg=BG)
        self.info.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.title = tk.Label(self.info, text="Song Name", font=("Courier", 18, "bold"), bg=BG, fg=FG, wraplength=300)
        self.title.pack(pady=10)
        self.t_frm = tk.Frame(self.info, bg=BG)
        self.t_frm.pack(fill="x")
        self.p_can = tk.Canvas(self.t_frm, height=10, bg="#111", highlightthickness=0)
        self.p_can.pack(side="left", fill="x", expand=True)
        self.p_bar = self.p_can.create_rectangle(0, 0, 0, 10, fill=FG)
        self.t_lbl = tk.Label(self.t_frm, text="-0:00", font=("Courier", 10), bg=BG, fg=FG, width=6)
        self.t_lbl.pack(side="right")
        self.v_frm = tk.Frame(self.info, bg=BG)
        self.v_frm.pack(fill="x", pady=10)
        self.v_can = tk.Canvas(self.v_frm, height=10, bg="#111", highlightthickness=0)
        self.v_can.pack(side="left", fill="x", expand=True)
        self.v_bar = self.v_can.create_rectangle(0, 0, 0, 10, fill=FG)
        self.v_lbl = tk.Label(self.v_frm, text="50%", font=("Courier", 10), bg=BG, fg=FG, width=6)
        self.v_lbl.pack(side="right")
        self.btn_f = tk.Frame(self.info, bg=BG)
        self.btn_f.pack(pady=10)
        self.btns = []
        labels = ["PREV", "PAUSE", "NEXT", "REPEAT: OFF", "BACK"]
        cmds = [self.prev, self.toggle, self.next, self.toggle_repeat, lambda: self.ctrl.show_frame(MP3Menu)]
        for i, lbl in enumerate(labels):
            btn = tk.Button(self.btn_f, text=lbl, font=("Courier", 8, "bold"), bg=BG, fg=FG, bd=0, command=cmds[i])
            btn.grid(row=0, column=i, padx=3)
            self.btns.append(btn)

    def refresh(self):
        if not self.ctrl.playlist:
            self.title.config(text="NOTHING IS PLAYING")
        else:
            song_file = self.ctrl.playlist[self.ctrl.idx]
            self.title.config(text=song_file.replace(".mp3", ""))
            img_p = os.path.join(self.ctrl.path, "cover.png")
            if os.path.exists(img_p):
                img = Image.open(img_p).resize((300, 300), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.cover_label.config(image=photo);
                self.cover_label.image = photo
            else:
                self.cover_label.config(image="", text="NO COVER")
        self.btns[3].config(text=f"REPEAT: {'ON' if self.ctrl.repeat_state else 'OFF'}")
        self.update_ui_loop();
        self.update_vol_bar();
        self.update_visuals()

    def update_vol_bar(self):
        ratio = self.ctrl.vol_level / 0.5
        self.v_can.coords(self.v_bar, 0, 0, ratio * self.v_can.winfo_width(), 10)
        self.v_lbl.config(text=f"{int(ratio * 100)}%")

    def move(self, d, is_vertical=False):
        if is_vertical:
            self.ctrl.vol_level = max(0, min(0.5, self.ctrl.vol_level + (d * -0.05)))
            pygame.mixer.music.set_volume(self.ctrl.vol_level)
            self.update_vol_bar();
            self.ctrl.save_settings()
        else:
            self.cur_idx = (self.cur_idx + d) % len(self.btns);
            self.update_visuals()

    def update_visuals(self):
        for i, b in enumerate(self.btns):
            b.config(bg=FG if i == self.cur_idx else BG, fg=BG if i == self.cur_idx else FG)

    def update_ui_loop(self):
        self.btns[1].config(text="PLAY" if self.ctrl.is_paused else "PAUSE")
        if pygame.mixer.music.get_busy():
            try:
                total = MP3(os.path.join(self.ctrl.path, self.ctrl.playlist[self.ctrl.idx])).info.length
                curr = pygame.mixer.music.get_pos() / 1000.0
                ratio = curr / total
                self.p_can.coords(self.p_bar, 0, 0, ratio * self.p_can.winfo_width(), 10)
                m, s = divmod(max(0, int(total - curr)), 60)
                self.t_lbl.config(text=f"-{m}:{s:02d}")
            except:
                pass
        if self.ctrl.current_screen == NowPlaying: self.after(1000, self.update_ui_loop)

    def toggle_repeat(self):
        self.ctrl.repeat_state = not self.ctrl.repeat_state
        self.refresh();
        self.ctrl.save_settings()

    def toggle(self):
        if self.ctrl.is_paused:
            pygame.mixer.music.unpause(); self.ctrl.is_paused = False
        else:
            pygame.mixer.music.pause(); self.ctrl.is_paused = True

    def next(self):
        if self.ctrl.playlist:
            n = (self.ctrl.idx + 1) % len(self.ctrl.playlist)
            self.ctrl.play_track(self.ctrl.playlist, n, self.ctrl.path, force_switch=True)

    def prev(self):
        if self.ctrl.playlist:
            n = (self.ctrl.idx - 1) % len(self.ctrl.playlist)
            self.ctrl.play_track(self.ctrl.playlist, n, self.ctrl.path, force_switch=True)

    def select(self):
        self.btns[self.cur_idx].invoke()


class SettingsMenu(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx, self.view = 0, "main"
        self.btns = []
        self.menu_container = tk.Frame(self, bg=BG)
        self.menu_container.pack(fill="both", expand=True, pady=20)

    def refresh(self):
        self.show_main_settings()

    def clear_menu(self):
        for widget in self.menu_container.winfo_children(): widget.destroy()
        self.btns, self.cur_idx = [], 0

    def show_main_settings(self):
        self.view = "main";
        self.clear_menu()
        opts = [("SYSTEM", self.show_system), ("AUDIO", self.show_audio), ("PLAYLISTS", self.show_playlists),
                ("NETWORK", lambda: self.ctrl.show_frame(NetworkLibrary)),
                ("BACK", lambda: self.ctrl.show_frame(MP3Menu))]
        self.build_btns(opts)

    def show_system(self):
        self.view = "system";
        self.clear_menu()
        res_label = "NATIVE" if self.ctrl.resolution_mode == "native" else "800x480"
        opts = [(f"SLEEP: {self.ctrl.sleep_opts[self.ctrl.sleep_idx]}", self.cycle_sl),
                (f"FPS CAP: {self.ctrl.fps_cap}", self.cycle_fps),
                (f"RESOLUTION: {res_label}", self.toggle_resolution),
                ("REBOOT", lambda: os.system("sudo reboot")),
                ("SHUTDOWN", lambda: os.system("sudo poweroff")),
                ("RESTART APP", self.ctrl.restart_app),
                ("BACK", self.show_main_settings)]
        self.build_btns(opts)

    def show_audio(self):
        self.view = "audio";
        self.clear_menu()
        out_mode = "3.5mm" if self.ctrl.audio_output == "jack" else "BT"
        opts = [(f"OUTPUT: {out_mode}", self.toggle_output), ("BACK", self.show_main_settings)]
        self.build_btns(opts)

    def show_playlists(self):
        self.view = "playlists";
        self.clear_menu()
        path = "/home/dietpi/pidice/MP3s/"
        try:
            dirs = natural_sort([d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))])
        except:
            dirs = []
        for folder in dirs:
            b = tk.Button(self.menu_container, text=f"DELETE: {folder}", font=("Courier", 10), bg=BG, fg="red",
                          command=lambda n=folder: CustomPopup(self.ctrl, "SAFETY", "Use CLI to delete."))
            b.pack(pady=2, fill="x", padx=50);
            self.btns.append(b)
        back_btn = tk.Button(self.menu_container, text="BACK", font=("Courier", 10), bg=BG, fg=FG,
                             command=self.show_main_settings)
        back_btn.pack(pady=10);
        self.btns.append(back_btn)
        self.update_visuals()

    def build_btns(self, opts):
        for text, cmd in opts:
            b = tk.Button(self.menu_container, text=text, font=("Courier", 10), bg=BG, fg=FG, bd=0, command=cmd)
            b.pack(pady=2, fill="x", padx=100);
            self.btns.append(b)
        self.update_visuals()

    def toggle_resolution(self):
        self.ctrl.resolution_mode = "800x480" if self.ctrl.resolution_mode == "native" else "native"
        self.ctrl.save_settings();
        CustomPopup(self.ctrl, "RESOLUTION", "Restart to apply.");
        self.show_system()

    def toggle_output(self):
        self.ctrl.audio_output = "bt" if self.ctrl.audio_output == "jack" else "jack"
        self.ctrl.save_settings();
        self.show_audio()

    def cycle_sl(self):
        self.ctrl.sleep_idx = (self.ctrl.sleep_idx + 1) % len(self.ctrl.sleep_opts)
        self.ctrl.save_settings();
        self.show_system()

    def cycle_fps(self):
        fps_opts = [5, 10, 15, 20, 25, 30]
        curr = fps_opts.index(self.ctrl.fps_cap) if self.ctrl.fps_cap in fps_opts else 5
        self.ctrl.fps_cap = fps_opts[(curr + 1) % len(fps_opts)]
        self.ctrl.save_settings();
        self.show_system()

    def move(self, d, is_vertical=True):
        if self.btns: self.cur_idx = (self.cur_idx + d) % len(self.btns); self.update_visuals()

    def select(self):
        if self.btns: self.btns[self.cur_idx].invoke()

    def update_visuals(self):
        for i, b in enumerate(self.btns):
            b.config(bg=FG if i == self.cur_idx else BG, fg=BG if i == self.cur_idx else FG)


class NetworkLibrary(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        tk.Label(self, text="NETWORK SYNC", font=("Courier", 16, "bold"), bg=BG, fg=FG).pack(pady=20)
        tk.Button(self, text="BACK", command=lambda: self.ctrl.show_frame(SettingsMenu)).pack()


# --- App Engine ---

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        try:
            os.nice(-10)
        except:
            pass
        pygame.mixer.pre_init(44100, -16, 2, 4096)
        pygame.mixer.init()
        self.settings_file = "/home/dietpi/pidice/settings.json"
        self.img_cache = {}
        self.load_settings()

        if self.resolution_mode == "800x480":
            self.attributes("-fullscreen", False);
            self.screen_w, self.screen_h = 800, 480
            self.geometry(f"{self.screen_w}x{self.screen_h}")
        else:
            self.attributes("-fullscreen", True);
            self.update_idletasks()
            self.screen_w, self.screen_h = self.winfo_screenwidth(), self.winfo_screenheight()

        self.configure(bg=BG);
        self.current_screen = None
        self.playlist, self.idx, self.path = [], 0, "";
        self.is_paused = False
        self.sleep_opts = ["OFF", "15m", "30m", "1h"]

        self.top_bar = TopBar(self, self);
        self.top_bar.pack(side="top", fill="x")
        self.container = tk.Frame(self, bg=BG, width=self.screen_w, height=self.screen_h - 30)
        self.container.pack(side="top", fill="both", expand=True);
        self.container.pack_propagate(False)

        self.frames = {}
        for F in (MP3Menu, NowPlaying, SettingsMenu, NetworkLibrary):
            frame = F(self.container, self);
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.bind("<Key>", self.handle_keys)
        self.show_frame(MP3Menu);
        self.check_music()

    def check_music(self):
        if not pygame.mixer.music.get_busy() and not self.is_paused and self.playlist:
            if self.repeat_state or self.idx < len(self.playlist) - 1:
                self.idx = (self.idx + 1) % len(self.playlist)
                self.play_track(self.playlist, self.idx, self.path, force_switch=False)
        self.after(1000, self.check_music)

    def show_frame(self, cont):
        frame = self.frames[cont];
        self.current_screen = cont
        frame.tkraise()
        if hasattr(frame, 'refresh'): frame.refresh()

    def handle_keys(self, event):
        f = self.frames[self.current_screen];
        key = event.keysym
        if key in ("Left", "KP_Left", "KP_4"):
            f.move(-1, False)
        elif key in ("Right", "KP_Right", "KP_6"):
            f.move(1, False)
        elif key in ("Up", "KP_Up", "KP_8"):
            if self.current_screen == MP3Menu and f.view_mode == "playlists":
                self.show_frame(SettingsMenu)
            else:
                f.move(-1, True)
        elif key in ("Down", "KP_Down", "KP_2"):
            if self.current_screen == MP3Menu and f.view_mode == "playlists":
                self.show_frame(NowPlaying)
            else:
                f.move(1, True)
        elif key in ("Return", "KP_Enter"):
            if hasattr(f, 'select'): f.select()
        elif key == "Escape":
            self.show_frame(MP3Menu)

    def play_track(self, playlist, index, path, force_switch=False):
        self.playlist, self.idx, self.path = playlist, index, path
        pygame.mixer.music.load(os.path.join(path, playlist[index]))
        pygame.mixer.music.set_volume(self.vol_level);
        pygame.mixer.music.play()
        self.is_paused = False
        if force_switch and self.current_screen != NowPlaying:
            self.show_frame(NowPlaying)
        elif self.current_screen == NowPlaying:
            self.frames[NowPlaying].refresh()

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    d = json.load(f)
                self.vol_level = d.get("vol_level", 0.25)
                self.repeat_state = d.get("repeat", False)
                self.sleep_idx = d.get("sleep_idx", 0)
                self.audio_output = d.get("audio_output", "jack")
                self.fps_cap = d.get("fps_cap", 30)
                self.resolution_mode = d.get("resolution_mode", "native")
            except:
                self.set_defaults()
        else:
            self.set_defaults()

    def save_settings(self):
        data = {"vol_level": self.vol_level, "repeat": self.repeat_state, "sleep_idx": self.sleep_idx,
                "audio_output": self.audio_output, "fps_cap": self.fps_cap, "resolution_mode": self.resolution_mode}
        with open(self.settings_file, "w") as f: json.dump(data, f)

    def restart_app(self):
        os.execv(sys.executable, ['python3'] + sys.argv)


if __name__ == "__main__":
    app = App();
    app.mainloop()