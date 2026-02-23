#!/bin/bash
# start.sh

# Start the app (Rotation is now handled by the system)
sudo xinit /usr/bin/sh -c "matchbox-window-manager -use_titlebar no & /home/dietpi/pidice/venv/bin/python3 /home/dietpi/pidice/main.py" -- :0 -novtswitch