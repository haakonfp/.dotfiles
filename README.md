# .dotfiles

The shared Bash, LazyVim, tmux and Agamotto setup from the reference Omarchy PC,
with an Omarchy desktop profile and an Ubuntu WSL profile. Epic configuration
is an explicit WSL-only addition.

## Start here

Use the `main` branch. For a new machine, clone it with:

```bash
git clone --branch main git@github.com:haakonfp/.dotfiles.git ~/.dotfiles
cd ~/.dotfiles
```

Use Bash and Python 3 to run the installer as your normal user. The permanent
checkout should be `~/.dotfiles`: installed configuration files link to it.
Preview performs no writes, package operations, downloads or sign-ins.

For first rollout to the other PCs, including an existing checkout that already
manages live files, follow [the machine-by-machine guide](docs/rollout.md).
Use a separate fresh checkout for that migration so updating Git cannot change
the old symlinked configuration before the installer has backed it up.
Move that temporary checkout into the permanent location before continuing.

### Finish a `.dotfiles-next` migration

For Ubuntu WSL, whether bootstrap has already run or not:

```bash
cd ~/.dotfiles-next
git pull --ff-only
./relocate --profile wsl         # preview
./relocate --profile wsl --apply # move and repair links
cd ~/.dotfiles
```

For an Epic work PC, add `--epic` to both relocation commands; an existing Epic
opt-in is retained automatically. On Omarchy, use `--profile omarchy` instead.
The old checkout moves into `~/.local/state/dotfiles/checkouts/`, including its
uncommitted/untracked files. Restore records and legacy links follow that archive.
The new checkout becomes `~/.dotfiles`; no `-next` directory remains. A failed
relocation attempts to restore both folders and the configuration.
This step only moves/configures files. If bootstrap has not completed yet,
continue with the appropriate commands below from `~/.dotfiles`.

### Another Omarchy PC

```bash
cd ~/.dotfiles
./install --profile omarchy             # preview configuration changes
./bootstrap --profile omarchy --dry-run # preview tool provisioning
./bootstrap --profile omarchy           # tools, fonts, links, Agamotto wallpaper
```

The Omarchy profile requires an installed Omarchy 4 system with Lua Hyprland
configuration. It uses the installed Omarchy defaults and adds personal
overrides. It does not install Epic tools or configure Epic accounts.

### Ubuntu LTS inside WSL2

```bash
cd ~/.dotfiles
./bootstrap-wsl --dry-run
./bootstrap-wsl --windows-fonts
python3 scripts/windows-terminal.py         # preview host settings
python3 scripts/windows-terminal.py --apply # back up and merge host settings
```

Run these commands inside Ubuntu, not Windows PowerShell. Native Docker
requires WSL2 with a standard Microsoft WSL2 kernel; check
`wsl --list --verbose` in Windows PowerShell first. WSL1 is rejected before
provisioning. This installs native Docker Engine, Compose and Buildx inside WSL, selects
Bash, and installs the shared tools/configuration. Docker Desktop or a foreign
Docker installation is preserved and reported as a conflict; it is never
uninstalled automatically. A new WSL session is needed after Docker group or
login-shell changes. If the distro is not using systemd, the bootstrap prints
the one-time Docker service instructions.

The `--windows-fonts` option installs JetBrainsMono Nerd Font Mono for the
Windows user as well as Linux. Windows Terminal uses the Windows font installation.
The separate settings-merger commands above preview the host changes before
applying them.

You can supply `--settings "/mnt/c/Users/you/.../settings.json"`. The merger
preserves existing profile GUIDs, launch commands, ordering, unrelated settings
and font sizes. It aligns transparency to this PC: 90% opacity, acrylic off,
and a dark application theme with Mica off. It accepts JSONC; application writes formatted JSON,
with the original comments/bytes retained in the adjacent backup. Custom
`newTabMenu` layouts keep their existing profile-number shortcuts and print a
host-check note. See [Windows details](windows/README.md).

### Optional Epic workstation setup (WSL only)

```bash
cd ~/.dotfiles
./bootstrap-wsl --epic --dry-run
./bootstrap-wsl --epic --windows-fonts
python3 scripts/windows-terminal.py
python3 scripts/windows-terminal.py --apply
```

The Epic bootstrap links the Epic extension, prepares a local conditional Git
include and optionally links the Windows/Twingate-managed kubeconfig. Existing
Linux kubeconfigs remain intact. Then open a new Bash session and run:

```bash
epic-ai-setup
```

`epic-ai-setup` is the separate interactive gateway/SSO step; it never renames
or combines existing accounts. Partial
existing profiles stop setup so they can be inspected.

