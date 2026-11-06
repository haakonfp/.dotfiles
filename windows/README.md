Windows host fonts and terminal settings
=======================================

The bootstrap requires Ubuntu on **WSL2** with a Microsoft standard kernel for
native Docker. In Windows PowerShell, check `wsl.exe --list --verbose`; convert
an older distro with `wsl.exe --set-version YOUR-DISTRO-NAME 2` before bootstrap.
Custom kernels without the Microsoft WSL2 release marker are refused by the
bootstrap's conservative platform check. Windows interop must be enabled for
the host font installer and automatic settings discovery.

From WSL, run `scripts/install-fonts.sh --dry-run --windows` to preview,
then `scripts/install-fonts.sh --windows` to install for Linux and the Windows
user. Without `--windows` only Linux fonts are installed. Bootstrap can call
the Linux step first, then repeat with `--windows`; a completed pinned Linux
installation is reused. No administrator account is needed.

The source is [Nerd Fonts 3.5.1](https://github.com/ryanoasis/nerd-fonts/releases/tag/v3.5.1),
JetBrainsMono 2.304. The pinned archive SHA256 is
`04d5e8f903693f9dd13e16f867e994834e681eb3c72c0d337a770dcda09010cf`,
verified against the [official release asset digest](https://github.com/ryanoasis/nerd-fonts/releases/expanded_assets/v3.5.1).
The release also publishes [SHA-256.txt](https://github.com/ryanoasis/nerd-fonts/releases/download/v3.5.1/SHA-256.txt).
Only the 16 `JetBrainsMonoNerdFontMono-*.ttf` variants are installed. The
archive's OFL.txt and upstream icon-license attribution are retained beside
the Linux fonts and under the Windows per-user fonts license directory.
The font uses the [SIL Open Font License 1.1](https://github.com/JetBrains/JetBrainsMono/blob/v2.304/OFL.txt).

PowerShell can install from an already verified directory, with spaces allowed:

```powershell
.\windows\Install-Fonts.ps1 -SourceDirectory 'C:\Users\Your Name\Downloads\verified-fonts' -WhatIf
.\windows\Install-Fonts.ps1 -SourceDirectory 'C:\Users\Your Name\Downloads\verified-fonts'
.\windows\Install-Fonts.ps1 -Check
```

The Windows installer copies to `%LOCALAPPDATA%\Microsoft\Windows\Fonts`,
registers fonts under HKCU, loads new resources and broadcasts `WM_FONTCHANGE`.
Close applications or restart Windows before replacing font files Windows has
locked. Restart Terminal after installation. The PowerShell script trusts its
source directory; the shell installer verifies the release archive first.

Preview settings from WSL (Python 3 can also run this directly from PowerShell):

```sh
python3 scripts/windows-terminal.py
python3 scripts/windows-terminal.py --settings '/mnt/c/Users/Your Name/AppData/Local/Microsoft/Windows Terminal/settings.json'
python3 scripts/windows-terminal.py --settings '/path/to/settings.json' --apply
```

Discovery reads Windows LOCALAPPDATA through CMD's explicit Unicode output,
including usernames containing spaces or non-ASCII characters, and checks Store, unpackaged and Preview
locations; a portable/custom installation needs `--settings`. Launch Terminal
once first so its settings and generated profiles exist. The merger preserves
the default profile and launch commands: select Ubuntu in Terminal's dropdown
(or set it as the default profile); an explicit Zsh command in an existing
profile continues to launch Zsh. Start a new WSL session after bootstrap selects
Bash or changes Docker group membership. Apply writes normalized
JSON and keeps the original JSONC, including comments, in an adjacent
`settings.json.bak.TIMESTAMP`. Restore by closing Terminal and copying that
backup over the settings file. Repeated application creates no new backup.

Defaults use Agamotto, an underline cursor, JetBrainsMono Nerd Font Mono Medium,
and 90% opacity when unset. Existing profile size, opacity and other unrelated
options remain. Existing palette/font overrides are aligned with the shared
appearance; set local size/opacity in Terminal's profile settings afterward.

Keys follow [Windows Terminal's action schema](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/actions):
Shift+Alt+1–8 selects tabs, Shift+Alt+9 selects the last tab. Ctrl+Shift+1–8
opens available visible profile indices for the default new-tab menu; higher unused
chords and Ctrl+Shift+9 are preserved. A custom `newTabMenu` can reorder/filter
profiles dynamically, so the merger preserves all existing Ctrl+Shift+number
profile chords and reports that they need host verification. Ctrl+Shift+C/V/W copies/pastes/closes a pane. Ctrl+C/V/W and
Alt+1–9 pass through, Ctrl+1–9 sends distinct CSI-u sequences. Alt+Enter passes
through for tmux; Shift+Enter and Alt+Shift+Enter send CSI-u. F11 retains its
existing/default fullscreen action.

Acceptance checks on each Windows machine: confirm font weight/size and
opacity; verify profile ordering and any custom new-tab menu; exercise tmux
Ctrl+numbers and Alt/Shift+Enter splits; copy/paste through tmux and Neovim;
check F11. Host display scaling and keyboard remapping remain Windows choices.
Windows execution and actual WSL clipboard/key forwarding require a real host;
the repository's tests use disposable settings and fixture font archives.
