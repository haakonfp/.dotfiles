# Use the setup on each PC

The full bootstrap installs tools and then applies configuration. `install`
only links/configures files; its default is a preview. Run the scripts as your
normal user, not with `sudo ./bootstrap`; they request sudo for package/service
steps themselves. Account login and Windows host checks happen on that PC.

## Get the updated checkout

Use the `main` branch of `haakonfp/.dotfiles`.

For an existing machine whose old `.dotfiles` checkout may already be symlinked
into its live configuration, clone into a separate path for this first migration:

```bash
git clone --branch main git@github.com:haakonfp/.dotfiles.git ~/.dotfiles-next
cd ~/.dotfiles-next
```

Use your existing GitHub authentication. Install Git first if necessary. Keep
this checkout separate for the preview, then make `~/.dotfiles` permanent.
For WSL, run:

```bash
./relocate --profile wsl
./relocate --profile wsl --apply
cd ~/.dotfiles
```

On an Epic work PC, add `--epic` to both commands; on Omarchy, replace the
profile with `--profile omarchy`. This works before or after bootstrap. It
enrolls configuration before moving the old checkout into
`~/.local/state/dotfiles/checkouts/`, preserving its changes and private files,
then moves the fresh checkout to `~/.dotfiles`, repairs links and updates backup
records. Legacy links and restore operations can still use the archived checkout.
Keep that hidden archive for restoration. The `-next` folder is gone afterward.
On a fresh PC you can clone directly to `~/.dotfiles` instead.

## Another Omarchy PC

Use an installed Omarchy 4 system with Lua Hyprland configuration. From the
updated checkout:

```bash
./install --profile omarchy
./bootstrap --profile omarchy --dry-run
./bootstrap --profile omarchy
```

The first two commands preview. The last installs missing tools/fonts and the
Foot/Brave/Spotify prerequisites, links the shared/desktop settings, restores
locked editor plugins/language tools, and applies Agamotto with `hangar.jpg`.
Existing Git-installed Agamotto directories are backed up whole before being
replaced; no Git metadata or user theme files are discarded. Keep the printed
backup-manifest path.

Open a new Foot terminal after completion. Existing monitor configuration and
local overrides are preserved, including when the old config directories were
links. If a monitor file is absent, the installed Omarchy default is seeded;
adjust scale/layout for that PC if needed. `~/downloads` and
`~/media/screenshots` are configured without moving existing files.
Bootstrap also selects plain transparent windows and Foot's 90% background
opacity with blur off, clearing a previous glassy/opaque mode with backups.
For an existing installed checkout that only needs this correction, run
`./install --profile omarchy --apply` followed by
`omarchy hyprland window transparency transparent` on versions offering that
command, then open a new Foot window. Bootstrap detects command availability.

Verify once:

- Open Neovim and check `:checkhealth` / `:Mason` for the projects you use.
- Open two tmux sessions and check pane/window/session shortcuts; closing the
  last pane should exit that client while the other session stays running.
- Use `Super+Shift+S`; confirm the screenshot is in `~/media/screenshots`.
- Confirm font size, wallpaper, browser downloads, keyboard/Compose and monitor
  layout. See the [small Omarchy checklist](omarchy-checklist.md).

No Epic setup is installed on Omarchy.

## Each Windows PC

Use Windows Terminal and Ubuntu LTS inside **WSL2**. In Windows PowerShell:

```powershell
wsl --list --verbose
```

The Ubuntu instance must show version 2. If it shows 1, convert the actual distro
name before running the bootstrap, for example `wsl --set-version Ubuntu 2`.
The bootstrap expects a standard Microsoft WSL2 kernel. Do not upgrade the Ubuntu
distribution merely to run this configuration.

Open the Ubuntu profile in Windows Terminal, then run these from the updated
checkout inside Ubuntu (not from PowerShell):

```bash
./bootstrap-wsl --dry-run
./bootstrap-wsl --windows-fonts
python3 scripts/windows-terminal.py
python3 scripts/windows-terminal.py --apply
```

The first command previews provisioning; the Python commands preview and then
back up/merge host Terminal settings. `--windows-fonts` installs the font both
inside Linux and for your Windows user. Windows directories containing Unicode
characters or spaces are supported. For a portable/custom Terminal installation,
pass `--settings '/mnt/c/Users/you/.../settings.json'` to both Python commands.
Launch Terminal once before discovery so its settings exist.
The merger applies 90% opacity with acrylic and Mica disabled, including old
profile transparency overrides. Clear transparency requires Windows 11.

Close/reopen Terminal after host font installation and start a new WSL session
for Bash/default-shell and Docker group changes. Profile launch commands are
preserved: select your Ubuntu profile explicitly. If its command line forces
Zsh, change that override to Bash (or remove the shell override to use Ubuntu's
new default). Native PowerShell/cmd profiles do not become Linux shells.

Native Docker is installed inside Ubuntu. Docker Desktop/foreign Docker is a
reported conflict and is never removed automatically. If systemd is disabled,
follow the bootstrap's one-time `/etc/wsl.conf`/service instructions. Then check
`docker info` in the new session. No VPN diagnostics or network settings are added.

Verify the font, `Alt+Enter` / `Alt+Shift+Enter` pane splits, `Ctrl+1…9` tmux
sessions, Shift-modified Terminal tab/profile shortcuts, `Ctrl+Shift+C/V/W`,
F11 fullscreen and Neovim clipboard. Custom Terminal dropdown menus retain their
own profile-number shortcuts for a manual ordering check. See [Windows details](../windows/README.md).

### Epic on a Windows workstation

Use this instead of the ordinary WSL bootstrap when that PC needs Epic:

```bash
./bootstrap-wsl --epic --dry-run
./bootstrap-wsl --epic --windows-fonts
```

Merge Terminal settings as above, then start a new Bash session and run:

```bash
epic-ai-setup
```

That separate step can request Epic SSO. Fill in your own work identity in
`~/.config/dotfiles/git-epic.local`. Under `~/dev/epic`, Claude/Codex and the
retained `gh solve/follow` helpers use isolated work profiles; elsewhere they
use personal profiles. Use `EPIC_WORKSPACE` for another work root and rerun the
explicit Epic bootstrap. Existing kubeconfigs and credentials are preserved.
Bootstrap and Epic setup install [sidebar event hooks](agent-sidebar.md) for the
selected accounts. Restart running agents; review Codex `/hooks` if prompted.
The [Epic guide](epic.md) explains personal sign-in, separate work homes, how
the shared gateway configures both clients, and Git identity versus SSH access.

## Restore

Use the backup manifest printed by installation, from the updated checkout:

```bash
./install --restore /path/to/manifest.json
./install --restore /path/to/manifest.json --apply
```

Restore refuses to overwrite later edits or proceed if an original backup is
missing. Windows Terminal settings have their own adjacent backup. Package
installation, Docker service/group changes, host font installation and the
selected Omarchy theme are outside the file-link rollback; the README explains
those boundaries. Keep the checkout and backups until the destination checks
have passed.
