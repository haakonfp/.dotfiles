# WSL Neovim through mise

The user prefers mise to Bob for WSL Neovim. Keep the reference Omarchy PC's
native Arch Neovim installation; both use the same copied editor configuration.

WSL bootstrap selects `neovim@0.12.6` in the existing backed-up global mise config,
activates it for Mason, and links `~/.local/bin/nvim` to mise's persistent shim.
Project version pins remain local. The previous owned portable link may be
repointed; its installation and Bob's state remain on disk. Unknown local
executables are preserved. Omarchy retains its existing provisioning behavior.

Keeping Bob would require separate manager/path integration. Keeping the portable
fallback would retain a second installer alongside mise. The selected approach
uses the manager already responsible for the WSL runtime and AI clients.
