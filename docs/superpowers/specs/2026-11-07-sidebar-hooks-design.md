# Automatic sidebar hooks

Setup must configure the two personal agents on Omarchy and ordinary WSL, and
all four personal/Epic agents on opted-in WSL. Preserve existing hooks, provider
settings and credentials; do not create work settings before gateway setup.

Use the pinned sidebar binary's pure `setup` JSON generator and merge its
definitions into each account's own config. This keeps events aligned with the
installed sidebar. Copying this PC's account files would include private state;
running the interactive wizard does not fit bootstrap. Reuse private backups
and atomic writes from the existing preference helper. Repeat setup must avoid
duplicate hooks and preserve unchanged config bytes and hook trust state.

Bootstrap installs personal hooks and configured opted-in work hooks.
`epic-ai-setup` adds work hooks after the profiles are ready. A standalone
preview/apply command supports existing installations. Enable the Codex hook
feature, preserve native trust review, and document restart requirements.

Implementation: add the merger/CLI, wire both setup paths, update instructions,
then run focused merge/profile/integration checks and review before publication.
