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

- Full expanded suite: **79 tests passed**, including a private tmux server
  verifying that closing the last pane exits its client and preserves another
  session. The suite was run outside the sandbox's Unix-socket restriction.
- Actual installed Omarchy 4.0.6 headless theme generation, Foot configuration
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

## Destination checks

There is no Windows host or second Omarchy PC connected to this session. Actual
Windows font registration/rendering, terminal key forwarding and host clipboard;
Ubuntu package downloads/builds, Docker service/group access; physical keyboard
behavior, monitor scale, live wallpaper/bar appearance; Epic SSO and sidebar event
hooks still need a first run on each destination. Tests do not establish those
host-specific results. The [rollout guide](rollout.md) gives the commands and
short acceptance checklist.

Verification did not apply the setup to the live desktop, install packages,
authenticate accounts or change services. Git publishing is handled separately.
