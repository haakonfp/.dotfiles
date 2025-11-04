#!/bin/bash

SESSION_NAME="work"
WORK_DIR="$HOME/dev/osirion"
DEFAULT_SUBDIR="apps/web"

# function to find directory up to 2 levels deep
find_subdir() {
    local search_term="$1"
    local found=$(find "$WORK_DIR" -maxdepth 2 -type d -name "$search_term" -print -quit)
    echo "$found"
}

# determine working directory
if [ -n "$1" ]; then
    FOUND_DIR=$(find_subdir "$1")
    if [ -n "$FOUND_DIR" ]; then
        TARGET_DIR="$FOUND_DIR"
        echo "Found directory: $TARGET_DIR"
    else
        echo "Warning: Directory matching '$1' not found. Using default."
        TARGET_DIR="$WORK_DIR/$DEFAULT_SUBDIR"
    fi
else
    TARGET_DIR="$WORK_DIR/$DEFAULT_SUBDIR"
fi

tmux has-session -t $SESSION_NAME 2>/dev/null

if [ $? != 0 ]; then
    tmux new-session -d -s $SESSION_NAME -n "vim" -c "$TARGET_DIR"
    tmux send-keys -t $SESSION_NAME:vim "nvim" C-m
    tmux new-window -t $SESSION_NAME:1 -n "run" -c "$TARGET_DIR"
    tmux new-window -t $SESSION_NAME:2 -n "browse" -c "$WORK_DIR"
    tmux new-window -t $SESSION_NAME:3 -n "opencode" -c "$TARGET_DIR"
    tmux send-keys -t $SESSION_NAME:opencode "opencode" C-m
    tmux select-window -t $SESSION_NAME:0
else
    echo "work session already exists. attaching..."
fi

tmux attach-session -t $SESSION_NAME
