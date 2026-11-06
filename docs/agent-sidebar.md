# Agent sidebar setup

Bootstrap installs the pinned sidebar checkout and binary at
`~/.local/share/tmux/plugins/tmux-agent-sidebar`. Tmux prefix+`e` toggles it.
Authentication and event integration are per account/home; keep existing hooks.

- Sign into personal agents normally outside the Epic workspace: `claude auth login`
  and `codex login`. On an opted-in WSL workstation, run `epic-ai-setup` separately
  for the gateway accounts. Do not copy login caches between computers.
- For Claude, run `/plugin marketplace add ~/.local/share/tmux/plugins/tmux-agent-sidebar`
  and `/plugin install tmux-agent-sidebar@hiroppy` inside the selected account.
  Repeat in `claude-epic` only on opted-in WSL when work setup is complete.
- For Codex, open the sidebar's yellow information badge and use its setup snippet
  for that client version. Back up the selected account's configuration first;
  merge the sidebar events into existing hooks rather than replacing the config.
  Repeat in `codex-epic` only where that account is configured.
- If you use OpenCode, link only the plugin bridge file to
  `~/.config/opencode/plugins/tmux-agent-sidebar.js`, preserving the other plugins.
  The source is `.opencode/plugins/tmux-agent-sidebar.js` inside the sidebar checkout.
- Start a new agent pane and submit a prompt. Confirm its running/waiting/finished
  status appears. In tmux the shared wrapper uses `--no-daemon` only when the
  installed Codex client supports it, so pane hook variables stay attached.

The plugin's own [documentation](https://hiroppy.github.io/tmux-agent-sidebar/)
covers client-specific hooks. These steps intentionally avoid replacing private
agent settings or credentials and do not install any Epic integration on Omarchy.
