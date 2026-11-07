#!/usr/bin/env python3
"""Merge portable UI/edit preferences, never account or provider configuration.

Python 3.11+; standard library only. Merge functions return content for callers
with their own transaction support. The CLI previews paths by default and makes
each changed file atomic with a private backup when --apply is explicit.
Changed TOML is reserialized (comments/formatting normalize); all unrelated
parsed values survive, including inline tables, arrays, dates, and providers.
Already matching files are returned byte-for-byte, avoiding repeated backups.
"""
import argparse
import datetime
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import tomllib
import uuid

CODEX_STATUS_LINE = [
    'model-with-reasoning', 'current-dir', 'git-branch', 'run-state',
    'context-remaining', 'weekly-limit', 'context-window-size',
    'used-tokens', 'task-progress',
]


def _object(value, name):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object/table; refusing to replace it')
    return value


def _strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f'Invalid JSON constant: {value}')

    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)


def merge_claude_settings(text, statusline_command='claude-statusline'):
    """Set acceptEdits/statusLine, retaining all other settings and rule lists."""
    if not isinstance(statusline_command, str) or not statusline_command.strip():
        raise ValueError('The Claude status line command must be nonempty')
    data = _object(_strict_json(text) if text.strip() else {}, 'Claude settings')
    permissions = _object(data.get('permissions', {}), 'Claude permissions')
    statusline = _object(data.get('statusLine', {}), 'Claude statusLine')
    if (permissions.get('defaultMode') == 'acceptEdits'
            and statusline.get('type') == 'command'
            and statusline.get('command') == statusline_command):
        return text
    permissions['defaultMode'] = 'acceptEdits'
    statusline.update(type='command', command=statusline_command)
    data.update(permissions=permissions, statusLine=statusline)
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def _toml_value(value):
    """Serialize every value type produced by tomllib, with quoted table keys."""
    if isinstance(value, str):
        # JSON basic strings share TOML's escapes, except TOML bans raw DEL.
        # Keep astral Unicode as UTF-8: JSON's surrogate-pair escapes are not
        # Unicode scalar escapes and consequently are invalid TOML.
        return json.dumps(value, ensure_ascii=False).replace('\x7f', '\\u007f')
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return 'nan'
        return repr(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, list):
        return '[' + ', '.join(_toml_value(item) for item in value) + ']'
    if isinstance(value, dict):
        return '{ ' + ', '.join(f'{_toml_value(key)} = {_toml_value(item)}'
                                for key, item in value.items()) + ' }'
    raise ValueError(f'Cannot serialize TOML value of type {type(value).__name__}')


def merge_codex_config(text):
    """Set the approved sandbox/approval defaults and reference TUI appearance."""
    data = tomllib.loads(text)
    tui = _object(data.get('tui', {}), 'Codex tui')
    if (data.get('approval_policy') == 'on-request'
            and data.get('sandbox_mode') == 'workspace-write'
            and tui.get('status_line') == CODEX_STATUS_LINE
            and tui.get('status_line_use_colors') is True):
        return text
    data.update(approval_policy='on-request', sandbox_mode='workspace-write')
    tui.update(status_line=list(CODEX_STATUS_LINE), status_line_use_colors=True)
    data['tui'] = tui
    output = ''.join(f'{_toml_value(key)} = {_toml_value(value)}\n'
                     for key, value in data.items())
    # Fail closed if an unusual value cannot be represented as valid TOML.
    tomllib.loads(output)
    return output


def validate_config_path(path):
    """Reject linked/nonregular configs and linked parents, rather than retarget."""
    path = Path(path).expanduser().absolute()
    for directory in reversed(path.parents):
        if directory.is_symlink():
            raise ValueError(f'Refusing linked configuration directory: {directory}')
        if directory.exists() and not directory.is_dir():
            raise ValueError(f'Configuration parent is not a directory: {directory}')
    if path.is_symlink():
        raise ValueError(f'Refusing linked configuration file: {path}')
    try:
        info = path.lstat()
    except FileNotFoundError:
        return path
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError(f'Refusing nonregular or hardlinked configuration: {path}')
    return path


def preference_files(*, claude_home=None, codex_home=None,
                     statusline_command='claude-statusline'):
    """Return selected absolute config paths and merged content without writing.

    Homes are explicit so the caller decides between personal/work accounts.
    Every supplied config is validated before the caller receives any changes.
    """
    output = {}
    for home, name, merge in (
            (claude_home, 'settings.json',
             lambda text: merge_claude_settings(text, statusline_command)),
            (codex_home, 'config.toml', merge_codex_config)):
        if home is None:
            continue
        path = validate_config_path(Path(home) / name)
        text = path.read_text(encoding='utf-8') if path.exists() else ''
        output[path] = merge(text)
    return output


def _snapshot(path):
    validate_config_path(path)
    try:
        info = path.stat()
        return path.read_bytes(), stat.S_IMODE(info.st_mode), info.st_ino, info.st_dev
    except FileNotFoundError:
        return None


def _private_backup(path, original):
    backup = path.with_name(path.name + '.before-ai-preferences-' + uuid.uuid4().hex)
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        backup.unlink(missing_ok=True)
        raise
    return backup


def apply_preferences(files):
    """Atomically write changed files, backing up existing bytes privately.

    All paths are preflighted first; individual replacements are atomic. For a
    multi-file transaction/rollback use preference_files in the main installer.
    Returns (path, backup-or-None) pairs. Symlinks/hardlinks are never followed.
    """
    changes = []
    for name, text in files.items():
        path = validate_config_path(name)
        before = _snapshot(path)
        content = text.encode('utf-8')
        if before is None or before[0] != content:
            changes.append((path, before, content))
    applied = []
    for path, before, content in changes:
        # Detect intervening changes before creating directories or backups.
        if _snapshot(path) != before:
            raise ValueError(f'Configuration changed during preview: {path}')
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix='.ai-preferences-', dir=path.parent)
        temporary = Path(temporary)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, before[1] if before else 0o600)
            if _snapshot(path) != before:
                raise ValueError(f'Configuration changed before replacement: {path}')
            backup = _private_backup(path, before[0]) if before else None
            if _snapshot(path) != before:
                raise ValueError(f'Configuration changed after backup: {path}')
            os.replace(temporary, path)
            applied.append((path, backup))
        finally:
            temporary.unlink(missing_ok=True)
    return applied


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claude-home', type=Path, help='Explicit selected Claude config directory')
    parser.add_argument('--codex-home', type=Path, help='Explicit selected Codex config directory')
    parser.add_argument('--statusline-command', default='claude-statusline',
                        help='Claude shell command (default: claude-statusline on PATH)')
    parser.add_argument('--apply', action='store_true', help='Back up and atomically write changes')
    args = parser.parse_args(argv)
    if args.claude_home is None and args.codex_home is None:
        parser.error('Select --claude-home and/or --codex-home explicitly')
    try:
        files = preference_files(claude_home=args.claude_home, codex_home=args.codex_home,
                                 statusline_command=args.statusline_command)
        for path, text in files.items():
            changed = not path.exists() or path.read_bytes() != text.encode('utf-8')
            print(f'{"Update" if changed else "Unchanged"}: {path}')
        if args.apply:
            for path, backup in apply_preferences(files):
                print(f'Applied: {path}' + (f' (backup: {backup})' if backup else ''))
        else:
            print('Preview only; use --apply to write these preferences.')
    except (ValueError, OSError) as exc:
        print(f'AI preferences: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
