# Optional WSL-only routing. Loading this file defines functions; no startup probes.
_epic_require_wsl() {
  local release os
  release=$(uname -r) || return
  os=$(cat /etc/os-release) || return
  if [[ ${release,,} != *microsoft* ]] || ! [[ $'\n'"$os"$'\n' == *$'\nID=ubuntu\n'* || $'\n'"$os"$'\n' == *$'\nID="ubuntu"\n'* ]]; then
    printf 'Epic commands require Ubuntu WSL.\n' >&2
    return 1
  fi
}
_epic_workspace() {
  local current root
  current=$(pwd -P) || return 1
  # realpath -m resolves symlink ancestors even before a workspace is created.
  root=$(realpath -m -- "${EPIC_WORKSPACE:-$HOME/dev/epic}") || return 1
  [[ $current == "$root" || $current == "$root/"* ]]
}
_epic_clean_env() {
  # Run in a child process: no unsets or profile exports leak into the shell.
  local name
  local -a options=()
  while IFS= read -r name; do
    case $name in
      ANTHROPIC_*|OPENAI_*|CODEX_*|CLAUDE_*|AWS_*|AZURE_OPENAI_*|GOOGLE_API_KEY|GOOGLE_APPLICATION_CREDENTIALS|GEMINI_API_KEY)
        options+=(-u "$name") ;;
    esac
  done < <(compgen -e)
  command env "${options[@]}" "$@"
}
_epic_agent() {
  local agent=$1 profile=$2
  shift 2
  _epic_require_wsl || return
  local information=false
  if [[ $agent == claude && $# == 1 ]]; then
    case $1 in --version|-v|--help|-h) information=true ;; esac
  fi
  local claude_home="$HOME/.claude" codex_home="$HOME/.codex"
  if [[ $profile == epic ]]; then
    claude_home="$HOME/.claude-epic"
    codex_home="$HOME/.codex-epic"
    if [[ $agent == claude ]]; then
      $information || [[ -f $claude_home/settings.json && -f $claude_home/gateway-helper-config.json ]] || {
        printf 'Epic Claude is not configured. Run: epic-ai-setup\n' >&2; return 1;
      }
    else
      [[ -f $codex_home/config.toml && -f $codex_home/claude-gateway.json ]] || {
        printf 'Epic Codex is not configured. Run: epic-ai-setup\n' >&2; return 1;
      }
    fi
  else
    # Codex requires an explicitly selected home to exist. Create only the
    # invoked personal client's directory; existing account state stays intact.
    local personal_home=$codex_home
    [[ $agent != claude ]] || personal_home=$claude_home
    if ! $information && [[ ! -e $personal_home && ! -L $personal_home ]]; then
      (umask 077; mkdir -p -- "$personal_home") || return
    fi
  fi
  local argument no_daemon=false
  for argument in "$@"; do [[ $argument != --no-daemon ]] || no_daemon=true; done
  if [[ $agent == codex && -n ${TMUX:-} ]] && ! $no_daemon; then
    # The flag is client-dependent. Help is local, and runs only when invoking Codex.
    if _epic_clean_env codex --help 2>/dev/null | command grep -q -- --no-daemon; then
      set -- --no-daemon "$@"
    fi
  fi
  local -a homes=("CLAUDE_CONFIG_DIR=$claude_home" "CODEX_HOME=$codex_home")
  if [[ $profile == epic ]]; then
    homes+=("CLAUDE_GATEWAY_USER_CONFIG_FILE=$claude_home/gateway-helper-config.json"
      "CLAUDE_GATEWAY_CODEX_USER_CONFIG_FILE=$codex_home/claude-gateway.json")
  fi
  _epic_clean_env "${homes[@]}" "$agent" "$@"
}
claude-epic() { _epic_agent claude epic "$@"; }
codex-epic() { _epic_agent codex epic "$@"; }
claude() {
  if _epic_workspace; then claude-epic "$@"; else _epic_agent claude personal "$@"; fi
}
codex() {
  if _epic_workspace; then codex-epic "$@"; else _epic_agent codex personal "$@"; fi
}
