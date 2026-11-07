"""Exercise real hook merges and profile selection in temporary account homes."""
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import tomllib
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))


class SidebarHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='sidebar hooks ')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'home with spaces'
        self.home.mkdir()
        spec = importlib.util.spec_from_file_location('sidebar_hooks', REPO / 'scripts/sidebar_hooks.py')
        self.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tool)
        self.plugin = self.home / '.local/share/tmux/plugins/tmux-agent-sidebar'
        (self.plugin / 'bin').mkdir(parents=True)
        (self.plugin / 'hook.sh').write_text('#!/bin/bash\n')
        self.snippets = {agent: {'hooks': {'Stop': [{'matcher': '', 'hooks': [
            {'type': 'command', 'command': f'bash {shlex.quote(str(self.plugin / "hook.sh"))} {agent} stop'}]}]}}
                         for agent in ('claude', 'codex')}
        binary = self.plugin / 'bin/tmux-agent-sidebar'
        payload = {'hook_script': str(self.plugin / 'hook.sh'),
                   'agents': {agent: {'snippet': snippet} for agent, snippet in self.snippets.items()}}
        binary.write_text('#!/usr/bin/python3\nimport json,sys\nassert sys.argv[1:] == ["setup"]\nprint(' + repr(json.dumps(payload)) + ')\n')
        binary.chmod(0o755)

    def write(self, relative, content):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def configure_epic(self):
        self.write('.claude-epic/settings.json', '{"apiKeyHelper":"claude-gateway token"}')
        self.write('.claude-epic/gateway-helper-config.json', '{}')
        self.write('.codex-epic/config.toml', 'model_provider="portkey"\nmodel="keep-model"\n')
        self.write('.codex-epic/claude-gateway.json', '{}')

    def test_merge_preserves_gateway_and_other_hooks_and_is_repeatable(self):
        original = {'apiKeyHelper': 'claude-gateway token', 'hooks': {'Stop': [{'hooks': [
            {'type': 'command', 'command': 'claude-gateway pre-auth', 'timeout': 7},
            dict(self.snippets['claude']['hooks']['Stop'][0]['hooks'][0], timeout=4)]}]}}
        merged = self.tool.merge_hooks(original, self.snippets['claude'])
        self.assertEqual(merged, original)
        self.assertEqual(self.tool.merge_hooks(merged, self.snippets['claude']), merged)
        added = self.tool.merge_hooks({'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'personal-hook'}]}]}}, self.snippets['claude'])
        self.assertEqual(len(added['hooks']['Stop'][0]['hooks']), 2)

    def test_personal_only_does_not_touch_even_configured_epic_accounts(self):
        self.configure_epic()
        files = self.tool.hook_files(self.home)
        self.assertEqual({str(path.relative_to(self.home)) for path in files},
                         {'.claude/settings.json', '.codex/hooks.json', '.codex/config.toml'})

    def test_fresh_epic_opt_in_defers_work_profiles_until_configured(self):
        self.tool.apply_preferences(self.tool.hook_files(self.home, epic=True))
        self.assertFalse((self.home / '.claude-epic').exists())
        self.assertFalse((self.home / '.codex-epic').exists())

    def test_four_profiles_preserve_accounts_back_up_and_repeat_without_changes(self):
        self.configure_epic()
        personal = self.write('.claude/settings.json', '{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"personal-hook"}]}]}}\n')
        codex = self.write('.codex/config.toml', 'model="keep"\n[features]\ncodex_hooks=false\nother=true\n[hooks.state.existing]\ntrusted_hash="keep-hash"\n')
        self.write('.codex/auth.json', '{"sentinel":"keep credentials"}')
        originals = {personal: personal.read_bytes(), codex: codex.read_bytes()}
        self.tool.apply_preferences(self.tool.hook_files(self.home, epic=True))
        for relative in ('.claude/settings.json', '.codex/hooks.json', '.claude-epic/settings.json', '.codex-epic/hooks.json'):
            self.assertIn('Stop', json.loads((self.home / relative).read_text())['hooks'])
        self.assertEqual(json.loads((self.home / '.claude-epic/settings.json').read_text())['apiKeyHelper'], 'claude-gateway token')
        for relative in ('.codex/config.toml', '.codex-epic/config.toml'):
            self.assertTrue(tomllib.loads((self.home / relative).read_text())['features']['hooks'])
        self.assertEqual(tomllib.loads(codex.read_text())['hooks']['state']['existing']['trusted_hash'], 'keep-hash')
        self.assertEqual(tomllib.loads((self.home / '.codex-epic/config.toml').read_text())['model_provider'], 'portkey')
        self.assertEqual((self.home / '.codex/auth.json').read_text(), '{"sentinel":"keep credentials"}')
        for path, content in originals.items():
            backups = list(path.parent.glob(path.name + '.before-ai-preferences-*'))
            self.assertTrue(any(item.read_bytes() == content and item.stat().st_mode & 0o777 == 0o600 for item in backups))
        self.assertEqual(self.tool.apply_preferences(self.tool.hook_files(self.home, epic=True)), [])

    def test_invalid_last_profile_prevents_all_writes(self):
        self.configure_epic()
        path = self.write('.codex-epic/hooks.json', '{"hooks":{"Stop":"invalid"}}')
        with self.assertRaises(ValueError):
            self.tool.apply_preferences(self.tool.hook_files(self.home, epic=True))
        self.assertFalse((self.home / '.claude/settings.json').exists())
        self.assertFalse(list(path.parent.glob('*.before-ai-preferences-*')))

    def test_inline_codex_hooks_are_not_registered_a_second_time(self):
        command = self.snippets['codex']['hooks']['Stop'][0]['hooks'][0]['command']
        self.write('.codex/config.toml', '[hooks]\nStop=[{hooks=[{type="command",command=' + json.dumps(command) + '}]}]\n')
        files = self.tool.hook_files(self.home)
        self.assertEqual(json.loads(files[self.home / '.codex/hooks.json'])['hooks'].get('Stop', []), [])

    def test_existing_claude_sidebar_plugin_switches_to_direct_hooks_without_disabling_others(self):
        self.write('.claude/settings.json', '{"enabledPlugins":{"tmux-agent-sidebar@hiroppy":true,"other@personal":true}}')
        files = self.tool.hook_files(self.home)
        settings = json.loads(files[self.home / '.claude/settings.json'])
        self.assertEqual(settings['enabledPlugins'], {'tmux-agent-sidebar@hiroppy': False, 'other@personal': True})
        self.assertIn('Stop', settings['hooks'])


if __name__ == '__main__':
    unittest.main()
