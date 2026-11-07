import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ai_installer', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerAIPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='AI installer ')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'home with spaces'
        self.home.mkdir()

    def write(self, relative, content):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def plan(self, epic=False):
        return {item['path']: item for item in installer.plan_install(self.home, 'wsl', epic=epic)}

    def test_personal_defaults_are_in_transaction_without_creating_work_profiles(self):
        planned = self.plan(epic=True)
        self.assertIn('.claude/settings.json', planned)
        self.assertIn('.codex/config.toml', planned)
        self.assertNotIn('.claude-epic/settings.json', planned)
        self.assertNotIn('.codex-epic/config.toml', planned)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_existing_provider_and_hook_data_survive_and_restore(self):
        claude = self.write('.claude/settings.json', '{"apiKeyHelper":"private-helper","hooks":{"Stop":[]}}\n')
        codex = self.write('.codex/config.toml', '# private provider\nmodel_provider="custom"\n[model_providers.custom]\nbase_url="https://example.test"\n')
        original = {claude: claude.read_bytes(), codex: codex.read_bytes()}
        operations = installer.plan_install(self.home, 'wsl')
        with contextlib.redirect_stdout(io.StringIO()):
            manifest = installer.apply_plan(self.home, operations)
        data = json.loads(claude.read_text())
        self.assertEqual(data['apiKeyHelper'], 'private-helper')
        self.assertEqual(data['permissions']['defaultMode'], 'acceptEdits')
        self.assertIn('claude-statusline', data['statusLine']['command'])
        config = tomllib.loads(codex.read_text())
        self.assertEqual(config['model_providers']['custom']['base_url'], 'https://example.test')
        self.assertEqual(config['approval_policy'], 'on-request')
        self.assertEqual(config['sandbox_mode'], 'workspace-write')
        self.assertIn('weekly-limit', config['tui']['status_line'])
        self.assertEqual(installer.plan_install(self.home, 'wsl'), [])
        with contextlib.redirect_stdout(io.StringIO()):
            installer.restore_manifest(self.home, manifest, apply=True)
        for path, content in original.items():
            self.assertEqual(path.read_bytes(), content)

    def test_only_configured_opted_in_work_profiles_receive_preferences(self):
        self.write('.claude-epic/settings.json', '{"apiKeyHelper":"claude-gateway token"}')
        self.write('.claude-epic/gateway-helper-config.json', '{}')
        self.write('.codex-epic/config.toml', 'model_provider="epic"\n')
        self.write('.codex-epic/claude-gateway.json', '{}')
        personal = self.plan(epic=False)
        self.assertNotIn('.claude-epic/settings.json', personal)
        planned = self.plan(epic=True)
        self.assertIn('.claude-epic/settings.json', planned)
        self.assertIn('.codex-epic/config.toml', planned)
        self.assertEqual(json.loads(planned['.claude-epic/settings.json']['content'])['apiKeyHelper'], 'claude-gateway token')

    def test_legacy_personal_portkey_changes_to_chatgpt_but_epic_stays_portkey(self):
        personal = self.write('.codex/config.toml', '''model_provider="portkey"
model="gpt-5.6-luna"
model_catalog_json="/private/gateway-models.json"
profile="work"
[model_providers.portkey]
base_url="https://gateway.example.test"
[mcp_servers.personal]
command="personal-tool"
''')
        original = personal.read_bytes()
        self.write('.codex/auth.json', '{"private":"existing auth stays untouched"}')
        self.write('.codex-epic/config.toml', 'model_provider="portkey"\nmodel="gpt-5.6-sol"\n')
        self.write('.codex-epic/claude-gateway.json', '{}')
        planned = self.plan(epic=True)
        config = tomllib.loads(planned['.codex/config.toml']['content'])
        self.assertEqual(config['model_provider'], 'openai')
        self.assertEqual(config['forced_login_method'], 'chatgpt')
        self.assertEqual(config['cli_auth_credentials_store'], 'file')
        for key in ('model', 'model_catalog_json', 'profile'):
            self.assertNotIn(key, config)
        self.assertNotIn('portkey', config.get('model_providers', {}))
        self.assertEqual(config['mcp_servers']['personal']['command'], 'personal-tool')
        work = tomllib.loads(planned['.codex-epic/config.toml']['content'])
        self.assertEqual(work['model_provider'], 'portkey')
        self.assertEqual(work['model'], 'gpt-5.6-sol')
        with contextlib.redirect_stdout(io.StringIO()):
            manifest = installer.apply_plan(self.home, list(planned.values()))
        self.assertEqual((self.home / '.codex/auth.json').read_text(), '{"private":"existing auth stays untouched"}')
        self.assertEqual(installer.plan_install(self.home, 'wsl', epic=True), [])
        with contextlib.redirect_stdout(io.StringIO()):
            installer.restore_manifest(self.home, manifest, apply=True)
        self.assertEqual(personal.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
