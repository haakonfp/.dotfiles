#!/bin/bash

SESSION_NAME="dev"

tmux has-session -t $SESSION_NAME 2>/dev/null

if [ $? != 0 ]; then
    tmux new-session -d -s $SESSION_NAME -n "vim"
    # tmux send-keys -t $SESSION_NAME:vim "nvim" C-m
    tmux new-window -t $SESSION_NAME:1 -n "run"
    tmux new-window -t $SESSION_NAME:2 -n "browse"
	tmux select-window -t $SESSION_NAME:0
else
    echo "dev session already exists. attaching..."
fi

tmux attach-session -t $SESSION_NAME
