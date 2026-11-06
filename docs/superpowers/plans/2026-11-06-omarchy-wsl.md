# Omarchy and Ubuntu WSL Implementation Plan

> **For agentic workers:** Use the executing-plans workflow for the shared configuration and installer, and dispatch isolated platform components with their own bounded interfaces. Follow test-driven development for scripts with filesystem or account effects.

**Goal:** Reproduce this PC's daily configuration on Omarchy and Ubuntu WSL, with optional Epic setup confined to WSL.

**Architecture:** Retain Stow-style packages but deploy explicit file links with a transactional Python installer so previews, complete preflight, backups and rollback work before Stow is installed. Shared packages are `bash`, `common`, `nvim`, `tmux`, `gitconfig`, `gh`, and `starship`; `omarchy` and `epic` are explicitly selected additions. Bash and tmux use the installed Omarchy integration when available and portable Agamotto defaults otherwise.

**Tech Stack:** Bash, Python 3 standard library, Lua, TOML, PowerShell for Windows host tasks.

**Spec:** `docs/superpowers/specs/2026-11-06-omarchy-wsl-design.txt`

## Global Constraints

- Work only in the repository; do not enroll this desktop, authenticate, install system packages or contact coworkers.
- The approved baseline is the live configuration under `/home/hfp/.config`, excluding backups/state/secrets.
- `detach-on-destroy on`; preserve all other agreed tmux controls and sidebar settings.
- Omarchy and ordinary WSL must never activate Epic routing, enterprise Git configuration or Epic AI homes.
- No VPN diagnostics, network probes, startup checks or new background services beyond explicitly provisioned native Docker.
- Downloads: `~/downloads`; screenshots: `~/media/screenshots`; wallpaper: `hangar.jpg`.
- Font: `JetBrainsMono Nerd Font Mono`, Medium plus normal/bold/italic variants; install on the Windows host too.
- Windows Terminal: Shift+Alt+numbers switch tabs; Shift+Ctrl+numbers open profiles; Ctrl+Shift+C/V/W copy/paste/close; Alt+Enter forwarded, F11 retained.
- Preserve credentials, existing user data, unrelated Windows profiles/settings, Git identity and local overrides.

## Review Focus

- Installer partial failure, changed installed files and foreign symlinks must not lose data during apply or rollback.
- Legacy `~/.tmux.conf` and `~/.gitconfig` must not shadow the new XDG files.
- JSONC comments, strings containing URLs, trailing commas and current/legacy terminal action formats must parse without corrupting profiles.
- Directory routing must distinguish `~/dev/epic` from `~/dev/epic-other`, and explicit work commands must refuse unconfigured profiles.
- First-run tools, paths with spaces, unavailable optional tools and a GUI-less WSL shell must work without accessing this desktop.

### Task 1: Shared and Omarchy configuration

**Files:** Replace `nvim/.config/nvim`; create `tmux/.config/tmux`, `common/.config/dotfiles`, `omarchy/.config`; update `bash`, `gitconfig`, `starship`; retain `gh` helpers.

**Interfaces:** Common shell file is `~/.config/dotfiles/shell/common.bash`; Epic extension is `~/.config/dotfiles/shell/epic.bash`; portable themes are under `~/.config/dotfiles/themes/agamotto/`. `~/.config/dotfiles/local.bash`, `~/.gitconfig.local` and `~/.config/tmux/local.conf` are local overrides.

- [x] Copy active live configs only, excluding `.git`, backups, cache, generated theme links and secrets.
- [x] Add portable theme adapters and non-Omarchy shell helpers, preserving Omarchy integration on Omarchy.
- [x] Set tmux detach behavior, make project/help/sidebar scripts portable, and preserve local override points.
- [x] Sanitize user paths; install desktop preferences through one-time setup rather than overwriting unrelated XDG/MIME/bookmark settings.
- [x] Validate Lua syntax, isolated tmux configuration and clean Bash startup. Human prose/config copies need no mirror tests.

### Task 2: Transactional installer

**Files:** `install`, `clean-env`, `scripts/install.py`, `scripts/configure-omarchy.py`, `tests/test_install.py`.

