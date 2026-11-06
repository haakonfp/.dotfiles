"""Run against disposable settings; never use the host Windows configuration."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/windows-terminal.py'


def module():
    spec = importlib.util.spec_from_file_location('windows_terminal', SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def effective(settings):
    """Resolve current IDs and legacy inline commands at the public WT boundary."""
    commands = {a['id']: a['command'] for a in settings.get('actions', [])
                if 'id' in a and 'command' in a}
    result = {}
    for a in settings.get('actions', []) + settings.get('keybindings', []):
        if 'keys' not in a:
            continue
        keys = a['keys'] if isinstance(a['keys'], list) else [a['keys']]
        for key in keys:
            normalized = '+'.join(sorted(key.lower().split('+')))
            result[normalized] = a.get('command', commands.get(a.get('id'), a.get('id')))
    return result


def binding(settings, key):
    return effective(settings).get('+'.join(sorted(key.split('+'))))


class WindowsTerminalTests(unittest.TestCase):
    def test_preview_writes_nothing_and_apply_backs_up_original_once(self):
        with tempfile.TemporaryDirectory(prefix='terminal with spaces ') as d:
            p = Path(d) / 'settings.json'
            original = b'// keep original in backup\n{"profiles":{"list":[{"guid":"{one}","commandline":"wsl.exe -d Ubuntu"}]}}\n'
            p.write_bytes(original)
            before = sorted(Path(d).iterdir())
            run = subprocess.run([sys.executable, str(SCRIPT), '--settings', str(p)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('Preview', run.stdout)
            self.assertEqual(p.read_bytes(), original)
            self.assertEqual(sorted(Path(d).iterdir()), before)
            run = subprocess.run([sys.executable, str(SCRIPT), '--settings', str(p), '--apply'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            backups = list(Path(d).glob('settings.json.bak.*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            applied = p.read_bytes()
            run = subprocess.run([sys.executable, str(SCRIPT), '--settings', str(p), '--apply'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(p.read_bytes(), applied)
            self.assertEqual(list(Path(d).glob('settings.json.bak.*')), backups)

    def test_jsonc_handles_urls_escapes_comments_and_trailing_commas(self):
        m = module()
        value = m.parse_jsonc(r'''\ufeff'''.replace(r'\ufeff', '\ufeff') + r'''{
          // comment
          "url": "https://example.test/a//b/*c*/,}",
          "quoted": "\"x\"", /* block */ "path": "C:\\Users\\A B",
          "items": ["},]", 2,],
        }''')
        self.assertEqual(value, {'url': 'https://example.test/a//b/*c*/,}', 'quoted': '"x"', 'path': r'C:\Users\A B', 'items': ['},]', 2]})
        for invalid in ['{"a":1 /* unfinished', '{"a": [1,,]}', '{"a":1,"a":2}']:
            with self.assertRaises(ValueError):
                m.parse_jsonc(invalid)

    def test_profiles_identity_commands_order_and_local_appearance_survive(self):
        m = module()
        src = {'defaultProfile':'{two}', 'custom':'https://a/b', 'schemes':[{'name':'Other','red':'#123456'}],
               'profiles': {'defaults': {'font': {'size': 14, 'features': {'calt': 0}}, 'opacity': 77, 'padding': '5'},
                 'list':[{'guid':'{two}', 'commandline':'wsl.exe -d Custom', 'font': {'size': 16, 'face':'Old'}, 'opacity':63},
                         {'guid':'{one}', 'source':'Windows.Terminal.PowershellCore', 'hidden':True}]}}
        original = copy.deepcopy(src)
        got = m.merge_settings(src)
        self.assertEqual(src, original, 'merge must not mutate the input')
        self.assertEqual([p['guid'] for p in got['profiles']['list']], ['{two}', '{one}'])
        self.assertEqual(got['profiles']['list'][0]['commandline'], 'wsl.exe -d Custom')
        self.assertEqual(got['profiles']['list'][1], original['profiles']['list'][1])
        self.assertEqual(got['defaultProfile'], '{two}')
        self.assertEqual(got['custom'], 'https://a/b')
        self.assertEqual(got['schemes'][0], original['schemes'][0])
        defaults = got['profiles']['defaults']
        self.assertEqual(defaults['font']['face'], 'JetBrainsMono Nerd Font Mono')
        self.assertEqual(defaults['font']['weight'], 'medium')
        self.assertEqual(defaults['font']['size'], 14)
        self.assertEqual(defaults['font']['features'], {'calt': 0})
        self.assertEqual(defaults['opacity'], 90)
        self.assertEqual(got['profiles']['list'][0]['font']['size'], 16)
        self.assertEqual(got['profiles']['list'][0]['font']['face'], 'JetBrainsMono Nerd Font Mono')
        self.assertEqual(got['profiles']['list'][0]['opacity'], 90)
        scheme = next(s for s in got['schemes'] if s['name'] == 'Agamotto')
        self.assertEqual((scheme['background'], scheme['purple'], scheme['selectionBackground'], scheme['cursorColor']),
                         ('#0A0118', '#BD93F9', '#5B4B8A', '#FFFFFF'))

    def test_legacy_conflicts_duplicates_and_key_arrays_preserve_other_bindings(self):
        src = {'profiles':{'list':[{}, {}, {}]}, 'actions':[
            {'command':'paste','keys':['ctrl+v','shift+insert']},
            {'command':'copy','keys':'CTRL+C'},
            {'command':'closeWindow','keys':'ctrl+w'},
            {'command':'toggleFullscreen','keys':['alt+enter','f11']},
            {'command':'find','keys':'alt+1'},
            {'command':'find','keys':'shift+alt+1'},
            {'command':'find','keys':'alt+shift+1'},
            {'command':'resetFontSize','keys':'ctrl+shift+9'},
            {'command':'find','keys':'ctrl+shift+8'},
            {'command':'find','keys':'ctrl+shift+f'}]}
        got = module().merge_settings(src)
        self.assertEqual(binding(got,'shift+insert'), 'paste')
        self.assertEqual(binding(got,'f11'), 'toggleFullscreen')
        self.assertEqual(binding(got,'ctrl+shift+f'), 'find')
        self.assertEqual(binding(got,'ctrl+shift+9'), 'resetFontSize')
        self.assertEqual(binding(got,'ctrl+shift+8'), 'find')
        self.assertEqual(binding(got,'alt+enter'), 'unbound')
        self.assertEqual(binding(got,'ctrl+c'), 'unbound')
        self.assertEqual(binding(got,'ctrl+v'), 'unbound')
        self.assertEqual(binding(got,'ctrl+w'), 'unbound')
        self.assertEqual(binding(got,'alt+1'), 'unbound')
        self.assertEqual(binding(got,'shift+alt+9'), {'action':'switchToTab','index':4294967295})
        self.assertEqual(binding(got,'ctrl+shift+3'), {'action':'newTab','index':2})
        self.assertEqual(binding(got,'ctrl+shift+c'), {'action':'copy','singleLine':False})
        self.assertEqual(binding(got,'ctrl+shift+v'), 'paste')
        self.assertEqual(binding(got,'ctrl+shift+w'), 'closePane')
        for i in range(1,10):
            self.assertEqual(binding(got,f'ctrl+{i}'), {'action':'sendInput','input': f'\x1b[{48+i};5u'})
        self.assertEqual(binding(got,'shift+enter'), {'action':'sendInput','input':'\x1b[13;2u'})
        self.assertEqual(binding(got,'shift+alt+enter'), {'action':'sendInput','input':'\x1b[13;4u'})
        bindings = [tuple(sorted(k.lower().split('+'))) for a in got['actions'] if 'keys' in a
                    for k in (a['keys'] if isinstance(a['keys'], list) else [a['keys']])]
        self.assertEqual(bindings.count(('1','alt','shift')), 1)
        self.assertEqual(module().merge_settings(got), got)

    def test_modern_action_ids_and_legacy_conflicts_in_both_arrays(self):
        src = {'profiles':{'list':[{}, {'hidden':True}, {}]}, 'actions':[
            {'id':'User.Paste','command':'paste'},
            {'command':'find','keys':['ctrl+1','ctrl+shift+f']},
            {'id':'User.Fullscreen','command':'toggleFullscreen'}], 'keybindings':[
            {'id':'User.Paste','keys':['ctrl+v','shift+insert']},
            {'id':'User.Fullscreen','keys':['alt+enter','f11']},
            {'id':'User.Paste','keys':'alt+shift+1'}]}
        got = module().merge_settings(src)
        self.assertEqual(binding(got,'shift+insert'), 'paste')
        self.assertEqual(binding(got,'f11'), 'toggleFullscreen')
        self.assertEqual(binding(got,'ctrl+shift+f'), 'find')
        self.assertEqual(binding(got,'alt+enter'), 'unbound')
        self.assertEqual(binding(got,'ctrl+1'), {'action':'sendInput','input':'\x1b[49;5u'})
        self.assertEqual(binding(got,'ctrl+shift+2'), {'action':'newTab','index':1})
        self.assertIsNone(binding(got,'ctrl+shift+3'))
        self.assertEqual(module().merge_settings(got), got)

    def test_nine_profiles_only_maps_first_eight(self):
        got = module().merge_settings({'profiles':{'list':[{} for _ in range(12)]}, 'keybindings':[]})
        self.assertEqual(binding(got,'ctrl+shift+8'), {'action':'newTab','index':7})
        self.assertIsNone(binding(got,'ctrl+shift+9'))

    def test_existing_color_overrides_cannot_shadow_shared_palette(self):
        got = module().merge_settings({'profiles': {
            'defaults': {'cursorColor':'#123456', 'foreground':'#987654', 'acrylicOpacity':0.72},
            'list': [{'cursorColor':'#345678', 'selectionBackground':'#654321',
                      'background':'#111111', 'fontSize':15}]}})
        defaults = got['profiles']['defaults']
        profile = got['profiles']['list'][0]
        self.assertEqual(defaults['cursorColor'], '#FFFFFF')
        self.assertEqual(defaults['foreground'], '#F8F8F2')
        self.assertEqual(defaults['opacity'], 90)
        self.assertEqual(profile['selectionBackground'], '#5B4B8A')
        self.assertEqual(profile['background'], '#0A0118')
        self.assertEqual(profile['cursorColor'], '#FFFFFF')
        self.assertEqual(profile['fontSize'],15)

    def test_plain_transparency_overrides_acrylic_and_inactive_profile_settings(self):
        got = module().merge_settings({'profiles': {
            'defaults': {'opacity':75, 'useAcrylic':True, 'acrylicOpacity':0.5,
                         'unfocusedAppearance':{'opacity':60, 'useAcrylic':True}},
            'list': [{'opacity':100, 'useAcrylic':True, 'acrylicOpacity':0.8,
                      'unfocusedAppearance':{'opacity':50, 'useAcrylic':True, 'cursorColor':'#AABBCC'}}]}})
        defaults = got['profiles']['defaults']
        profile = got['profiles']['list'][0]
        for appearance in (defaults, profile, defaults['unfocusedAppearance'], profile['unfocusedAppearance']):
            self.assertEqual(appearance['opacity'], 90)
            self.assertFalse(appearance['useAcrylic'])
            self.assertNotIn('acrylicOpacity', appearance)
        self.assertEqual(profile['unfocusedAppearance']['cursorColor'], '#AABBCC')
        self.assertEqual(module().merge_settings(got), got)

    def test_selected_application_theme_disables_mica_without_changing_other_themes(self):
        other = {'name':'Frosted', 'window':{'useMica':True}}
        got = module().merge_settings({'theme':'Frosted', 'themes':[other]})
        self.assertEqual(got['themes'][0], other)
        selected = next(theme for theme in got['themes'] if theme['name'] == got['theme'])
        self.assertFalse(selected['window']['useMica'])
        self.assertEqual(selected['window']['applicationTheme'], 'dark')
        self.assertEqual(module().merge_settings(got), got)

    def test_custom_new_tab_menu_preserves_profile_chords_instead_of_guessing(self):
        for menu in [
            [{'type':'profile', 'profile':'{one}'}],
            [{'type':'profile', 'profile':'{four}'}, {'type':'remainingProfiles'}],
            [{'type':'folder', 'name':'WSL', 'entries':[{'type':'matchProfiles', 'source':'Windows.Terminal.Wsl'}]}],
        ]:
            src = {'profiles':{'list':[{'guid':'{one}'},{'guid':'{two}'},
                                       {'guid':'{three}'},{'guid':'{four}'}]},
                   'newTabMenu':menu, 'actions':[
                       {'command':'find','keys':'ctrl+shift+4'},
                       {'command':{'action':'newTab','profile':'{four}'},'keys':'ctrl+shift+1'}]}
            got = module().merge_settings(src)
            self.assertEqual(got['newTabMenu'],menu)
            self.assertEqual(binding(got,'ctrl+shift+4'),'find')
            self.assertEqual(binding(got,'ctrl+shift+1'),{'action':'newTab','profile':'{four}'})
            self.assertIsNone(binding(got,'ctrl+shift+2'))
            self.assertEqual(module().merge_settings(got),got)

    def test_explicit_default_new_tab_menu_maps_existing_profiles(self):
        got = module().merge_settings({'profiles':{'list':[{},{}]},
                                       'newTabMenu':[{'type':'remainingProfiles'}]})
        self.assertEqual(binding(got,'ctrl+shift+2'),{'action':'newTab','index':1})
        self.assertIsNone(binding(got,'ctrl+shift+3'))

    def test_legacy_profile_array_preserved(self):
        got = module().merge_settings({'profiles':[{'guid':'abc','commandline':'pwsh.exe'}]})
        self.assertEqual(got['profiles'][0]['guid'], 'abc')
        self.assertEqual(got['profiles'][0]['commandline'], 'pwsh.exe')
        self.assertEqual(got['profiles'][0]['font']['face'], 'JetBrainsMono Nerd Font Mono')

    def test_invalid_input_never_replaces_or_backs_up(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'settings.json'
            for text in ['{"profiles": ', '{"profiles":{"list":42}}', '{"actions":{}}']:
                p.write_text(text)
                run = subprocess.run([sys.executable,str(SCRIPT),'--settings',str(p),'--apply'],capture_output=True,text=True)
                self.assertNotEqual(run.returncode,0)
                self.assertEqual(p.read_text(),text)
                self.assertEqual(list(Path(d).iterdir()),[p])

    def test_discovery_finds_store_or_unpacked_with_ascii_and_unicode_spaces(self):
        for prefix in ('Windows user ', 'Windows Bjørn 用户 '):
            with tempfile.TemporaryDirectory(prefix=prefix) as d:
                root = Path(d)
                bin_dir = root / 'bin'
                bin_dir.mkdir()
                cmd = bin_dir / 'cmd.exe'
                cmd.write_text('#!/usr/bin/python3\nimport os,sys\n'
                               'encoding = "utf-16le" if "/u" in [a.lower() for a in sys.argv] else "cp850"\n'
                               'sys.stdout.buffer.write((os.environ["FAKE_LOCALAPPDATA"] + "\\r\\n").encode(encoding, errors="replace"))\n')
                wslpath = bin_dir / 'wslpath'
                wslpath.write_text('#!/bin/sh\nprintf "%s\\n" "$2"\n')
                cmd.chmod(0o755)
                wslpath.chmod(0o755)
                env = {**os.environ,'PATH':str(bin_dir),'FAKE_LOCALAPPDATA':d}
                for relative in ['Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json', 'Microsoft/Windows Terminal/settings.json']:
                    p = root / relative
                    p.parent.mkdir(parents=True,exist_ok=True)
                    p.write_text('{"profiles":{"list":[]}}')
                    run = subprocess.run([sys.executable,str(SCRIPT)],capture_output=True,text=True,env=env)
                    self.assertEqual(run.returncode,0,run.stderr)
                    self.assertIn(str(p),run.stdout)
                    p.unlink()
                run = subprocess.run([sys.executable,str(SCRIPT)],capture_output=True,text=True,env=env)
                self.assertNotEqual(run.returncode,0)
                self.assertIn('--settings',run.stderr)


if __name__ == '__main__':
    unittest.main()
