#!/bin/bash

SESSION_NAME="work"
WORK_DIR="$HOME/dev/osirion"

tmux has-session -t $SESSION_NAME 2>/dev/null

if [ $? != 0 ]; then
    tmux new-session -d -s $SESSION_NAME -n "vim" -c "$WORK_DIR/apps/web"
    tmux send-keys -t $SESSION_NAME:vim "nvim" C-m
    tmux new-window -t $SESSION_NAME:1 -n "run" -c "$WORK_DIR/apps/web"
    tmux new-window -t $SESSION_NAME:2 -n "browse" -c "$WORK_DIR"
	tmux select-window -t $SESSION_NAME:0
else
    echo "work session already exists. attaching..."
fi

tmux attach-session -t $SESSION_NAME
