# Agent appearance and edit defaults

The installer merges these preferences into the selected account files, with
the normal installation backup/restore transaction. Personal profiles get them
on both platforms. Work profiles get them only with the opted-in Epic profile,
after their gateway config exists; preferences never create a partial work login.

Codex uses `approval_policy = "on-request"`, `sandbox_mode = "workspace-write"`,
and the reference PC's colored statusline: model/reasoning, directory, Git branch,
run state, remaining context, weekly limit, context size, used tokens and task
progress. Existing provider, model, hooks, MCP and authentication settings remain.
Changed TOML formatting/comments normalize; original bytes remain in the backup.
The opted-in Epic installer additionally repairs an old personal Portkey config
for direct ChatGPT login; see [account separation and login](epic.md).

Claude uses `permissions.defaultMode = "acceptEdits"`. The shared
`~/.local/bin/claude-statusline` renders model, directory, Git branch, remaining
context, context size and token counts; weekly capacity appears only when Claude
supplies that metric. It makes no network calls. Unsupported Codex-only metrics
are omitted. Existing permission rules, hooks and gateway settings are retained.

These defaults let routine edits proceed automatically; operations requiring
additional permission may still prompt. Per-session choices and managed policy
remain in effect. This does not select bypass-permissions/full-access mode.

The standalone preference merger previews explicit homes by default:

```bash
cd ~/.dotfiles
python3 scripts/ai_preferences.py --claude-home ~/.claude --codex-home ~/.codex
# Add --apply to back up and write, or select the configured -epic homes.
```

To explicitly switch only the personal Codex configuration to OpenAI/ChatGPT:

```bash
python3 scripts/ai_preferences.py --codex-home ~/.codex --personal-openai --apply
cd ~
codex login
```

This removes the selected custom provider and its model/catalog selection, with
a private backup. It does not copy credentials or sign in; Epic homes are refused.

Python 3.11+ is required (stock Ubuntu 24.04+ and current Omarchy provide it).
Linked or hardlinked account config paths require explicit reconciliation.
No credentials or machine-local account files are stored in this repository.

References: [Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference),
[Codex sandbox and approvals](https://learn.chatgpt.com/docs/agent-approvals-security),
[Claude permissions](https://code.claude.com/docs/en/permissions), and
[Claude statusline](https://code.claude.com/docs/en/statusline).
