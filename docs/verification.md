# Platform verification

The second platform review found and fixed gaps not covered by the original
70-test fixture suite:

- Interactive Omarchy aliases conflicted with `ff`/`eff` function definitions;
  startup now removes those aliases before defining the shared functions.
- Local tool fallbacks could lose to older system binaries in later shells;
  `~/.local/bin` is now promoted and deduplicated.
- An existing Git-installed Agamotto directory retained a marker that made
  Omarchy reject the linked theme payload. The old theme is now backed up whole
  and restored with its repository metadata and original directories intact.
- Replacing old directory links could hide unselected machine-local files.
  Monitor configuration and local Bash/Foot/tmux preferences are now retained;
  a missing monitor module uses the installed Omarchy template.
- Windows CMD's OEM output could break names containing characters such as
  `ø`. Settings/kubeconfig discovery now requests Unicode output explicitly.
- Native Docker needs WSL2. Bootstrap now rejects WSL1 before provisioning and
  documents the standard Microsoft WSL2 kernel prerequisite.

## Executed here

- Full expanded suite: **195 tests passed**, including a private tmux server
  verifying that closing the last pane exits its client and preserves another
  session. The suite was run outside the sandbox's Unix-socket restriction.
- Actual installed Omarchy 4.5.0 headless theme generation, Foot configuration
  parsing and Hyprland Lua verification in disposable homes, including a
  pre-existing Git-installed theme.
- Actual interactive Bash startup against installed Omarchy defaults in a
  disposable home; shared functions, local overrides and local binary precedence
  loaded successfully.
- Keyboard-map compilation and terminal desktop-entry argument checks against
  the installed Omarchy/Hyprland tooling.
- Isolated full LazyVim startup using copied plugin caches, with downloads
  disabled, loaded Agamotto and the copied user options.
- Windows JSONC/profile/key merging, Unicode-path transport, font payload handling,
  Epic routing/isolation and bootstrap failure cases use executable temporary
  fixtures. Real Neovim startup-error behavior is tested with headless Neovim.
- The Windows font installer executes under portable PowerShell with substituted
  registry/native APIs. Regressions reproduce Windows PowerShell's terminating
  missing-value error, cover fresh/partial installs and unchanged retries, preserve
  unrelated registrations, and ensure access failures still stop installation.
  These three tests require `pwsh` (or native Windows `powershell.exe`) on PATH;
  they otherwise skip.
- Runtime regressions cover a fresh machine without mise, old Node/pnpm,
  runtime-only/obsolete .NET, checkout-only SDK selections including an inherited
  activated PATH, preservation of
  compatible versions and configuration backups. Earlier offline checks with
  actual mise and fixture runtimes verified global selection and activation.
  The new mandatory `@latest` client selection requires online release metadata;
  it is covered by offline installer fixtures here, with real downloads left for
  the destination bootstrap.
- Neovim fallback fixtures isolate PATH from this PC's executable. An unused Bob
  installation no longer blocks a missing `nvim`; its files remain untouched,
  and the portable binary works in a fresh shell. A separate regression confirms
  Bash forgets a cached old system executable after the fallback is installed.
- WSL fixtures cover global mise Neovim selection, preserving project pins and
  Bob, a persistent command outside the checkout, migration from the owned
  portable link, and preservation of an unrecognized local executable. Omarchy
  provisioning does not add a mise Neovim default.
  Actual mise downloaded Neovim 0.12.6 into a disposable home; bootstrap created
  the shim link and a fresh Bash process launched it from outside the checkout.
- A real headless Neovim fixture confirms that a failed Mason install lets
  another queued installer complete before returning failure with the log path.
  Another reproduces installs started during plugin restoration: bootstrap keeps
  that same Neovim process alive until they finish, without aborting/restarting
  the jobs between plugin and language-tool setup.
  Real cached Lazy/LazyVim configuration merging reproduces the duplicate-install
  error during build-time Mason reconfiguration. Bootstrap now owns installs in
  that process; a separate normal-startup test retains automatic installation.
  A shell regression checks that failure preserves its exit code and cleans the
  temporary directory after bootstrap's local variables have left scope.
- Omarchy glassy/opaque mode removal is previewed, backed up and restored;
  WSL leaves it alone. Terminal settings tests cover opacity/acrylic overrides,
  unfocused appearance and a Mica-free application theme.
- Login migration covers a copied managed loader, a link from another checkout,
  a changed personal initializer with repeat/restore, and a custom profile that
  must not be saved as its own initializer.
- Git migration covers copied shared configs in both global locations, a link
  from another checkout, and changed private settings. Real Git queries verify
  identity/helper precedence and relative includes, with repeat and rollback.
  Configs may include their saved predecessors without creating an include
  loop, including migration from a linked Git configuration directory.
  Private dependency copies retain binary contents/executable permissions and
  a forced partial-copy failure restores the original directory link.
- Canonical checkout migration covers preview, first enrollment, an existing
  `-next` installation, dirty old checkout preservation, personal authentication,
  absolute/relative backup links, restore after the move, and injected second
  enrollment/metadata failures. Epic opt-in is inferred and can be disabled.
  Final review regressions cover relative links inside archived checkouts,
  authentication links in real Codex/Claude/SSH directories, and restoring their
  original targets after a late failure. Unrelated project links stay untouched;
  a checkout containing its own backup state is rejected before writes.
- Real Git checks verify personal/work/sibling identity and credential-helper
  scoping, including setting personal identity after Epic setup. The shared
  gateway credential helper uses isolated work homes and provider environment.

Omarchy 4.5's cold-start cursor hook is disabled only in the headless Hyprland
parsing fixture, where there is no running compositor for that startup effect.

## Destination checks

Agent preferences are tested for JSON/TOML value preservation, repeat/no-op,
private backups and transaction restore. Claude statusline tests execute with
real temporary Git repositories and optional/malformed session metadata.
Legacy Epic Claude migration tests cover explicit gateway recognition, profile
conflicts, private sidecar handling, path rewriting and late-failure rollback.
Setup regressions verify missing-file failures, valid partial repair, snapshots
before installer writes, and retaining complete Codex configs when installation
fails. No corporate SSO or real gateway installation was run here.

Mise release policy and override commands were checked with actual mise
2026.11.2 and 2026.8.12 in isolated homes. Fixtures enforce fresh metadata and
cache cleanup on failed upstream resolution. This PC's global age exclusions now
include Claude, Codex and Neovim; its selected tool versions were not changed.

There is no Windows host or second Omarchy PC connected to this session. Actual
Windows font registration/rendering, terminal key forwarding and host clipboard;
Ubuntu package downloads/builds, Docker service/group access; physical keyboard
behavior, monitor scale, live wallpaper/bar appearance; Epic SSO and sidebar event
hooks still need a first run on each destination. Tests do not establish those
host-specific results. The [rollout guide](rollout.md) gives the commands and
short acceptance checklist.

Verification did not apply the setup to the live desktop, install packages,
authenticate accounts or change services. Git publishing is handled separately.
