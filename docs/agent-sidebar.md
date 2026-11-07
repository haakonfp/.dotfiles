# Agent sidebar setup

Bootstrap installs the pinned sidebar checkout and binary at
`~/.local/share/tmux/plugins/tmux-agent-sidebar`. Tmux prefix+`e` toggles it.
Setup now merges event hooks automatically into each account, preserving other
hooks, provider settings and login state. The definitions come from the pinned
sidebar's `setup` command; no agent wizard or login is run.

- Omarchy and ordinary WSL bootstrap configure personal Claude and Codex.
- WSL bootstrap with `--epic` also configures already-ready Epic profiles.
  For a fresh work login, `epic-ai-setup` configures both work profiles and adds
  their hooks once gateway setup completes. No partial work login is created.
- Existing files have private backups beside them; repeated setup adds no
  duplicate handlers. Existing Codex hook trust state is preserved. When moving
  from Claude's sidebar marketplace plugin, setup disables only that plugin and
  uses direct hooks, preventing duplicate events; other plugins stay as set.

To update only hooks on an existing installation, without package provisioning:

```bash
cd ~/.dotfiles
git pull --ff-only
# Omarchy:
python3 scripts/sidebar_hooks.py --profile omarchy --apply
# Ubuntu WSL with Epic configured:
python3 scripts/sidebar_hooks.py --profile wsl --epic --apply
# Ordinary WSL: omit --epic.
```

Omit `--apply` to preview. The sidebar must already be installed. Restart running
agents after setup. A fresh Codex profile may request a one-time review/trust in
`/hooks`; setup enables the hook feature but does not bypass native trust review.
See [OpenAI's hook documentation](https://learn.chatgpt.com/docs/hooks).

Authentication is still local to each account:

- Sign into personal agents normally outside the Epic workspace: `claude auth login`
  and `codex login`. On an opted-in WSL workstation, run `epic-ai-setup` separately
  for the gateway accounts. Do not copy login caches between computers.
- If you use OpenCode, link only the plugin bridge file to
  `~/.config/opencode/plugins/tmux-agent-sidebar.js`, preserving the other plugins.
  The source is `.opencode/plugins/tmux-agent-sidebar.js` inside the sidebar checkout.
- Start a new agent pane and submit a prompt. Confirm its running/waiting/finished
  status appears. In tmux the shared wrapper uses `--no-daemon` only when the
  installed Codex client supports it, so pane hook variables stay attached.

The plugin's own [documentation](https://hiroppy.github.io/tmux-agent-sidebar/)
covers client-specific events. Epic integration is installed only on opted-in WSL.
