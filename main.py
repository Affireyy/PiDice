import os
import sys
import json
import time
import tkinter as tk
from PIL import Image, ImageTk
import pygame
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
import io

# Force the modern GPIO factory for newer Linux kernels
os.environ['GPIOZERO_PIN_FACTORY'] = 'lgpio'
try:
    from gpiozero import Button as PhysicalButton
except ImportError:
    PhysicalButton = None

# --- STYLING ---
BG = "#2B2B2B"
FG = "#FF8200"


def natural_sort(l):
    import re
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


def get_single_song_art(song_path):
    """Extracts album art from a specific MP3 file"""
    try:
        audio = MP3(song_path, ID3=ID3)
        for tag in audio.tags.values():
            if isinstance(tag, APIC):
                return Image.open(io.BytesIO(tag.data))
    except:
        pass
    return None


# --- SCREENS ---

class Home(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx = 0
        tk.Label(self, text="PI-DICE PLAYER", font=("Courier", 24, "bold"), bg=BG, fg=FG).pack(pady=40)
        self.btn_container = tk.Frame(self, bg=BG)
        self.btn_container.pack(expand=True)

        self.btns = []
        menu_items = [("MUSIC", MP3Menu), ("NETWORK", NetworkLibrary), ("SETTINGS", SettingsMenu)]
        for text, target in menu_items:
            b = tk.Button(self.btn_container, text=text, font=("Courier", 14), bg=BG, fg=FG,
                          bd=0, highlightthickness=2, padx=20, pady=10,
                          command=lambda t=target: self.ctrl.show_frame(t))
            b.pack(pady=5, fill="x")
            self.btns.append(b)

    def refresh(self):
        self.cur_idx = 0
        self.update_visuals()

    def move(self, d, is_vertical=True):
        self.cur_idx = (self.cur_idx + d) % len(self.btns)
        self.update_visuals()

    def update_visuals(self):
        for i, b in enumerate(self.btns):
            b.config(bg=FG if i == self.cur_idx else BG, fg=BG if i == self.cur_idx else FG)


class NetworkLibrary(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        tk.Label(self, text="NETWORK LIBRARY", font=("Courier", 20, "bold"), bg=BG, fg=FG).pack(pady=50)
        tk.Label(self, text="Work In Progress...", font=("Courier", 14), bg=BG, fg="#888").pack(pady=20)
        self.btn = tk.Button(self, text="BACK", font=("Courier", 12), bg=FG, fg=BG,
                             command=lambda: self.ctrl.show_frame(Home))
        self.btn.pack(pady=20)
        self.btns = [self.btn]
        self.cur_idx = 0

    def move(self, d, is_vertical=True): pass


class MP3Menu(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx = 0
        self.view_mode = "menu"
        self.is_playlist_selected = False
        self.sub_menu_frame = None
        self.list_frame = None
        self.pl_btns, self.sg_btns = [], []

    def refresh(self):
        self.clear_screen()
        self.view_mode = "menu"
        self.is_playlist_selected = False
        self.sub_menu_frame = tk.Frame(self, bg=BG)
        self.sub_menu_frame.pack(expand=True)
        self.btns = []
        opts = [("PLAYLISTS", self.show_playlists), ("NOW PLAYING", lambda: self.ctrl.show_frame(NowPlaying)),
                ("BACK", lambda: self.ctrl.show_frame(Home))]
        for text, cmd in opts:
            b = tk.Button(self.sub_menu_frame, text=text, font=("Courier", 14), bg=BG, fg=FG, bd=0,
                          highlightthickness=2, padx=20, pady=10, command=cmd)
            b.pack(pady=5, fill="x")
            self.btns.append(b)
        self.cur_idx = 0
        self.update_visuals()

    def clear_screen(self):
        if self.sub_menu_frame: self.sub_menu_frame.destroy()
        if self.list_frame: self.list_frame.destroy()
        self.pl_btns, self.sg_btns = [], []

    def show_playlists(self):
        self.clear_screen()
        self.view_mode = "list"
        self.is_playlist_selected = False
        self.list_frame = tk.Frame(self, bg=BG)
        self.list_frame.pack(fill="both", expand=True)
        self.left = tk.Frame(self.list_frame, bg=BG, width=350);
        self.left.pack(side="left", fill="both", padx=10);
        self.left.pack_propagate(False)
        self.right = tk.Frame(self.list_frame, bg=BG);
        self.right.pack(side="right", fill="both", expand=True, padx=10)

        self.pl_can = tk.Canvas(self.left, bg=BG, highlightthickness=0);
        self.pl_can.pack(fill="both", expand=True)
        self.pl_con = tk.Frame(self.pl_can, bg=BG);
        self.pl_can.create_window((0, 0), window=self.pl_con, anchor="nw")

        self.sg_can = tk.Canvas(self.right, bg=BG, highlightthickness=0);
        self.sg_can.pack(fill="both", expand=True)
        self.sg_con = tk.Frame(self.sg_can, bg=BG);
        self.sg_can.create_window((0, 0), window=self.sg_con, anchor="nw")
        self.load_playlist_view()

    def load_playlist_view(self):
        path = "/home/dietpi/pidice/MP3s/"
        try:
            dirs = natural_sort([d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))])
        except:
            dirs = []
        dirs.append("BACK")
        for folder in dirs:
            f_frame = tk.Frame(self.pl_con, bg=BG);
            f_frame.pack(fill="x", pady=2)
            img_label = tk.Label(f_frame, bg=BG);
            img_label.pack(side="left")
            display_name = folder.upper()
            if folder != "BACK":
                img = None
                if "(METADATA)" not in display_name:
                    img_p = os.path.join(path, folder, "cover.png")
                    if os.path.exists(img_p): img = Image.open(img_p)
                if img:
                    try:
                        img_resized = img.resize((30, 30), Image.Resampling.LANCZOS)
                        p_img = ImageTk.PhotoImage(img_resized);
                        img_label.config(image=p_img);
                        img_label.image = p_img
                    except:
                        pass
            btn = tk.Button(f_frame, text=f" {display_name}", font=("Courier", 10), bg=BG, fg=FG, bd=0, anchor="w",
                            command=lambda f=folder: self.load_songs(f) if f != "BACK" else self.refresh())
            btn.pack(side="left", fill="x", expand=True);
            self.pl_btns.append(btn)
        self.pl_con.update_idletasks();
        self.pl_can.config(scrollregion=self.pl_can.bbox("all"))
        self.focus_side, self.cur_idx = "left", 0
        self.update_visuals()

    def load_songs(self, folder):
        self.is_playlist_selected = True
        self.ctrl.path = f"/home/dietpi/pidice/MP3s/{folder}"

        # Hard Clear
        for widget in self.sg_con.winfo_children(): widget.destroy()
        self.sg_btns = []

        try:
            self.current_songs = natural_sort([f for f in os.listdir(self.ctrl.path) if f.endswith(".mp3")])
        except:
            self.current_songs = []

        is_metadata = "(METADATA)" in folder.upper()
        for s in self.current_songs:
            s_frame = tk.Frame(self.sg_con, bg=BG);
            s_frame.pack(fill="x", pady=1)
            img_label = tk.Label(s_frame, bg=BG);
            img_label.pack(side="left")
            if is_metadata:
                img = get_single_song_art(os.path.join(self.ctrl.path, s))
                if img:
                    try:
                        img_resized = img.resize((25, 25), Image.Resampling.LANCZOS)
                        p_img = ImageTk.PhotoImage(img_resized);
                        img_label.config(image=p_img);
                        img_label.image = p_img
                    except:
                        pass
            btn = tk.Button(s_frame, text=f" {s[:30]}", font=("Courier", 9), bg=BG, fg=FG, bd=0, anchor="w",
                            command=lambda sn=s: self.ctrl.play_track(self.current_songs, self.current_songs.index(sn),
                                                                      self.ctrl.path))
            btn.pack(side="left", fill="x", expand=True);
            self.sg_btns.append(btn)

        self.sg_con.update_idletasks();
        self.sg_can.config(scrollregion=self.sg_can.bbox("all"))
        self.sg_can.yview_moveto(0)
        self.focus_side, self.cur_idx = "right", 0
        self.update_visuals()

    def move(self, d, is_vertical=True):
        if self.view_mode == "menu":
            self.cur_idx = (self.cur_idx + d) % len(self.btns)
        else:
            # FIX: Immediate swap on horizontal to prevent double-press
            if not is_vertical:
                if d == 1 and self.focus_side == "left" and self.is_playlist_selected:
                    self.focus_side, self.cur_idx = "right", 0
                    self.update_visuals()
                    return
                elif d == -1 and self.focus_side == "right":
                    self.focus_side, self.cur_idx = "left", 0
                    self.update_visuals()
                    return

            active = self.pl_btns if self.focus_side == "left" else self.sg_btns
            if not active: return
            self.cur_idx = (self.cur_idx + d) % len(active)

            # Scrolling logic
            canvas = self.pl_can if self.focus_side == "left" else self.sg_can
            self.update_idletasks()
            target = active[self.cur_idx].master  # Always use parent frame for geometry
            bbox = canvas.bbox("all")
            total_h = float(bbox[3] - bbox[1]) if bbox else 1.0

            btn_top = target.winfo_y() / total_h
            btn_bottom = (target.winfo_y() + target.winfo_height()) / total_h
            view_top, view_bottom = canvas.yview()

            if btn_top < view_top:
                canvas.yview_moveto(btn_top)
            elif btn_bottom > view_bottom:
                canvas.yview_moveto(btn_bottom - (view_bottom - view_top))
        self.update_visuals()

    def update_visuals(self):
        if self.view_mode == "menu":
            for i, b in enumerate(self.btns):
                b.config(bg=FG if i == self.cur_idx else BG, fg=BG if i == self.cur_idx else FG)
        else:
            for b in self.pl_btns + self.sg_btns: b.config(bg=BG, fg=FG)
            active = self.pl_btns if self.focus_side == "left" else self.sg_btns
            if active and self.cur_idx < len(active):
                active[self.cur_idx].config(bg=FG, fg=BG)

    def trigger_selection(self):
        if self.view_mode == "menu":
            self.btns[self.cur_idx].invoke()
        else:
            active = self.pl_btns if self.focus_side == "left" else self.sg_btns
            if active: active[self.cur_idx].invoke()


class NowPlaying(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.ctrl = controller
        self.cur_idx, self.vol_level, self.repeat = 1, 0.25, False
        self.grid_columnconfigure((0, 1), weight=1)
        self.cover_label = tk.Label(self, bg=BG);
        self.cover_label.grid(row=0, column=0, sticky="nsew", padx=20)
        self.info = tk.Frame(self, bg=BG);
        self.info.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.title = tk.Label(self.info, text="Song Name", font=("Courier", 18, "bold"), bg=BG, fg=FG, wraplength=300);
        self.title.pack(pady=10)
        self.t_frm = tk.Frame(self.info, bg=BG);
        self.t_frm.pack(fill="x")
        self.p_can = tk.Canvas(self.t_frm, height=10, bg="#333", highlightthickness=0);
        self.p_can.pack(side="left", fill="x", expand=True)
        self.p_bar = self.p_can.create_rectangle(0, 0, 0, 10, fill=FG)
        self.t_lbl = tk.Label(self.t_frm, text="-0:00", font=("Courier", 10), bg=BG, fg=FG, width=6);
        self.t_lbl.pack(side="right")
        self.v_frm = tk.Frame(self.info, bg=BG);
        self.v_frm.pack(fill="x", pady=10)
        self.v_can = tk.Canvas(self.v_frm, height=10, bg="#333", highlightthickness=0);
        self.v_can.pack(side="left", fill="x", expand=True)
        self.v_bar = self.v_can.create_rectangle(0, 0, 0, 10, fill=FG)
        self.v_lbl = tk.Label(self.v_frm, text="50%", font=("Courier", 10), bg=BG, fg=FG, width=6);
        self.v_lbl.pack(side="right")
        self.btn_f = tk.Frame(self.info, bg=BG);
        self.btn_f.pack(pady=10)
        self.btns = []
        labels, cmds = ["PREV", "PAUSE", "NEXT", "REPEAT: OFF", "HOME"], [self.prev, self.toggle, self.next,
                                                                          self.toggle_repeat,
                                                                          lambda: self.ctrl.show_frame(Home)]
        for i, lbl in enumerate(labels):
            btn = tk.Button(self.btn_f, text=lbl, font=("Courier", 8, "bold"), bg=BG, fg=FG, bd=0, command=cmds[i])
            btn.grid(row=0, column=i, padx=3);
            self.btns.append(btn)

    def refresh(self):
        if not self.ctrl.playlist:
            self.title.config(text="NOTHING IS PLAYING"); self.cover_label.config(image="", text="")
        else:
            song_file = self.ctrl.playlist[self.ctrl.idx]
            self.title.config(text=song_file.replace(".mp3", ""))
            img = None
            if "(METADATA)" in self.ctrl.path.upper():
                img = get_single_song_art(os.path.join(self.ctrl.path, song_file))
            else:
                img_p = os.path.join(self.ctrl.path, "cover.png")
                if os.path.exists(img_p): img = Image.open(img_p)
            if img:
                try:
                    img_resized = img.resize((300, 300), Image.Resampling.LANCZOS);
                    photo = ImageTk.PhotoImage(img_resized)
                    self.cover_label.config(image=photo);
                    self.cover_label.image = photo
                except:
                    pass
            else:
                self.cover_label.config(image="", text="NO COVER")
        self.update_ui_loop();
        self.update_vol_bar();
        self.update_visuals()

    def update_ui_loop(self):
        self.btns[1].config(text="PLAY" if self.ctrl.is_paused else "PAUSE")
        if pygame.mixer.music.get_busy():
            try:
                total = MP3(os.path.join(self.ctrl.path, self.ctrl.playlist[self.ctrl.idx])).info.length
                curr = pygame.mixer.music.get_pos() / 1000.0
                self.p_can.coords(self.p_bar, 0, 0, (curr / total) * self.p_can.winfo_width(), 10)
                m, s = divmod(max(0, int(total - curr)), 60);
                self.t_lbl.config(text=f"-{m}:{s:02d}")
            except:
                pass
        if self.ctrl.current_screen == NowPlaying: self.after(3000, self.update_ui_loop)

    def update_vol_bar(self):
        ratio = self.vol_level / 0.5;
        self.v_can.coords(self.v_bar, 0, 0, ratio * self.v_can.winfo_width(), 10);
        self.v_lbl.config(text=f"{int(ratio * 100)}%")

    def change_volume(self, d):
        self.vol_level = max(0.0, min(0.5, self.vol_level + (d * 0.025))); pygame.mixer.music.set_volume(
            self.vol_level); self.update_vol_bar(); self.ctrl.queue_save()

    def toggle_repeat(self):
        self.repeat = not self.repeat; self.btns[3].config(
            text=f"REPEAT: {'ON' if self.repeat else 'OFF'}"); self.ctrl.queue_save()

    def move(self, d, is_vertical=True):
        self.cur_idx = (self.cur_idx + d) % len(self.btns); self.update_visuals()

    def update_visuals(self):
        for i, b in enumerate(self.btns): b.config(bg=FG if i == self.cur_idx else BG,
                                                   fg=BG if i == self.cur_idx else FG)

    def toggle(self):
        if self.ctrl.is_paused:
            pygame.mixer.music.unpause(); self.ctrl.is_paused = False
        else:
            pygame.mixer.music.pause(); self.ctrl.is_paused = True

    def next(self):
        if not self.ctrl.playlist: return
        n = self.ctrl.idx + 1 if self.ctrl.idx < len(self.ctrl.playlist) - 1 else (0 if self.repeat else self.ctrl.idx)
        self.ctrl.play_track(self.ctrl.playlist, n, self.ctrl.path);
        self.refresh()

    def prev(self):
        if not self.ctrl.playlist: return
        self.ctrl.play_track(self.ctrl.playlist, max(0, self.ctrl.idx - 1), self.ctrl.path);
        self.refresh()


class SettingsMenu(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG);
        self.ctrl = controller
        self.cur_idx, self.sleep_idx = 0, 0
        self.sleep_opts = ["OFF", "30s", "1m", "3m", "5m", "10m"];
        self.sleep_times = [0, 30000, 60000, 180000, 300000, 600000]
        tk.Label(self, text="SETTINGS", font=("Courier", 18, "bold"), bg=BG, fg=FG).pack(pady=10)
        self.pwr_lbl = tk.Label(self, text="POWER: --", font=("Courier", 10), bg=BG, fg="yellow");
        self.pwr_lbl.pack()
        self.stats_lbl = tk.Label(self, text="CPU: --% | --°C", font=("Courier", 10), bg=BG, fg=FG);
        self.stats_lbl.pack(pady=5)
        self.btns = []
        texts = ["OVERLAY: OFF", "SLEEP: OFF", "REBOOT", "SHUTDOWN", "RESTART APP", "QUIT TO TERMINAL", "BACK"]
        cmds = [self.toggle_ov, self.cycle_sl, lambda: os.system("sudo reboot"), lambda: os.system("sudo poweroff"),
                self.ctrl.restart_app, self.ctrl.quit_app, lambda: self.ctrl.show_frame(Home)]
        for i, t in enumerate(texts):
            b = tk.Button(self, text=t, font=("Courier", 10), bg=BG, fg=FG, command=cmds[i]);
            b.pack(pady=3, fill="x", padx=100);
            self.btns.append(b)

    def refresh(self):
        self.cur_idx = 0; self.update_stats(); self.update_visuals()

    def update_stats(self):
        try:
            import psutil
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                t = int(f.read()) / 1000
            pwr = os.popen('vcgencmd get_throttled').read().split('=')[1].strip()
            self.pwr_lbl.config(text=f"POWER: {'OK' if pwr == '0x0' else 'UNDERVOLT!'}",
                                fg="green" if pwr == "0x0" else "red")
            self.stats_lbl.config(text=f"CPU: {psutil.cpu_percent()}% | {t:.1f}°C")
        except:
            pass
        if self.ctrl.current_screen == SettingsMenu: self.after(5000, self.update_stats)

    def toggle_ov(self):
        s = self.btns[0].cget("text") == "OVERLAY: OFF"; self.btns[0].config(
            text=f"OVERLAY: {'ON' if s else 'OFF'}"); self.ctrl.toggle_stats_overlay(s); self.ctrl.queue_save()

    def cycle_sl(self):
        self.sleep_idx = (self.sleep_idx + 1) % len(self.sleep_opts); self.btns[1].config(
            text=f"SLEEP: {self.sleep_opts[self.sleep_idx]}"); self.ctrl.sleep_limit = self.sleep_times[
            self.sleep_idx]; self.ctrl.queue_save()

    def move(self, d, is_vertical=True):
        self.cur_idx = (self.cur_idx + d) % len(self.btns); self.update_visuals()

    def update_visuals(self):
        for i, b in enumerate(self.btns): b.config(bg=FG if i == self.cur_idx else BG,
                                                   fg=BG if i == self.cur_idx else FG)


class App(tk.Tk):
    def __init__(self):
        os.environ['DISPLAY'] = ':0'
        try:
            pygame.mixer.pre_init(44100, -16, 2, 4096); pygame.mixer.init()
        except:
            pygame.mixer.init()
        super().__init__();
        self.attributes('-fullscreen', True);
        self.attributes('-topmost', True);
        self.configure(bg=BG)
        self.hw_map = {17: "Up", 27: "Down", 22: "Left", 23: "Right", 24: "Return"}
        self.hw_btns = []
        if PhysicalButton:
            for pin, key in self.hw_map.items():
                b = PhysicalButton(pin, bounce_time=0.05);
                b.when_pressed = lambda k=key: self.handle_hw_press(k);
                self.hw_btns.append(b)
        self.cfg = "/home/dietpi/pidice/settings.json"
        self.container = tk.Frame(self, bg=BG);
        self.container.pack(fill="both", expand=True)
        self.playlist, self.idx, self.path, self.current_screen = [], 0, "", None
        self.last_act, self.is_asleep, self.is_paused, self.sleep_limit, self._save = time.time(), False, False, 0, None
        self.overlay = tk.Label(self, text="", font=("Courier", 8, "bold"), bg="#111", fg=FG, padx=5, bd=1)
        self.frames = {}
        for F in (Home, MP3Menu, NowPlaying, SettingsMenu, NetworkLibrary):
            f = F(self.container, self);
            self.frames[F] = f;
            f.grid(row=0, column=0, sticky="nsew")
        self.load_settings();
        self.bind("<KeyPress>", self.handle_keys);
        self.show_frame(Home);
        self.check_loops()

    def handle_hw_press(self, key_name):
        class FakeEvent:
            def __init__(self, k): self.keysym = k

        self.handle_keys(FakeEvent(key_name))

    def load_settings(self):
        if os.path.exists(self.cfg):
            try:
                with open(self.cfg, "r") as f:
                    data = json.load(f);
                    v = data.get("volume", 0.25);
                    self.frames[NowPlaying].vol_level = v;
                    pygame.mixer.music.set_volume(v)
                    rep = data.get("repeat", False);
                    self.frames[NowPlaying].repeat = rep;
                    self.sleep_limit = data.get("sleep_limit", 0)
            except:
                pass

    def queue_save(self):
        if self._save: self.after_cancel(self._save)
        self._save = self.after(5000, self.save_now)

    def save_now(self):
        try:
            settings = {"volume": self.frames[NowPlaying].vol_level, "repeat": self.frames[NowPlaying].repeat,
                        "sleep_limit": self.sleep_limit, "overlay": self.overlay.winfo_ismapped()}
            with open(self.cfg, "w") as f:
                json.dump(settings, f)
        except:
            pass

    def check_loops(self):
        if self.playlist and not pygame.mixer.music.get_busy() and not self.is_paused:
            np = self.frames[NowPlaying]
            if self.idx < len(self.playlist) - 1:
                self.play_track(self.playlist, self.idx + 1, self.path)
            elif np.repeat:
                self.play_track(self.playlist, 0, self.path)
            if self.current_screen == NowPlaying: np.refresh()
        if self.sleep_limit > 0 and not self.is_asleep and (time.time() - self.last_act > self.sleep_limit / 1000):
            self.is_asleep = True;
            os.system("xset dpms force off")
        self.after(4000, self.check_loops)

    def handle_keys(self, e):
        if self.is_asleep: self.is_asleep = False; os.system(
            "xset dpms force on"); self.last_act = time.time(); return "break"
        self.last_act = time.time();
        f = self.frames[self.current_screen];
        k = e.keysym
        if k in ("Right", "Left"):
            f.move(1 if k == "Right" else -1, is_vertical=False)
        elif k in ("Up", "Down"):
            if self.current_screen == NowPlaying:
                f.change_volume(1 if k == "Up" else -1)
            else:
                f.move(-1 if k == "Up" else 1, is_vertical=True)
        elif k in ("Return", "KP_Enter"):
            if hasattr(f, "trigger_selection"):
                f.trigger_selection()
            elif hasattr(f, "btns"):
                f.btns[f.cur_idx].invoke()
        return "break"

    def show_frame(self, c):
        self.current_screen = c;
        self.frames[c].tkraise();
        self.frames[c].focus_set()
        if hasattr(self.frames[c], 'refresh'): self.after(50, self.frames[c].refresh)

    def toggle_stats_overlay(self, show):
        if show:
            self.overlay.place(relx=1.0, x=-5, y=5, anchor="ne"); self.overlay.lift(); self.update_ov()
        else:
            self.overlay.place_forget()

    def update_ov(self):
        if self.overlay.winfo_ismapped():
            try:
                import psutil
                with open("/sys/class/thermal/thermal_zone0/temp") as f:
                    t = int(f.read()) / 1000
                self.overlay.config(text=f"CPU:{psutil.cpu_percent()}%|{t:.0f}°")
            except:
                pass
            self.after(6000, self.update_ov)

    def play_track(self, pl, i, p):
        self.playlist, self.idx, self.path, self.is_paused = pl, i, p, False
        try:
            pygame.mixer.music.load(os.path.join(p, pl[i]));
            pygame.mixer.music.play()
            if self.current_screen != NowPlaying: self.show_frame(NowPlaying)
        except:
            pass

    def restart_app(self):
        pygame.mixer.quit(); os.execv(sys.executable, ['python3'] + sys.argv)

    def quit_app(self):
        pygame.mixer.quit(); self.destroy()


if __name__ == "__main__": App().mainloop()