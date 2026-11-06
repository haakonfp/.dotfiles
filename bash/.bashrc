# Omarchy needs its environment even for noninteractive SSH shells.
DOTFILES_BASHRC_LOADED=1
if [[ -r /usr/share/omarchy/default/bash/env-bootstrap ]]; then
  source /usr/share/omarchy/default/bash/env-bootstrap
fi
[[ $- != *i* ]] && return
if [[ -r ${OMARCHY_PATH:-/usr/share/omarchy}/default/bash/rc ]]; then
  source "${OMARCHY_PATH:-/usr/share/omarchy}/default/bash/rc"
  DOTFILES_OMARCHY=1
fi
[[ -r $HOME/.config/dotfiles/shell/common.bash ]] && source "$HOME/.config/dotfiles/shell/common.bash"
