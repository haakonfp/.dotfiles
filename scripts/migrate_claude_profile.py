#!/usr/bin/env python3
"""Relocate a recognized legacy Epic Claude profile without merging accounts.

The public function defaults to a read-only preview. Its result has ``status``,
``reason``, ``source``, ``destination``, ``changed_paths`` and ``journal`` keys.
``blocked`` means preflight failed; ``failed`` means application failed (the
journal records whether rollback completed). Neither status permits setup to
continue. No authentication, gateway install, or Codex state is touched.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import stat
import tempfile
import uuid


CONFIG_FILES = (
    'settings.json', 'settings.local.json', 'gateway-helper-config.json',
    '.claude.json', 'plugins/installed_plugins.json', 'plugins/known_marketplaces.json',
)


def _safe_path(path, home):
    """Reject symlinks in an account/config/state path before following any."""
    for ancestor in reversed((path, *path.parents)):
        if ancestor.is_symlink():
            raise ValueError('symlinked path: ' + str(ancestor))
    if not path.is_relative_to(home):
        raise ValueError('path outside home')


def _read_config(path):
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('config is not a regular file: ' + str(path))
    original = path.read_bytes()
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('ambiguous duplicate JSON key')
            value[key] = item
        return value
    def reject_constant(value):
        raise ValueError('nonstandard JSON constant')
    try:
        value = json.loads(original, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (ValueError, UnicodeError):
        raise ValueError('invalid JSON: ' + str(path)) from None
    return original, stat.S_IMODE(path.stat().st_mode), value


def _gateway_owned(value):
    # A mention in documentation or an allowed shell command is not proof that
    # the account uses this provider. Only its credential helper is decisive.
    helper = value.get('apiKeyHelper') if isinstance(value, dict) else None
    if not isinstance(helper, str):
        return False
    try:
        words = shlex.split(helper)
    except ValueError:
        return False
    return bool(words) and Path(words[0]).name in ('claude-gateway', 'claude-gateway.exe')


def _rewrite(value, source, destination):
    def relocate(text):
        for old, new in ((str(source), str(destination)), ('~/.claude', '~/.claude-epic')):
            # Match a path token, including paths embedded in shell commands.
            pattern = r'(?<![\w./~-])' + re.escape(old) + r'(?=/|$|[\s\x22\x27])'
            text = re.sub(pattern, lambda match: new, text)
        return text
    if isinstance(value, str):
        return relocate(value)
    if isinstance(value, list):
        return [_rewrite(item, source, destination) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key = relocate(key)
            if key in result:
                raise ValueError('rewritten JSON keys would collide')
            result[key] = _rewrite(item, source, destination)
        return result
    return value


def _atomic_write(path, content, mode):
    descriptor, name = tempfile.mkstemp(prefix='.ai-migration-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def _private_directory(path, home):
    _safe_path(path, home)
    if path.exists():
        if not path.is_dir():
            raise ValueError('state path is not a directory: ' + str(path))
        # Existing ancestors such as ~/.local are not ours to chmod.
        return
    if path != home:
        _private_directory(path.parent, home)
    path.mkdir(mode=0o700)


def migrate_legacy_claude(home: Path, apply=False):
    """Preview/apply a whole-profile rename; return a secret-free result dict.

    Only the known JSON config files are parsed. Credential files and session
    trees move with their directory and are never read. Rewritten configs have
    exact original-byte backups in a private recovery directory. Run with Claude
    stopped; the helper does not coordinate concurrent Claude writes.
    """
    home = Path(os.path.abspath(home))
    source, destination = home / '.claude', home / '.claude-epic'
    sidecar = home / '.claude.json'
    result = dict(status='not-needed', reason='No legacy gateway-owned Claude profile.',
                  source=str(source), destination=str(destination), changed_paths=[], journal=None)
    configs = []
    empty_destination_mode = None
    try:
        _safe_path(source, home)
        _safe_path(destination, home)
        if not source.exists():
            return result
        if not source.is_dir():
            raise ValueError('legacy Claude profile is not a directory')
        marker = source / 'gateway-helper-config.json'
        settings = source / 'settings.json'
        for path in (marker, settings):
            _safe_path(path, home)
        recognized = marker.is_file()
        if settings.exists():
            data = _read_config(settings)[2]
            # An explicitly reconciled personal profile can retain an inert
            # legacy helper/cache on disk. Never move its new personal login.
            if isinstance(data, dict) and data.get('forceLoginMethod') == 'claudeai' and not _gateway_owned(data):
                return result
            recognized = _gateway_owned(data) or recognized
        if not recognized:
            return result
        if destination.exists():
            if not destination.is_dir() or any(destination.iterdir()):
                raise ValueError('Epic Claude destination is not an empty directory')
            empty_destination_mode = stat.S_IMODE(destination.stat().st_mode)
        _safe_path(sidecar, home)
        if sidecar.exists() and (source / '.claude.json').exists():
            raise ValueError('both legacy Claude sidecar locations exist')
        for relative in CONFIG_FILES:
            path = source / relative
            _safe_path(path, home)
            if path.exists():
                original, mode, value = _read_config(path)
                updated = _rewrite(value, source, destination)
                content = original if updated == value else (json.dumps(updated, ensure_ascii=False, indent=2) + '\n').encode()
                configs.append((path, destination / relative, original, mode, content))
        if sidecar.exists():
            original, mode, value = _read_config(sidecar)
            updated = _rewrite(value, source, destination)
            content = original if updated == value else (json.dumps(updated, ensure_ascii=False, indent=2) + '\n').encode()
            configs.append((sidecar, destination / '.claude.json', original, mode, content))
        state = home / '.local/state/dotfiles/ai-migrations'
        _safe_path(state, home)
        for parent in (home, source, *{item[0].parent for item in configs}, state):
            existing = parent
            while not existing.exists():
                existing = existing.parent
            if not existing.is_dir() or not os.access(existing, os.W_OK | os.X_OK):
                raise PermissionError('migration directory is not writable')
        result['changed_paths'] = [str(destination)]
        if sidecar.exists():
            result['changed_paths'].append(str(sidecar))
        result['changed_paths'].extend(str(new) for old, new, original, mode, content in configs if content != original)
        result.update(status='preview', reason='Recognized legacy gateway-owned Claude profile; migration ready.')
    except (OSError, ValueError) as error:
        result.update(status='blocked', reason=str(error) if isinstance(error, ValueError) else 'Migration preflight failed: ' + type(error).__name__)
        return result
    if not apply:
        return result

    journal, journal_path = None, None
    moved_profile = moved_sidecar = removed_empty = False
    written = []
    try:
        _private_directory(state, home)
        recovery = state / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex)
        recovery.mkdir(mode=0o700)
        backup_dir = recovery / 'backups'
        backup_dir.mkdir(mode=0o700)
        journal_path = recovery / 'journal.json'
        result['journal'] = str(journal_path)
        journal = dict(version=1, status='prepared', source=str(source), destination=str(destination),
                       destination_was_empty=empty_destination_mode is not None,
                       moves=[dict(source=str(source), destination=str(destination), applied=False)], backups=[])
        if sidecar.exists():
            journal['moves'].append(dict(source=str(sidecar), destination=str(destination / '.claude.json'), applied=False))
        for index, (old, new, original, mode, content) in enumerate(configs):
            backup = backup_dir / f'{index:03d}.json'
            _atomic_write(backup, original, 0o600)
            journal['backups'].append(dict(original=str(old), destination=str(new), backup=str(backup), mode=mode))
        def save_journal():
            _atomic_write(journal_path, (json.dumps(journal, indent=2) + '\n').encode(), 0o600)
        save_journal()
        if empty_destination_mode is not None:
            destination.rmdir()
            removed_empty = True
        source.rename(destination)
        moved_profile = True
        journal['moves'][0]['applied'] = True
        save_journal()
        if sidecar.exists():
            sidecar.rename(destination / '.claude.json')
            moved_sidecar = True
            journal['moves'][1]['applied'] = True
            save_journal()
        for old, new, original, mode, content in configs:
            if content != original:
                _atomic_write(new, content, mode)
                written.append((new, original, mode))
        journal['status'] = 'migrated'
        save_journal()
        result.update(status='migrated', reason='Legacy Epic Claude profile migrated; original config backups retained.')
    except (OSError, ValueError) as error:
        rollback_errors = []
        # Restore bytes before reversing moves, then put the complete tree back.
        for path, original, mode in reversed(written):
            try:
                _atomic_write(path, original, mode)
            except OSError:
                rollback_errors.append('config restore failed')
        if moved_sidecar:
            try:
                (destination / '.claude.json').rename(sidecar)
            except OSError:
                rollback_errors.append('sidecar restore failed')
        if moved_profile:
            try:
                destination.rename(source)
            except OSError:
                rollback_errors.append('profile restore failed')
        if removed_empty and not destination.exists():
            try:
                destination.mkdir(mode=empty_destination_mode)
                destination.chmod(empty_destination_mode)
            except OSError:
                rollback_errors.append('empty destination restore failed')
        if journal_path and journal:
            journal.update(status='rollback-incomplete' if rollback_errors else 'rolled-back',
                           error_type=type(error).__name__, rollback_errors=rollback_errors)
            try:
                _atomic_write(journal_path, (json.dumps(journal, indent=2) + '\n').encode(), 0o600)
            except OSError:
                rollback_errors.append('journal update failed')
        result.update(status='failed', reason='Migration failed: ' + type(error).__name__ +
                      ('; recovery requires journal review.' if rollback_errors else '; changes rolled back.'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--apply', action='store_true', help='Apply the migration (default: preview only).')
    args = parser.parse_args()
    result = migrate_legacy_claude(args.home, apply=args.apply)
    print(json.dumps(result))
    return 1 if result['status'] in ('blocked', 'failed') else 0


if __name__ == '__main__':
    raise SystemExit(main())
