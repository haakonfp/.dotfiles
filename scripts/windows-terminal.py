#!/usr/bin/env python3
"""Preview/merge Agamotto into Windows Terminal. Uses only Python's standard library.

JSONC is parsed lexically; apply writes normalized JSON and saves the original,
including comments, in an adjacent timestamped backup. Profile identities,
commands, ordering and unrelated settings are retained.
"""
import argparse
import copy
import difflib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

SCHEME = {
    'name': 'Agamotto', 'background': '#0A0118', 'foreground': '#F8F8F2',
    'selectionBackground': '#5B4B8A', 'cursorColor': '#FFFFFF',
    'black': '#0A0118', 'red': '#FF4D6D', 'green': '#33FF44',
    'yellow': '#FFEB66', 'blue': '#829BFF', 'purple': '#BD93F9',
    'cyan': '#8BE9FD', 'white': '#F8F8F2', 'brightBlack': '#57517A',
    'brightRed': '#FF708C', 'brightGreen': '#33FF44', 'brightYellow': '#FFFFA5',
    'brightBlue': '#ADBDFF', 'brightPurple': '#FF92DF',
    'brightCyan': '#A4FFFF', 'brightWhite': '#FFFFFF',
}
FONT = 'JetBrainsMono Nerd Font Mono'


def transparency(profile, defaults=False):
    legacy = 'acrylicOpacity' in profile
    profile.pop('acrylicOpacity', None)
    for key, value in [('opacity', 90), ('useAcrylic', False)]:
        if defaults or legacy or key in profile:
            profile[key] = value
    unfocused = profile.get('unfocusedAppearance')
    if unfocused is not None:
        if not isinstance(unfocused, dict):
            raise ValueError('unfocusedAppearance must be an object or null')
        transparency(unfocused)


def parse_jsonc(source):
    """Strip only lexical comments/trailing commas, never string contents."""
    chars = list(source.lstrip('\ufeff'))
    inside = escaped = False
    i = 0
    while i < len(chars):
        c = chars[i]
        if inside:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                inside = False
        elif c == '"':
            inside = True
        elif c == '/' and i + 1 < len(chars) and chars[i + 1] in '/*':
            block = chars[i + 1] == '*'
            start = i
            i += 2
            if block:
                while i + 1 < len(chars) and ''.join(chars[i:i+2]) != '*/':
                    i += 1
                if i + 1 >= len(chars):
                    raise ValueError('Unterminated JSONC block comment')
                i += 2
            else:
                while i < len(chars) and chars[i] not in '\r\n':
                    i += 1
            for j in range(start, i):
                if chars[j] not in '\r\n':
                    chars[j] = ' '
            continue
        i += 1
    inside = escaped = False
    for i, c in enumerate(chars):
        if inside:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                inside = False
        elif c == '"':
            inside = True
        elif c == ',':
            j = i + 1
            while j < len(chars) and chars[j].isspace():
                j += 1
            if j < len(chars) and chars[j] in ']}':
                chars[i] = ' '

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(''.join(chars), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f'Invalid JSON constant {value}')))


def normalized_key(key):
    return '+'.join(sorted(key.lower().split('+')))


def appearance(profile, defaults=False):
    # Change existing appearance overrides too, while preserving size,
    # OpenType features, padding and other machine-specific profile properties.
    for key, value in [('colorScheme', 'Agamotto'), ('cursorShape', 'underscore')]:
        if defaults or key in profile:
            profile[key] = value
    for key in ['foreground', 'background', 'selectionBackground', 'cursorColor']:
        if key in profile:
            profile[key] = SCHEME[key]
    if defaults or 'font' in profile or 'fontFace' in profile or 'fontWeight' in profile:
        font = profile.setdefault('font', {})
        if not isinstance(font, dict):
            raise ValueError('Profile font must be an object')
        font.update(face=FONT, weight='medium')
        for key, value in [('fontFace', FONT), ('fontWeight', 'medium')]:
            if key in profile:
                profile[key] = value
    transparency(profile, defaults)


