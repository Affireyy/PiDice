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
# Force the modern GPIO factory for Raspberry Pi compatibility
os.environ['GPIOZERO_PIN_FACTORY'] = 'lgpio'
try:
    from gpiozero import Button as PhysicalButton
except ImportError:
    PhysicalButton = None

# --- UI STYLING CONSTANTS ---
BG = "#2B2B2B"  # Dark Charcoal Background
FG = "#FF8200"  # Vibrant Orange Foreground/Accent


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
    """ persistent header displaying time, CPU usage, and temperature. """

    def __init__(self, parent, controller):
        super().__init__(parent, bg=FG, height=30)
        self.ctrl = controller
        self.pack_propagate(False)

        # Left-aligned clock
        self.lbl_time = tk.Label(self, font=("Courier", 12, "bold"), bg=FG, fg=BG)
        self.lbl_time.pack(side="left", padx=20)

        # Right-aligned system stats
        self.lbl_stats = tk.Label(self, font=("Courier", 10, "bold"), bg=FG, fg=BG)
        self.lbl_stats.pack(side="right", padx=20)

        self.update_bar()

    def update_bar(self):
        """ Periodically updates time and hardware telemetry. """
        # Set clock to Swedish timezone
        try:
            tz = zoneinfo.ZoneInfo("Europe/Stockholm")
            now = datetime.now(tz)
            t_str = now.strftime("%H:%M:%S")
        except:
            t_str = time.strftime("%H:%M:%S")

        self.lbl_time.config(text=t_str)

        # Fetch CPU utilization and thermal data
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
    def draw_coverflow(self):
        self.canvas.delete("all")
        if not self.playlists: return

        # Use dynamic screen centers
        center_x = self.ctrl.screen_w // 2
        center_y = (self.ctrl.screen_h // 2) - 40

        indices = [(self.cur_idx - 1) % len(self.playlists), self.cur_idx, (self.cur_idx + 1) % len(self.playlists)]

        for i, idx in enumerate(indices):
            folder = self.playlists[idx]
            # Scaling images based on screen width
            scale_factor = self.ctrl.screen_w / 800
            size = (int(300 * scale_factor), int(300 * scale_factor)) if i == 1 else (int(200 * scale_factor),
                                                                                      int(200 * scale_factor))

            # Dynamic spacing
            offset = int(250 * scale_factor)
            x = center_x if i == 1 else (center_x - offset if i == 0 else center_x + offset)

            p = os.path.join("/home/dietpi/pidice/MP3s/", folder, "cover.png")

            try:
                img = Image.open(p) if os.path.exists(p) else Image.new('RGB', size, color='#111')
                img = img.resize(size, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.canvas.create_image(x, center_y, image=photo)
                if i == 0:
                    self.img0 = photo
                elif i == 1:
                    self.img1 = photo
                else:
                    self.img2 = photo
            except:
                pass

        self.canvas.create_text(center_x, center_y + int(200 * scale_factor),
                                text=self.playlists[self.cur_idx].upper(),
                                font=("Courier", int(18 * scale_factor), "bold"), fill=FG)


class NowPlaying(tk.Frame):
    """ Playback interface displaying current track details and controls. """

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx = 1  # Start focus on the Play/Pause button

        self.grid_columnconfigure((0, 1), weight=1)
        # Album Art Display
        self.cover_label = tk.Label(self, bg=BG)
        self.cover_label.grid(row=0, column=0, sticky="nsew", padx=20)

        # Song info and controls container
        self.info = tk.Frame(self, bg=BG)
        self.info.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        self.title = tk.Label(self.info, text="Song Name", font=("Courier", 18, "bold"), bg=BG, fg=FG, wraplength=300)
        self.title.pack(pady=10)

        # Progress Bar section
        self.t_frm = tk.Frame(self.info, bg=BG)
        self.t_frm.pack(fill="x")

        self.p_can = tk.Canvas(self.t_frm, height=10, bg="#333", highlightthickness=0)
        self.p_can.pack(side="left", fill="x", expand=True)
        self.p_bar = self.p_can.create_rectangle(0, 0, 0, 10, fill=FG)

        self.t_lbl = tk.Label(self.t_frm, text="-0:00", font=("Courier", 10), bg=BG, fg=FG, width=6)
        self.t_lbl.pack(side="right")

        # Volume Bar section
        self.v_frm = tk.Frame(self.info, bg=BG)
        self.v_frm.pack(fill="x", pady=10)

        self.v_can = tk.Canvas(self.v_frm, height=10, bg="#333", highlightthickness=0)
        self.v_can.pack(side="left", fill="x", expand=True)
        self.v_bar = self.v_can.create_rectangle(0, 0, 0, 10, fill=FG)

        self.v_lbl = tk.Label(self.v_frm, text="50%", font=("Courier", 10), bg=BG, fg=FG, width=6)
        self.v_lbl.pack(side="right")

        # Playback Buttons (Prev, Toggle, Next, Repeat, Back)
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
        """ Updates song title, album art, and button states. """
        if not self.ctrl.playlist:
            self.title.config(text="NOTHING IS PLAYING")
            self.cover_label.config(image="", text="")
        else:
            song_file = self.ctrl.playlist[self.ctrl.idx]
            self.title.config(text=song_file.replace(".mp3", ""))
            img = None
            # Check for specific metadata tags or local cover image
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
        """ Updates the playback timer and progress bar every second. """
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
        # Only schedule updates if the screen is active
        if self.ctrl.current_screen == NowPlaying:
            self.after(1000, self.update_ui_loop)

    def update_vol_bar(self):
        """ Syncs the volume bar visualization with system volume settings. """
        ratio = self.ctrl.vol_level / 0.5
        self.v_can.coords(self.v_bar, 0, 0, ratio * self.v_can.winfo_width(), 10)
        self.v_lbl.config(text=f"{int(ratio * 100)}%")

    def change_volume(self, d):
        """ Adjusts volume and saves the new setting to disk. """
        self.ctrl.vol_level = max(0.0, min(0.5, self.ctrl.vol_level + (d * 0.025)))
        pygame.mixer.music.set_volume(self.ctrl.vol_level)
        self.update_vol_bar()
        self.ctrl.save_settings()

    def toggle_repeat(self):
        """ Toggles track/playlist repetition. """
        self.ctrl.repeat_state = not self.ctrl.repeat_state
        self.btns[3].config(text=f"REPEAT: {'ON' if self.ctrl.repeat_state else 'OFF'}")
        self.ctrl.save_settings()

    def move(self, d, is_vertical=True):
        """ Cycles focus through the playback buttons. """
        self.cur_idx = (self.cur_idx + d) % len(self.btns)
        self.update_visuals()

    def update_visuals(self):
        """ Highlights the selected button. """
        for i, b in enumerate(self.btns):
            b.config(bg=FG if i == self.cur_idx else BG, fg=BG if i == self.cur_idx else FG)

    def toggle(self):
        """ Play/Pause functionality. """
        if self.ctrl.is_paused:
            pygame.mixer.music.unpause()
            self.ctrl.is_paused = False
        else:
            pygame.mixer.music.pause()
            self.ctrl.is_paused = True

    def next(self):
        """ Skips to the next track. """
        if self.ctrl.playlist:
            if self.ctrl.idx < len(self.ctrl.playlist) - 1:
                n = self.ctrl.idx + 1
            else:
                n = 0 if self.ctrl.repeat_state else self.ctrl.idx
            if n != self.ctrl.idx or self.ctrl.repeat_state:
                self.ctrl.play_track(self.ctrl.playlist, n, self.ctrl.path)
                self.refresh()

    def prev(self):
        """ Goes back to the previous track. """
        if self.ctrl.playlist:
            n = max(0, self.ctrl.idx - 1)
            self.ctrl.play_track(self.ctrl.playlist, n, self.ctrl.path)
            self.refresh()


class SettingsMenu(tk.Frame):
    """ Interface for hardware and app configuration. """

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx, self.view = 0, "main"
        self.btns = []

        # Top status line
        self.stats_lbl = tk.Label(self, text="CPU: --% | --°C", font=("Courier", 10), bg=BG, fg=FG)
        self.stats_lbl.pack(pady=10)

        self.menu_container = tk.Frame(self, bg=BG)
        self.menu_container.pack(fill="both", expand=True)

    def refresh(self):
        """ Rebuilds the settings view. """
        self.show_main_settings()
        self.update_stats()

    def clear_menu(self):
        """ Destroys existing widgets before rendering a new submenu. """
        for widget in self.menu_container.winfo_children():
            widget.destroy()
        self.btns, self.cur_idx = [], 0

    def show_main_settings(self):
        """ Renders the root settings options. """
        self.view = "main";
        self.clear_menu()
        opts = [
            ("SYSTEM", self.show_system),
            ("AUDIO", self.show_audio),
            ("PLAYLISTS", self.show_playlists),
            ("NETWORK", lambda: self.ctrl.show_frame(NetworkLibrary)),
            ("BACK", lambda: self.ctrl.show_frame(MP3Menu))
        ]
        self.build_btns(opts)

    def show_system(self):
        """ Renders hardware power and performance options. """
        self.view = "system";
        self.clear_menu()
        sl_text = f"SLEEP: {self.ctrl.sleep_opts[self.ctrl.sleep_idx]}"
        fps_text = f"FPS CAP: {self.ctrl.fps_cap}"
        opts = [
            (sl_text, self.cycle_sl),
            (fps_text, self.cycle_fps),
            ("REBOOT", lambda: os.system("sudo reboot")),
            ("SHUTDOWN", lambda: os.system("sudo poweroff")),
            ("RESTART APP", self.ctrl.restart_app),
            ("BACK", self.show_main_settings)
        ]
        self.build_btns(opts)

    def show_audio(self):
        """ Renders audio output routing options. """
        self.view = "audio";
        self.clear_menu()
        out_mode = "3.5mm" if self.ctrl.audio_output == "jack" else "BT"
        opts = [
            (f"OUTPUT: {out_mode}", self.toggle_output),
            ("BACK", self.show_main_settings)
        ]
        self.build_btns(opts)

    def show_playlists(self):
        """ Renders a list of folders with a delete option. """
        self.view = "playlists";
        self.clear_menu()
        path = "/home/dietpi/pidice/MP3s/"
        try:
            dirs = natural_sort([d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))])
        except:
            dirs = []
        for folder in dirs:
            b = tk.Button(self.menu_container, text=f"DELETE: {folder}", font=("Courier", 10), bg=BG, fg="red",
                          command=lambda n=folder: self.remove_playlist(n))
            b.pack(pady=2, fill="x", padx=50);
            self.btns.append(b)

        back_btn = tk.Button(self.menu_container, text="BACK", font=("Courier", 10), bg=BG, fg=FG,
                             command=self.show_main_settings)
        back_btn.pack(pady=10);
        self.btns.append(back_btn)
        self.update_visuals()

    def build_btns(self, opts):
        """ Utility to create standardized menu buttons. """
        for text, cmd in opts:
            b = tk.Button(self.menu_container, text=text, font=("Courier", 10), bg=BG, fg=FG, bd=0, command=cmd)
            b.pack(pady=3, fill="x", padx=100)
            self.btns.append(b)
        self.update_visuals()

    def cycle_sl(self):
        """ Cycles through sleep timer presets. """
        self.ctrl.sleep_idx = (self.ctrl.sleep_idx + 1) % len(self.ctrl.sleep_opts)
        self.ctrl.save_settings()
        self.show_system()

    def cycle_fps(self):
        """ Cycles through FPS cap limits for power management. """
        fps_opts = [5, 10, 15, 20, 25, 30]
        try:
            curr_idx = fps_opts.index(self.ctrl.fps_cap)
            self.ctrl.fps_cap = fps_opts[(curr_idx + 1) % len(fps_opts)]
        except:
            self.ctrl.fps_cap = 30
        self.ctrl.save_settings()
        self.show_system()

    def toggle_output(self):
        """ Switches between headphone jack and Bluetooth output. """
        self.ctrl.audio_output = "bt" if self.ctrl.audio_output == "jack" else "jack"
        self.ctrl.save_settings()
        self.show_audio()

    def remove_playlist(self, name):
        """ Deletes a playlist folder from the filesystem. """
        if messagebox.askyesno("Confirm", f"Delete {name}?"):
            try:
                shutil.rmtree(os.path.join("/home/dietpi/pidice/MP3s/", name))
                self.show_playlists()
            except:
                pass

    def move(self, d, is_vertical=True):
        """ Cycles menu focus. """
        if self.btns:
            self.cur_idx = (self.cur_idx + d) % len(self.btns)
            self.update_visuals()

    def update_visuals(self):
        """ Updates button highlighting. """
        for i, b in enumerate(self.btns):
            b.config(bg=FG if i == self.cur_idx else BG, fg=BG if i == self.cur_idx else FG)

    def update_stats(self):
        """ Background task to update telemetry in the settings header. """
        try:
            import psutil
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                t = int(f.read()) / 1000
            self.stats_lbl.config(text=f"CPU: {psutil.cpu_percent()}% | {t:.1f}°C")
        except:
            pass
        if self.ctrl.current_screen == SettingsMenu:
            self.after(5000, self.update_stats)


