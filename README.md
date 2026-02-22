# PiDice Media Center and Networking Hub

PiDice is a specialized, lightweight media player and networking utility designed for devices running **DietPi**. It balances hardware efficiency with a high-contrast, adaptable user interface that scales dynamically to any screen size.

## Core Features

### High-Stability Audio Architecture
* **Low-Latency Playback**: Leverages `pygame.mixer` with custom pre-initialization (44.1kHz, 16-bit) and a large 4096-sample buffer to prevent audio dropouts.
* **Process Priority**: Automatically adjusts Linux "niceness" levels (`os.nice(-10)`) to ensure audio handling takes precedence over UI tasks.
* **Smart Sorting**: Implementation of natural sorting algorithms for logical track and playlist ordering.

### Dynamic User Interface
* **Responsive Scaling**: Utilizes dynamic geometry management (`winfo_screenwidth`) to automatically fit the resolution of the connected display.
* **Coverflow Browser**: A Canvas-driven, 3-panel interactive carousel for navigating album folders.
* **System Telemetry**: Integrated TopBar displaying live CPU utilization and core temperature readings.

### Performance Management
* **Frame Rate Control**: User-configurable FPS cap (5–30 FPS) via the Settings menu to manage power and heat.
* **Persistent Configuration**: Automated state saving (Volume, Repeat, FPS) via a local `settings.json` file.
* **Localized Synchronization**: Hardcoded timezone handling for consistent time display across Swedish regions.

## Directory Structure

To ensure functionality, the music library must follow this specific hierarchy:

```text
/home/dietpi/pidice/
├── main.py            # Main application script
├── settings.json      # Auto-generated configuration file
└── MP3s/              # Root music directory
    ├── Playlist_Name/
    │   ├── cover.png  # Folder artwork (required for Coverflow)
    │   └── track1.mp3 # Audio files
