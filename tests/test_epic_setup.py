import json
from pathlib import Path
import unittest
import test_bootstrap


class EpicSetupTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_bootstrap.BootstrapTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.wsl()
        self.home = self.fixture.home
        library = self.home / '.config/dotfiles/shell/epic.bash'
        library.parent.mkdir(parents=True)
        library.symlink_to(test_bootstrap.REPO / 'epic/.config/dotfiles/shell/epic.bash')
        codex = self.home / '.codex-epic'
        codex.mkdir()
        (codex / 'config.toml').write_text('model_provider="epic"\n')
        (codex / 'claude-gateway.json').write_text('{}')

    def run_setup(self):
        return self.fixture.run_script('epic/.local/bin/epic-ai-setup')

    def gateway(self):
        self.fixture.fake('claude-gateway', '''
[[ $1 == run ]] || { echo 'Working Codex must not be set up again' >&2; exit 93; }
printf '{"apiKeyHelper":"claude-gateway token"}\n' > "$CLAUDE_CONFIG_DIR/settings.json"
printf '{}\n' > "$CLAUDE_GATEWAY_USER_CONFIG_FILE"
''')

    def test_success_without_profile_files_is_reported_as_failure(self):
        self.fixture.fake('claude-gateway', 'echo "fixture SSO success"; exit 0')
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('settings.json', result.stderr)
        self.assertNotIn('Setup finished', result.stdout)
        self.assertEqual((self.home / '.codex-epic/config.toml').read_text(), 'model_provider="epic"\n')

    def test_valid_partial_claude_profile_is_backed_up_and_completed(self):
        profile = self.home / '.claude-epic'
        profile.mkdir()
        original = '{"custom":"keep in backup"}\n'
        (profile / 'settings.json').write_text(original)
        self.gateway()
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((profile / 'gateway-helper-config.json').is_file())
        self.assertEqual(json.loads((profile / 'settings.json').read_text())['permissions']['defaultMode'], 'acceptEdits')
        backups = list((self.home / '.local/state/dotfiles/epic-setup').rglob('settings.json'))
        self.assertTrue(any(path.read_text() == original for path in backups))

    def test_gateway_owned_default_profile_moves_into_epic_before_launch(self):
        legacy = self.home / '.claude'
        legacy.mkdir()
        (legacy / 'settings.json').write_text('{"apiKeyHelper":"claude-gateway token"}')
        (legacy / 'gateway-helper-config.json').write_text('{}')
        (legacy / '.credentials.json').write_bytes(b'private fixture bytes')
        self.fixture.fake('claude-gateway', 'echo "Existing work profiles must not be reauthenticated" >&2; exit 94')
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        epic = self.home / '.claude-epic'
        self.assertEqual((epic / '.credentials.json').read_bytes(), b'private fixture bytes')
        self.assertFalse((legacy / 'gateway-helper-config.json').exists())
        self.assertEqual(json.loads((epic / 'settings.json').read_text())['apiKeyHelper'], 'claude-gateway token')

    def test_partial_target_keeps_live_token_cache_and_repairs_in_place(self):
        legacy = self.home / '.claude'
        legacy.mkdir()
        original = json.dumps({'apiKeyHelper': 'claude-gateway token', 'old': 'profile',
                               'env': {'ANTHROPIC_BASE_URL': 'https://portkey.example.test', 'KEEP': 'yes'},
                               'hooks': {'SessionStart': [{'hooks': [
                                   {'type': 'command', 'command': 'claude-gateway pre-auth'},
                                   {'type': 'command', 'command': 'sidebar-hook'}]}]}})
        (legacy / 'settings.json').write_text(original)
        (legacy / 'gateway-helper-config.json').write_text('{}')
        target = self.home / '.claude-epic'
        (target / 'tokens/codex').mkdir(parents=True)
        secret = target / 'tokens/codex/cache.enc'
        secret.write_bytes(b'private existing gateway cache')
        (target / 'gateway-helper-config.json').write_text('{}')
        (target / '.claude.json').write_text('{"existing":"work state"}')
        self.fixture.fake('claude-gateway', 'echo "Existing working Claude settings should be reused" >&2; exit 94')
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(secret.read_bytes(), b'private existing gateway cache')
        personal = json.loads((legacy / 'settings.json').read_text())
        self.assertNotIn('apiKeyHelper', personal)
        self.assertEqual(personal['env'], {'KEEP': 'yes'})
        self.assertEqual(personal['forceLoginMethod'], 'claudeai')
        self.assertEqual(personal['hooks']['SessionStart'][0]['hooks'],
                         [{'type': 'command', 'command': 'sidebar-hook'}])
        backups = list(legacy.glob('settings.json.before-ai-preferences-*'))
        self.assertTrue(any(path.read_text() == original for path in backups))
        self.assertEqual((target / '.claude.json').read_text(), '{"existing":"work state"}')
        self.assertEqual(json.loads((target / 'settings.json').read_text())['permissions']['defaultMode'], 'acceptEdits')
        self.assertEqual(json.loads((target / 'settings.json').read_text())['apiKeyHelper'], 'claude-gateway token')
        repeated = self.run_setup()
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        self.assertEqual((legacy / 'settings.json').read_text(), json.dumps(personal, ensure_ascii=False, indent=2) + '\n')
        self.assertIn('"epic"', (self.home / '.codex-epic/config.toml').read_text())

    def installer(self, fail=False):
        profile = self.home / '.claude-epic'
        profile.mkdir()
        (profile / 'settings.json').write_text('{"before":"installer"}\n')
        body = '''cat > "${@: -1}" <<'INSTALL'
#!/bin/bash
mkdir -p "$HOME/.local/bin"
printf '{"apiKeyHelper":"claude-gateway token"}\n' > "$CLAUDE_CONFIG_DIR/settings.json"
printf '{}\n' > "$CLAUDE_GATEWAY_USER_CONFIG_FILE"
printf 'model_provider="changed-by-installer"\n' > "$CODEX_HOME/config.toml"
printf '{"changed":true}\n' > "$CLAUDE_GATEWAY_CODEX_USER_CONFIG_FILE"
printf '#!/bin/bash\nexit 99\n' > "$HOME/.local/bin/claude-gateway"
chmod +x "$HOME/.local/bin/claude-gateway"
'''
        body += ('exit 19\n' if fail else '') + 'INSTALL\n'
        self.fixture.fake('curl', body)

    def test_failed_reconciliation_keeps_working_legacy_settings(self):
        legacy = self.home / '.claude'
        legacy.mkdir()
        original = '{"apiKeyHelper":"claude-gateway token"}'
        (legacy / 'settings.json').write_text(original)
        target = self.home / '.claude-epic'
        (target / 'tokens').mkdir(parents=True)
        (target / 'tokens/cache.enc').write_bytes(b'unchanged')
        self.fixture.fake('claude-gateway', 'exit 19')
        result = self.run_setup()
        self.assertEqual(result.returncode, 19, result.stdout + result.stderr)
        self.assertEqual((legacy / 'settings.json').read_text(), original)
        self.assertEqual((target / 'tokens/cache.enc').read_bytes(), b'unchanged')

    def test_installer_is_backed_up_first_and_preserves_complete_codex(self):
        self.installer()
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        backups = list((self.home / '.local/state/dotfiles/epic-setup').rglob('settings.json'))
        self.assertTrue(any(path.read_text() == '{"before":"installer"}\n' for path in backups))
        codex = self.home / '.codex-epic'
        self.assertIn('"epic"', (codex / 'config.toml').read_text())
        self.assertNotIn('changed-by-installer', (codex / 'config.toml').read_text())
        self.assertEqual((codex / 'claude-gateway.json').read_text(), '{}')

    def test_failed_installer_restores_preexisting_complete_codex(self):
        self.installer(fail=True)
        result = self.run_setup()
        self.assertEqual(result.returncode, 19, result.stdout + result.stderr)
        codex = self.home / '.codex-epic'
        self.assertEqual((codex / 'config.toml').read_text(), 'model_provider="epic"\n')
        self.assertEqual((codex / 'claude-gateway.json').read_text(), '{}')

    def test_setup_prepares_personal_chatgpt_without_changing_work_provider(self):
        target = self.home / '.claude-epic'
        target.mkdir()
        (target / 'settings.json').write_text('{}')
        (target / 'gateway-helper-config.json').write_text('{}')
        personal = self.home / '.codex'
        personal.mkdir()
        (personal / 'config.toml').write_text('model_provider="portkey"\nmodel="gateway-only-model"\n')
        self.fixture.fake('claude-gateway', 'exit 99')
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        import tomllib
        config = tomllib.loads((personal / 'config.toml').read_text())
        self.assertEqual(config['model_provider'], 'openai')
        self.assertEqual(config['forced_login_method'], 'chatgpt')
        self.assertNotIn('model', config)
        self.assertEqual(tomllib.loads((self.home / '.codex-epic/config.toml').read_text())['model_provider'], 'epic')
        self.assertIn('codex login', result.stdout)

    def test_ready_work_profiles_receive_sidebar_hooks_for_all_four_agents(self):
        target = self.home / '.claude-epic'
        target.mkdir()
        (target / 'settings.json').write_text('{"apiKeyHelper":"claude-gateway token"}')
        (target / 'gateway-helper-config.json').write_text('{}')
        plugin = self.home / '.local/share/tmux/plugins/tmux-agent-sidebar'
        (plugin / 'bin').mkdir(parents=True)
        (plugin / 'hook.sh').write_text('#!/bin/bash\n')
        data = {'hook_script': str(plugin / 'hook.sh'), 'agents': {
            agent: {'snippet': {'hooks': {'Stop': [{'hooks': [{'type': 'command',
                'command': f'sidebar-{agent}-stop'}]}]}}} for agent in ('claude', 'codex')}}
        binary = plugin / 'bin/tmux-agent-sidebar'
        binary.write_text('#!/usr/bin/python3\nprint(' + repr(json.dumps(data)) + ')\n')
        binary.chmod(0o755)
        self.fixture.fake('claude-gateway', 'exit 99')
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for relative in ('.claude/settings.json', '.claude-epic/settings.json',
                         '.codex/hooks.json', '.codex-epic/hooks.json'):
            self.assertIn('Stop', json.loads((self.home / relative).read_text())['hooks'])
        self.assertEqual(json.loads((target / 'settings.json').read_text())['apiKeyHelper'], 'claude-gateway token')


if __name__ == '__main__':
    unittest.main()
