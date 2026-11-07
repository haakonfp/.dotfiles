#!/usr/bin/env python3
"""Install the pinned sidebar's generated hooks into selected agent profiles."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import tomllib

from ai_preferences import _object, _strict_json, _toml_value, apply_preferences, validate_config_path


def command_identity(handler):
    if handler.get('type') != 'command':
        return None
    command = handler.get('command', '')
    try:
        words = shlex.split(command)
    except ValueError:
        return command
    # The generator uses bash + an absolute script path. Normalize quoting and
    # symlink aliases so a manually installed equivalent is not added twice.
    if len(words) >= 2 and Path(words[0]).name == 'bash':
        words[0] = 'bash'
        words[1] = str(Path(words[1]).expanduser().resolve())
    return tuple(words)


def matcher_identity(group):
    matcher = group.get('matcher', '')
    return '' if matcher in ('', '*', None) else matcher


def validate_hooks(document):
    data = _object(document, 'Hook config')
    events = _object(data.get('hooks', {}), 'Hook events')
    for event, groups in events.items():
        if not isinstance(groups, list):
            raise ValueError(f'Hook event {event} must be an array')
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get('hooks'), list):
                raise ValueError(f'Hook group in {event} must contain an array of handlers')
            if any(not isinstance(handler, dict) for handler in group['hooks']):
                raise ValueError(f'Hook handlers in {event} must be objects')
    return events


def merge_hooks(existing, snippet, inline=None):
    validate_hooks(existing)
    additions = validate_hooks(snippet)
    inline = inline or {}
    merged = deepcopy(existing)
    output = merged.setdefault('hooks', {})
    for event, groups in additions.items():
        external = inline.get(event, [])
        if not isinstance(external, list):
            raise ValueError(f'Inline hook event {event} must be an array')
        for addition in groups:
            matcher = matcher_identity(addition)
            current = output.get(event, [])
            present = {command_identity(handler)
                       for group in [*current, *external] if matcher_identity(group) == matcher
                       for handler in group.get('hooks', []) if handler.get('type') == 'command'}
            missing = [handler for handler in addition['hooks'] if command_identity(handler) not in present]
            if not missing:
                continue
            target = next((group for group in current if matcher_identity(group) == matcher), None)
            if target is None:
                target = dict(deepcopy(addition), hooks=[])
                output.setdefault(event, []).append(target)
            target['hooks'].extend(deepcopy(missing))
    return merged


def json_content(original, data):
    return original if original and _strict_json(original) == data else json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def hook_files(home, *, epic=False):
    """Plan every selected file before writes; work hooks require ready profiles."""
    home = Path(home)
    plugin = home / '.local/share/tmux/plugins/tmux-agent-sidebar'
    binary = plugin / 'bin/tmux-agent-sidebar'
    if not binary.is_file() or not (plugin / 'hook.sh').is_file():
        raise ValueError('Sidebar is not installed. Run bootstrap or scripts/install-tmux-plugins first.')
    generated = _strict_json(subprocess.run([str(binary), 'setup'], check=True, capture_output=True,
                                            text=True, timeout=30).stdout)
    if Path(generated.get('hook_script', '')).resolve() != (plugin / 'hook.sh').resolve():
        raise ValueError('Sidebar setup did not resolve its installed hook.sh')
    snippets = {agent: generated['agents'][agent]['snippet'] for agent in ('claude', 'codex')}
    for snippet in snippets.values():
        validate_hooks(snippet)
    homes = [('claude', home / '.claude'), ('codex', home / '.codex')]
    if epic:
        for agent, names in (('claude', ('settings.json', 'gateway-helper-config.json')),
                             ('codex', ('config.toml', 'claude-gateway.json'))):
            selected = home / f'.{agent}-epic'
            if all((selected / name).is_file() for name in names):
                homes.append((agent, selected))
    files = {}
    for agent, selected in homes:
        path = validate_config_path(selected / ('settings.json' if agent == 'claude' else 'hooks.json'))
        original = path.read_text() if path.is_file() else ''
        existing = _strict_json(original) if original.strip() else {}
        inline = None
        if agent == 'codex':
            config = validate_config_path(selected / 'config.toml')
            config_original = config.read_text() if config.is_file() else ''
            data = tomllib.loads(config_original)
            inline = _object(data.get('hooks', {}), 'Codex hooks')
            features = _object(data.get('features', {}), 'Codex features')
            features.pop('codex_hooks', None)
            features['hooks'] = True
            data['features'] = features
            files[config] = (config_original if data == tomllib.loads(config_original) else
                             ''.join(f'{_toml_value(key)} = {_toml_value(value)}\n' for key, value in data.items()))
        if agent == 'claude':
            plugins = _object(existing.get('enabledPlugins', {}), 'Claude enabled plugins')
            # Use one hook source: direct generated handlers. The old optional
            # sidebar plugin supplies the same hooks and would fire them twice.
            if plugins.get('tmux-agent-sidebar@hiroppy') is True:
                existing['enabledPlugins']['tmux-agent-sidebar@hiroppy'] = False
        files[path] = json_content(original, merge_hooks(existing, snippets[agent], inline))
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('omarchy', 'wsl'), required=True)
    parser.add_argument('--epic', action='store_true', help='Include already-configured WSL Epic profiles')
    parser.add_argument('--apply', action='store_true', help='Write with private backups; default is preview')
    args = parser.parse_args(argv)
    try:
        if args.epic and (args.profile != 'wsl' or 'microsoft' not in platform.release().lower()
                          or platform.freedesktop_os_release().get('ID') != 'ubuntu'):
            raise ValueError('--epic requires Ubuntu WSL')
        files = hook_files(Path.home(), epic=args.epic)
        for path, text in files.items():
            changed = not path.is_file() or path.read_text() != text
            print(f'{"Update" if changed else "Unchanged"}: {path}')
        if args.apply:
            for path, backup in apply_preferences(files):
                if backup:
                    print(f'Backup: {backup}')
            print('Sidebar hooks configured. Restart running agents; Codex may require one-time /hooks trust.')
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('Sidebar hooks: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
