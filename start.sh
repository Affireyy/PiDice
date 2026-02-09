#!/bin/bash

sudo xinit /usr/bin/sh -c "matchbox-window-manager -use_titlebar no & python3 /home/dietpi/pidice/main.py" -- :0 -novtswitch