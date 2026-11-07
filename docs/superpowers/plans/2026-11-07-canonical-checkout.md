# Canonical checkout migration and Epic setup

> **For agentic workers:** Use the existing test-first workflow and independent review before merging. The user authorized implementation and direct publication to main.

**Goal:** Make `~/.dotfiles` the permanent checkout, preserving old data and working configuration links, while verifying work-only Epic routing and installing current AI clients with mise.

**Architecture:** An explicit relocation command previews by default. It first enrolls configuration from the new checkout, archives the old canonical checkout under hidden state, moves the new checkout into place, reapplies links, and updates restore metadata. Any failure reverses the steps. Epic setup remains a separate opt-in WSL bootstrap task.

**Tech stack:** Python standard library, existing transactional installer, Bash/mise, unittest.

## Constraints

- No live reference-PC installation, account login, gateway download, package install or old-repository deletion during development.
- Preserve existing personal Git/agent credentials. Archive the old checkout instead of discarding untracked changes.
- Repair installed links and backup/manifest references; retain functioning rollback after relocation.
- Support relocation before or after bootstrap; preserve an existing Epic opt-in unless explicitly changed.
- Personal clients outside `~/dev/epic`; Epic clients inside it; explicit Epic launchers work anywhere on WSL.
- AI client updates occur during explicit bootstrap, through mise, with separate account homes.

## Tasks

- [x] Add relocation filesystem regressions for preview, an old canonical checkout, already-installed links, backup restore, private authentication files, and injected failure.
- [x] Add `relocate` and `scripts/relocate.py`, reusing installer enrollment/restore; return the manifest path from installer apply.
- [x] Preserve unselected GitHub CLI authentication files when replacing a linked configuration directory.
- [x] Verify Epic routing and gateway setup against the coworker's script, without modifying that repository; add missing work-folder creation and isolated credential-helper handling.
- [x] Ensure explicit bootstrap installs latest Claude/Codex with mise even when older binaries exist.
- [x] Document permanent-folder migration, Bash, personal/work logins, Git identity/authentication and copyable WSL commands.
- [ ] Run full tests and independent review; commit by feature, merge and push main.

## Review focus

Existing dirty checkout preservation; relative symlinks in historical backups; restored manifests pointing at the archived old checkout; failing second enrollment or metadata update; personal credentials behind old directory links; Epic configuration not leaking into sibling or personal repositories.
