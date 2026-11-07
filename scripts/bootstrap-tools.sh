#!/usr/bin/env bash
# Explicit provisioning only. Sourcing this library performs no work.
bootstrap_usage() {
  cat <<'EOF'
Usage: ./bootstrap --profile omarchy|wsl [--epic] [--dry-run]
                   [--windows-fonts] [--windows-settings PATH]
Installs missing tools, fonts and the pinned tmux sidebar, then links dotfiles.
--dry-run performs no writes, package operations, downloads or Windows commands.
--epic requires Ubuntu WSL; account setup remains a separate epic-ai-setup command.
Windows Terminal settings are applied only when --windows-settings PATH is supplied.
EOF
}
bootstrap_error() { printf '%s\n' "$*" >&2; return 1; }
bootstrap_ubuntu_wsl() {
  local release os
  release=$(uname -r) || return 1
  os=$(cat /etc/os-release) || return 1
  [[ ${release,,} == *microsoft* ]] &&
    [[ $'\n'"$os"$'\n' == *$'\nID=ubuntu\n'* || $'\n'"$os"$'\n' == *$'\nID="ubuntu"\n'* ]]
}
bootstrap_wsl2() {
  local release
  release=$(uname -r) || return 1
  # Microsoft standard kernels identify WSL2, including older kernels whose
  # release ends in -microsoft-standard without the later -WSL2 suffix.
  case ${release,,} in
    *microsoft-standard*|*microsoft*wsl2*) return 0 ;;
    *) bootstrap_error 'Native Docker requires WSL2 with a Microsoft standard kernel. Check wsl.exe --list --verbose from Windows; convert WSL1 before retrying.' ;;
  esac
}
bootstrap_fetch() {
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 "$1" -o "$2"
}
bootstrap_docker_preflight() {
  # Local metadata only; never contact a daemon, registry or remote context.
  local context endpoint resolved package
  [[ -z ${DOCKER_HOST:-} || ${DOCKER_HOST} == unix:///var/run/docker.sock ]] || {
    bootstrap_error 'Docker conflict: DOCKER_HOST selects a foreign daemon. Keep the existing setup or clear it explicitly.'; return 1;
  }
  [[ -z ${DOCKER_CONTEXT:-} || ${DOCKER_CONTEXT} == default ]] || {
    bootstrap_error 'Docker conflict: a non-default DOCKER_CONTEXT is selected.'; return 1;
  }
  if [[ -S /var/run/docker.sock || -L /var/run/docker.sock ]]; then
    resolved=$(readlink -f /var/run/docker.sock) || return
    [[ $resolved == /run/docker.sock || $resolved == /var/run/docker.sock ]] || {
      bootstrap_error 'Docker conflict: the existing socket points outside native Docker.'; return 1;
    }
  fi
  if command -v docker >/dev/null; then
    resolved=$(readlink -f "$(command -v docker)") || return
    [[ $resolved != /mnt/* && $resolved != *docker-desktop* ]] || {
      bootstrap_error 'Docker Desktop integration detected; refusing to install a competing native Docker engine.'; return 1;
    }
    context=$(docker context show 2>/dev/null) || {
      bootstrap_error 'Docker exists but its active context cannot be inspected; preserve it and resolve manually.'; return 1;
    }
    [[ $context == default ]] || {
      bootstrap_error 'Docker Desktop or foreign Docker context detected; refusing a competing engine.'; return 1;
    }
    endpoint=$(docker context inspect default --format '{{.Endpoints.docker.Host}}' 2>/dev/null) || return
    [[ $endpoint == unix:///var/run/docker.sock || $endpoint == unix:///run/docker.sock ]] || {
      bootstrap_error 'Docker conflict: the default context uses a foreign daemon endpoint.'; return 1;
    }
    package=$(dpkg-query -W -f='${Status}' docker.io 2>/dev/null || true)
    [[ $package == 'install ok installed' ]] || {
      bootstrap_error 'Existing Docker is not Ubuntu docker.io; preserving it rather than mixing package sources.'; return 1;
    }
  elif [[ -e /mnt/wsl/docker-desktop/cli-tools/usr/bin/docker || -d /mnt/wsl/docker-desktop/shared-sockets ]]; then
    bootstrap_error 'Docker Desktop integration detected; disable it explicitly before choosing native Docker.'; return 1
  fi
  for package in docker-ce docker-ce-cli containerd.io podman-docker; do
    if [[ $(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true) == 'install ok installed' ]]; then
      bootstrap_error "Docker conflict: $package is installed; refusing to replace an existing container setup."; return 1
    fi
  done
}
bootstrap_packages() {
  local profile=$1 package
  local -a missing=()
  if [[ $profile == wsl ]]; then
    # LTS-version-specific dependencies are resolved by apt rather than hardcoded ICU names.
    local -a packages=(bash bash-completion git tmux fzf fd-find ripgrep bat jq curl ca-certificates
      unzip zip xz-utils tar stow build-essential pkg-config libssl-dev libevent-dev
      libncurses-dev libicu-dev libgssapi-krb5-2 zlib1g bison python3 python3-venv python3-pip fontconfig wl-clipboard
      docker.io docker-compose-v2 docker-buildx)
    for package in "${packages[@]}"; do
      [[ $(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true) == 'install ok installed' ]] || missing+=("$package")
    done
    if ((${#missing[@]})); then
      sudo apt-get update
      # No dist-upgrade, no removals, and no external Docker repository.
      sudo apt-get install --no-remove -y "${missing[@]}"
    fi
  else
    command -v omarchy >/dev/null || { bootstrap_error 'Use the Omarchy profile on an installed Omarchy system.'; return 1; }
    omarchy pkg add foot brave-bin spotify bash bash-completion git github-cli tmux neovim starship zoxide eza fzf fd ripgrep bat jq lazygit \
      curl ca-certificates unzip zip xz tar stow base-devel openssl libevent ncurses python python-pip fontconfig
  fi
}
bootstrap_alias_commands() {
  local pair name alternate target
  for pair in fd:fdfind bat:batcat; do
    name=${pair%%:*}; alternate=${pair#*:}
    if ! command -v "$name" >/dev/null && command -v "$alternate" >/dev/null; then
      target="$HOME/.local/bin/$name"
      [[ ! -e $target && ! -L $target ]] || { bootstrap_error "$target exists but is not executable; preserve it and resolve manually."; return 1; }
      ln -s -- "$(command -v "$alternate")" "$target"
    fi
  done
}
bootstrap_rust() {
  if ! command -v rustup >/dev/null; then
    if command -v cargo >/dev/null || command -v rustc >/dev/null; then
      bootstrap_error 'Rust exists without rustup. Preserve its ownership; install rustup explicitly before continuing.'; return 1
    fi
    bootstrap_fetch https://sh.rustup.rs "$bootstrap_stage/rustup.sh"
    bash "$bootstrap_stage/rustup.sh" -y --no-modify-path --profile default --default-toolchain stable
  fi
  # Add stable only when missing, without changing the default or directory overrides.
  if ! rustup toolchain list | grep -q '^stable-'; then
    rustup toolchain install stable --profile default --component rustfmt --component clippy
  else
    local components
    components=$(rustup component list --toolchain stable --installed)
    [[ $components == *rustfmt-* ]] || rustup component add --toolchain stable rustfmt
    [[ $components == *clippy-* ]] || rustup component add --toolchain stable clippy
  fi
}
bootstrap_version_at_least() {
  local current=${1#v} minimum=$2
  [[ $current =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] &&
    [[ $(printf '%s\n%s\n' "$minimum" "$current" | sort -V | head -1) == "$minimum" ]]
}
bootstrap_runtime() {
  local tool=$1 executable resolved
  local mise_data="${MISE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/mise}"
  shift
  executable=$(command -v "$tool") || return 1
  resolved=$(readlink -f -- "$executable") || return 1
  if [[ $resolved == "$mise_data/"* || $executable == "$mise_data/"* ]]; then
    # An activated parent shell can pass a project-only tool's direct path.
    # cd alone does not undo activation in a noninteractive bootstrap child.
    executable=$(mise -C / which "$tool" 2>/dev/null) || return 1
  fi
  (cd / && "$executable" "$@")
}
bootstrap_dotnet_sdk() {
  local sdk available_sdks
  # Mason installs from its staging directory, not from this checkout. A mise
  # project selection here does not establish a usable default elsewhere.
  available_sdks=$(bootstrap_runtime dotnet --list-sdks 2>/dev/null) || return 1
  while read -r sdk _; do
    if [[ $sdk =~ ^([0-9]+)\. ]] && (( BASH_REMATCH[1] >= 8 )); then return 0; fi
  done <<< "$available_sdks"
  return 1
}
bootstrap_mise() {
  local profile=${1:-omarchy} tool spec current minimum backup='' environment result
  local config_dir="${MISE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/mise}"
  local config="$config_dir/conf.d/dotfiles.toml"
  local global_config="${MISE_GLOBAL_CONFIG_FILE:-$config_dir/config.toml}"
  local -a runtimes=() tools=()
  for spec in node@26.8.2 pnpm@12.11.2; do
    tool=${spec%@*}; minimum=${spec#*@}
    current=$(bootstrap_runtime "$tool" --version 2>/dev/null) || current=''
    if bootstrap_version_at_least "$current" "$minimum"; then
      printf 'Keeping compatible %s: %s.\n' "$tool" "$current"
    else
      printf 'Provisioning %s with mise (missing or older than %s).\n' "$tool" "$minimum"
      runtimes+=("$spec")
    fi
  done
  bootstrap_dotnet_sdk || runtimes+=(dotnet@10)
  [[ $profile != wsl ]] || runtimes+=(neovim@0.12.6)
  if ! command -v mise >/dev/null; then
    bootstrap_fetch https://mise.run "$bootstrap_stage/mise.sh"
    MISE_INSTALL_PATH="$HOME/.local/bin/mise" bash "$bootstrap_stage/mise.sh"
  fi
  # Utilities use our fragment. Runtimes and AI clients become actual global
  # defaults: the main config outranks fragments, and project pins stay intact.
  for spec in gh@latest starship@latest zoxide@latest eza@latest lazygit@latest; do
    tool=${spec%@*}
    if ! command -v "$tool" >/dev/null; then
      tools+=("$spec")
    fi
  done
  mkdir -p -- "${global_config%/*}"
  if [[ -e $global_config || -L $global_config ]]; then
    backup=$(mktemp "$global_config.before-dotfiles.XXXXXX") || return
    cp -- "$global_config" "$backup" || return
  fi
  # An explicit @latest resolves the newest release even when an older client
  # is already installed. Both accounts share these binaries, not their homes.
  mise -C / use --path "$global_config" --pin "${runtimes[@]}" claude@latest codex@latest || {
    result=$?
    [[ -z $backup ]] || printf 'Mise configuration backup: %s\n' "$backup"
    return "$result"
  }
  if [[ -n $backup ]]; then
    if cmp -s -- "$backup" "$global_config"; then
      rm -- "$backup" || return
    else
      printf 'Mise configuration backup: %s\n' "$backup"
    fi
  fi
  if ((${#tools[@]})); then
    mkdir -p -- "${config%/*}"
    mise -C / use --path "$config" --pin "${tools[@]}" || return
  fi
  mise reshim || return
  # A noninteractive bootstrap has no prompt hook. Always activate the checked
  # global environment, including when a parent supplied a project-only PATH.
  # Neovim children then inherit the SDK and DOTNET_ROOT outside the checkout.
  environment=$(mise -C / env --shell bash) || return
  eval "$environment"
  hash -r
  for spec in node@26.8.2 pnpm@12.11.2; do
    tool=${spec%@*}
    current=$(bootstrap_runtime "$tool" --version 2>/dev/null) || current=''
    bootstrap_version_at_least "$current" "${spec#*@}" || {
      bootstrap_error "Mise provisioning did not activate $tool >= ${spec#*@}; inspect your mise overrides before retrying."; return 1;
    }
  done
  bootstrap_dotnet_sdk || { bootstrap_error 'Mise provisioning did not activate a .NET SDK >=8; inspect mise overrides and DOTNET_ROOT before retrying.'; return 1; }
}
bootstrap_neovim() {
  local profile=${1:-omarchy}
  local check='+lua if vim.fn.has("nvim-0.12.0") == 0 then vim.cmd("cquit 1") end'
  if [[ $profile == wsl ]]; then
    local selected shim entry previous
    selected=$(mise -C / which nvim) || {
      bootstrap_error 'Mise has no global Neovim; rerun bootstrap to provision it.'; return 1;
    }
    "$selected" --clean --headless "$check" +qa >/dev/null 2>&1 || {
      bootstrap_error 'Mise Neovim must be >=0.12.0 for the locked editor plugins.'; return 1;
    }
    shim="${MISE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/mise}/shims/nvim"
    [[ -x $shim ]] || { bootstrap_error 'Mise Neovim shim is missing; run mise reshim and retry.'; return 1; }
    entry="$HOME/.local/bin/nvim"
    if [[ -e $entry || -L $entry ]]; then
      previous=$(readlink -- "$entry" 2>/dev/null) || previous=''
      if [[ ! -L $entry || ( $previous != "$shim" && $previous != "$HOME/.local/opt/neovim-0.12.6/bin/nvim" ) ]]; then
        bootstrap_error 'Preserving existing ~/.local/bin/nvim; move it aside before selecting mise.'; return 1
      fi
    fi
    mkdir -p -- "${entry%/*}"
    ln -sfn -- "$shim" "$entry"
    hash -r
    return 0
  fi
  # The locked nvim-treesitter revision requires Neovim 0.12.0 or newer.
  if command -v nvim >/dev/null && nvim --clean --headless "$check" +qa >/dev/null 2>&1; then
    return 0
  fi
  # Provide the portable fallback even when another manager is installed.
  # Its files/version selection remain intact; only a conflict at our own
  # ~/.local/bin/nvim path needs manual reconciliation below.
  local arch archive target="$HOME/.local/opt/neovim-0.12.6"
  arch=$(uname -m)
  case $arch in x86_64) arch=x86_64 ;; aarch64|arm64) arch=arm64 ;; *) bootstrap_error "Unsupported Neovim architecture: $arch"; return 1 ;; esac
  archive="nvim-linux-$arch.tar.gz"
  if [[ ! -x $target/bin/nvim ]]; then
    bootstrap_fetch "https://github.com/neovim/neovim/releases/download/v0.12.6/$archive" "$bootstrap_stage/$archive"
    mkdir -p -- "$bootstrap_stage/neovim" "$HOME/.local/opt"
    tar -xzf "$bootstrap_stage/$archive" -C "$bootstrap_stage/neovim" --strip-components=1
    [[ ! -e $target && ! -L $target ]] || { bootstrap_error "Preserving conflicting $target"; return 1; }
    mv -- "$bootstrap_stage/neovim" "$target"
  fi
  if [[ -e $HOME/.local/bin/nvim || -L $HOME/.local/bin/nvim ]]; then
    [[ $(readlink -f "$HOME/.local/bin/nvim") == "$target/bin/nvim" ]] || {
      bootstrap_error 'Existing ~/.local/bin/nvim is incompatible; preserve it and resolve manually.'; return 1;
    }
  else
    ln -s -- "$target/bin/nvim" "$HOME/.local/bin/nvim"
  fi
  hash -r
}
bootstrap_tmux() {
  # A unique private server checks the actual parser, never an existing session.
  local socket="dotfiles-bootstrap-$$" version result=0
  if command -v tmux >/dev/null; then
    version=$(tmux -V)
    if [[ $version =~ tmux\ ([0-9]+)\.([0-9]+) ]] &&
        (( BASH_REMATCH[1] > 3 || (BASH_REMATCH[1] == 3 && BASH_REMATCH[2] >= 3) )); then
      tmux -L "$socket" -f /dev/null new-session -d -s capability \; set-option -g extended-keys-format csi-u >/dev/null 2>&1 || result=$?
      tmux -L "$socket" kill-server >/dev/null 2>&1 || true
      ((result == 0)) && return 0
    fi
  fi
  bootstrap_fetch https://github.com/tmux/tmux/releases/download/3.6a/tmux-3.6a.tar.gz "$bootstrap_stage/tmux.tar.gz"
  tar -xzf "$bootstrap_stage/tmux.tar.gz" -C "$bootstrap_stage"
  (cd "$bootstrap_stage/tmux-3.6a" && ./configure --prefix="$HOME/.local" && make -j2 && make install)
}
bootstrap_editor_assets() {
  # Neovim may exit zero after command/Lua errors followed by +qa. Protect
  # script loading too, and turn every initialization error into a process failure.
  local protected='lua local ok, err = xpcall(function() assert(vim.v.errmsg == "", vim.v.errmsg); dofile(vim.env.DOTFILES_EDITOR_SCRIPT) end, debug.traceback); if not ok then vim.api.nvim_err_writeln(err); vim.cmd("cquit 1") end'
  # LazyVim can start Mason installs while restoring plugins. Keep that process
  # alive through the explicit Mason wait; an intermediate +qa aborts its jobs.
  cat > "$bootstrap_stage/editor.lua" <<'LUA'
assert(vim.g.lazy_did_setup, "Lazy plugin setup did not initialize")
local config = require("lazy.core.config")
assert(type(config.plugins) == "table" and next(config.plugins), "Lazy plugin registry is empty")
-- The copied lockfile, not moving plugin heads, defines this editor setup.
local runner = require("lazy.manage").restore({wait = true, show = false})
assert(runner and type(runner.wait) == "function", "Lazy restore returned no runner")
runner:wait()
-- Runner:wait completes jobs; failures are recorded on each plugin's Tasks.
for name, plugin in pairs(config.plugins) do
  for _, task in ipairs(plugin._ and plugin._.tasks or {}) do
    assert(not task:has_errors(), "Lazy restore failed for " .. name .. ": " ..
      (task.output and task:output() or "plugin task error"))
  end
end

local registry = require("mason-registry")
local plugin = assert(require("lazy.core.config").plugins["mason.nvim"], "Mason plugin is missing")
local opts = require("lazy.core.plugin").values(plugin, "opts", false)
assert(type(opts) == "table", "Mason plugin options are missing")
local done, pending, failures = false, 0, {}
registry.refresh(function(success)
  -- Registry refresh callbacks can run later on the event loop, outside the
  -- protected initializer. Catch their errors here so they cannot look successful.
  local ok, err = xpcall(function()
    assert(success ~= false, "Mason registry refresh failed")
    for _, name in ipairs(opts.ensure_installed or {}) do
      local package = registry.get_package(name)
      if not package:is_installed() then
        pending = pending + 1
        local settled = false
        local function finish(failed)
          if settled then return end
          settled = true
          pending = pending - 1
          if failed then table.insert(failures, name) end
        end
        package:once("install:success", function() finish(false) end)
        package:once("install:failed", function() finish(true) end)
        if not package:is_installing() then package:install() end
      end
    end
  end, debug.traceback)
  if not ok then table.insert(failures, err) end
  done = true
end)
-- Exiting on the first failure aborts every other installer. Let the queued
-- work settle, then report all failures while preserving successful installs.
local completed = vim.wait(900000, function() return done and pending == 0 end, 100)
local log_hint = "; inspect " .. vim.fn.stdpath("log") .. "/mason.log"
assert(completed, "Mason setup incomplete (15 minute timeout)" .. log_hint)
assert(#failures == 0, "Mason setup incomplete: " .. table.concat(failures, ", ") .. log_hint)
print("Mason language tools installed. Verify :checkhealth and project SDK requirements locally.")
LUA
  DOTFILES_NVIM_BOOTSTRAP=1 DOTFILES_EDITOR_SCRIPT="$bootstrap_stage/editor.lua" nvim --headless "+$protected" +qa || return
}
bootstrap_native_docker() {
  local user current_shell
  user=$(id -un)
  if [[ " $(id -nG) " != *' docker '* ]]; then
    sudo usermod -aG docker "$user"
    echo 'Docker group access added. Exit WSL and start a new session before using Docker without sudo.'
  fi
  if [[ $(cat /proc/1/comm) == systemd ]]; then
    sudo systemctl enable --now docker.service
  else
    echo 'Native Docker installed. WSL is not using systemd: enable [boot] systemd=true in /etc/wsl.conf, run wsl.exe --shutdown from Windows, then sudo systemctl enable --now docker.'
  fi
  current_shell=$(getent passwd "$user")
  current_shell=${current_shell##*:}
  [[ $current_shell == /bin/bash || $current_shell == /usr/bin/bash ]] || sudo chsh -s /bin/bash "$user"
}
bootstrap_epic_local() {
  # No AI homes or authentication here; only explicitly opted-in local integration.
  python3 - <<'PY'
from pathlib import Path
import os
import shutil
import time
home = Path.home()
local = home / '.gitconfig.local'
work = Path(os.environ.get('EPIC_WORKSPACE', str(home / 'dev/epic'))).resolve()
work.mkdir(parents=True, exist_ok=True)
profile = home / '.config/dotfiles/git-epic.local'
profile.parent.mkdir(parents=True, exist_ok=True)
if not profile.exists() and not profile.is_symlink():
    profile.write_text(r'''# Supply your own Epic identity here; no account was copied.
# [user]
#     name = Your Name
#     email = your-work-address
[url "git@github.ol.epicgames.net:"]
    insteadOf = https://github.ol.epicgames.net/
[credential "https://live.roost.on.epicgames.com"]
    helper =
    helper = "!\"$HOME/.local/bin/epic-git-credential\""
''')
def quoted(value):
    return str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
workspace = home / '.config/dotfiles/git-epic-workspace.local'
workspace_text = '# Generated by explicit dotfiles Epic bootstrap.\n' + f'[includeIf "gitdir:{quoted(work)}/"]\n    path = "{quoted(profile)}"\n'
if workspace.is_symlink():
    raise SystemExit('Preserving symlinked Epic workspace include; resolve it manually.')
if workspace.exists() and workspace.read_text() != workspace_text:
    if not workspace.read_text().startswith('# Generated by explicit dotfiles Epic bootstrap.\n'):
        raise SystemExit('Preserving existing Epic workspace include; resolve it manually.')
    shutil.copy2(workspace, workspace.with_name(workspace.name + '.before-change-' + str(time.time_ns())))
workspace.write_text(workspace_text)
# The managed root loader reads the optional gate after personal defaults.
# Remove only our exact legacy block; arbitrary private includes remain local.
owned = '\n# Optional WSL Epic workspace\n[include]\n    path = ~/.config/dotfiles/git-epic-include.conf\n'
if local.is_file() and not local.is_symlink():
    text = local.read_text()
    if owned in text:
        backup = local.with_name(local.name + '.before-epic-' + str(time.time_ns()))
        shutil.copy2(local, backup)
        local.write_text(text.replace(owned, ''))
print('Set your Epic Git identity in ~/.config/dotfiles/git-epic.local before committing work.')
PY
  if command -v cmd.exe >/dev/null && command -v wslpath >/dev/null; then
    local windows_home source target="$HOME/.kube/config"
    if windows_home=$(cmd.exe /U /D /C 'echo %USERPROFILE%' 2>/dev/null |
        python3 -c 'import sys; sys.stdout.write(sys.stdin.buffer.read().decode("utf-16le").rstrip("\r\n"))') &&
        windows_home=$(wslpath -u "${windows_home//$'\r'/}") &&
        [[ -f $windows_home/.kube/config ]]; then
      source="$windows_home/.kube/config"
      if [[ -e $target || -L $target ]]; then
        echo 'Existing Linux kubeconfig preserved; select corporate kubeconfig explicitly with KUBECONFIG when needed.'
      else
        mkdir -p -- "$HOME/.kube"
        ln -s -- "$source" "$target"
        echo 'Windows kubeconfig linked. Validate Windows certificate paths and exec auth helpers locally; contents were not logged.'
      fi
    else
      echo 'No Windows kubeconfig source found; skipping.' >&2
    fi
  else
    echo 'WSL Windows interop unavailable; skipping optional kubeconfig link.' >&2
  fi
  echo 'Epic AI setup is separate: run epic-ai-setup when ready for gateway installation and SSO.'
}
bootstrap_main() {
  local profile='' epic=false dry_run=false windows_fonts=false windows_settings=''
  while (($#)); do
    case $1 in
      --profile) (($# >= 2)) || { bootstrap_usage >&2; return 2; }; profile=$2; shift ;;
      --epic) epic=true ;;
      --dry-run) dry_run=true ;;
      --windows-fonts) windows_fonts=true ;;
      --windows-settings) (($# >= 2)) || { bootstrap_usage >&2; return 2; }; windows_settings=$2; shift ;;
      -h|--help) bootstrap_usage; return 0 ;;
      *) bootstrap_error "Unknown bootstrap option: $1"; return 2 ;;
    esac
    shift
  done
  [[ $profile == omarchy || $profile == wsl ]] || { bootstrap_usage >&2; return 2; }
  if $epic && { [[ $profile != wsl ]] || ! bootstrap_ubuntu_wsl; }; then
    bootstrap_error '--epic requires Ubuntu WSL, including during dry-run.'; return 1
  fi
  if [[ $profile == wsl ]] && ! bootstrap_ubuntu_wsl; then
    bootstrap_error 'The WSL profile requires Ubuntu WSL.'; return 1
  fi
  [[ $profile != wsl ]] || bootstrap_wsl2 || return
  if [[ $profile != wsl ]] && { $windows_fonts || [[ -n $windows_settings ]]; }; then
    bootstrap_error 'Windows options require Ubuntu WSL.'; return 1
  fi
  if $dry_run; then
    printf 'Would provision %s: core tools, Rust stable/Cargo/rustfmt/Clippy, mise Node 26.8.2/pnpm 12.11.2, install/update latest Claude/Codex (including existing clients), font family, pinned tmux sidebar; then install --apply.\n' "$profile"
    [[ $profile != wsl ]] || echo 'Would provision Neovim 0.12.6 globally through mise; preflight native Docker ownership, install Ubuntu Docker Engine/Compose/Buildx, configure service/group access and select Bash.'
    $epic && echo 'Would add optional Epic shell links, conditional local Git include and non-destructive Windows kubeconfig link; no AI homes or SSO.'
    $windows_fonts && echo 'Would install Windows host fonts.'
    [[ -z $windows_settings ]] || printf 'Would merge Windows Terminal settings at %s.\n' "$windows_settings"
    return 0
  fi
  # Check conflict and platform before mkdir, apt, downloads, or other mutations.
  [[ $profile != wsl ]] || bootstrap_docker_preflight || return
  if [[ $profile == omarchy ]]; then
    command -v omarchy >/dev/null || { bootstrap_error 'Omarchy package CLI is required.'; return 1; }
  fi
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.local/share/mise/shims:$PATH"
  local bootstrap_stage bootstrap_cleanup
  bootstrap_stage=$(mktemp -d)
  # Capture the safely quoted path now: EXIT may run after locals leave scope.
  printf -v bootstrap_cleanup 'rm -rf -- %q' "$bootstrap_stage"
  trap "$bootstrap_cleanup" EXIT
  mkdir -p -- "$HOME/.local/bin"
  bootstrap_packages "$profile"
  bootstrap_alias_commands
  bootstrap_rust
  bootstrap_mise "$profile"
  bootstrap_neovim "$profile"
  bootstrap_tmux
  "$repo/scripts/install-tmux-plugins"
  local -a font_args=() install_args=(--profile "$profile" --apply)
  $windows_fonts && font_args+=(--windows)
  "$repo/scripts/install-fonts.sh" "${font_args[@]}"
  [[ $profile != wsl ]] || bootstrap_native_docker
  $epic && install_args+=(--epic)
  "$repo/install" "${install_args[@]}"
  if [[ $profile == omarchy ]]; then
    omarchy theme set agamotto
    # Older Omarchy 4 releases predate the glassy-mode command; the theme
    # reload and explicit Foot settings still work on those installations.
    if command -v omarchy-hyprland-window-transparency >/dev/null; then
      omarchy hyprland window transparency transparent
    fi
  fi
  bootstrap_editor_assets
  $epic && bootstrap_epic_local
  [[ -z $windows_settings ]] || python3 "$repo/scripts/windows-terminal.py" --settings "$windows_settings" --apply
  echo 'Tools and configuration installed. Agent authentication, sidebar event hooks, project SDK health and Windows acceptance checks remain local; see README.'
  # Print versions without credentials; no startup updates or auth checks.
  for tool in git gh tmux nvim node pnpm dotnet cargo rustc starship zoxide eza fzf fd rg bat jq lazygit claude codex; do
    printf '%s: ' "$tool"
    "$tool" --version 2>/dev/null | head -1 || true
  done
  rm -rf -- "$bootstrap_stage"
  trap - EXIT
}