Within `~/dev/epic`, `claude` and `codex` (including the retained `gh solve`
and `gh follow` workflows through the shared `dotfiles-agent` dispatcher) select isolated `~/.claude-epic` and
`~/.codex-epic` homes. Elsewhere they use the personal homes. Explicit
`claude-epic` and `codex-epic` commands work from any directory. Missing work
configuration fails with a setup hint; it does not fall back to a personal account.
Set your own Epic Git identity in `~/.config/dotfiles/git-epic.local` before
committing work. For another workspace, export `EPIC_WORKSPACE` before running
the explicit Epic bootstrap and keep it in your local Bash override.

No Epic profiles, gateway commands, corporate Git settings or kubeconfig links
are installed by the Omarchy or ordinary WSL profile. Reinstalling without
`--epic` removes only this checkout's Epic links/gate; private account files
remain on disk. Start a new shell after changing profiles. There are no VPN
diagnostics or changes to Windows VPN/network settings.

The root Git loader reads personal defaults before the optional work gate, so
later personal identity edits cannot override Epic repositories. Commit identity
is separate from enterprise SSH authentication. See [the Epic setup guide](docs/epic.md)
for personal/work logins, gateway setup for both clients, explicit launchers,
Git identities and worktree/kubeconfig boundaries.

## What gets installed

| Shared | Omarchy only | Opted-in WSL Epic only |
| --- | --- | --- |
| Bash aliases, history/completion, Starship, zoxide | Foot, keyboard preferences and desktop shortcuts | Isolated AI launch helpers |
| Full LazyVim configuration and plugin lockfile | Agamotto palette, bar and `hangar.jpg` | Conditional enterprise Git configuration |
| tmux keys, project/session scripts, agent sidebar | `~/downloads`, `~/media/screenshots`, downloads bookmark | Optional Windows kubeconfig link |
| Git settings/aliases and existing `gh` helpers | Application defaults and night-light preferences | Separate explicit gateway/SSO setup |

Bootstrap installs Rust/Cargo with rustfmt/Clippy, compiler/build dependencies,
Git/gh, Neovim, tmux, zoxide, eza, fzf, fd, ripgrep, bat, jq, lazygit, Starship
and the font family. Omarchy bootstrap also installs the minimal personal
shortcut applications `foot`, `brave-bin`, and `spotify` with `omarchy pkg add`.
It uses rustup and mise without changing project toolchain overrides.
Each explicit bootstrap installs or updates `claude@latest` and `codex@latest`
through mise, shared by the personal and Epic profiles with separate login homes.
The Epic gateway is installed/configured only by the explicit `epic-ai-setup` step.
The Node/pnpm baseline is 26.8.2/12.11.2. Compatible tools are retained;
missing or older Node/pnpm versions are installed through mise automatically.
For .NET, an existing SDK version 8 or newer is retained; missing, obsolete or
runtime-only installations get the .NET 10 SDK through mise. You do not need
to install these runtimes or mise manually. Updated runtime defaults go in
the global mise config, backed up beside it as `config.toml.before-dotfiles.*`;
unrelated entries and project version pins remain. Bootstrap activates the mise
environment immediately so Mason sees the SDK from its install directory too.
Docker Desktop conflicts still require an explicit user choice.

The editor lockfile requires Neovim 0.12 or later. Bootstrap provides upstream
0.12.6 when necessary and checks tmux's actual extended-key support before using
the distro version. Language servers/formatters are provisioned through Mason;
project-specific SDKs and package dependencies still belong to the projects.
Mason lets all queued installers finish before reporting any failures, with the
log path printed for diagnosis. Successful installs survive a retry. Desktop
theme application runs before this step, so a package failure does not prevent it.
The sidebar checkout is pinned and built through Cargo; no plugin wizard changes
your live tmux or agent settings during installation.

After provisioning, complete local agent login and the sidebar's event hooks
using [the sidebar setup notes](docs/agent-sidebar.md). These account-specific
steps preserve existing settings and authentication. They are not copied from
another computer.

## Configuration-only installation and restore

Configuration-only installation requires the shortcut applications to be installed
separately. If Brave is unavailable, the installer warns about the `brave-bin`
prerequisite and preserves the existing HTML/http/https defaults. Other MIME
handlers stay intact. The Omarchy package includes the reference Foot desktop
entry and the harmless `codex` default-agent preference; Super+I retains the
agent picker. Agent login remains local.

When compatible tools are already installed:

```bash
./install --profile omarchy         # preview
./install --profile omarchy --apply # link and apply one-time desktop preferences
# Or: ./install --profile wsl [--epic] --apply
```

The packages keep their Stow layout, but the installer manages individual file
links itself so backups and restore work before any Stow dependency is available.
It preflights the complete plan, saves conflicts under
`~/.local/state/dotfiles/backups/`, and prints the manifest path. Repeated runs
leave correct links and preferences alone. A failed apply attempts to roll back.