def merge_settings(source):
    if not isinstance(source, dict):
        raise ValueError('Settings must be a JSON object')
    settings = copy.deepcopy(source)
    # Mica sits underneath terminal panes, so it must be off as well as acrylic
    # for plain transparency. Select our theme without modifying other themes.
    themes = settings.setdefault('themes', [])
    if not isinstance(themes, list) or any(not isinstance(theme, dict) for theme in themes):
        raise ValueError('themes must be an array of objects')
    matching_themes = [theme for theme in themes if theme.get('name') == 'Agamotto']
    if len(matching_themes) > 1:
        raise ValueError('Duplicate Agamotto application themes; resolve these before merging')
    if matching_themes:
        app_theme = matching_themes[0]
    else:
        app_theme = {'name': 'Agamotto'}
        themes.append(app_theme)
    window = app_theme.setdefault('window', {})
    if not isinstance(window, dict):
        raise ValueError('Application theme window must be an object')
    window.update(applicationTheme='dark', useMica=False)
    settings['theme'] = 'Agamotto'
    profiles = settings.setdefault('profiles', {})
    if isinstance(profiles, dict):
        listed = profiles.setdefault('list', [])
        defaults = profiles.setdefault('defaults', {})
        if not isinstance(defaults, dict):
            raise ValueError('profiles.defaults must be an object')
        appearance(defaults, True)
    elif isinstance(profiles, list):
        listed = profiles
    else:
        raise ValueError('profiles must be an object or legacy array')
    if not isinstance(listed, list) or any(not isinstance(p, dict) for p in listed):
        raise ValueError('profiles.list must be an array of profile objects')
    for profile in listed:
        appearance(profile, isinstance(profiles, list))
    schemes = settings.setdefault('schemes', [])
    if not isinstance(schemes, list) or any(not isinstance(s, dict) for s in schemes):
        raise ValueError('schemes must be an array of objects')
    matching = [s for s in schemes if s.get('name') == 'Agamotto']
    if len(matching) > 1:
        raise ValueError('Duplicate Agamotto schemes; resolve these before merging')
    if matching:
        matching[0].update(SCHEME)
    else:
        schemes.append(copy.deepcopy(SCHEME))
    actions = settings.setdefault('actions', [])
    modern = 'keybindings' in settings
    for field in ['actions', 'keybindings']:
        if field in settings and (not isinstance(settings[field], list) or
                                 any(not isinstance(a, dict) for a in settings[field])):
            raise ValueError(f'{field} must be an array of objects')
    desired = {}
    for i in range(1, 10):
        desired[f'alt+{i}'] = 'unbound'
        desired[f'ctrl+{i}'] = {'action': 'sendInput', 'input': f'\x1b[{48+i};5u'}
        desired[f'alt+shift+{i}'] = {'action': 'switchToTab', 'index': i - 1 if i < 9 else 4294967295}
    # A custom menu can filter/reorder/nest dynamic profiles. Preserve its
    # profile-number chords rather than invent runtime dropdown indices.
    standard_menu = settings.get('newTabMenu', [{'type': 'remainingProfiles'}]) == [{'type': 'remainingProfiles'}]
    count = sum(not p.get('hidden', False) for p in listed) if standard_menu else 0
    for i in range(1, min(8, count) + 1):
        desired[f'ctrl+shift+{i}'] = {'action': 'newTab', 'index': i - 1}
    desired.update({
        'ctrl+c': 'unbound', 'ctrl+v': 'unbound', 'ctrl+w': 'unbound',
        'ctrl+shift+c': {'action': 'copy', 'singleLine': False},
        'ctrl+shift+v': 'paste', 'ctrl+shift+w': 'closePane',
        'alt+enter': 'unbound',
        'shift+enter': {'action': 'sendInput', 'input': '\x1b[13;2u'},
        'alt+shift+enter': {'action': 'sendInput', 'input': '\x1b[13;4u'},
    })
    touched = {normalized_key(k) for k in desired}
    # Strip only conflicting chords, including duplicates and mixed key arrays.
    # Keep named action definitions so unrelated ID references remain valid.
    for field in ['actions', 'keybindings']:
        if field not in settings:
            continue
        kept = []
        for entry in settings[field]:
            if 'keys' not in entry:
                kept.append(entry)
                continue
            keys = entry['keys']
            choices = keys if isinstance(keys, list) else [keys]
            if any(not isinstance(k, str) for k in choices):
                raise ValueError('Action keys must be strings or arrays of strings')
            remaining = [k for k in choices if normalized_key(k) not in touched]
            if remaining:
                entry['keys'] = remaining if isinstance(keys, list) else remaining[0]
                kept.append(entry)
            elif 'command' in entry and 'id' in entry:
                del entry['keys']
                kept.append(entry)
        settings[field] = kept
    actions = settings['actions']
    for key, command in desired.items():
        if not modern:
            actions.append({'command': command, 'keys': key})
            continue
        if command == 'unbound':
            action_id = 'unbound'
        else:
            action_id = 'Dotfiles.Agamotto.' + key.replace('+', '.')
            existing = [a for a in actions if a.get('id') == action_id]
            if existing and (len(existing) != 1 or existing[0].get('command') != command):
                raise ValueError(f'Conflicting reserved action ID: {action_id}')
            if not existing:
                actions.append({'id': action_id, 'command': command})
        settings['keybindings'].append({'id': action_id, 'keys': key})
    return settings


