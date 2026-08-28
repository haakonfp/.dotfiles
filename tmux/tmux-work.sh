#!/bin/bash

SESSION_NAME="work"
WORK_DIR="$HOME/dev/osirion"
DEFAULT_SUBDIR="apps/web3"

default_dir() {
    echo "$WORK_DIR/$DEFAULT_SUBDIR"
}

absolute_dir() {
    (cd "$1" && pwd -P)
}

shell_quote() {
    printf "%q" "$1"
}

tmux_cd() {
    tmux send-keys -t "$1" "cd $(shell_quote "$2")" C-m
}

tmux_run() {
    tmux send-keys -t "$1" "cd $(shell_quote "$2") && $3" C-m
}

resolve_target_dir() {
    local input="$1"
    local found

    if [ -z "$input" ]; then
        default_dir
        return 0
    fi

    case "$input" in
        "~") input="$HOME" ;;
        "~/"*) input="$HOME/${input#~/}" ;;
    esac

    if [ -d "$input" ]; then
        absolute_dir "$input"
        return 0
    fi

    if [ -d "$WORK_DIR/$input" ]; then
        absolute_dir "$WORK_DIR/$input"
        return 0
    fi

    case "$input" in
        */*) return 1 ;;
    esac

    found=$(find "$WORK_DIR" -maxdepth 3 \
        \( -name ".git" -o -name "node_modules" -o -name ".turbo" -o -name ".svelte-kit" -o -name "build" -o -name "dist" \) -prune \
        -o -type d -name "$input" -print -quit)

    if [ -n "$found" ]; then
        absolute_dir "$found"
        return 0
    fi

    return 1
}

# determine working directory
if [ -n "$1" ]; then
    TARGET_DIR=$(resolve_target_dir "$1")
    if [ -n "$TARGET_DIR" ]; then
        echo "Found directory: $TARGET_DIR"
    else
        echo "Warning: Directory matching '$1' not found. Using default."
        TARGET_DIR=$(default_dir)
    fi
else
    TARGET_DIR=$(default_dir)
fi

tmux has-session -t $SESSION_NAME 2>/dev/null

if [ $? != 0 ]; then
    tmux new-session -d -s $SESSION_NAME -n "vim" -c "$TARGET_DIR"
    tmux_run "$SESSION_NAME:vim" "$TARGET_DIR" "nvim"
    tmux new-window -t $SESSION_NAME:1 -n "run" -c "$WORK_DIR"
    tmux_cd "$SESSION_NAME:run" "$WORK_DIR"
    tmux new-window -t $SESSION_NAME:2 -n "browse" -c "$WORK_DIR"
    tmux_cd "$SESSION_NAME:browse" "$WORK_DIR"
    tmux new-window -t $SESSION_NAME:3 -n "codex" -c "$TARGET_DIR"
    tmux_run "$SESSION_NAME:codex" "$TARGET_DIR" "clear && codex"
    tmux select-window -t $SESSION_NAME:0
else
    echo "work session already exists. attaching..."
fi

tmux attach-session -t $SESSION_NAME
