"""Exercise provisioning boundaries without package installs or real account state."""
import json
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import shlex
import tempfile
import tarfile
import tomllib
import unittest

REPO = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='dotfiles bootstrap ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = dict((key, value) for key, value in os.environ.items()
                        if not key.startswith(('MISE_', '__MISE_', 'XDG_')))
        self.env.update(HOME=str(self.home), PATH=f'{self.bin}:/usr/bin:/bin', USER='tester',
                        XDG_CONFIG_HOME=str(self.home / '.config'),
                        XDG_DATA_HOME=str(self.home / '.local/share'),
                        XDG_STATE_HOME=str(self.home / '.local/state'),
                        XDG_CACHE_HOME=str(self.home / '.cache'),
                        MISE_DATA_DIR=str(self.home / '.local/share/mise'),
                        MISE_CACHE_DIR=str(self.home / '.cache/mise'),
                        MISE_STATE_DIR=str(self.home / '.local/state/mise'),
                        MISE_SYSTEM_CONFIG_DIR=str(self.root / 'system-config'),
                        MISE_SYSTEM_DATA_DIR=str(self.root / 'system-data'))
        for name in ('MISE_CONFIG_DIR', 'MISE_GLOBAL_CONFIG_FILE'):
            self.env.pop(name, None)
        for name in ('sudo', 'curl', 'apt-get', 'cargo', 'rustup', 'git', 'mise', 'cmd.exe', 'wslpath'):
            self.fake(name, 'echo "unexpected external operation" >&2; exit 99')

    def fake(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/bash\n' + body + '\n')
        path.chmod(0o755)

    def wsl(self):
        self.fake('uname', 'if [[ $1 == -r ]]; then echo 6.6-microsoft-standard-WSL2; else echo x86_64; fi')
        self.fake('cat', 'if [[ $1 == /etc/os-release ]]; then echo ID=ubuntu; else /usr/bin/cat "$@"; fi')

    def run_script(self, path, *args):
        return subprocess.run(['bash', str(REPO / path), *args], env=self.env, text=True, capture_output=True)

    def shell(self, script, cwd=None):
        return subprocess.run(['bash', '--noprofile', '--norc', '-c',
            'source "' + str(REPO / 'epic/.config/dotfiles/shell/epic.bash') + '"; ' + script],
            env=self.env, cwd=cwd or self.home, text=True, capture_output=True)

    def test_dry_run_writes_nothing_and_invokes_no_installers(self):
        self.wsl()
        result = self.run_script('bootstrap-wsl', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Docker', result.stdout)
        self.assertIn('latest Claude/Codex', result.stdout)
        self.assertIn('existing clients', result.stdout)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_wsl1_rejected_before_any_provisioning_or_home_writes(self):
        self.wsl()
        self.fake('uname', 'echo 4.4.0-19041-Microsoft')
        result = self.run_script('bootstrap-wsl')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('WSL2', result.stderr)
        self.assertNotIn('unexpected external operation', result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_older_standard_wsl2_kernel_is_accepted_in_preview(self):
        self.wsl()
        self.fake('uname', 'echo 4.19.128-microsoft-standard')
        result = self.run_script('bootstrap-wsl', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_epic_kubeconfig_windows_unicode_directory_is_linked(self):
        windows = self.root / 'Windows Bjørn 用户'
        (windows / '.kube').mkdir(parents=True)
        (windows / '.kube/config').write_text('private fixture')
        self.env['FAKE_WINDOWS_HOME'] = str(windows)
        self.fake('cmd.exe', "/usr/bin/python3 -c 'import os,sys; value=os.environ[\"FAKE_WINDOWS_HOME\"] + \"\\r\\n\"; encoding=\"utf-16le\" if \"/u\" in [a.lower() for a in sys.argv] else \"cp850\"; sys.stdout.buffer.write(value.encode(encoding, errors=\"replace\"))' \"$@\"")
        self.fake('wslpath', 'printf \"%s\\n\" \"$2\"')
        result = self.library('bootstrap_epic_local')
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.home / '.kube/config'
        self.assertTrue(target.is_symlink(), result.stdout + result.stderr)
        self.assertEqual(target.resolve(), windows / '.kube/config')
        self.assertNotIn('private fixture', result.stdout + result.stderr)

    def test_epic_omarchy_rejected_even_in_preview(self):
        result = self.run_script('bootstrap', '--profile', 'omarchy', '--epic', '--dry-run')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Ubuntu WSL', result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_epic_ubuntu_wsl_guard_precedes_profile_creation(self):
        result = self.run_script('epic/.local/bin/epic-ai-setup')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Ubuntu WSL', result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_docker_desktop_refused_before_packages(self):
        self.wsl()
        self.fake('docker', 'if [[ $1 == context ]]; then echo desktop-linux; fi')
        result = self.run_script('bootstrap-wsl')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Docker', result.stderr)
        self.assertNotIn('unexpected external operation', result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_foreign_docker_endpoint_refused_before_packages(self):
        self.wsl()
        self.env['DOCKER_HOST'] = 'tcp://remote:2376'
        result = self.run_script('bootstrap-wsl')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Docker', result.stderr)
        self.assertNotIn('unexpected external operation', result.stderr)

    def agent(self, name):
        self.fake(name, 'if [[ ${1:-} == --help ]]; then echo --no-daemon; exit; fi\n/usr/bin/python3 -c \'import os,json,sys; print(json.dumps({"env":dict(os.environ),"args":sys.argv[1:]}))\' "$@"')

    def configured(self):
        for directory, files in (('.claude-epic', ('settings.json', 'gateway-helper-config.json')),
                                 ('.codex-epic', ('config.toml', 'claude-gateway.json'))):
            root = self.home / directory
            root.mkdir()
            for file in files:
                (root / file).write_text('' if file == 'config.toml' else '{}')

    def test_missing_epic_profiles_fail_without_personal_fallback(self):
        self.wsl()
        self.agent('claude')
        work = self.home / 'dev/epic'
        work.mkdir(parents=True)
        result = self.shell('claude', work)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('epic-ai-setup', result.stderr)
        self.assertEqual(result.stdout, '')

    def test_claude_information_flags_work_before_epic_profile_setup(self):
        self.wsl()
        self.agent('claude')
        work = self.home / 'dev/epic'
        work.mkdir(parents=True)
        for flag in ('--version', '-v', '-h'):
            with self.subTest(flag=flag):
                result = self.shell('claude ' + flag, work)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['args'], [flag])
                self.assertFalse((self.home / '.claude-epic').exists())
        result = self.shell('claude --help', work)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('not configured', result.stderr)

    def test_directory_boundary_symlinks_and_explicit_selection(self):
        self.wsl()
        self.agent('codex')
        self.configured()
        work = self.home / 'dev/epic'
        other = self.home / 'dev/epic-other'
        work.mkdir(parents=True)
        other.mkdir()
        alias = self.home / 'alias'
        alias.symlink_to(work, target_is_directory=True)
        for cwd, command, expected in ((work, 'codex', '.codex-epic'), (other, 'codex', '.codex'),
                                        (alias, 'codex', '.codex-epic'), (other, 'codex-epic', '.codex-epic')):
            with self.subTest(cwd=cwd, command=command):
                result = self.shell(command, cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['env']['CODEX_HOME'], str(self.home / expected))

    def test_both_directions_scrub_overrides_without_polluting_parent(self):
        self.wsl()
        self.agent('claude')
        self.configured()
        self.env.update(ANTHROPIC_API_KEY='secret', OPENAI_API_KEY='secret', CLAUDE_GATEWAY_CONFIG_OVERRIDES='bad',
                        CODEX_HOME='/wrong', AWS_BEARER_TOKEN_BEDROCK='secret')
        for command, directory in (('claude', '.claude'), ('claude-epic', '.claude-epic')):
            result = self.shell(command + '; printf "PARENT:%s" "$ANTHROPIC_API_KEY"')
            self.assertEqual(result.returncode, 0, result.stderr)
            payload, parent = result.stdout.split('\n', 1)
            env = json.loads(payload)['env']
            self.assertEqual(env['CLAUDE_CONFIG_DIR'], str(self.home / directory))
            for name in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'CLAUDE_GATEWAY_CONFIG_OVERRIDES', 'AWS_BEARER_TOKEN_BEDROCK'):
                self.assertNotIn(name, env)
            self.assertEqual(parent, 'PARENT:secret')

    def test_personal_agent_first_invocation_creates_only_its_private_home(self):
        self.wsl()
        for agent, directory, unrelated in (('codex', '.codex', '.claude'), ('claude', '.claude', '.codex')):
            with self.subTest(agent=agent):
                self.agent(agent)
                result = self.shell(agent)
                self.assertEqual(result.returncode, 0, result.stderr)
                home = self.home / directory
                self.assertTrue(home.is_dir())
                self.assertEqual(home.stat().st_mode & 0o777, 0o700)
                self.assertFalse((self.home / unrelated).exists())
                home.rmdir()
                for epic in ('.claude-epic', '.codex-epic'):
                    self.assertFalse((self.home / epic).exists())

    def test_no_daemon_inserted_once_when_supported_inside_tmux(self):
        self.wsl()
        self.agent('codex')
        self.env['TMUX'] = '/tmp/fake,1,0'
        for command in ('codex hello', 'codex --no-daemon hello'):
            result = self.shell(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['args'], ['--no-daemon', 'hello'])

    def test_epic_setup_preserves_existing_profiles_and_scopes_gateway(self):
        self.wsl()
        lib = self.home / '.config/dotfiles/shell/epic.bash'
        lib.parent.mkdir(parents=True)
        lib.symlink_to(REPO / 'epic/.config/dotfiles/shell/epic.bash')
        self.configured()
        sentinel = self.home / '.claude-epic/settings.json'
        sentinel.write_text('{"existing":"keep"}')
        self.fake('claude-gateway', 'exit 99')
        result = self.run_script('epic/.local/bin/epic-ai-setup')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(sentinel.read_text())['existing'], 'keep')
        self.assertEqual(json.loads(sentinel.read_text())['permissions']['defaultMode'], 'acceptEdits')
        self.assertFalse((self.home / '.claude').exists())

    def library(self, script):
        return subprocess.run(['bash', '--noprofile', '--norc', '-c',
            'set -euo pipefail; source "' + str(REPO / 'scripts/bootstrap-tools.sh') + '"; ' + script],
            env=self.env, text=True, capture_output=True)

    def test_sidebar_failed_build_preserves_existing_checkout(self):
        target = self.home / '.local/share/tmux/plugins/tmux-agent-sidebar'
        (target / '.git').mkdir(parents=True)
        sentinel = target / 'user-file'
        sentinel.write_text('keep me')
        self.fake('git', 'case "$*" in *"remote get-url origin") echo https://github.com/hiroppy/tmux-agent-sidebar.git ;; *"status --porcelain"*) ;; *"rev-parse HEAD") echo d89fe2025cd3f7149b0c8af9d48f15eab5fc2a3a ;; *) exit 98 ;; esac')
        result = self.run_script('scripts/install-tmux-plugins')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(sentinel.exists(), 'failed build removed existing user checkout')

    def test_partial_epic_setup_fails_before_downloading(self):
        self.wsl()
        lib = self.home / '.config/dotfiles/shell/epic.bash'
        lib.parent.mkdir(parents=True)
        lib.symlink_to(REPO / 'epic/.config/dotfiles/shell/epic.bash')
        profile = self.home / '.claude-epic'
        profile.mkdir()
        (profile / 'settings.json').write_text('keep')
        result = self.run_script('epic/.local/bin/epic-ai-setup')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Partial', result.stderr)
        self.assertNotIn('unexpected external operation', result.stderr)
        self.assertEqual((profile / 'settings.json').read_text(), 'keep')

    def test_no_daemon_inside_one_argument_is_not_an_existing_flag(self):
        self.wsl()
        self.agent('codex')
        self.env['TMUX'] = 'fake'
        result = self.shell("codex 'explain --no-daemon please'")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['args'], ['--no-daemon', 'explain --no-daemon please'])

    def test_custom_workspace_symlink_resolves_and_scrubs_codex(self):
        self.wsl()
        self.agent('codex')
        self.configured()
        work = self.home / 'custom work'
        work.mkdir()
        alias = self.home / 'work alias'
        alias.symlink_to(work, target_is_directory=True)
        self.env.update(EPIC_WORKSPACE=str(alias), OPENAI_BASE_URL='wrong', OPENAI_API_KEY='wrong',
                        CLAUDE_CODE_OAUTH_TOKEN='wrong', CODEX_SQLITE_HOME='/wrong')
        result = self.shell('codex', work)
        self.assertEqual(result.returncode, 0, result.stderr)
        env = json.loads(result.stdout)['env']
        self.assertEqual(env['CODEX_HOME'], str(self.home / '.codex-epic'))
        for name in ('OPENAI_BASE_URL', 'OPENAI_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN', 'CODEX_SQLITE_HOME'):
            self.assertNotIn(name, env)

    def test_rust_existing_stable_does_not_update_or_change_default(self):
        self.fake('rustup', 'case "$*" in "toolchain list") echo "stable-x86_64-unknown-linux-gnu (default)" ;; "component list --toolchain stable --installed") printf "%s\\n" rustfmt-x86_64-unknown-linux-gnu clippy-x86_64-unknown-linux-gnu ;; *) echo "unexpected rustup mutation" >&2; exit 99 ;; esac')
        result = self.library('bootstrap_rust')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_epic_local_preserves_kubeconfig_and_git_identity(self):
        self.wsl()
        (self.home / '.kube').mkdir()
        (self.home / '.kube/config').write_text('PRIVATE KUBECONFIG')
        (self.home / '.gitconfig.local').write_text('[user]\n name = Existing Person\n')
        windows = self.root / 'Windows User'
        (windows / '.kube').mkdir(parents=True)
        (windows / '.kube/config').write_text('PRIVATE WINDOWS KUBECONFIG')
        self.fake('cmd.exe', "/usr/bin/python3 -c 'import sys; sys.stdout.buffer.write(\"C:\\\\Users\\\\Windows User\\r\\n\".encode(\"utf-16le\" if \"/u\" in [a.lower() for a in sys.argv] else \"cp850\"))' \"$@\"")
        self.fake('wslpath', 'echo "' + str(windows) + '"')
        for iteration in range(2):
            result = self.library('bootstrap_epic_local')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('PRIVATE', result.stdout + result.stderr)
        self.assertEqual((self.home / '.kube/config').read_text(), 'PRIVATE KUBECONFIG')
        git = (self.home / '.gitconfig.local').read_text()
        self.assertEqual(git, '[user]\n name = Existing Person\n')
        self.assertFalse((self.home / '.claude-epic').exists())

    def test_epic_bootstrap_does_not_create_a_personal_git_config(self):
        self.fake('cmd.exe', 'exit 1')
        result = self.library('bootstrap_epic_local')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.home / '.gitconfig.local').exists())

    def test_epic_bootstrap_removes_only_its_legacy_personal_include_with_backup(self):
        self.fake('cmd.exe', 'exit 1')
        local = self.home / '.gitconfig.local'
        personal = '[user]\n name = Personal Person\n[include]\n path = ~/private-git.conf\n'
        original = personal + '\n# Optional WSL Epic workspace\n[include]\n    path = ~/.config/dotfiles/git-epic-include.conf\n'
        local.write_text(original)
        for _ in range(2):
            result = self.library('bootstrap_epic_local')
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(local.read_text(), personal)
        backups = list(self.home.glob('.gitconfig.local.before-epic-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)

    def test_epic_bootstrap_preserves_symlinked_personal_git_config(self):
        self.fake('cmd.exe', 'exit 1')
        target = self.home / 'private-git.conf'
        original = '[user]\n name = Personal Person\n\n# Optional WSL Epic workspace\n[include]\n    path = ~/.config/dotfiles/git-epic-include.conf\n'
        target.write_text(original)
        local = self.home / '.gitconfig.local'
        local.symlink_to(target)
        result = self.library('bootstrap_epic_local')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(local.is_symlink())
        self.assertEqual(target.read_text(), original)

    def test_opted_in_epic_bootstrap_creates_workspace_without_agent_homes(self):
        self.fake('cmd.exe', 'exit 1')
        result = self.library('bootstrap_epic_local')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / 'dev/epic').is_dir())
        for directory in ('.claude', '.codex', '.claude-epic', '.codex-epic'):
            self.assertFalse((self.home / directory).exists())

    def test_epic_bootstrap_creates_only_the_configured_workspace(self):
        self.fake('cmd.exe', 'exit 1')
        workspace = self.home / 'work projects/Epic'
        self.env['EPIC_WORKSPACE'] = str(workspace)
        result = self.library('bootstrap_epic_local')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(workspace.is_dir())
        self.assertFalse((self.home / 'dev/epic').exists())

    def real_git(self, cwd, *args, input=None):
        # Ignore inherited Git author/config overrides and the machine's Git
        # configuration. Only these temporary local profiles participate.
        env = {key: value for key, value in self.env.items()
               if not key.startswith('GIT_') and key != 'EMAIL'}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=str(self.home / '.gitconfig'),
                   GIT_TERMINAL_PROMPT='0', GIT_ASKPASS='/bin/false', SSH_ASKPASS='/bin/false')
        return subprocess.run(['/usr/bin/git', '-C', str(cwd), *args], input=input,
                              env=env, text=True, capture_output=True)

    def epic_git_fixture(self):
        self.wsl()
        self.fake('cmd.exe', 'exit 1')
        (self.home / '.gitconfig.local').write_text(
            '[user]\n name = Personal Person\n email = personal@example.test\n')
        result = self.library('bootstrap_epic_local')
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.home / '.config/dotfiles'
        self.install_epic_profile_fixture()
        with (config / 'git-epic.local').open('a') as stream:
            stream.write('[user]\n name = Work Person\n email = work@example.test\n')
        gateway = self.home / '.local/bin/claude-gateway'
        gateway.parent.mkdir(parents=True, exist_ok=True)
        gateway.write_text('#!/bin/bash\n'
                           '[[ $1 == credential-helper && $2 == get ]] || exit 98\n'
                           'cat >/dev/null\n'
                           '/usr/bin/python3 -c \'import json,os; from pathlib import Path; keys = '
                           '["CLAUDE_CONFIG_DIR", "CODEX_HOME", "CLAUDE_GATEWAY_USER_CONFIG_FILE", '
                           '"CLAUDE_GATEWAY_CODEX_USER_CONFIG_FILE", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", '
                           '"CLAUDE_GATEWAY_CONFIG_OVERRIDES"]; Path(os.environ["HOME"] + "/gateway-env.json")'
                           '.write_text(json.dumps({key:os.environ[key] for key in keys if key in os.environ}))\'\n'
                           'printf called >> "$HOME/gateway-calls"\n'
                           'printf "username=work-fixture\\npassword=fixture-only\\n"\n')
        gateway.chmod(0o755)

    def install_epic_profile_fixture(self):
        spec = importlib.util.spec_from_file_location('bootstrap_test_installer', REPO / 'scripts/install.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with contextlib.redirect_stdout(io.StringIO()):
            operations = installer.plan_install(self.home, 'wsl', epic=True)
            installer.apply_plan(self.home, operations)

    def test_personal_identity_set_after_epic_setup_cannot_override_work_identity(self):
        self.fake('cmd.exe', 'exit 1')
        self.install_epic_profile_fixture()
        result = self.library('bootstrap_epic_local')
        self.assertEqual(result.returncode, 0, result.stderr)
        for path, name, email in (('.gitconfig.local', 'Personal Person', 'personal@example.test'),
                ('.config/dotfiles/git-epic.local', 'Work Person', 'work@example.test')):
            for key, value in (('user.name', name), ('user.email', email)):
                configured = self.real_git(self.home, 'config', '--file', str(self.home / path), key, value)
                self.assertEqual(configured.returncode, 0, configured.stderr)
        for relative, email in (('dev/epic/project', 'work@example.test'),
                                ('dev/personal/project', 'personal@example.test'),
                                ('dev/epic-other/project', 'personal@example.test')):
            with self.subTest(repo=relative):
                repo = self.home / relative
                repo.mkdir(parents=True)
                initialized = self.real_git(repo, 'init', '-q')
                self.assertEqual(initialized.returncode, 0, initialized.stderr)
                identity = self.real_git(repo, 'config', '--get', 'user.email')
                self.assertEqual(identity.returncode, 0, identity.stderr)
                self.assertEqual(identity.stdout.strip(), email)

    def install_git_helper_fixture(self):
        shell = self.home / '.config/dotfiles/shell/epic.bash'
        shell.parent.mkdir(parents=True, exist_ok=True)
        shell.symlink_to(REPO / 'epic/.config/dotfiles/shell/epic.bash')
        helper = self.home / '.local/bin/epic-git-credential'
        helper.parent.mkdir(parents=True, exist_ok=True)
        helper.symlink_to(REPO / 'epic/.local/bin/epic-git-credential')

    def test_git_identity_rewrite_and_credentials_are_scoped_to_epic_repositories(self):
        self.epic_git_fixture()
        self.env.update(OPENAI_API_KEY='wrong', ANTHROPIC_API_KEY='wrong',
                        CLAUDE_GATEWAY_CONFIG_OVERRIDES='wrong', CLAUDE_CONFIG_DIR='/wrong',
                        CLAUDE_GATEWAY_USER_CONFIG_FILE='/wrong', CODEX_HOME='/wrong',
                        CLAUDE_GATEWAY_CODEX_USER_CONFIG_FILE='/wrong')
        for relative, work in (('dev/epic', True), ('dev/epic/team/project', True),
                               ('dev/epic-other/project', False), ('dev/personal/project', False)):
            repo = self.home / relative
            repo.mkdir(parents=True, exist_ok=True)
            with self.subTest(repo=relative):
                initialized = self.real_git(repo, 'init', '-q')
                self.assertEqual(initialized.returncode, 0, initialized.stderr)
                identity = self.real_git(repo, 'var', 'GIT_AUTHOR_IDENT')
                self.assertEqual(identity.returncode, 0, identity.stderr)
                self.assertTrue(identity.stdout.startswith(
                    'Work Person <work@example.test> ' if work else 'Personal Person <personal@example.test> '),
                    identity.stdout)
                remote = self.real_git(repo, 'remote', 'add', 'origin',
                                       'https://github.ol.epicgames.net/team/project.git')
                self.assertEqual(remote.returncode, 0, remote.stderr)
                url = self.real_git(repo, 'remote', 'get-url', 'origin')
                self.assertEqual(url.returncode, 0, url.stderr)
                self.assertEqual(url.stdout.strip(), 'git@github.ol.epicgames.net:team/project.git' if work
                                 else 'https://github.ol.epicgames.net/team/project.git')
                marker = self.home / 'gateway-calls'
                marker.unlink(missing_ok=True)
                credentials = self.real_git(repo, 'credential', 'fill',
                    input='protocol=https\nhost=live.roost.on.epicgames.com\n\n')
                self.assertEqual(credentials.returncode == 0, work, credentials.stderr)
                self.assertEqual(marker.exists(), work)
                if work:
                    self.assertIn('username=work-fixture', credentials.stdout)
                    self.assertEqual(marker.read_text(), 'called')
                    gateway_env = json.loads((self.home / 'gateway-env.json').read_text())
                    self.assertEqual(gateway_env, {
                        'CLAUDE_CONFIG_DIR': str(self.home / '.claude-epic'),
                        'CODEX_HOME': str(self.home / '.codex-epic'),
                        'CLAUDE_GATEWAY_USER_CONFIG_FILE': str(self.home / '.claude-epic/gateway-helper-config.json'),
                        'CLAUDE_GATEWAY_CODEX_USER_CONFIG_FILE': str(self.home / '.codex-epic/claude-gateway.json')})
                marker.unlink(missing_ok=True)
                unrelated = self.real_git(repo, 'credential', 'fill',
                    input='protocol=https\nhost=github.com\n\n')
                self.assertNotEqual(unrelated.returncode, 0)
                self.assertFalse(marker.exists(), 'enterprise helper ran for an unrelated host')

    def runtime_fixture(self):
        # Keep the process boundary offline; the real bootstrap chooses which
        # tools to install, which config to update, and whether to activate it.
        (self.bin / 'mise').write_bytes((REPO / 'tests/fixtures/mise-runtime.py').read_bytes())
        for tool in ('claude', 'codex', 'gh', 'starship', 'zoxide', 'eza', 'lazygit'):
            self.fake(tool, 'exit 0')
        self.fake('node', 'echo v26.8.2')
        self.fake('pnpm', 'echo 12.11.2')
        self.fake('dotnet', 'echo "8.0.422 [/custom/sdk]"')

    def runtime_calls(self):
        path = self.home / '.test-mise/calls.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_old_node_and_pnpm_are_upgraded_and_available_immediately(self):
        self.runtime_fixture()
        self.fake('node', 'echo v24.0.0')
        self.fake('pnpm', 'echo 11.0.0')
        config = self.home / '.config/mise/config.toml'
        config.parent.mkdir(parents=True)
        original = '[tools]\nnode = "24"\npnpm = "11"\npython = "3.13"\n'
        config.write_text(original)
        result = self.library('bootstrap_mise; bootstrap_mise; node --version; pnpm --version')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('v26.8.2', result.stdout)
        self.assertIn('12.11.2', result.stdout)
        self.assertIn('python = "3.13"', config.read_text())
        backups = list(config.parent.glob('config.toml.before-dotfiles.*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
        self.assertIn(['use', '--path', str(config), '--pin', 'node@26.8.2', 'pnpm@12.11.2',
                       'claude@latest', 'codex@latest'], self.runtime_calls())
        self.assertIn(['use', '--path', str(config), '--pin', 'claude@latest', 'codex@latest'], self.runtime_calls())
        self.assertEqual(sum(call[0] == 'use' for call in self.runtime_calls()), 2)

    def test_compatible_newer_node_is_preserved_when_pnpm_needs_upgrade(self):
        self.runtime_fixture()
        self.fake('node', 'echo v28.1.0')
        self.fake('pnpm', 'echo 11.0.0')
        result = self.library('bootstrap_mise; node --version; pnpm --version')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('v28.1.0', result.stdout)
        self.assertIn('12.11.2', result.stdout)
        requests = [arg for call in self.runtime_calls() if call[0] == 'use' for arg in call if '@' in arg]
        self.assertEqual(requests, ['pnpm@12.11.2', 'claude@latest', 'codex@latest'])

    def test_existing_ai_clis_become_latest_global_mise_defaults_without_account_changes(self):
        self.runtime_fixture()
        old_binaries = {}
        for tool in ('claude', 'codex'):
            self.fake(tool, 'echo old-standalone-client')
            old_binaries[tool] = (self.bin / tool).read_bytes()
        config = self.home / '.config/mise/config.toml'
        config.parent.mkdir(parents=True)
        original = '[tools]\nclaude = "1.0.0"\ncodex = "0.1.0"\npython = "3.13"\n[settings]\nexperimental = true\n'
        config.write_text(original)
        project = self.home / 'project'
        project.mkdir()
        project_config = project / 'mise.toml'
        project_config.write_text('[tools]\nnode = "22"\n')
        personal = self.home / '.codex/auth.json'
        personal.parent.mkdir()
        personal.write_text('private fixture')
        result = self.library('cd ' + shlex.quote(str(project)) +
                              '; bootstrap_mise; claude --version; codex --version')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('2.7.4', result.stdout)
        self.assertIn('0.167.0', result.stdout)
        selected = tomllib.loads(config.read_text())
        self.assertEqual(selected['tools'], {'claude': '2.7.4', 'codex': '0.167.0', 'python': '3.13'})
        self.assertTrue(selected['settings']['experimental'])
        self.assertEqual(project_config.read_text(), '[tools]\nnode = "22"\n')
        self.assertEqual(personal.read_text(), 'private fixture')
        backups = list(config.parent.glob('config.toml.before-dotfiles.*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)
        for tool, content in old_binaries.items():
            self.assertEqual((self.bin / tool).read_bytes(), content)
        self.assertFalse((config.parent / 'conf.d/dotfiles.toml').exists())

    def test_ai_update_failure_stops_bootstrap_with_supported_runtimes(self):
        self.runtime_fixture()
        self.env['FAKE_MISE_FAIL'] = '1'
        result = self.library('bootstrap_mise; echo SHOULD_NOT_CONTINUE')
        self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
        self.assertNotIn('SHOULD_NOT_CONTINUE', result.stdout)
        self.assertFalse(any(call[0] == 'env' for call in self.runtime_calls()))

    def test_explicit_refresh_gets_fresh_releases_and_preserves_other_policies(self):
        self.runtime_fixture()
        self.env['FAKE_MISE_REQUIRE_FRESH'] = '1'
        config = self.home / '.config/mise/config.toml'
        config.parent.mkdir(parents=True)
        original = ('[tools]\npython = "3.13"\n[settings]\nminimum_release_age = "7d"\n'
                    'minimum_release_age_excludes = ["python", "claude"]\n')
        config.write_text(original)
        for tool in ('claude', 'codex', 'neovim', 'python', 'github'):
            cached = Path(self.env['MISE_CACHE_DIR']) / tool / 'stale-versions'
            cached.parent.mkdir(parents=True)
            cached.write_text('cached release list')
        project = self.home / 'project'
        project.mkdir()
        pinned = project / 'mise.toml'
        pinned.write_text('[tools]\nclaude = "1.0.0"\nneovim = "0.11.2"\n')
        result = self.library('cd ' + shlex.quote(str(project)) +
                              '; bootstrap_mise wsl; bootstrap_neovim wsl; bootstrap_mise wsl; '
                              'claude --version; codex --version; nvim --version')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('2.7.4', result.stdout)
        self.assertIn('0.167.0', result.stdout)
        self.assertIn('NVIM v0.12.7', result.stdout)
        selected = tomllib.loads(config.read_text())
        self.assertEqual(selected['settings']['minimum_release_age'], '7d')
        self.assertEqual(selected['settings']['minimum_release_age_excludes'], ['python', 'claude', 'codex', 'neovim'])
        self.assertEqual(selected['tools']['python'], '3.13')
        self.assertNotIn('use_versions_host', selected['settings'])
        self.assertEqual(pinned.read_text(), '[tools]\nclaude = "1.0.0"\nneovim = "0.11.2"\n')
        for tool in ('claude', 'codex', 'neovim', 'python', 'github'):
            self.assertTrue((Path(self.env['MISE_CACHE_DIR']) / tool / 'stale-versions').exists())
        self.assertEqual(list(config.parent.glob('config.toml.before-dotfiles.*'))[0].read_text(), original)
        invocations = [json.loads(line) for line in (self.home / '.test-mise/invocations.jsonl').read_text().splitlines()]
        for invocation in invocations:
            if invocation['args'][0] in ('env', 'reshim'):
                self.assertIsNone(invocation['versions_host'])
                self.assertEqual(invocation['cache_dir'], self.env['MISE_CACHE_DIR'])
            elif invocation['args'][0] == 'use':
                self.assertNotEqual(invocation['cache_dir'], self.env['MISE_CACHE_DIR'])
                self.assertFalse(Path(invocation['cache_dir']).exists(), 'Temporary resolution cache leaked')

    def test_refresh_honors_custom_global_config_without_touching_default(self):
        self.runtime_fixture()
        self.env.update(MISE_CONFIG_DIR=str(self.home / 'custom mise'),
                        MISE_GLOBAL_CONFIG_FILE=str(self.home / 'custom global.toml'))
        custom = Path(self.env['MISE_GLOBAL_CONFIG_FILE'])
        custom.write_text('[settings]\nminimum_release_age_excludes = ["ruby"]\n')
        result = self.library('bootstrap_mise wsl')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(tomllib.loads(custom.read_text())['settings']['minimum_release_age_excludes'],
                         ['ruby', 'claude', 'codex', 'neovim'])
        self.assertFalse((self.home / '.config/mise').exists())

    def test_failed_freshness_policy_stops_before_any_install(self):
        self.runtime_fixture()
        self.env['FAKE_MISE_SETTINGS_FAIL'] = '1'
        result = self.library('bootstrap_mise wsl; echo SHOULD_NOT_CONTINUE')
        self.assertEqual(result.returncode, 45, result.stdout + result.stderr)
        self.assertNotIn('SHOULD_NOT_CONTINUE', result.stdout)
        self.assertFalse(any(call[0] == 'use' for call in self.runtime_calls()))

    def test_failed_latest_install_cleans_temporary_cache_and_preserves_stale_cache(self):
        self.runtime_fixture()
        self.env['FAKE_MISE_FAIL'] = '1'
        cached = Path(self.env['MISE_CACHE_DIR']) / 'github/stale-versions'
        cached.parent.mkdir(parents=True)
        cached.write_text('cached release list')
        result = self.library('bootstrap_mise wsl; echo SHOULD_NOT_CONTINUE')
        self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
        self.assertNotIn('SHOULD_NOT_CONTINUE', result.stdout)
        invocations = [json.loads(line) for line in (self.home / '.test-mise/invocations.jsonl').read_text().splitlines()]
        installs = [call for call in invocations if call['args'][0] == 'use']
        self.assertEqual(len(installs), 1)
        self.assertNotEqual(installs[0]['cache_dir'], self.env['MISE_CACHE_DIR'])
        self.assertFalse(Path(installs[0]['cache_dir']).exists(), 'Failed install leaked temporary cache')
        self.assertEqual(cached.read_text(), 'cached release list')

    def test_wsl_rejects_latest_neovim_below_plugin_floor(self):
        self.runtime_fixture()
        self.env['FAKE_MISE_NVIM_LATEST'] = '0.11.9'
        result = self.library('bootstrap_mise wsl; bootstrap_neovim wsl; echo SHOULD_NOT_CONTINUE')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('>=0.12.0', result.stderr)
        self.assertNotIn('SHOULD_NOT_CONTINUE', result.stdout)

    def test_fresh_runtime_setup_installs_all_three_without_manual_prerequisites(self):
        self.runtime_fixture()
        for tool in ('node', 'pnpm', 'dotnet'):
            (self.bin / tool).unlink()
        # Give this process ordinary shell utilities but no distro runtimes.
        for tool in ('bash', 'sort', 'head', 'mkdir', 'mktemp', 'cp', 'cmp', 'rm', 'readlink'):
            (self.bin / tool).symlink_to('/usr/bin/' + tool)
        self.env['PATH'] = str(self.bin)
        result = self.library('bootstrap_mise; node --version; pnpm --version; dotnet --list-sdks; claude --version; codex --version')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('v26.8.2', result.stdout)
        self.assertIn('12.11.2', result.stdout)
        self.assertIn('10.0.100', result.stdout)
        self.assertIn('2.7.4', result.stdout)
        self.assertIn('0.167.0', result.stdout)

    def test_fresh_setup_also_installs_mise_when_missing(self):
        self.runtime_fixture()
        binary = self.root / 'mise-binary'
        (self.bin / 'mise').replace(binary)
        for tool in ('node', 'pnpm', 'dotnet'):
            (self.bin / tool).unlink()
        for tool in ('bash', 'sort', 'head', 'mkdir', 'mktemp', 'cp', 'cmp', 'rm', 'readlink'):
            (self.bin / tool).symlink_to('/usr/bin/' + tool)
        local_bin = self.home / '.local/bin'
        local_bin.mkdir(parents=True)
        self.env['PATH'] = str(local_bin) + ':' + str(self.bin)
        self.env['MISE_BINARY_FIXTURE'] = str(binary)
        installer = self.root / 'install-mise.sh'
        installer.write_text('#!/bin/bash\ncp -- "$MISE_BINARY_FIXTURE" "$MISE_INSTALL_PATH"\n')
        self.env['MISE_INSTALLER_FIXTURE'] = str(installer)
        self.fake('curl', 'cp -- "$MISE_INSTALLER_FIXTURE" "${@: -1}"')
        result = self.library('bootstrap_stage=' + shlex.quote(str(self.root)) +
                              '; bootstrap_mise; node --version; pnpm --version; dotnet --list-sdks')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((local_bin / 'mise').is_file())
        self.assertIn('v26.8.2', result.stdout)
        self.assertIn('12.11.2', result.stdout)
        self.assertIn('10.0.100', result.stdout)

    def test_runtime_install_failure_stops_before_environment_activation(self):
        self.runtime_fixture()
        self.fake('node', 'echo v24.0.0')
        self.env['FAKE_MISE_FAIL'] = '1'
        result = self.library('bootstrap_mise; echo SHOULD_NOT_CONTINUE')
        self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
        self.assertNotIn('SHOULD_NOT_CONTINUE', result.stdout)
        self.assertFalse(any(call[0] == 'env' for call in self.runtime_calls()))

    def test_checkout_local_sdk_does_not_hide_missing_global_sdk(self):
        self.runtime_fixture()
        self.env['CHECKOUT_DIRECTORY'] = os.getcwd()
        self.fake('dotnet', 'if [[ $PWD == "$CHECKOUT_DIRECTORY" ]]; then echo "10.0.100 [/checkout/sdk]"; fi')
        result = self.library('bootstrap_mise; cd /; dotnet --list-sdks')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('10.0.100 [/fixture/sdk]', result.stdout)

    def test_inherited_project_sdk_path_gets_a_persistent_global_default(self):
        self.runtime_fixture()
        project_bin = self.home / '.local/share/mise/dotnet-root'
        project_bin.mkdir(parents=True)
        binary = project_bin / 'dotnet'
        binary.write_text('#!/bin/bash\necho "10.0.100 [/project/sdk]"\n')
        binary.chmod(0o755)
        self.env['PATH'] = str(project_bin) + ':' + self.env['PATH']
        result = self.library('bootstrap_mise; cd /; dotnet --list-sdks')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('10.0.100 [/fixture/sdk]', result.stdout)
        config = self.home / '.config/mise/config.toml'
        self.assertIn('dotnet = "10.0.100"', config.read_text())

    def test_mise_environment_failure_is_not_silently_ignored(self):
        self.runtime_fixture()
        self.fake('node', 'echo v24.0.0')
        self.env['FAKE_MISE_ENV_FAIL'] = '1'
        result = self.library('bootstrap_mise; echo SHOULD_NOT_CONTINUE')
        self.assertEqual(result.returncode, 43, result.stdout + result.stderr)
        self.assertNotIn('SHOULD_NOT_CONTINUE', result.stdout)

    def test_editor_asset_failure_is_propagated(self):
        self.fake('nvim', 'echo "plugin installation failed" >&2; exit 31')
        result = self.library('bootstrap_stage=' + shlex.quote(str(self.root)) + '; bootstrap_editor_assets')
        self.assertEqual(result.returncode, 31, result.stderr)
        self.assertIn('plugin installation failed', result.stderr)

    def test_bootstrap_failure_cleans_staging_after_function_scope_ends(self):
        stage = self.root / "staging ' with spaces"
        stage.mkdir()
        self.env['FIXTURE_STAGE'] = str(stage)
        fake_repo = self.root / 'repo'
        (fake_repo / 'scripts').mkdir(parents=True)
        for path in ('scripts/install-tmux-plugins', 'scripts/install-fonts.sh', 'install'):
            script = fake_repo / path
            script.write_text('#!/bin/bash\nexit 0\n')
            script.chmod(0o755)
        result = self.library('''
repo=''' + shlex.quote(str(fake_repo)) + '''
mktemp() { printf '%s\\n' "$FIXTURE_STAGE"; }
omarchy() { :; }
bootstrap_packages() { :; }
bootstrap_alias_commands() { :; }
bootstrap_rust() { :; }
bootstrap_mise() { :; }
bootstrap_neovim() { :; }
bootstrap_tmux() { :; }
bootstrap_editor_assets() { return 37; }
bootstrap_main --profile omarchy
''')
        self.assertEqual(result.returncode, 37, result.stdout + result.stderr)
        self.assertNotIn('unbound variable', result.stderr)
        self.assertFalse(stage.exists(), 'EXIT cleanup lost its function-local staging path')

    def dispatcher_fixture(self):
        shell = self.home / '.config/dotfiles/shell'
        shell.mkdir(parents=True, exist_ok=True)
        for name in ('agents.bash', 'epic.bash'):
            package = 'epic' if name == 'epic.bash' else 'common'
            (shell / name).symlink_to(REPO / package / '.config/dotfiles/shell' / name)
        (shell.parent / 'epic.enabled').write_text('enabled')
        binary = self.home / '.local/bin'
        binary.mkdir(parents=True)
        (binary / 'dotfiles-agent').symlink_to(REPO / 'common/.local/bin/dotfiles-agent')

    def subprocess_agent(self, agent='codex', cwd=None, args=()):
        command = '"$HOME/.local/bin/dotfiles-agent" ' + shlex.join([agent, *args])
        return subprocess.run(['/bin/sh', '-c', command], env=self.env, cwd=cwd or self.home,
                              text=True, capture_output=True)

    def test_gh_launches_use_isolated_dispatch_from_posix_shell(self):
        self.wsl()
        self.agent('codex')
        self.configured()
        self.dispatcher_fixture()
        work = self.home / 'dev/epic/project'
        work.mkdir(parents=True)
        launches = [line.strip() for line in (REPO / 'gh/.config/gh/config.yml').read_text().splitlines()
                    if '--full-auto --search "$prompt"' in line]
        self.assertEqual(len(launches), 2)
        for launch in launches:
            result = subprocess.run(['/bin/sh', '-c', 'prompt="fixture issue"; ' + launch],
                                    env=self.env, cwd=work, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['env'].get('CODEX_HOME', 'PERSONAL_DEFAULT'), str(self.home / '.codex-epic'))
            self.assertEqual(payload['args'], ['--full-auto', '--search', 'fixture issue'])

    def test_dispatcher_gates_accounts_and_scrubs_both_directions(self):
        self.wsl()
        self.configured()
        self.dispatcher_fixture()
        for agent in ('claude', 'codex'):
            self.agent(agent)
        work = self.home / 'dev/epic'
        other = self.home / 'dev/epic-other'
        work.mkdir(parents=True)
        other.mkdir()
        alias = self.home / 'work alias'
        alias.symlink_to(work, target_is_directory=True)
        self.env.update(OPENAI_API_KEY='wrong', ANTHROPIC_API_KEY='wrong', CODEX_HOME='/wrong',
                        CLAUDE_GATEWAY_CONFIG_OVERRIDES='wrong', AWS_BEARER_TOKEN_BEDROCK='wrong', TMUX='fixture')
        for agent in ('claude', 'codex'):
            for cwd, profile in ((work, 'epic'), (alias, 'epic'), (other, 'personal')):
                with self.subTest(agent=agent, cwd=cwd):
                    result = self.subprocess_agent(agent, cwd, ['--no-daemon', 'hello'] if agent == 'codex' else ['hello'])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    payload = json.loads(result.stdout)
                    env = payload['env']
                    self.assertEqual(env['CODEX_HOME'], str(self.home / ('.codex-epic' if profile == 'epic' else '.codex')))
                    for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'CLAUDE_GATEWAY_CONFIG_OVERRIDES', 'AWS_BEARER_TOKEN_BEDROCK'):
                        self.assertNotIn(key, env)
                    if agent == 'codex':
                        self.assertEqual(payload['args'], ['--no-daemon', 'hello'])
        result = self.subprocess_agent('codex', work, ['hello'])
        self.assertEqual(json.loads(result.stdout)['args'], ['--no-daemon', 'hello'])
        (self.home / '.codex-epic/config.toml').unlink()
        result = self.subprocess_agent('codex', work)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('epic-ai-setup', result.stderr)
        self.assertEqual(result.stdout, '')
        (self.home / '.config/dotfiles/epic.enabled').unlink()
        result = self.subprocess_agent('codex', work)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['env']['CODEX_HOME'], '/wrong')
        (self.home / '.config/dotfiles/epic.enabled').write_text('enabled')
        self.fake('uname', 'echo Linux')
        self.env.pop('WSL_DISTRO_NAME', None)
        result = self.subprocess_agent('codex', work)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['env']['CODEX_HOME'], '/wrong')
        result = self.subprocess_agent('bash', work)
        self.assertNotEqual(result.returncode, 0)

    def real_editor(self, preload=''):
        if not Path('/usr/bin/nvim').is_file():
            self.skipTest('real Neovim unavailable')
        for key, suffix in (('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'),
                            ('XDG_STATE_HOME', 'state'), ('XDG_CACHE_HOME', 'cache')):
            self.env[key] = str(self.root / suffix)
        self.fake('nvim', 'exec /usr/bin/nvim --clean ' + (('--cmd ' + shlex.quote('lua dofile(' + repr(preload) + ')')) if preload else '') + ' "$@"')

    def editor_run(self):
        return self.library('bootstrap_stage=' + shlex.quote(str(self.root)) +
                            '; bootstrap_editor_assets; echo SUCCESS_SENTINEL')

    def test_real_neovim_missing_lazy_fails_before_success(self):
        self.real_editor()
        result = self.editor_run()
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('SUCCESS_SENTINEL', result.stdout)

    def test_real_neovim_restore_tasks_and_mason_failures_stop_success(self):
        base = """
local real_wait = vim.wait
vim.wait = function(ms, ...) return real_wait(math.min(ms, 100), ...) end
vim.g.lazy_did_setup = true
vim.api.nvim_create_user_command('Lazy', function() end, {bang=true, nargs='*'})
local task = {has_errors=function() return false end}
local plugin = {name='fixture', _={tasks={task}}}
local plugins = {fixture=plugin, ['mason.nvim']={}}
package.preload['lazy.core.config'] = function() return {plugins=plugins} end
package.preload['lazy.manage'] = function() return {restore=function()
  return {_plugins={fixture=plugin}, wait=function() RESTORE_WAIT end}
end} end
package.preload['lazy.core.plugin'] = function() return {values=function() return {ensure_installed={'fixture'}} end} end
package.preload['mason-registry'] = function() return {refresh=function(cb) cb(true) end, get_package=function() return {is_installed=function() return true end} end} end
"""
        cases = {
            'restore task error': ("task.has_errors=function() return true end", '', 'Lazy restore failed for fixture'),
            'missing Mason registry': ('', "package.preload['mason-registry']=nil", "module 'mason-registry' not found"),
            'missing Mason plugin': ('', "plugins['mason.nvim']=nil", 'Mason plugin is missing'),
            'Mason options failure': ('', "package.preload['lazy.core.plugin']=function() error('fixture options failure') end", 'fixture options failure'),
            'Mason refresh initializer': ('', "package.preload['mason-registry']=function() return {refresh=function() error('fixture refresh failure') end} end", 'fixture refresh failure'),
            'Mason callback failure': ('', "package.preload['mason-registry']=function() return {refresh=function(cb) vim.schedule(cb) end, get_package=function() return {is_installed=function() error('fixture callback failure') end} end} end", 'fixture callback failure'),
            'Mason refresh timeout': ('', "vim.wait=function() return false end; package.preload['mason-registry']=function() return {refresh=function() end} end", '15 minute timeout'),
            'healthy installed dependencies': ('', '', None),
        }
        for name, (wait_body, extra, expected_error) in cases.items():
            with self.subTest(case=name):
                preload = self.root / 'preload.lua'
                preload.write_text(base.replace('RESTORE_WAIT', wait_body) + extra)
                self.real_editor(str(preload))
                result = self.editor_run()
                if expected_error:
                    self.assertNotEqual(result.returncode, 0, result.stderr)
                    self.assertIn(expected_error, result.stderr)
                    self.assertNotIn('SUCCESS_SENTINEL', result.stdout)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('SUCCESS_SENTINEL', result.stdout)
                    self.assertIn('Mason language tools installed', result.stdout + result.stderr)

    def test_editor_restore_does_not_exit_with_mason_install_in_flight(self):
        aborted = self.root / 'package-aborted'
        finished = self.root / 'package-installed'
        starts = self.root / 'package-starts'
        self.env.update(PACKAGE_ABORTED=str(aborted), PACKAGE_INSTALLED=str(finished),
                        PACKAGE_STARTS=str(starts))
        preload = self.root / 'preload.lua'
        preload.write_text('''
vim.g.lazy_did_setup = true
local installing, installed = false, false
local callbacks = {}
local function start()
  assert(not installing, 'Installer was started twice')
  installing = true
  vim.fn.writefile({'started'}, vim.env.PACKAGE_STARTS, 'a')
  vim.defer_fn(function()
    installing, installed = false, true
    vim.fn.writefile({'installed'}, vim.env.PACKAGE_INSTALLED)
    if callbacks['install:success'] then callbacks['install:success']() end
  end, 200)
end
vim.api.nvim_create_autocmd('VimLeavePre', {callback=function()
  if installing then vim.fn.writefile({'aborted'}, vim.env.PACKAGE_ABORTED) end
end})
package.preload['lazy.core.config'] = function() return {plugins={['mason.nvim']={}}} end
package.preload['lazy.manage'] = function() return {restore=function()
  -- LazyVim's Mason configuration starts installs during plugin restoration.
  return {wait=function() start() end}
end} end
package.preload['lazy.core.plugin'] = function() return {values=function()
  return {ensure_installed={'fixture'}}
end} end
package.preload['mason-registry'] = function() return {
  refresh=function(cb) cb(true) end,
  get_package=function() return {
    is_installed=function() return installed end,
    is_installing=function() return installing end,
    once=function(_, event, cb) callbacks[event] = cb end,
    install=start,
  } end,
} end
''')
        self.real_editor(str(preload))
        result = self.editor_run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(aborted.exists(), 'Neovim quit during an active Mason install')
        self.assertTrue(finished.exists(), result.stdout + result.stderr)
        self.assertEqual(starts.read_text().splitlines(), ['started'])
        self.assertIn('SUCCESS_SENTINEL', result.stdout)

    def lazyvim_mason_fixture(self):
        cache = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'nvim/lazy'
        lazy = cache / 'lazy.nvim'
        upstream = cache / 'LazyVim/lua/lazyvim/plugins/lsp/init.lua'
        if not lazy.is_dir() or not upstream.is_file():
            self.skipTest('Cached Lazy/LazyVim needed for real configuration merge')
        self.env['FIXTURE_LAZY'] = str(lazy)
        self.env['FIXTURE_LAZYVIM_LSP'] = str(upstream)
        self.env['FIXTURE_USER_LANGUAGES'] = str(REPO / 'nvim/.config/nvim/lua/plugins/osirion-languages.lua')
        self.env['FIXTURE_INSTALLS'] = str(self.root / 'installs')
        preload = self.root / 'preload.lua'
        preload.write_text('''
vim.opt.rtp:prepend(vim.env.FIXTURE_LAZY)
local packages = {}
local function get_package(name)
  if packages[name] then return packages[name] end
  local installing, installed, callbacks = false, false, {}
  local pkg = {
    is_installed=function() return installed end,
    is_installing=function() return installing end,
    once=function(_, event, cb) callbacks[event] = cb end,
    install=function()
      assert(not installing, 'Package is already installing.')
      installing = true
      vim.fn.writefile({name}, vim.env.FIXTURE_INSTALLS, 'a')
      vim.defer_fn(function()
        installing, installed = false, true
        if callbacks['install:success'] then callbacks['install:success']() end
      end, 500)
    end,
  }
  packages[name] = pkg
  return pkg
end
dotfiles_fixture_done = function()
  for _, pkg in pairs(packages) do
    if not pkg:is_installed() then return false end
  end
  return next(packages) ~= nil
end
package.preload['mason'] = function() return {setup=function() end} end
package.preload['mason-registry'] = function() return {
  refresh=function(cb) cb(true, {}) end, on=function() end, get_package=get_package,
} end
local inherited
for _, spec in ipairs(dofile(vim.env.FIXTURE_LAZYVIM_LSP)) do
  if spec[1] == 'mason-org/mason.nvim' then inherited = spec end
end
assert(inherited, 'Upstream Mason spec missing')
inherited.dir = vim.fn.stdpath('data') .. '/fixture-mason'
vim.fn.mkdir(inherited.dir, 'p')
inherited.lazy, inherited.build, inherited.cmd, inherited.keys = false, nil, nil, nil
require('lazy').setup({
  spec={inherited, dofile(vim.env.FIXTURE_USER_LANGUAGES)[1]},
  install={missing=false}, checker={enabled=false}, change_detection={enabled=false},
  lockfile=vim.fn.stdpath('state') .. '/fixture-lock.json',
})
local config = require('lazy.core.config')
local plugin = assert(config.plugins['mason.nvim'])
local opts = require('lazy.core.plugin').values(plugin, 'opts', false)
-- A real inherited + user configuration merge, re-entered by a plugin build.
require('lazy.manage').restore = function()
  local ok, err = pcall(function() plugin.config(plugin, opts) end)
  config.plugins['nvim-treesitter'] = {_={tasks={{
    has_errors=function() return not ok end, output=function() return tostring(err) end,
  }}}}
  return {wait=function() end}
end
''')
        self.real_editor(str(preload))

    def test_lazyvim_mason_reconfiguration_during_build_does_not_install_twice(self):
        self.lazyvim_mason_fixture()
        result = self.editor_run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        installs = (self.root / 'installs').read_text().splitlines()
        self.assertEqual(len(installs), len(set(installs)), 'A package was installed twice')
        self.assertIn('csharpier', installs)
        self.assertIn('shfmt', installs)
        self.assertNotIn('Package is already installing', result.stdout + result.stderr)
        self.assertIn('SUCCESS_SENTINEL', result.stdout)

    def test_normal_neovim_retains_lazyvim_automatic_mason_installation(self):
        self.lazyvim_mason_fixture()
        result = subprocess.run([
            str(self.bin / 'nvim'), '--headless',
            '+lua assert(vim.wait(3000, dotfiles_fixture_done), "Automatic Mason installs did not finish")',
            '+qa',
        ], env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('Automatic Mason installs did not finish', result.stderr)
        installs = (self.root / 'installs').read_text().splitlines()
        self.assertIn('csharpier', installs)
        self.assertIn('shfmt', installs)
        self.assertEqual(len(installs), len(set(installs)))

    def test_mason_failure_waits_for_other_installs_and_reports_log(self):
        finished = self.root / 'other-package-installed'
        self.env['OTHER_PACKAGE_INSTALLED'] = str(finished)
        preload = self.root / 'preload.lua'
        preload.write_text('''
vim.g.lazy_did_setup = true
package.preload['lazy.core.config'] = function() return {plugins={['mason.nvim']={}}} end
package.preload['lazy.manage'] = function() return {restore=function() return {wait=function() end} end} end
package.preload['lazy.core.plugin'] = function() return {values=function()
  return {ensure_installed={'csharpier', 'yaml-language-server'}}
end} end
package.preload['mason-registry'] = function() return {
  refresh=function(cb) cb(true) end,
  get_package=function(name)
    local callbacks = {}
    return {
      is_installed=function() return false end,
      is_installing=function() return false end,
      once=function(_, event, cb) callbacks[event] = cb end,
      install=function()
        if name == 'csharpier' then
          vim.defer_fn(function() callbacks['install:failed']() end, 10)
        else
          vim.defer_fn(function()
            vim.fn.writefile({'installed'}, vim.env.OTHER_PACKAGE_INSTALLED)
            callbacks['install:success']()
          end, 100)
        end
      end,
    }
  end,
} end
''')
        self.real_editor(str(preload))
        result = self.editor_run()
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertTrue(finished.exists(), result.stdout + result.stderr)
        self.assertIn('csharpier', result.stderr)
        self.assertIn(str(self.root / 'state/nvim/mason.log'), result.stderr)
        self.assertNotIn('SUCCESS_SENTINEL', result.stdout)

    def test_omarchy_bootstrap_provisions_minimal_shortcut_apps_with_cli(self):
        log = self.root / 'packages'
        self.fake('omarchy', 'printf "%s\\n" "$@" > ' + shlex.quote(str(log)))
        self.fake('omarchy-pkg-add', 'echo legacy-command >&2; exit 99')
        result = self.library('bootstrap_packages omarchy')
        self.assertEqual(result.returncode, 0, result.stderr)
        packages = log.read_text().splitlines()
        self.assertEqual(packages[:2], ['pkg', 'add'])
        for package in ('foot', 'brave-bin', 'spotify'):
            self.assertIn(package, packages)

    def test_git_gate_removal_disables_corporate_settings_without_removing_identity(self):
        result = self.library('bootstrap_epic_local')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.install_epic_profile_fixture()
        gate = self.home / '.config/dotfiles/git-epic-include.conf'
        repo = self.home / 'dev/epic/project'
        repo.mkdir(parents=True)
        subprocess.run(['/usr/bin/git', 'init', '-q', str(repo)], env=self.env, check=True)
        enabled = self.real_git(repo, 'config', '--get', 'url.git@github.ol.epicgames.net:.insteadOf')
        self.assertEqual(enabled.returncode, 0, enabled.stderr)
        self.assertEqual(enabled.stdout.strip(), 'https://github.ol.epicgames.net/')
        gate.unlink()
        disabled = self.real_git(repo, 'config', '--get', 'url.git@github.ol.epicgames.net:.insteadOf')
        self.assertNotEqual(disabled.returncode, 0)
        self.assertTrue((self.home / '.config/dotfiles/git-epic.local').exists())

    def test_codex_unsupported_no_daemon_flag_is_not_injected(self):
        self.wsl()
        self.agent('codex')
        path = self.bin / 'codex'
        path.write_text(path.read_text().replace('echo --no-daemon', 'echo normal-help'))
        self.env['TMUX'] = 'fake'
        result = self.shell('codex hello')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['args'], ['hello'])

    def test_wsl_dry_run_with_epic_and_windows_never_calls_host(self):
        self.wsl()
        result = self.run_script('bootstrap-wsl', '--epic', '--windows-fonts', '--windows-settings',
                                 '/mnt/c/Users/Test User/settings.json', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Epic', result.stdout)
        self.assertIn('Windows Terminal', result.stdout)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_docker_foreign_default_context_endpoint_is_rejected(self):
        self.wsl()
        self.fake('docker', 'if [[ $2 == show ]]; then echo default; else echo tcp://foreign:2376; fi')
        result = self.run_script('bootstrap-wsl')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('foreign daemon endpoint', result.stderr)
        self.assertNotIn('unexpected external operation', result.stderr)

    def test_epic_credential_helper_runs_with_spaces_in_home(self):
        self.wsl()
        self.fake('cmd.exe', 'exit 1')
        result = self.library('bootstrap_epic_local')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.install_git_helper_fixture()
        binary = self.home / '.local/bin/claude-gateway'
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_text('#!/bin/bash\nprintf "username=test-user\\npassword=test-fixture\\n"\n')
        binary.chmod(0o755)
        config = self.home / '.config/dotfiles/git-epic.local'
        result = subprocess.run(['/usr/bin/git', '-c', 'include.path=' + str(config), 'credential', 'fill'],
            input='protocol=https\nhost=live.roost.on.epicgames.com\n\n',
            env=dict(self.env, GIT_TERMINAL_PROMPT='0', GIT_CONFIG_GLOBAL='/dev/null'), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('username=test-user', result.stdout)

    def neovim_archive_fixture(self):
        # Isolate PATH so the reference PC's /usr/bin/nvim cannot mask absence.
        local_bin = self.home / '.local/bin'
        local_bin.mkdir(parents=True)
        self.env['PATH'] = f'{local_bin}:{self.bin}'
        for name in ('bash', 'uname', 'mkdir', 'tar', 'gzip', 'mv', 'ln', 'readlink'):
            (self.bin / name).symlink_to('/usr/bin/' + name)
        payload = self.root / 'payload/nvim-linux-x86_64/bin'
        payload.mkdir(parents=True)
        nvim = payload / 'nvim'
        nvim.write_text('#!/bin/bash\nif [[ $1 == --version ]]; then echo "NVIM v0.12.6"; fi\nexit 0\n')
        nvim.chmod(0o755)
        archive = self.root / 'nvim.tar.gz'
        with tarfile.open(archive, 'w:gz') as bundle:
            bundle.add(payload.parent, arcname='nvim-linux-x86_64')
        self.env['FIXTURE_NVIM_ARCHIVE'] = str(archive)
        self.fake('curl', '''exec /usr/bin/python3 -c 'import os,shutil,sys
args=sys.argv[1:]
assert args[-3] == "https://github.com/neovim/neovim/releases/download/v0.12.6/nvim-linux-x86_64.tar.gz", args
shutil.copyfile(os.environ["FIXTURE_NVIM_ARCHIVE"], args[args.index("-o")+1])' "$@"''')

    def test_missing_neovim_is_installed_when_unused_bob_is_present(self):
        self.neovim_archive_fixture()
        self.fake('bob', 'echo "unused bob must not be invoked" >&2; exit 99')
        old = self.home / '.local/share/bob/nvim-bin/nvim'
        old.parent.mkdir(parents=True)
        old.write_text('old Bob proxy preserved')
        result = self.library('bootstrap_stage=' + shlex.quote(str(self.root)) +
                              '; bootstrap_neovim; nvim --version')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('NVIM v0.12.6', result.stdout)
        self.assertEqual(old.read_text(), 'old Bob proxy preserved')
        expected = self.home / '.local/opt/neovim-0.12.6/bin/nvim'
        self.assertEqual((self.home / '.local/bin/nvim').resolve(), expected)
        fresh = self.library('nvim --version')
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.assertIn('NVIM v0.12.6', fresh.stdout)

    def test_neovim_fallback_replaces_cached_system_command_selection(self):
        self.neovim_archive_fixture()
        self.fake('bob', 'echo "unrelated bob must not block an upgrade" >&2; exit 99')
        system_bin = self.root / 'system-bin'
        system_bin.mkdir()
        old = system_bin / 'nvim'
        old.write_text('#!/bin/bash\nif [[ $1 == --version ]]; then echo "NVIM v0.11.2"; exit 0; fi\nexit 1\n')
        old.chmod(0o755)
        self.env['PATH'] += ':' + str(system_bin)
        result = self.library('bootstrap_stage=' + shlex.quote(str(self.root)) +
                              '; nvim --version; bootstrap_neovim; nvim --version')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['NVIM v0.11.2', 'NVIM v0.12.6'])

    def test_wsl_neovim_uses_global_mise_and_persistent_command_with_bob_present(self):
        self.runtime_fixture()
        self.fake('bob', 'echo "Bob must not be modified" >&2; exit 99')
        project = self.home / 'project'
        project.mkdir()
        project_config = project / 'mise.toml'
        project_config.write_text('[tools]\nneovim = "0.11.2"\n')
        result = self.library('cd ' + shlex.quote(str(project)) +
                              '; bootstrap_mise wsl; bootstrap_neovim wsl; cd /; nvim --version')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        config = self.home / '.config/mise/config.toml'
        self.assertEqual(tomllib.loads(config.read_text())['tools'].get('neovim'), '0.12.7')
        self.assertEqual(project_config.read_text(), '[tools]\nneovim = "0.11.2"\n')
        shim = self.home / '.local/share/mise/shims/nvim'
        target = self.home / '.local/bin/nvim'
        self.assertTrue(target.is_symlink(), 'Missing persistent Neovim command')
        self.assertEqual(os.readlink(target), str(shim))
        fresh = self.library('PATH="$HOME/.local/bin:/usr/bin:/bin"; cd /; nvim --version')
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.assertIn('NVIM v0.12.7', fresh.stdout)
        self.assertFalse((self.home / '.local/opt/neovim-0.12.6').exists())

    def test_wsl_mise_replaces_only_its_old_portable_neovim_link(self):
        self.runtime_fixture()
        portable = self.home / '.local/opt/neovim-0.12.6/bin/nvim'
        portable.parent.mkdir(parents=True)
        portable.write_text('#!/bin/bash\necho "old portable fixture"\n')
        portable.chmod(0o755)
        target = self.home / '.local/bin/nvim'
        target.parent.mkdir(parents=True)
        target.symlink_to(portable)
        result = self.library('bootstrap_mise wsl; bootstrap_neovim wsl')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(os.readlink(target), str(self.home / '.local/share/mise/shims/nvim'))
        self.assertIn('old portable fixture', portable.read_text())

    def test_wsl_mise_preserves_unrecognized_local_neovim_file(self):
        self.runtime_fixture()
        target = self.home / '.local/bin/nvim'
        target.parent.mkdir(parents=True)
        original = '#!/bin/bash\necho "custom Neovim"\n'
        target.write_text(original)
        target.chmod(0o755)
        result = self.library('bootstrap_mise wsl; bootstrap_neovim wsl')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(target.read_text(), original)
        self.assertIn('preserv', result.stderr.lower())

    def test_omarchy_does_not_add_a_mise_neovim_default(self):
        self.runtime_fixture()
        result = self.library('bootstrap_mise omarchy')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        config = self.home / '.config/mise/config.toml'
        self.assertNotIn('neovim', tomllib.loads(config.read_text())['tools'])

    def test_neovim_floor_matches_locked_treesitter(self):
        # Emulate vim.fn.has for the installed version at the process boundary.
        # The copied Treesitter lock requires 0.12; 0.11 must request the fallback.
        self.fake('bob', 'exit 99')
        for installed, acceptable in (('0.11.2', False), ('0.11.9', False),
                                      ('0.12.0', True), ('0.12.6', True)):
            with self.subTest(installed=installed):
                body = '/usr/bin/python3 -c \'import re,sys; installed=tuple(map(int, sys.argv[1].split("."))); requested=re.search(r"nvim-([0-9.]+)", " ".join(sys.argv[2:])).group(1); parts=list(map(int,requested.split("."))); parts += [0]*(3-len(parts)); sys.exit(0 if installed >= tuple(parts) else 1)\' ' + installed + ' "$@"'
                self.fake('nvim', body)
                result = self.library('bootstrap_stage=' + shlex.quote(str(self.root)) +
                                      '; bootstrap_fetch() { echo FALLBACK_REQUESTED >&2; return 66; }; bootstrap_neovim')
                if acceptable:
                    self.assertEqual(result.returncode, 0, result.stderr)
                else:
                    self.assertEqual(result.returncode, 66, result.stderr)
                    self.assertIn('FALLBACK_REQUESTED', result.stderr)
                self.assertEqual(list(self.home.iterdir()), [])

    def test_dotnet_runtime_only_or_obsolete_sdk_gets_a_working_sdk(self):
        self.runtime_fixture()
        for sdks in ('', '6.0.428 [/usr/share/dotnet/sdk]'):
            with self.subTest(sdks=sdks):
                self.fake('dotnet', 'if [[ $1 == --list-sdks ]]; then echo "' + sdks + '"; else echo 10.0.0; fi')
                result = self.library('bootstrap_mise; dotnet --list-sdks; printf "%s" "$DOTNET_ROOT"')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('10.0.100', result.stdout)
                self.assertIn('/fixture/sdk', result.stdout)

    def test_existing_supported_dotnet_sdk_and_tool_config_are_preserved(self):
        self.runtime_fixture()
        self.fake('node', 'echo v26.8.2')
        self.fake('pnpm', 'echo 12.11.2')
        self.fake('dotnet', 'if [[ $1 == --list-sdks ]]; then echo "8.0.422 [/custom/dotnet/sdk]"; else echo 8.0.422; fi')
        for tool in ('claude', 'codex', 'gh', 'starship', 'zoxide', 'eza', 'lazygit'):
            self.fake(tool, 'exit 0')
        config = self.home / '.config/mise/config.toml'
        config.parent.mkdir(parents=True)
        config.write_text('[tools]\nnode = "26.8.2"\n')
        result = self.library('bootstrap_mise')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(tomllib.loads(config.read_text())['tools'],
                         {'node': '26.8.2', 'claude': '2.7.4', 'codex': '0.167.0'})
        self.assertFalse((config.parent / 'conf.d/dotfiles.toml').exists())


if __name__ == '__main__':
    unittest.main()
