#!/bin/bash
# start.sh

# 1. Run the app
sudo xinit /usr/bin/sh -c "matchbox-window-manager -use_titlebar no & /home/dietpi/pidice/venv/bin/python3 /home/dietpi/pidice/main.py" -- :0 -novtswitch

# 2. When you click 'Quit', xinit will close and the script reaches here.
clear
echo "----------------------------------------------------"
echo " PI-DICE HAS EXITED TO TERMINAL"
echo "----------------------------------------------------"
echo " The app will restart if you log out or reboot."
echo " To return to the command line, stay on this screen."
echo ""
echo " PRESS ANY KEY TO RESTART THE APP MANUALLY"
echo "----------------------------------------------------"

# 3. This 'read' command stops the script from finishing.
# As long as it's waiting, the system won't restart the app.
read -n 1 -s