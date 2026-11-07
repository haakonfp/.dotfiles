"""Merge preferences without moving accounts, and exercise the real status renderer."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import tomllib
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / 'scripts/ai_preferences.py'
STATUS = REPO / 'common/.local/bin/claude-statusline'


def load_tool():
    spec = importlib.util.spec_from_file_location('ai_preferences', TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MergeTests(unittest.TestCase):
    def test_claude_preserves_account_hooks_and_permission_rules(self):
        tool = load_tool()
        original = {'env': {'ANTHROPIC_BASE_URL': 'https://work.example.test'},
                    'model': 'keep-my-model', 'hooks': {'Stop': []},
                    'permissions': {'deny': ['Bash(rm *)'], 'allow': ['Read'], 'defaultMode': 'default'},
                    'statusLine': {'type': 'command', 'command': 'old', 'padding': 2}}
        merged = tool.merge_claude_settings(json.dumps(original), 'python3 /safe/statusline')
        result = json.loads(merged)
        self.assertEqual(result['permissions']['defaultMode'], 'acceptEdits')
        self.assertEqual(result['statusLine'], {'type': 'command', 'command': 'python3 /safe/statusline', 'padding': 2})
        for name in ('env', 'model', 'hooks'):
            self.assertEqual(result[name], original[name])
        self.assertEqual(result['permissions']['deny'], ['Bash(rm *)'])
        self.assertEqual(result['permissions']['allow'], ['Read'])
        self.assertEqual(tool.merge_claude_settings(merged, 'python3 /safe/statusline'), merged)

    def test_codex_preserves_multiline_arrays_inline_tables_dates_and_providers(self):
        tool = load_tool()
        original = '''# Local account stays here.
model = "local-model"
approval_policy = { granular = { rules = true } }
sandbox_mode = "read-only"
tui = { status_line = ["git-branch"], notifications = ["agent-turn-complete"] }
notify = [
  "python3", "file with spaces.py",
]
when = 2025-01-01T12:01:02Z
[model_providers.work]
name = "Work"
base_url = "https://work.example.test"
env_key = "WORK_KEY"
[mcp_servers.custom]
command = "custom"
args = ["--keep"]
'''
        merged = tool.merge_codex_config(original)
        result = tomllib.loads(merged)
        expected = tomllib.loads(original)
        expected['approval_policy'] = 'on-request'
        expected['sandbox_mode'] = 'workspace-write'
        expected['tui']['status_line'] = ['model-with-reasoning', 'current-dir', 'git-branch',
                                         'run-state', 'context-remaining', 'weekly-limit',
                                         'context-window-size', 'used-tokens', 'task-progress']
        expected['tui']['status_line_use_colors'] = True
        self.assertEqual(result, expected)
        self.assertEqual(tool.merge_codex_config(merged), merged)

    def test_codex_unicode_and_all_toml_value_types_survive_merge(self):
        tool = load_tool()
        original = '''label = "project 🌍"
escaped = "\\u007F"
date = 2025-01-02
time = 12:34:56.123456
datetime = 2025-01-02T12:34:56.123456
positive_infinity = +inf
negative_infinity = -inf
[tui]
unrelated = true
[[servers]]
name = "one"
options = { nested = [1, true, 3.5] }
[[servers]]
name = "two"
'''
        merged = tomllib.loads(tool.merge_codex_config(original))
        old = tomllib.loads(original)
        for name, value in old.items():
            if name != 'tui':
                self.assertEqual(merged[name], value)
        self.assertTrue(merged['tui']['unrelated'])

    def test_invalid_configs_are_refused_without_replacing_unknown_values(self):
        tool = load_tool()
        for raw in ('[]', '{"permissions": []}', '{"statusLine": null}', '{bad',
                    '{"model":"first", "model":"second"}', '{"value":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                tool.merge_claude_settings(raw)
        for raw in ('tui = 4', 'model = "unterminated', 'tui = [1, 2]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                tool.merge_codex_config(raw)


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ai preferences ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.claude = self.root / 'work claude'
        self.codex = self.root / 'personal codex'

    def cli(self, *args):
        return subprocess.run(['python3', str(TOOL), *map(str, args)], capture_output=True, text=True)

    def test_explicit_homes_preview_apply_backup_and_idempotence(self):
        self.claude.mkdir()
        settings = self.claude / 'settings.json'
        old = '{"model": "work-model"}\n'
        settings.write_text(old)
        settings.chmod(0o640)
        result = self.cli('--claude-home', self.claude, '--codex-home', self.codex)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(settings.read_text(), old)
        self.assertFalse(self.codex.exists())
        result = self.cli('--claude-home', self.claude, '--codex-home', self.codex, '--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(settings.read_text())['model'], 'work-model')
        self.assertEqual(stat.S_IMODE(settings.stat().st_mode), 0o640)
        self.assertEqual(stat.S_IMODE((self.codex / 'config.toml').stat().st_mode), 0o600)
        backups = list(self.claude.glob('settings.json.before-ai-preferences-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), old)
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
        again = self.cli('--claude-home', self.claude, '--codex-home', self.codex, '--apply')
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(list(self.claude.glob('settings.json.before-ai-preferences-*')), backups)

    def test_all_config_validation_happens_before_any_write(self):
        self.codex.mkdir()
        (self.codex / 'config.toml').write_text('model = [broken')
        result = self.cli('--claude-home', self.claude, '--codex-home', self.codex, '--apply')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.claude.exists())

    def test_symlinks_and_hardlinks_are_refused_without_touching_targets(self):
        tool = load_tool()
        self.claude.mkdir()
        target = self.root / 'private'
        target.write_text('{}')
        settings = self.claude / 'settings.json'
        settings.symlink_to(target)
        with self.assertRaises(ValueError):
            tool.preference_files(claude_home=self.claude)
        self.assertEqual(target.read_text(), '{}')
        settings.unlink()
        os.link(target, settings)
        with self.assertRaises(ValueError):
            tool.preference_files(claude_home=self.claude)
        self.assertEqual(target.read_text(), '{}')

    def test_linked_parent_is_refused(self):
        tool = load_tool()
        real = self.root / 'real'
        real.mkdir()
        self.claude.symlink_to(real, target_is_directory=True)
        with self.assertRaises(ValueError):
            tool.preference_files(claude_home=self.claude)

    def test_atomic_failure_keeps_original_and_cleans_temporary_files(self):
        tool = load_tool()
        self.claude.mkdir()
        path = self.claude / 'settings.json'
        path.write_text('{}')
        with mock.patch.object(tool.os, 'replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                tool.apply_preferences({path: '{"new": true}\n'})
        self.assertEqual(path.read_text(), '{}')
        self.assertFalse(list(self.claude.glob('.ai-preferences-*')))
        self.assertEqual(len(list(self.claude.glob('settings.json.before-ai-preferences-*'))), 1)

    def test_cli_requires_explicit_target(self):
        self.assertNotEqual(self.cli('--apply').returncode, 0)


class StatuslineTests(unittest.TestCase):
    def status(self, payload):
        return subprocess.run([str(STATUS)], input=payload, text=True,
                              capture_output=True, env=dict(os.environ, NO_COLOR='1'), timeout=3)

    def test_real_git_branch_and_documented_payload_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            subprocess.run(['git', 'init', '--initial-branch=feature/status', folder],
                           check=True, capture_output=True)
            payload = {'model': {'display_name': 'Claude Example'},
                       'workspace': {'current_dir': folder},
                       'context_window': {'remaining_percentage': 76.5, 'context_window_size': 200000,
                                          'total_input_tokens': 15500, 'total_output_tokens': 1200},
                       'rate_limits': {'seven_day': {'used_percentage': 20}}}
            result = self.status(json.dumps(payload))
            self.assertEqual(result.returncode, 0, result.stderr)
            for segment in ('Claude Example', folder, 'feature/status', '76.5% context left',
                            'context 200,000', 'tokens 15,500 in / 1,200 out', 'week 80% left'):
                self.assertIn(segment, result.stdout)
            self.assertNotIn('reasoning', result.stdout)
            self.assertNotIn('progress', result.stdout)

    def test_empty_null_malformed_and_unsupported_fields_are_quiet(self):
        for raw in ('', 'null', '{}', '[]', '{bad', '{"model":null,"workspace":null,"context_window":null}',
                    '{"model":{"display_name":[]}, "context_window":{"remaining_percentage":"bad"}}'):
            with self.subTest(raw=raw):
                result = self.status(raw)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                self.assertEqual(result.stdout, '\n')

    def test_control_characters_never_reach_terminal(self):
        payload = {'model': {'display_name': 'Claude\x1b[31m\n\u202eevil'},
                   'workspace': {'current_dir': '/missing/\x1b]2;bad\x07\rdir'},
                   'context_window': {'remaining_percentage': 0, 'total_input_tokens': 0,
                                      'total_output_tokens': 0}}
        result = self.status(json.dumps(payload))
        self.assertEqual(result.returncode, 0)
        for control in ('\x1b', '\x07', '\r', '\u202e'):
            self.assertNotIn(control, result.stdout)
        self.assertEqual(result.stdout.count('\n'), 1)
        self.assertIn('0% context left', result.stdout)
        self.assertIn('tokens 0 in / 0 out', result.stdout)

    def test_current_usage_fallback_includes_cache_tokens_and_ignores_bad_percentages(self):
        payload = {'context_window': {'remaining_percentage': 300,
                                      'current_usage': {'input_tokens': 10, 'output_tokens': 3,
                                                        'cache_creation_input_tokens': 20,
                                                        'cache_read_input_tokens': 30}}}
        result = self.status(json.dumps(payload))
        self.assertEqual(result.stdout, 'tokens 60 in / 3 out\n')

    def test_extreme_numeric_values_are_ignored_instead_of_crashing(self):
        result = self.status(json.dumps({'context_window': {'total_input_tokens': 10**400,
                                                            'total_output_tokens': 1e308,
                                                            'remaining_percentage': float('inf')}}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, '\n')


if __name__ == '__main__':
    unittest.main()
