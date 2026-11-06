import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class ShellTests(unittest.TestCase):
    def test_omarchy_aliases_do_not_abort_interactive_user_configuration(self):
        with tempfile.TemporaryDirectory(prefix='interactive shell ') as directory:
            home = Path(directory)
            local = home / '.config/dotfiles/local.bash'
            local.parent.mkdir(parents=True)
            local.write_text('export DOTFILES_LOCAL_SENTINEL=loaded\n')
            env = dict(os.environ, HOME=directory,
                       COMMON_SHELL=str(REPO / 'common/.config/dotfiles/shell/common.bash'))
            process = subprocess.run(['bash', '--noprofile', '--norc', '-ic',
                                      'alias ff="printf default"; alias eff="printf default"; '
                                      'DOTFILES_OMARCHY=1; source "$COMMON_SHELL" || exit; '
                                      'declare -F ff eff clip open codex; printf "LOCAL:%s" "$DOTFILES_LOCAL_SENTINEL"'],
                                     env=env, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn('LOCAL:loaded', process.stdout)
            self.assertNotIn('syntax error', process.stderr)

    @unittest.skipUnless(Path('/usr/share/omarchy/default/bash/aliases').is_file(), 'Omarchy aliases unavailable')
    def test_installed_omarchy_aliases_and_shared_functions_coexist(self):
        with tempfile.TemporaryDirectory(prefix='stock aliases ') as directory:
            env = dict(os.environ, HOME=directory,
                       COMMON_SHELL=str(REPO / 'common/.config/dotfiles/shell/common.bash'))
            process = subprocess.run(['bash', '--noprofile', '--norc', '-ic',
                                      'source /usr/share/omarchy/default/bash/aliases; '
                                      'DOTFILES_OMARCHY=1; source "$COMMON_SHELL" || exit; '
                                      'declare -F ff eff clip open codex'], env=env, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stdout.splitlines(), ['ff', 'eff', 'clip', 'open', 'codex'])

    def test_local_tool_fallbacks_take_precedence_without_duplicate_path_entries(self):
        with tempfile.TemporaryDirectory(prefix='path ordering ') as directory:
            home = Path(directory)
            binary = home / '.local/bin'
            binary.mkdir(parents=True)
            local_tmux = binary / 'tmux'
            local_tmux.write_text('#!/bin/sh\nexit 0\n')
            local_tmux.chmod(0o755)
            env = dict(os.environ, HOME=directory,
                       PATH=f'/usr/bin:/bin:{binary}:/opt/tools:{binary}',
                       COMMON_SHELL=str(REPO / 'common/.config/dotfiles/shell/common.bash'))
            process = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-c',
                                      'DOTFILES_OMARCHY=1; source "$COMMON_SHELL"; command -v tmux; printf "%s" "$PATH"'],
                                     env=env, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            selected, path = process.stdout.split('\n', 1)
            self.assertEqual(selected, str(local_tmux))
            self.assertEqual(path.split(':').count(str(binary)), 1)

    def call_codex(self, help_text, tmux, arguments):
        with tempfile.TemporaryDirectory(prefix='shell test ') as directory:
            home = Path(directory)
            binary = home / 'bin'
            binary.mkdir()
            script = binary / 'codex'
            script.write_text('#!/usr/bin/python3\nimport json,sys\n'
                              f'if sys.argv[1:] == ["--help"]: print({help_text!r})\n'
                              'else: print(json.dumps(sys.argv[1:]))\n')
            script.chmod(0o755)
            env = dict(os.environ, HOME=directory, PATH=str(binary) + ':/usr/bin:/bin',
                       COMMON_SHELL=str(REPO / 'common/.config/dotfiles/shell/common.bash'))
            env.pop('TMUX', None)
            if tmux:
                env['TMUX'] = 'private-test'
            process = subprocess.run(['bash', '--noprofile', '--norc', '-c',
                                      'DOTFILES_OMARCHY=1; source "$COMMON_SHELL"; codex "$@"', 'test', *arguments],
                                     env=env, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            return json.loads(process.stdout)

    def test_unsupported_client_does_not_receive_no_daemon_flag(self):
        self.assertEqual(self.call_codex('Usage: codex', True, ['hello']), ['hello'])

    def test_supported_tmux_client_receives_one_flag(self):
        self.assertEqual(self.call_codex('--no-daemon', True, ['hello']), ['--no-daemon', 'hello'])
        self.assertEqual(self.call_codex('--no-daemon', True, ['--no-daemon', 'hello']), ['--no-daemon', 'hello'])

    def test_ordinary_client_keeps_original_arguments(self):
        self.assertEqual(self.call_codex('--no-daemon', False, ['hello']), ['hello'])


if __name__ == '__main__':
    unittest.main()