Existing Git configuration is retained in local previous-config files beside
the original locations, preserving relative includes, identities and credential
helpers. The new loader applies shared defaults and `~/.gitconfig.local`. Existing
login initialization is preserved too. An old `~/.tmux.conf` is backed up so it
cannot hide the new `~/.config/tmux/tmux.conf`.
Copied shared Git configs and links from an older checkout keep the saved
private settings active. If a private Git config has changed, a separate sibling
snapshot becomes active; existing saved files stay in place so configs can still
include them. The loader remembers that selection across repeated installs.
Relative includes keep their original base directory, and the installer can
restore the configuration from before migration.
When replacing an old Git directory link, local include files and credential
helpers are copied with their contents and permissions intact.
Copies of the dotfiles login loader, including links from an older checkout,
keep the saved initializer intact. If your personal login profile has changed,
its latest version becomes the saved initializer and the older version stays in
the installation's rollback backup. A custom profile that already sources the
saved initializer needs its additions moved to the local Bash override first,
so it cannot become recursive.

```bash
./install --restore /path/to/manifest.json         # preview restore
./install --restore /path/to/manifest.json --apply # restore
./clean-env --profile omarchy                     # preview unlinking
./clean-env --profile omarchy --apply              # remove owned repo links only
```

Restore refuses to overwrite changed/replaced installed files or proceed with
missing original backups. Unlinking is not a rollback: it leaves user data,
private overrides and desktop preferences alone. Generated theme state remains
managed by Omarchy. A theme change during bootstrap is separate from the link
manifest; after restore, select the previous theme with `omarchy theme set NAME`.
The Omarchy install also backs up and removes existing glassy/opaque mode flags
to match this PC's plain transparency. For an already installed checkout, apply
that mode to the running desktop and open a new Foot window:

```bash
./install --profile omarchy --apply
omarchy hyprland window transparency transparent
```

Foot uses 90% background opacity with blur off. Existing deliberate settings in
`~/.config/foot/local.ini` still take precedence. Bootstrap applies the mode for
you on versions with that command; older Omarchy 4 versions still apply the
theme and Foot settings. Mise runtime-default backups are separate from the installer manifest.

## Local preferences

- `~/.config/dotfiles/local.bash`: private aliases, environment, workspace paths.
- `~/.gitconfig.local`: identity, signing and credential settings; loaded last.
- `~/.config/tmux/local.conf`: machine-specific tmux overrides.
- `~/.config/foot/local.ini`: Foot font-size/opacity overrides (Omarchy).
- `~/.config/hypr/monitors.lua`: keep each PC's monitor arrangement/scaling;
  the reference settings are in [examples/hypr/monitors.lua](examples/hypr/monitors.lua).

The project picker searches Git repositories/worktrees beneath your home. `t`
opens the picker; `t osirion` selects `~/dev/osirion`; `TMUX_PROJECTS_DIR` changes
the default project directory. Local overrides and private accounts are not
tracked in this repository. Existing `Downloads`/`Pictures` files are never
automatically moved or deleted. Browser-specific download overrides may need
one settings change; see the [short Omarchy checklist](docs/omarchy-checklist.md).

## Keybindings

| Key | Action |
| --- | --- |
| `Ctrl+A` | tmux prefix |
| `Alt+Enter` / `Alt+Shift+Enter` | tmux side-by-side / stacked pane split |
| `Alt+arrows` | tmux pane focus |
| `Alt+1…9` | tmux window |
| `Ctrl+1…9` | tmux session in creation order |
| `Ctrl+Alt+Up/Down` | previous/next tmux session |
| prefix, then `C` / `S` | project picker / session tree |
| prefix, then `e` / `E` | sidebar here / everywhere |
| `Alt+Shift+1…8` / `Alt+Shift+9` | Windows Terminal tab / last tab |
| `Ctrl+Shift+1…8` | open existing Windows Terminal profile by dropdown index |
| `Ctrl+Shift+C/V/W` | Windows Terminal copy/paste/close pane |
| `F11` | Windows Terminal's default fullscreen key; `Alt+Enter` goes to tmux |
| `Super+T` / `Super+Shift+S` | Omarchy Foot in `~/dev` / screenshot |

Closing the last pane exits that tmux client instead of switching its terminal
into another session. Other sessions continue running. Windows host keyboard
remappings and display settings are separate from Hyprland preferences.

## Verification

```bash
python3 -m unittest discover -s tests -v
```

Tests use disposable homes and simulated external provisioning/Windows commands.
The tmux acceptance test uses its own temporary socket and skips if Unix sockets
are blocked; it can be rerun outside that sandbox. Real Windows rendering,
key forwarding, host clipboard, Ubuntu package resolution, Docker service access
and Epic SSO need verification on the destination PC. No credentials, caches,
shell/clipboard history, system-service symlinks or hardware state are deployed.

The old `zsh/` and `terminal/*.json` snapshots are retained for reference and
are not selected by the new installer. Historical NvChad backups are available
in Git history; the active editor package now contains the reference LazyVim setup.