def discover_settings():
    if os.name == 'nt':
        local = Path(os.environ['LOCALAPPDATA'])
    else:
        try:
            # CMD /U fixes the pipe encoding independently of Windows' OEM code page.
            result = subprocess.run(['cmd.exe', '/u', '/d', '/c', 'echo %LOCALAPPDATA%'],
                                    capture_output=True, check=True, timeout=15)
            windows_path = result.stdout.decode('utf-16le').strip()
            if not windows_path or '%' in windows_path:
                raise ValueError('Windows LOCALAPPDATA is unavailable')
            local = Path(subprocess.run(['wslpath', '-u', windows_path], capture_output=True,
                                        text=True, check=True, timeout=15).stdout.strip())
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            raise ValueError('Cannot discover Windows Terminal settings; use --settings PATH (WSL requires cmd.exe and wslpath)') from e
    candidates = [local / 'Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json',
                  local / 'Microsoft/Windows Terminal/settings.json',
                  local / 'Packages/Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe/LocalState/settings.json',
                  local / 'Microsoft/Windows Terminal Preview/settings.json']
    for path in candidates:
        if path.is_file():
            return path
    raise ValueError('Windows Terminal settings not found; start Terminal once or use --settings PATH. No file was created.')


def font_status():
    """Read-only installed-family check through the host; never installs during preview."""
    powershell = shutil.which('powershell.exe')
    if not powershell:
        return 'Host font detection unavailable here. Run windows/Install-Fonts.ps1 -Check on Windows.'
    command = "Add-Type -AssemblyName System.Drawing; $fonts = New-Object System.Drawing.Text.InstalledFontCollection; try { if (@($fonts.Families | Where-Object { $_.Name -eq 'JetBrainsMono Nerd Font Mono' -or $_.Name -eq 'JetBrainsMono NFM' }).Count -gt 0) { 'present' } else { 'missing' } } finally { $fonts.Dispose() }"
    try:
        result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-Command', command],
                                capture_output=True, text=True, check=True, timeout=20)
        if result.stdout.strip() == 'present':
            return f'Host font family detected: {FONT}. Restart Terminal after a font update.'
    except (OSError, subprocess.SubprocessError):
        return 'Host font detection failed. Run windows/Install-Fonts.ps1 -Check on Windows.'
    return 'Host font missing: run scripts/install-fonts.sh --windows from WSL, then restart Terminal.'


def apply_settings(path, original, rendered):
    if path.is_symlink():
        raise ValueError('Refusing to replace a settings symlink; pass its resolved target explicitly')
    backup = path.with_name(path.name + f'.bak.{time.time_ns()}')
    # Stage before touching the original; retain the exact original bytes in backup.
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', delete=False) as handle:
            temp_name = handle.name
            handle.write(rendered.encode('utf-8'))
            handle.flush()
            os.fsync(handle.fileno())
        shutil.copymode(path, temp_name)
        if path.read_bytes() != original:
            raise ValueError('Settings changed during merge; retry with the current file')
        with backup.open('xb') as handle:
            handle.write(original)
        shutil.copystat(path, backup)
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, help='Existing settings.json path (otherwise discover normal Windows installs)')
    parser.add_argument('--apply', action='store_true', help='Back up and apply; default prints a zero-write preview')
    args = parser.parse_args()
    try:
        path = args.settings if args.settings is not None else discover_settings()
        original = path.read_bytes()
        text = original.decode('utf-8-sig')
        source = parse_jsonc(text)
        merged = merge_settings(source)
        print(f'{"Apply" if args.apply else "Preview"}: {path}')
        if source.get('newTabMenu', [{'type': 'remainingProfiles'}]) != [{'type': 'remainingProfiles'}]:
            print('Custom newTabMenu: preserving existing Ctrl+Shift+number profile shortcuts; verify these against the Windows dropdown.')
        if merged == source:
            print('Already configured; no changes or backup needed.')
        else:
            rendered = json.dumps(merged, indent=4, ensure_ascii=False) + '\n'
            print(''.join(difflib.unified_diff(text.splitlines(True), rendered.splitlines(True),
                                             fromfile=str(path), tofile='merged settings')), end='')
            print('Apply normalizes JSONC to JSON; original comments are retained in the backup.')
            if args.apply:
                print(f'Backup: {apply_settings(path, original, rendered)}')
        print(font_status())
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f'windows-terminal: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
