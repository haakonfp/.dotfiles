# Mise release policy

An explicit bootstrap resolves `claude@latest` and `codex@latest`. On WSL it
also resolves `neovim@latest`, then validates Neovim >=0.12.0 for the locked
editor plugins. Omarchy keeps its native Neovim provisioning.

Both profiles add `claude`, `codex`, and `neovim` to the global
`minimum_release_age_excludes` array, preserving existing entries and the
release-age policy for other tools. The bootstrap backs up an existing global
config before editing it. Project selections and AI account files stay intact.

`@latest` alone can reuse old release lists. The explicit install uses a new
temporary `MISE_CACHE_DIR` and `MISE_USE_VERSIONS_HOST=0` so mise asks upstream
without its shared versions host or old local metadata. The temporary cache is
removed after success or failure; existing caches and installed versions remain.
If upstream resolution fails, the update fails instead of using an old cached
release list. The resolved releases are pinned as global defaults. Shell and
editor startup do not perform these refreshes.

To add only the age exclusions without installing or upgrading anything:

```bash
excludes=$(mise -C / settings get minimum_release_age_excludes) || exit
for tool in claude codex neovim; do
  if [[ $excludes != *\""$tool"\"* ]]; then
    mise -C / settings add minimum_release_age_excludes "$tool" || exit
  fi
done
```

`settings add` appends duplicates, which is why the guard matters. When Claude
and Codex are already excluded, the only mutation is:

```bash
mise -C / settings add minimum_release_age_excludes neovim
```

The policy and directory overrides were checked in isolated homes with mise
2026.11.2 and 2026.8.12. This uses their supported `settings get/add` commands,
`MISE_CACHE_DIR`, `MISE_USE_VERSIONS_HOST`, and `use --path --pin`. Older mise
versions were not verified. Direct upstream queries remain subject to upstream
availability and GitHub rate limits. Explicit per-tool release-age overrides,
backend overrides, or administrator locks may require local reconciliation.

References: [release-age exclusions](https://mise.jdx.dev/configuration/settings.html#minimum_release_age_excludes),
[versions host](https://mise.jdx.dev/configuration/settings.html#use_versions_host),
[cache directories](https://mise.jdx.dev/directories.html), and
[2026.8.12 settings](https://github.com/jdx/mise/blob/v2026.8.12/settings.toml).
