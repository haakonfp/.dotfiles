# Shared interactive Bash configuration. Private additions go in local.bash.
export EDITOR=nvim
export VISUAL=nvim
export SUDO_EDITOR=nvim
export BAT_THEME=ansi
export LESS=-FRX
# Omarchy may already append this directory. Keep compatible local fallbacks
# ahead of system tools, preserving other entries (including empty entries).
function _dotfiles_prepend_path {
  local directory=$1 rest=${PATH-} entry result=$1
  while [[ $rest == *:* ]]; do
    entry=${rest%%:*}
    rest=${rest#*:}
    [[ $entry == "$directory" ]] || result+=":$entry"
  done
  [[ $rest == "$directory" ]] || result+=":$rest"
  export PATH=$result
}
_dotfiles_prepend_path "$HOME/.local/bin"
unset -f _dotfiles_prepend_path
[[ -r $HOME/.cargo/env ]] && source "$HOME/.cargo/env"
if [[ ${DOTFILES_OMARCHY:-0} != 1 ]]; then
  shopt -s histappend checkwinsize
  HISTCONTROL=ignoreboth
  HISTSIZE=32768
  HISTFILESIZE=32768
  [[ -r /usr/share/bash-completion/bash_completion ]] && source /usr/share/bash-completion/bash_completion
  command -v mise >/dev/null && eval "$(mise activate bash)"
  command -v starship >/dev/null && eval "$(starship init bash)"
  command -v zoxide >/dev/null && eval "$(zoxide init bash)"
  if [[ -r /usr/share/fzf/key-bindings.bash ]]; then
    source /usr/share/fzf/key-bindings.bash
  elif [[ -r /usr/share/doc/fzf/examples/key-bindings.bash ]]; then
    source /usr/share/doc/fzf/examples/key-bindings.bash
  fi
  [[ -r /usr/share/bash-completion/completions/fzf ]] && source /usr/share/bash-completion/completions/fzf
  [[ -r $HOME/.config/dotfiles/inputrc ]] && bind -f "$HOME/.config/dotfiles/inputrc"
  alias ..='cd ..'
  alias ...='cd ../..'
  alias ....='cd ../../..'
  alias g=git
  alias gcm='git commit -m'
  alias gcam='git commit -a -m'
  alias gcad='git commit -a --amend'
  alias d=docker
  if command -v zoxide >/dev/null; then
    zd() { if (($# == 0)); then builtin cd ~; elif [[ -d $1 ]]; then builtin cd -- "$1"; else z "$@"; fi; }
    alias cd=zd
  fi
fi
if command -v eza >/dev/null; then
  alias eza='eza -al'
  alias ls='eza -lh --group-directories-first --icons=auto'
  alias lsa='ls -a'
  alias lt='eza --tree --level=2 --long --icons --git'
  alias lta='lt -a'
  alias xl='eza -lga --icons'
fi
alias gst='git s'
alias gp='git push'
alias py=python3
alias python=python3
alias py-source='source .venv/bin/activate'
alias uv-source='uv venv && source .venv/bin/activate'
alias uvicorn='python3 -m uvicorn'
alias pvim='py-source && nvim'
alias nvimconfig='cd "$HOME/.config/nvim" && nvim'
alias t='"$HOME/.config/tmux/project"'
# Stock Omarchy defines these as aliases; interactive Bash expands aliases
# while parsing function definitions unless we remove the conflicting names.
unalias ff eff 2>/dev/null || :
n() { if (($#)); then command nvim "$@"; else command nvim .; fi; }
ff() { command fzf --preview 'bat --style=numbers --color=always -- {}' "$@"; }
eff() { local selected; selected=$(ff) && [[ -n $selected ]] && nvim -- "$selected"; }
clip() {
  if [[ -n ${WAYLAND_DISPLAY:-} ]] && command -v wl-copy >/dev/null; then wl-copy "$@"
  elif command -v clip.exe >/dev/null; then clip.exe
  else printf 'No clipboard backend available\n' >&2; return 1; fi
}
open() {
  if [[ -n ${WSL_DISTRO_NAME:-} ]] || [[ $(uname -r) == *[Mm]icrosoft* ]]; then
    if command -v wslview >/dev/null; then command wslview "$@"
    elif command -v explorer.exe >/dev/null; then command explorer.exe "$@"
    else printf 'Windows browser integration unavailable\n' >&2; return 1; fi
  else command xdg-open "$@" >/dev/null 2>&1 & fi
}
source "${BASH_SOURCE[0]%/*}/agents.bash"
[[ -r $HOME/.config/dotfiles/local.bash ]] && source "$HOME/.config/dotfiles/local.bash"
:
