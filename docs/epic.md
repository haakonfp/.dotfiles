# Epic on Ubuntu WSL

`~/dev/epic` is the work directory. With the optional Epic profile enabled,
normal `claude` and `codex` commands select work accounts there and in its
subdirectories. Elsewhere they select personal accounts. Both accounts use the
same mise-managed client binaries, with separate configuration and login state.

## Install and sign in

Inside Ubuntu WSL2, from your dotfiles checkout:

```bash
./bootstrap-wsl --epic --dry-run
./bootstrap-wsl --epic --windows-fonts
```

The explicit bootstrap creates `~/dev/epic`, installs the optional links and Git
include, and sets Bash as the Linux login shell. Open a new Bash session after
bootstrap. A Windows Terminal profile with an explicit Zsh launch command will
continue to launch Zsh until that profile command is changed.

Each explicit bootstrap installs or updates `claude@latest` and `codex@latest`
and WSL `neovim@latest` through mise, with release-age exclusions and a fresh
upstream metadata cache. It records resolved versions in the global mise config.
Existing standalone clients remain on disk; the activated mise versions become
the defaults. Changed global config is backed up beside it as
`config.toml.before-dotfiles.*`. Compatible Node/pnpm/.NET versions, unrelated
tool settings and project pins are preserved. Shell startup does not check for
new client releases. See [mise's explicit latest selection](https://mise.jdx.dev/cli/use.html).

When upgrading an old Epic setup, run `epic-ai-setup` before signing into personal
Claude: its legacy default profile may still be gateway-managed. After setup,
sign into your personal accounts outside the work directory:

```bash
cd ~
claude auth login
codex login
```

The personal homes are `~/.claude` and `~/.codex`. The configuration installer
creates private settings with shared UI/edit defaults; account login remains
local. Ordinary personal account files stay in place. Legacy named profiles are
not automatically combined; an existing account may need a fresh login.

For an old setup where both Codex homes select Portkey, update and apply only
the configuration, then sign into your ChatGPT account from your home directory:

```bash
cd ~/.dotfiles
git pull --ff-only
./install --profile wsl --epic --apply
cd ~
codex logout
codex login
codex login status
```

The opted-in installer and `epic-ai-setup` convert a legacy personal Portkey
config in `~/.codex` to OpenAI with ChatGPT login. The original config is backed
up. Gateway model/catalog selection and the active provider's gateway settings
are removed from that personal config; Codex chooses its default personal model.
Other custom personal providers are retained. The working `~/.codex-epic`
provider, model and credentials stay separate. Login is interactive; choose the
ChatGPT account that has your Pro subscription. No API key is required.

Then explicitly prepare both work clients:

```bash
epic-ai-setup
cd ~/dev/epic
claude
codex
```

`epic-ai-setup` creates `~/.claude-epic` and `~/.codex-epic`, installs the shared
Epic `claude-gateway` if missing, and runs `claude-gateway run` for Claude plus
`claude-gateway codex setup` for Codex when their configuration is absent. This
is the interactive Epic gateway/SSO step for both clients. A complete existing
work profile does not repeat authentication. Existing config files are backed
up before running the installer or repairing valid partial profiles, and
complete client configs are restored if those commands rewrite them. Setup
verifies the expected files before reporting success; invalid configs stop it.
Neither ordinary bootstrap nor shell startup performs this sign-in. Bootstrap
activates mise, and the setup helper includes mise's installed shims on PATH;
no separate `mise env` command is required in a fresh configured Bash session.

If Claude previously opened the Epic account outside `~/dev/epic`, the old
default `~/.claude` may still be the work profile. Setup recognizes a gateway
helper config file or an `apiKeyHelper` whose executable is `claude-gateway`.
It moves that directory intact into an absent or truly empty `~/.claude-epic`
and moves its default `~/.claude.json` sidecar there when unambiguous. Only known
JSON config path references are rewritten; credentials and sessions move intact.
The recovery journal and original config bytes are private under
`~/.local/state/dotfiles/ai-migrations/`. Nonempty destinations, ambiguous
sidecars and linked paths stop migration rather than merging accounts.
If the Epic directory already contains tokens, logs or other state, setup
completes that profile in place. When the default Claude settings explicitly
use `claude-gateway`, setup recovers missing Epic settings from that working
configuration and preserves the existing Epic helper config and token cache.
Once the work configuration is complete, it backs up the personal settings,
removes the gateway credential helper, gateway environment/model settings and
gateway command hooks, and selects personal Claude.ai login. Other hooks and
preferences remain. Credential caches, sessions and existing source assets are
not moved or copied; legacy helper/cache files may remain inert on disk.
In particular, gateway tokens used by working Codex are not moved.
For this repair, close Claude sessions and run:

```bash
cd ~/.dotfiles
git pull --ff-only
epic-ai-setup
cd ~
claude auth login
```

Then `cd ~/dev/epic` and run `claude` to use Epic. Existing complete Epic
settings are preserved. If gateway setup fails, the working default settings
remain. The standalone whole-profile migration preview still reports conflicting
profiles for explicit reconciliation.
You can inspect the migration before setup:

```bash
cd ~/.dotfiles
python3 scripts/migrate_claude_profile.py
```

The installer applies shared statuslines and edit-approval defaults to personal
profiles and already-configured opted-in work profiles. Setup applies them to
newly configured work profiles too. See [agent preferences](agent-preferences.md).

## Account selection

| Invocation directory | `claude` / `codex` | `claude-epic` / `codex-epic` |
| --- | --- | --- |
| `~/dev/epic` or a subdirectory | Epic homes | Epic homes |
| `~/dev/epic-other`, personal projects, anywhere else | Personal homes | Epic homes |

The explicit Epic commands force work accounts from any directory. Missing work
configuration fails with an `epic-ai-setup` hint. Provider and authentication
environment overrides are cleared for the launched child process; the parent
shell is preserved. Physical directory resolution also handles symlinks into
the work directory. Selection uses the directory where the command is invoked,
so `cd` into the intended workspace before using client directory flags.
The retained `gh solve` and `gh follow` workflows use the same selection.

Codex's SQLite state defaults to its selected `CODEX_HOME`; inherited
`CODEX_SQLITE_HOME` is cleared with other overrides. A `sqlite_home` setting in
your own client config can change that default. See the
[official OpenAI environment documentation](https://learn.chatgpt.com/docs/config-file/environment-variables).

For a different root, export `EPIC_WORKSPACE` before the opted-in bootstrap and
keep the same absolute path in `~/.config/dotfiles/local.bash`. Bootstrap creates
that directory and generates its Git condition. Re-run the opted-in bootstrap
after changing the root so Git and agent routing agree.

## Git identity and authentication

Set personal defaults in `~/.gitconfig.local` and your own work identity in
`~/.config/dotfiles/git-epic.local`. For example, replace these placeholders:

```bash
git config --file ~/.gitconfig.local user.name 'Your Name'
git config --file ~/.gitconfig.local user.email 'your-personal-address'
git config --file ~/.config/dotfiles/git-epic.local user.name 'Your Name'
git config --file ~/.config/dotfiles/git-epic.local user.email 'your-work-address'
```

The generated conditional include selects the work profile in repositories
whose Git directory is under the work root. Personal defaults apply elsewhere,
including sibling paths such as `~/dev/epic-other`. Existing repository-local
Git settings can override these defaults; inspect an actual repository before
committing:

```bash
git config --show-origin --get user.email
git var GIT_AUTHOR_IDENT
git remote get-url origin
```

The managed `~/.gitconfig` loader reads `~/.gitconfig.local` before the optional
Epic gate. Updating personal defaults later therefore preserves the work
override. Explicit Epic bootstrap removes only its exact older generated
include block from a regular `~/.gitconfig.local`, with a backup; symlinked or
custom private includes remain intact. Reapply the configuration installer when
upgrading an older managed loader so it gains this final optional gate.

Commit name/email identify the author of a commit. They do not sign into the
enterprise Git server. The work profile rewrites
`https://github.ol.epicgames.net/` remotes to
`git@github.ol.epicgames.net:`; access still requires your own authorized SSH
key, enterprise account and network access. Bootstrap does not create, copy or
register SSH credentials.

The separate HTTPS helper for `https://live.roost.on.epicgames.com` invokes the
shared gateway with only the Epic homes and gateway configuration selected. Its
Git configuration applies only in matching work repositories and only to that
credential URL; it does not configure personal Git hosting credentials.

Existing private `git-epic.local` files are preserved. If yours still invokes
`claude-gateway credential-helper` directly, replace only that URL's credential
section after reviewing your existing settings:

```gitconfig
[credential "https://live.roost.on.epicgames.com"]
    helper =
    helper = "!\"$HOME/.local/bin/epic-git-credential\""
```

Git's condition matches the Git directory rather than the shell's working
directory. Linked worktrees, separate Git directories and repositories reached
through unusual symlink layouts can therefore differ from agent routing. Check
their resolved identity with the commands above and set an explicit
repository-local identity if needed.

## Kubeconfig and disabling Epic

The opted-in bootstrap optionally links a Windows-managed `.kube/config` when
Linux has no config at that path. An existing Linux config is preserved. This
link is global, not directory-selected; use `KUBECONFIG=/path/to/config` when you
need a different context. Windows certificate paths and executable auth helpers
may need local adjustment. The bootstrap does not change Windows networking,
VPN settings, kubeconfig contents or Kubernetes contexts.

Ordinary WSL and Omarchy installs do not enable Epic routing. Reinstalling
without `--epic` removes this checkout's optional links and include gate while
preserving private account files and the work directory. Start a new shell after
changing profiles. A kubeconfig link created during explicit bootstrap is not
removed by changing profiles; manage that local link explicitly when needed.