class NetworkLibrary(tk.Frame):
    """ Menu for network-based library management. """

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx = 0;
        self.btns = []

    def refresh(self):
        """ Renders network options. """
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

    def update_visuals(self):
        for i, b in enumerate(self.btns):
            b.config(bg=FG if i == self.cur_idx else BG, fg=BG if i == self.cur_idx else FG)


# --- CORE APPLICATION LOGIC ---

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        # Set process priority for audio stability
        try:
            os.nice(-10)
        except:
            pass

            # Initialize audio engine with high-buffer settings
        pygame.mixer.pre_init(44100, -16, 2, 4096)
        pygame.mixer.init()

        self.settings_file = "/home/dietpi/pidice/settings.json"

        # Load user preferences (Volume, FPS, etc.)
        self.load_settings()

        # Dynamic Window Configuration
        # This allows the app to fit any screen resolution automatically
        self.attributes("-fullscreen", True)
        self.update_idletasks()  # Ensure window properties are loaded
        self.screen_w = self.winfo_screenwidth()
        self.screen_h = self.winfo_screenheight()

        self.configure(bg=BG)
        self.config(highlightthickness=1, highlightbackground=FG)

        self.current_screen = None
        self.playlist, self.idx, self.path = [], 0, ""
        self.is_paused = False
        self.sleep_opts = ["OFF", "15m", "30m", "1h"]

        # Main Layout Components
        self.top_bar = TopBar(self, self)
        self.top_bar.pack(side="top", fill="x")

        self.container = tk.Frame(self, bg=BG)
        self.container.pack(side="top", fill="both", expand=True)

        # Initialize screen frames
        self.frames = {}
        for F in (MP3Menu, NowPlaying, SettingsMenu, NetworkLibrary):
            frame = F(self.container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.bind("<Key>", self.handle_keys)
        self.show_frame(MP3Menu)
        self.check_music()

    def load_settings(self):
        """ Reads configuration from disk or sets defaults. """
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    data = json.load(f)
                self.vol_level = data.get("vol_level", 0.25)
                self.repeat_state = data.get("repeat", False)
                self.sleep_idx = data.get("sleep_idx", 0)
                self.audio_output = data.get("audio_output", "jack")
                self.fps_cap = data.get("fps_cap", 30)
            except:
                self.set_defaults()
        else:
            self.set_defaults()

    def set_defaults(self):
        """ Fallback values for application settings. """
        self.vol_level, self.repeat_state, self.sleep_idx = 0.25, False, 0
        self.audio_output, self.fps_cap = "jack", 30

    def save_settings(self):
        """ Persists current user settings to JSON. """
        data = {
            "vol_level": self.vol_level,
            "repeat": self.repeat_state,
            "sleep_idx": self.sleep_idx,
            "audio_output": self.audio_output,
            "fps_cap": self.fps_cap
        }
        with open(self.settings_file, "w") as f:
            json.dump(data, f)


# --- MAIN EXECUTION LOOP ---
if __name__ == "__main__":
    app = App()
    clock = pygame.time.Clock()


    def run_loop():
        """ Custom event loop to manage Tkinter updates and FPS capping. """
        app.update_idletasks()
        app.update()

        # Enforce FPS limit to keep CPU usage low
        clock.tick(app.fps_cap)
        app.after(1, run_loop)


    app.after(1, run_loop)
    app.mainloop()