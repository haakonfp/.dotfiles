"""Legacy gateway migration exercises only temporary account trees."""
import importlib.util
import json
import os
import shlex
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / 'scripts/migrate_claude_profile.py'


class EpicMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='epic migration ')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        spec = importlib.util.spec_from_file_location('migrate_claude_profile', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.source = self.home / '.claude'
        self.destination = self.home / '.claude-epic'

    def write(self, relative, value):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) + '\n')
        return path

    def gateway(self):
        return self.write('.claude/gateway-helper-config.json', {'helper': 'claude-gateway'})

    def migrate(self, apply=True):
        return self.module.migrate_legacy_claude(self.home, apply=apply)

    def test_personal_profile_and_sidecar_are_untouched(self):
        settings = self.write('.claude/settings.json', {'name': 'Epic Claude', 'theme': 'dark'})
        sidecar = self.write('.claude.json', {'oauth': 'private sentinel'})
        before = settings.read_bytes(), sidecar.read_bytes()
        self.assertEqual(self.migrate()['status'], 'not-needed')
        self.assertEqual(before, (settings.read_bytes(), sidecar.read_bytes()))
        self.assertFalse(self.destination.exists())
        self.assertFalse((self.home / '.local').exists())

    def test_parsed_gateway_settings_are_recognized_and_preview_has_no_writes(self):
        self.write('.claude/settings.json', {'apiKeyHelper': shlex.quote(str(self.source / 'claude-gateway')) + ' auth'})
        result = self.migrate(apply=False)
        self.assertEqual(result['status'], 'preview')
        self.assertTrue(self.source.exists())
        self.assertFalse(self.destination.exists())
        self.assertFalse((self.home / '.local').exists())

    def test_merely_allowing_or_mentioning_gateway_does_not_migrate_personal_account(self):
        settings = self.write('.claude/settings.json', {
            'description': 'I sometimes inspect claude-gateway',
            'permissions': {'allow': ['Bash(claude-gateway --help)']},
        })
        original = settings.read_bytes()
        self.assertEqual(self.migrate()['status'], 'not-needed')
        self.assertEqual(settings.read_bytes(), original)
        self.assertFalse(self.destination.exists())

    def test_gateway_named_argument_or_password_path_is_not_a_gateway_executable(self):
        for command in ('pass show claude-gateway', 'op read op://Personal/claude-gateway/password'):
            with self.subTest(command=command):
                self.write('.claude/settings.json', {'apiKeyHelper': command})
                self.assertEqual(self.migrate()['status'], 'not-needed')
                self.assertFalse(self.destination.exists())

    def test_gateway_marker_moves_profile_and_sidecar_and_retains_binary_and_modes(self):
        marker = self.gateway()
        original = marker.read_bytes()
        marker.chmod(0o640)
        sidecar = self.write('.claude.json', {'projects': {str(self.source / 'project'): {}}})
        sidecar.chmod(0o600)
        binary = b'\x00\xffprivate-auth\x00'
        (self.source / '.credentials.json').write_bytes(binary)
        (self.source / '.credentials.json').chmod(0o600)
        codex = self.write('.codex-epic/auth.json', {'private': 'unchanged'})
        result = self.migrate()
        self.assertEqual(result['status'], 'migrated', result)
        self.assertFalse(self.source.exists())
        self.assertFalse(sidecar.exists())
        self.assertEqual((self.destination / '.credentials.json').read_bytes(), binary)
        self.assertEqual(stat.S_IMODE((self.destination / 'gateway-helper-config.json').stat().st_mode), 0o640)
        moved = self.destination / '.claude.json'
        self.assertEqual(json.loads(moved.read_text()), {'projects': {str(self.destination / 'project'): {}}})
        self.assertEqual(stat.S_IMODE(moved.stat().st_mode), 0o600)
        self.assertEqual(json.loads(codex.read_text()), {'private': 'unchanged'})
        journal_path = Path(result['journal'])
        journal = json.loads(journal_path.read_text())
        self.assertEqual(journal['status'], 'migrated')
        self.assertNotIn('private-auth', journal_path.read_text())
        self.assertEqual(stat.S_IMODE(journal_path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(journal_path.stat().st_mode), 0o600)
        backups = list((journal_path.parent / 'backups').rglob('*'))
        self.assertTrue(any(p.is_file() and p.read_bytes() == original for p in backups))

    def test_empty_destination_is_accepted(self):
        self.gateway()
        self.destination.mkdir(mode=0o750)
        self.assertEqual(self.migrate()['status'], 'migrated')
        self.assertTrue((self.destination / 'gateway-helper-config.json').exists())

    def test_nonempty_destination_fails_without_writes(self):
        marker = self.gateway()
        self.write('.claude-epic/settings.json', {'personal': 'must not merge'})
        result = self.migrate()
        self.assertEqual(result['status'], 'blocked', result)
        self.assertTrue(marker.exists())
        self.assertFalse((self.home / '.local').exists())

    def test_conflicting_sidecars_fail_without_writes(self):
        self.gateway()
        self.write('.claude.json', {'old': True})
        self.write('.claude/.claude.json', {'new': True})
        self.assertEqual(self.migrate()['status'], 'blocked')
        self.assertTrue((self.home / '.claude.json').exists())
        self.assertFalse((self.home / '.local').exists())

    def test_known_configs_rewrite_paths_but_leave_unrelated_data_and_files(self):
        self.gateway()
        self.write('.claude/settings.local.json', {
            str(self.source / 'key'): [str(self.source), '~/.claude/plugins', 'run ' + str(self.source / 'claude-gateway')],
            'unrelated': str(self.source) + '-other/file', 'description': 'claude profile',
        })
        self.write('.claude/plugins/installed_plugins.json', {'installPath': str(self.source / 'plugins/x')})
        self.write('.claude/plugins/known_marketplaces.json', {'path': '~/.claude/plugins/marketplaces/x'})
        unknown = self.write('.claude/session.json', {'path': str(self.source)})
        original_unknown = unknown.read_bytes()
        self.assertEqual(self.migrate()['status'], 'migrated')
        actual = json.loads((self.destination / 'settings.local.json').read_text())
        self.assertEqual(actual[str(self.destination / 'key')], [str(self.destination), '~/.claude-epic/plugins', 'run ' + str(self.destination / 'claude-gateway')])
        self.assertEqual(actual['unrelated'], str(self.source) + '-other/file')
        self.assertEqual((self.destination / 'session.json').read_bytes(), original_unknown)
        self.assertEqual(json.loads((self.destination / 'plugins/installed_plugins.json').read_text())['installPath'], str(self.destination / 'plugins/x'))

    def test_invalid_selected_json_fails_before_writes_without_echoing_content(self):
        self.gateway()
        (self.source / 'settings.local.json').write_text('{secret-sentinel')
        result = self.migrate()
        self.assertEqual(result['status'], 'blocked')
        self.assertNotIn('secret-sentinel', json.dumps(result))
        self.assertTrue(self.source.exists())
        self.assertFalse((self.home / '.local').exists())

    def test_symlinked_account_or_config_paths_are_refused(self):
        for relative in ('.claude', '.claude-epic', '.claude/settings.json', '.claude/plugins', '.claude.json'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as root:
                home = Path(root)
                (home / '.claude').mkdir()
                (home / '.claude/gateway-helper-config.json').write_text('{}')
                external = home / 'external'
                external.mkdir()
                target = home / relative
                if target == home / '.claude':
                    (target / 'gateway-helper-config.json').unlink()
                    target.rmdir()
                target.symlink_to(external, target_is_directory=True)
                result = self.module.migrate_legacy_claude(home, apply=True)
                self.assertEqual(result['status'], 'blocked', result)
                self.assertTrue(target.is_symlink())
                self.assertFalse((home / '.local').exists())

    def test_late_rewrite_failure_rolls_back_moves_bytes_and_empty_destination(self):
        self.gateway()
        settings = self.write('.claude/settings.json', {'path': str(self.source / 'helper')})
        settings.chmod(0o640)
        original = settings.read_bytes()
        sidecar = self.write('.claude.json', {'path': str(self.source)})
        original_sidecar = sidecar.read_bytes()
        self.destination.mkdir(mode=0o750)
        real_replace = os.replace
        def fail_sidecar(source, destination):
            if Path(destination) == self.destination / '.claude.json':
                raise PermissionError('injected late write failure')
            return real_replace(source, destination)
        with mock.patch.object(self.module.os, 'replace', side_effect=fail_sidecar):
            result = self.migrate()
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(settings.read_bytes(), original)
        self.assertEqual(stat.S_IMODE(settings.stat().st_mode), 0o640)
        self.assertEqual(sidecar.read_bytes(), original_sidecar)
        self.assertEqual(list(self.destination.iterdir()), [])
        self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode), 0o750)
        self.assertEqual(json.loads(Path(result['journal']).read_text())['status'], 'rolled-back')

    def test_duplicate_json_keys_are_refused_before_a_rewrite_loses_data(self):
        self.gateway()
        settings = self.source / 'settings.json'
        original = ('{"path": "' + str(self.source) + '", "path": "second value"}').encode()
        settings.write_bytes(original)
        self.assertEqual(self.migrate()['status'], 'blocked')
        self.assertEqual(settings.read_bytes(), original)
        self.assertFalse((self.home / '.local').exists())

    def test_nonstandard_json_numbers_are_refused_before_writes(self):
        self.gateway()
        (self.source / 'settings.json').write_text('{"value": NaN}')
        self.assertEqual(self.migrate()['status'], 'blocked')
        self.assertTrue(self.source.exists())
        self.assertFalse((self.home / '.local').exists())

    def test_path_key_collision_is_refused_before_writes(self):
        self.gateway()
        self.write('.claude/settings.json', {str(self.source): 'old', str(self.destination): 'new'})
        self.assertEqual(self.migrate()['status'], 'blocked')
        self.assertTrue(self.source.exists())
        self.assertFalse((self.home / '.local').exists())

    def test_unwritable_directory_fails_before_backups_or_moves(self):
        marker = self.gateway()
        real_access = os.access
        def cannot_write_source(path, mode):
            return False if Path(path) == self.source else real_access(path, mode)
        with mock.patch.object(self.module.os, 'access', side_effect=cannot_write_source):
            result = self.migrate()
        self.assertEqual(result['status'], 'blocked', result)
        self.assertTrue(marker.exists())
        self.assertFalse((self.home / '.local').exists())

    def test_symlinked_state_directory_does_not_receive_credentials_or_writes(self):
        self.gateway()
        external = self.home / 'external'
        external.mkdir()
        (self.home / '.local').symlink_to(external, target_is_directory=True)
        self.assertEqual(self.migrate()['status'], 'blocked')
        self.assertEqual(list(external.iterdir()), [])
        self.assertTrue(self.source.exists())

    def test_cli_conflict_is_nonzero_and_reports_no_config_contents(self):
        self.gateway()
        self.write('.claude-epic/settings.json', {'token': 'private-sentinel'})
        result = subprocess.run([sys.executable, str(SCRIPT), '--home', str(self.home), '--apply'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['status'], 'blocked')
        self.assertNotIn('private-sentinel', result.stdout + result.stderr)
        self.assertTrue(self.source.exists())

    def test_cli_defaults_to_preview_and_apply_is_explicit(self):
        self.gateway()
        result = subprocess.run([sys.executable, str(SCRIPT), '--home', str(self.home)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'preview')
        self.assertTrue(self.source.exists())
        result = subprocess.run([sys.executable, str(SCRIPT), '--home', str(self.home), '--apply'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'migrated')


if __name__ == '__main__':
    unittest.main()
