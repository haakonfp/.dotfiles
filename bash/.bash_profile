# Preserve the login initialization Bash used before enrolling this machine.
if [[ -r $HOME/.bash_profile.before-dotfiles ]]; then
  source "$HOME/.bash_profile.before-dotfiles"
elif [[ -r $HOME/.bash_login ]]; then
  source "$HOME/.bash_login"
elif [[ -r $HOME/.profile ]]; then
  source "$HOME/.profile"
fi
if [[ ${DOTFILES_BASHRC_LOADED:-0} != 1 && -r $HOME/.bashrc ]]; then
  source "$HOME/.bashrc"
fi
:
