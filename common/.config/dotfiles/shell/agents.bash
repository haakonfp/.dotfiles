# Lightweight client routing shared by interactive Bash and owned subprocesses.
# Keep agent hooks attached to the terminal's tmux environment.
unalias codex 2>/dev/null || :
codex() {
  local argument
  for argument in "$@"; do
    [[ $argument != --no-daemon ]] || { command codex "$@"; return; }
  done
  if [[ -n ${TMUX:-} ]] && command codex --help 2>/dev/null | command grep -q -- --no-daemon; then
    command codex --no-daemon "$@"
  else
    command codex "$@"
  fi
}
if [[ -r $HOME/.config/dotfiles/epic.enabled && -r $HOME/.config/dotfiles/shell/epic.bash ]] &&
  { [[ -n ${WSL_DISTRO_NAME:-} ]] || [[ $(uname -r) == *[Mm]icrosoft* ]]; }; then
  source "$HOME/.config/dotfiles/shell/epic.bash"
fi
