# WSL Neovim through mise

The user prefers mise to Bob for WSL Neovim. Keep the reference Omarchy PC's
native Arch Neovim installation; both use the same copied editor configuration.

WSL bootstrap resolves `neovim@latest` from fresh upstream metadata and pins the
resolved version in the existing backed-up global mise config,
activates it for Mason, and links `~/.local/bin/nvim` to mise's persistent shim.
Project version pins remain local. The previous owned portable link may be
repointed; its installation and Bob's state remain on disk. Unknown local
executables are preserved. Omarchy retains its existing provisioning behavior.

Keeping Bob would require separate manager/path integration. Keeping the portable
fallback would retain a second installer alongside mise. The selected approach
uses the manager already responsible for the WSL runtime and AI clients.

Claude, Codex and Neovim are excluded from the release-age delay while other
tools retain their policy. Neovim must still pass the locked plugins' >=0.12
check before editor setup continues.
