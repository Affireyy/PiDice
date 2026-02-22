import os
import sys
import json
import time
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import pygame
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
import io
import re
import threading
import shutil
from datetime import datetime
import zoneinfo

# --- HARDWARE & ENVIRONMENT CONFIGURATION ---
os.environ['GPIOZERO_PIN_FACTORY'] = 'lgpio'
try:
    from gpiozero import Button as PhysicalButton
except ImportError:
    PhysicalButton = None

# --- UI STYLING CONSTANTS ---
BG = "#2B2B2B"
FG = "#FF8200"


# --- UTILITIES ---
def natural_sort(l):
    """ Sorts a list in the way humans expect (e.g., 'song2' comes before 'song10'). """
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


def get_single_song_art(song_path):
    """ Extracts embedded ID3 album art from an MP3 file. """
    try:
        audio = MP3(song_path, ID3=ID3)
        for tag in audio.tags.values():
            if isinstance(tag, APIC):
                return Image.open(io.BytesIO(tag.data))
    except:
        pass
    return None


# --- UI COMPONENTS & SCREENS ---

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


class MP3Menu(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.view_mode = "playlists"
        self.playlists = []
        self.cur_idx = 0
        self.sel_folder = ""
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)

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
        self.canvas.pack()
        self.draw_coverflow()

    def draw_coverflow(self):
        self.canvas.delete("all")
        if not self.playlists: return

        center_x = self.ctrl.screen_w // 2
        center_y = (self.ctrl.screen_h // 2) - 40

        indices = [(self.cur_idx - 1) % len(self.playlists), self.cur_idx, (self.cur_idx + 1) % len(self.playlists)]

        for i, idx in enumerate(indices):
            folder = self.playlists[idx]
            scale_factor = self.ctrl.screen_w / 800
            size = (int(300 * scale_factor), int(300 * scale_factor)) if i == 1 else (int(200 * scale_factor),
                                                                                      int(200 * scale_factor))

            offset = int(250 * scale_factor)
            x = center_x if i == 1 else (center_x - offset if i == 0 else center_x + offset)

            p = os.path.join("/home/dietpi/pidice/MP3s/", folder, "cover.png")

            # Use Cache to stop the lag
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

            self.canvas.create_image(x, center_y, image=photo)
            if i == 0:
                self.img0 = photo
            elif i == 1:
                self.img1 = photo
            else:
                self.img2 = photo

        self.canvas.create_text(center_x, center_y + int(200 * scale_factor),
                                text=self.playlists[self.cur_idx].upper(),
                                font=("Courier", int(18 * scale_factor), "bold"), fill=FG)

    def show_songs_view(self):
        tk.Label(self, text=f"FOLDER: {self.sel_folder}", font=("Courier", 16, "bold"), bg=BG, fg=FG).pack(pady=10)
        path = os.path.join("/home/dietpi/pidice/MP3s/", self.sel_folder)
        try:
            songs = natural_sort([f for f in os.listdir(path) if f.endswith(".mp3")])
        except:
            songs = []

        self.btns = []
        for i, s in enumerate(songs):
            btn = tk.Button(self, text=s.replace(".mp3", ""), font=("Courier", 12), bg=BG, fg=FG, bd=0,
                            command=lambda s_list=songs, idx=i, p=path: self.ctrl.play_track(s_list, idx, p))
            btn.pack(pady=2, fill="x", padx=50)
            self.btns.append(btn)

        back = tk.Button(self, text="BACK", font=("Courier", 12, "bold"), bg=BG, fg=FG, bd=0,
                         command=self.back_to_playlists)
        back.pack(pady=20)
        self.btns.append(back)
        self.update_visuals()

    def back_to_playlists(self):
        self.view_mode = "playlists"
        self.refresh()

    def move(self, d, is_vertical=False):
        if self.view_mode == "playlists":
            if not is_vertical:  # Only move left/right in coverflow
                if self.playlists:
                    self.cur_idx = (self.cur_idx + d) % len(self.playlists)
                    self.draw_coverflow()
        else:
            if self.btns:
                self.cur_idx = (self.cur_idx + d) % len(self.btns)
                self.update_visuals()

    def select(self):
        if self.view_mode == "playlists":
            if self.playlists:
                self.sel_folder = self.playlists[self.cur_idx]
                self.view_mode = "songs"
                self.cur_idx = 0
                self.refresh()
        else:
            if self.btns:
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

        self.p_can = tk.Canvas(self.t_frm, height=10, bg="#333", highlightthickness=0)
        self.p_can.pack(side="left", fill="x", expand=True)
        self.p_bar = self.p_can.create_rectangle(0, 0, 0, 10, fill=FG)

        self.t_lbl = tk.Label(self.t_frm, text="-0:00", font=("Courier", 10), bg=BG, fg=FG, width=6)
        self.t_lbl.pack(side="right")

        self.v_frm = tk.Frame(self.info, bg=BG)
        self.v_frm.pack(fill="x", pady=10)

        self.v_can = tk.Canvas(self.v_frm, height=10, bg="#333", highlightthickness=0)
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
            self.cover_label.config(image="", text="")
        else:
            song_file = self.ctrl.playlist[self.ctrl.idx]
            self.title.config(text=song_file.replace(".mp3", ""))
            img = None
            if "(METADATA)" in self.ctrl.path.upper():
                img = get_single_song_art(os.path.join(self.ctrl.path, song_file))
            else:
                img_p = os.path.join(self.ctrl.path, "cover.png")
                if os.path.exists(img_p):
                    img = Image.open(img_p)

            if img:
                try:
                    ir = img.resize((300, 300), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(ir)
                    self.cover_label.config(image=photo)
                    self.cover_label.image = photo
                except:
                    pass
            else:
                self.cover_label.config(image="", text="NO COVER")

        self.btns[3].config(text=f"REPEAT: {'ON' if self.ctrl.repeat_state else 'OFF'}")
        self.update_ui_loop()
        self.update_vol_bar()
        self.update_visuals()

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
        if self.ctrl.current_screen == NowPlaying:
            self.after(1000, self.update_ui_loop)

    def update_vol_bar(self):
        ratio = self.ctrl.vol_level / 0.5
        self.v_can.coords(self.v_bar, 0, 0, ratio * self.v_can.winfo_width(), 10)
        self.v_lbl.config(text=f"{int(ratio * 100)}%")

    def move(self, d, is_vertical=False):
        if is_vertical:
            # Vertical adjusts volume
            self.ctrl.vol_level = max(0, min(0.5, self.ctrl.vol_level + (d * -0.05)))
            pygame.mixer.music.set_volume(self.ctrl.vol_level)
            self.update_vol_bar()
            self.ctrl.save_settings()
        else:
            # Horizontal navigates buttons
            self.cur_idx = (self.cur_idx + d) % len(self.btns)
            self.update_visuals()

    def select(self):
        self.btns[self.cur_idx].invoke()

    def update_visuals(self):
        for i, b in enumerate(self.btns):
            b.config(bg=FG if i == self.cur_idx else BG, fg=BG if i == self.cur_idx else FG)

    def toggle_repeat(self):
        self.ctrl.repeat_state = not self.ctrl.repeat_state
        self.btns[3].config(text=f"REPEAT: {'ON' if self.ctrl.repeat_state else 'OFF'}")
        self.ctrl.save_settings()

    def toggle(self):
        if self.ctrl.is_paused:
            pygame.mixer.music.unpause()
            self.ctrl.is_paused = False
        else:
            pygame.mixer.music.pause()
            self.ctrl.is_paused = True

    def next(self):
        if self.ctrl.playlist:
            n = (self.ctrl.idx + 1) if self.ctrl.idx < len(self.ctrl.playlist) - 1 else (
                0 if self.ctrl.repeat_state else self.ctrl.idx)
            self.ctrl.play_track(self.ctrl.playlist, n, self.ctrl.path)
            self.refresh()

    def prev(self):
        if self.ctrl.playlist:
            n = max(0, self.ctrl.idx - 1)
            self.ctrl.play_track(self.ctrl.playlist, n, self.ctrl.path)
            self.refresh()


class SettingsMenu(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx, self.view = 0, "main"
        self.btns = []
        self.stats_lbl = tk.Label(self, text="CPU: --% | --°C", font=("Courier", 10), bg=BG, fg=FG)
        self.stats_lbl.pack(pady=10)
        self.menu_container = tk.Frame(self, bg=BG)
        self.menu_container.pack(fill="both", expand=True)

    def refresh(self):
        self.show_main_settings()
        self.update_stats()

    def clear_menu(self):
        for widget in self.menu_container.winfo_children(): widget.destroy()
        self.btns, self.cur_idx = [], 0

    def show_main_settings(self):
        self.view = "main"
        self.clear_menu()
        opts = [("SYSTEM", self.show_system), ("AUDIO", self.show_audio), ("PLAYLISTS", self.show_playlists),
                ("NETWORK", lambda: self.ctrl.show_frame(NetworkLibrary)),
                ("BACK", lambda: self.ctrl.show_frame(MP3Menu))]
        self.build_btns(opts)

    def build_btns(self, opts):
        for text, cmd in opts:
            b = tk.Button(self.menu_container, text=text, font=("Courier", 10), bg=BG, fg=FG, bd=0, command=cmd)
            b.pack(pady=3, fill="x", padx=100)
            self.btns.append(b)
        self.update_visuals()

    def show_system(self):
        self.view = "system"
        self.clear_menu()
        opts = [(f"SLEEP: {self.ctrl.sleep_opts[self.ctrl.sleep_idx]}", self.cycle_sl),
                (f"FPS CAP: {self.ctrl.fps_cap}", self.cycle_fps), ("REBOOT", lambda: os.system("sudo reboot")),
                ("SHUTDOWN", lambda: os.system("sudo poweroff")), ("BACK", self.show_main_settings)]
        self.build_btns(opts)

    def show_audio(self):
        self.view = "audio"
        self.clear_menu()
        opts = [(f"OUTPUT: {'3.5mm' if self.ctrl.audio_output == 'jack' else 'BT'}", self.toggle_output),
                ("BACK", self.show_main_settings)]
        self.build_btns(opts)

    def show_playlists(self):
        self.view = "playlists"
        self.clear_menu()
        path = "/home/dietpi/pidice/MP3s/"
        try:
            dirs = natural_sort([d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))])
        except:
            dirs = []
        for f in dirs:
            b = tk.Button(self.menu_container, text=f"DELETE: {f}", font=("Courier", 10), bg=BG, fg="red",
                          command=lambda n=f: self.remove_playlist(n))
            b.pack(pady=2, fill="x", padx=50);
            self.btns.append(b)
        bk = tk.Button(self.menu_container, text="BACK", font=("Courier", 10), bg=BG, fg=FG,
                       command=self.show_main_settings)
        bk.pack(pady=10);
        self.btns.append(bk)
        self.update_visuals()

    def cycle_sl(self):
        self.ctrl.sleep_idx = (self.ctrl.sleep_idx + 1) % len(self.ctrl.sleep_opts)
        self.ctrl.save_settings();
        self.show_system()

    def cycle_fps(self):
        opts = [5, 10, 15, 20, 25, 30]
        self.ctrl.fps_cap = opts[(opts.index(self.ctrl.fps_cap) + 1) % len(opts)] if self.ctrl.fps_cap in opts else 30
        self.ctrl.save_settings();
        self.show_system()

    def toggle_output(self):
        self.ctrl.audio_output = "bt" if self.ctrl.audio_output == "jack" else "jack"
        self.ctrl.save_settings();
        self.show_audio()

    def remove_playlist(self, name):
        if messagebox.askyesno("Confirm", f"Delete {name}?"):
            try:
                shutil.rmtree(os.path.join("/home/dietpi/pidice/MP3s/", name)); self.show_playlists()
            except:
                pass

    def move(self, d, is_vertical=True):
        if self.btns:
            self.cur_idx = (self.cur_idx + d) % len(self.btns)
            self.update_visuals()

    def select(self):
        if self.btns:
            self.btns[self.cur_idx].invoke()

    def update_visuals(self):
        for i, b in enumerate(self.btns):
            b.config(bg=FG if i == self.cur_idx else BG, fg=BG if i == self.cur_idx else FG)

    def update_stats(self):
        try:
            import psutil
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                t = int(f.read()) / 1000
            self.stats_lbl.config(text=f"CPU: {psutil.cpu_percent()}% | {t:.1f}°C")
        except:
            pass
        if self.ctrl.current_screen == SettingsMenu: self.after(5000, self.update_stats)


class NetworkLibrary(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx = 0;
        self.btns = []

    def refresh(self):
        for widget in self.winfo_children(): widget.destroy()
        self.btns = []
        tk.Label(self, text="NETWORK LIBRARY", font=("Courier", 20, "bold"), bg=BG, fg=FG).pack(pady=40)
        opts = [("SCAN NETWORK", lambda: None), ("BACK", lambda: self.ctrl.show_frame(SettingsMenu))]
        for text, cmd in opts:
            btn = tk.Button(self, text=text, font=("Courier", 12), bg=BG, fg=FG, bd=0, command=cmd)
            btn.pack(pady=10, fill="x", padx=100);
            self.btns.append(btn)
        self.cur_idx = 0;
        self.update_visuals()

    def move(self, d, is_vertical=True):
        if self.btns: self.cur_idx = (self.cur_idx + d) % len(self.btns); self.update_visuals()

    def select(self):
        if self.btns: self.btns[self.cur_idx].invoke()

    def update_visuals(self):
        for i, b in enumerate(self.btns):
            b.config(bg=FG if i == self.cur_idx else BG, fg=BG if i == self.cur_idx else FG)


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

        # Initialize Image Cache
        self.img_cache = {}

        self.load_settings()
        self.attributes("-fullscreen", True)
        self.update_idletasks()
        self.screen_w, self.screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        self.configure(bg=BG)
        self.current_screen = None
        self.playlist, self.idx, self.path = [], 0, ""
        self.is_paused = False
        self.sleep_opts = ["OFF", "15m", "30m", "1h"]
        self.top_bar = TopBar(self, self)
        self.top_bar.pack(side="top", fill="x")
        self.container = tk.Frame(self, bg=BG)
        self.container.pack(side="top", fill="both", expand=True)
        self.frames = {}
        for F in (MP3Menu, NowPlaying, SettingsMenu, NetworkLibrary):
            frame = F(self.container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        self.show_frame(MP3Menu)
        self.bind("<Key>", self.handle_keys)
        self.check_music()

    def show_frame(self, cont):
        frame = self.frames[cont]
        self.current_screen = cont
        frame.tkraise()
        if hasattr(frame, 'refresh'): frame.refresh()

    def handle_keys(self, event):
        """ Routes arrow keys and enter to the active screen. """
        f = self.frames[self.current_screen]
        key = event.keysym

        # Horizontal Nav (Playlists/Buttons)
        if key in ("Left", "KP_Left", "KP_4"):
            f.move(-1, False)
        elif key in ("Right", "KP_Right", "KP_6"):
            f.move(1, False)

        # Vertical Nav (Open Screens)
        elif key in ("Up", "KP_Up", "KP_8"):
            if self.current_screen == MP3Menu:
                self.show_frame(SettingsMenu)
            else:
                f.move(-1, True)
        elif key in ("Down", "KP_Down", "KP_2"):
            if self.current_screen == MP3Menu:
                self.show_frame(NowPlaying)
            else:
                f.move(1, True)

        # Select/Enter
        elif key in ("Return", "KP_Enter"):
            if hasattr(f, 'select'): f.select()
        elif key == "Escape":
            self.show_frame(MP3Menu)

    def play_track(self, playlist, index, path):
        self.playlist, self.idx, self.path = playlist, index, path
        pygame.mixer.music.load(os.path.join(path, playlist[index]))
        pygame.mixer.music.set_volume(self.vol_level)
        pygame.mixer.music.play()
        self.is_paused = False
        if self.current_screen != NowPlaying: self.show_frame(NowPlaying)

    def check_music(self):
        if not pygame.mixer.music.get_busy() and not self.is_paused and self.playlist:
            if self.repeat_state or self.idx < len(self.playlist) - 1:
                self.idx = (self.idx + 1) % len(self.playlist)
                self.play_track(self.playlist, self.idx, self.path)
                if self.current_screen == NowPlaying: self.frames[NowPlaying].refresh()
        self.after(1000, self.check_music)

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
            except:
                self.set_defaults()
        else:
            self.set_defaults()

    def set_defaults(self):
        self.vol_level, self.repeat_state, self.sleep_idx = 0.25, False, 0
        self.audio_output, self.fps_cap = "jack", 30

    def save_settings(self):
        d = {"vol_level": self.vol_level, "repeat": self.repeat_state, "sleep_idx": self.sleep_idx,
             "audio_output": self.audio_output, "fps_cap": self.fps_cap}
        with open(self.settings_file, "w") as f: json.dump(d, f)


if __name__ == "__main__":
    try:
        app = App()
        clock = pygame.time.Clock()


        def run_loop():
            app.update_idletasks()
            app.update()
            clock.tick(app.fps_cap)
            app.after(1, run_loop)


        app.after(1, run_loop)
        app.mainloop()
    except Exception as e:
        print(f"\n[FATAL ERROR]: {e}")
        time.sleep(10)