**Interfaces:** `./install --profile omarchy|wsl [--epic] [--apply]`; default is preview; `--restore PATH` reverts one backup manifest; `--uninstall` removes owned links only. Bootstrap calls installer with these arguments. `--home PATH` supports disposable tests; refuse an Epic apply outside Ubuntu WSL. Configure Omarchy merges user dirs, bookmarks and MIME settings after backup, using a backup manifest shared with installer.

- [x] Write failing integration tests for zero-write preview, unknown/platform-invalid options, conflicts/backups, repeated apply, spaces, legacy shadowing and restoring edited/foreign files safely.
- [x] Implement whole-plan preflight, per-file links, backups/identity preservation and rollback manifest, plus one-time Omarchy preference merging.
- [x] Run `python -m unittest discover -s tests -p 'test_install.py' -v` and verify all pass.

### Task 3: Windows Terminal and font provisioning

**Files:** `scripts/windows-terminal.py`, `scripts/install-fonts.sh`, `windows/Install-Fonts.ps1`, optional PowerShell settings launcher, `tests/test_windows_terminal.py`.

**Interfaces:** `python3 scripts/windows-terminal.py --settings PATH [--apply]`; default preview, backup on apply, idempotent settings merge. Accept/discover Windows settings path. Font script uses pinned official Nerd Fonts archive/checksum and supports per-user Linux/Windows installation; do not fetch or install on this PC during implementation.

- [x] Write failing JSONC/profile-preservation and key-forwarding tests, including current action IDs/legacy inline actions, duplicates, last-tab behavior and repeated application.
- [x] Implement merging of Agamotto palette/font/appearance and intended keybindings while preserving profiles and unrelated settings.
- [x] Add versioned font source/checksum/license handling and Windows per-user registration, including spaces and existing font checks.
- [x] Run `python -m unittest discover -s tests -p 'test_windows_terminal.py' -v`.

### Task 4: Tool bootstrap and Epic isolation

**Files:** `bootstrap`, `bootstrap-wsl`, `scripts/bootstrap-tools.sh`, `scripts/install-tmux-plugins`, `epic/.config/dotfiles/shell/epic.bash`, `epic/.local/bin/*`, `tests/test_bootstrap.py`.

**Interfaces:** `./bootstrap --profile omarchy|wsl [--epic] [--dry-run]`; `./bootstrap-wsl` forwards profile `wsl`. Bootstrap installs missing core tools, native Docker for WSL, Rust via rustup, mise Node 26.8.2/pnpm 12.11.2, tmux sidebar at recorded revision, then invokes `install --apply`. Preview writes nothing and runs no network/package operations. Ordinary config linking never installs tools.

- [x] Write failing tests for dry-run side effects, platform/Epic guards, personal/work routing, missing work config, inherited provider environment and preexisting Docker protection.
- [x] Implement idempotent package/tool acquisition, supported-version checks, compile/runtime dependencies, font/plugin setup, and Bash selection on WSL without changing this desktop.
- [x] Adapt coworker Epic patterns to Bash: opt-in homes, separate explicit setup/SSO, conditional Git identity/host helpers, non-destructive Windows kubeconfig linking. Do not automatically migrate accounts.
- [x] Run `python -m unittest discover -s tests -p 'test_bootstrap.py' -v` and `bash -n` for scripts.

### Task 5: Integration, documentation and independent review

**Files:** `README.md`, `docs/omarchy-checklist.md`, `.gitignore`, optional verification script and final regressions.

- [x] Document fresh/existing machine commands, previews, dependencies, local identity/overrides, Epic setup, Windows host font/settings steps, rollback and platform-specific checks.
- [x] Run the complete Python suite, shell/Lua syntax validation, isolated home installations, and isolated tmux/Neovim checks where the sandbox allows.
- [x] Review all changes for personal paths, credential/state leakage, unfinished platform integration and unintended live changes.
- [x] Obtain independent whole-change code review, fix consequential findings, rerun affected/full checks and leave a reviewable change on `feat/omarchy-wsl`.

## Execution rulings

- The user explicitly requested implementation now; execute without another approval handoff.
- Work in their requested `.dotfiles` directory on a new feature branch. It is not linked to this desktop; a separate worktree would not improve runtime isolation and would complicate delivery.
- Existing Stow package paths remain compatible, but the transactional installer uses explicit links to provide rollback without a bootstrap dependency on Stow.
- Keep edits available for review; do not push or publish.
