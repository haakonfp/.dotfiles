#!/usr/bin/env python3
"""Complete explicitly selected work profiles, preserving existing account state."""
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import uuid

from ai_preferences import apply_preferences, merge_personal_codex_config, preference_files, validate_config_path
from migrate_claude_profile import migrate_legacy_claude


def profile_files(home):
    return {
        'claude': (home / '.claude-epic/settings.json', home / '.claude-epic/gateway-helper-config.json'),
        'codex': (home / '.codex-epic/config.toml', home / '.codex-epic/claude-gateway.json'),
    }


def validate_profiles(profiles):
    for paths in profiles.values():
        for path in paths:
            validate_config_path(path)
            if path.exists():
                try:
                    text = path.read_text()
                    json.loads(text) if path.suffix == '.json' else tomllib.loads(text)
                except (ValueError, UnicodeError):
                    raise ValueError(f'Partial or invalid Epic profile config: {path}') from None


def backup_profile(home, name, paths):
    existing = [path for path in paths if path.is_file()]
    if not existing:
        return []
    snapshots = [(path, path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) for path in existing]
    target = home / '.local/state/dotfiles/epic-setup' / uuid.uuid4().hex / name
    validate_config_path(target / 'snapshot')
    target.mkdir(parents=True, mode=0o700)
    target.parent.chmod(0o700)
    for path, content, mode in snapshots:
        destination = target / path.name
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
    print(f'Existing Epic {name} configuration saved under {target}')
    return snapshots


def restore_complete_profile(snapshots):
    for path, content, mode in snapshots:
        validate_config_path(path)
        if path.is_file() and path.read_bytes() == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, name = tempfile.mkstemp(prefix='.gateway-restore-', dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(content)
                os.fchmod(stream.fileno(), mode)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def setup(home):
    profiles = profile_files(home)
    migrated = False
    if not all(path.is_file() for path in profiles['claude']):
        destination = home / '.claude-epic'
        # Tokens/logs can precede settings.json, and Codex can already share
        # that live gateway cache. Complete it in place instead of attempting
        # to merge or relocate a legacy account over it.
        occupied = destination.is_dir() and any(destination.iterdir())
        if occupied:
            print('Completing the existing Epic Claude profile in place; the default Claude profile is retained.')
        else:
            migration = migrate_legacy_claude(home, apply=True)
            if migration['status'] in ('blocked', 'failed'):
                raise ValueError(migration['reason'])
            migrated = migration['status'] == 'migrated'
            if migrated:
                print(migration['reason'])
                print('Recovery journal: ' + migration['journal'])
    validate_profiles(profiles)
    missing = {name: paths for name, paths in profiles.items() if not all(path.is_file() for path in paths)}
    for directory in (home / '.claude-epic', home / '.codex-epic'):
        directory.mkdir(exist_ok=True, mode=0o700)
    if missing:
        # Installation itself may rewrite client configs. Snapshot every existing
        # profile first and restore already-complete profiles even on failure.
        snapshots = {name: backup_profile(home, name, paths) for name, paths in profiles.items()}
        try:
            gateway = shutil.which('claude-gateway')
            if gateway is None:
                print('Installing Epic gateway into the selected profiles; this may request Epic SSO.')
                with tempfile.TemporaryDirectory(prefix='dotfiles-gateway-') as directory:
                    script = str(Path(directory) / 'install.sh')
                    subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location',
                                    '--proto', '=https', '--tlsv1.2',
                                    'https://artifacts.ol.epicgames.net/artifactory/ai-gateway/install.sh',
                                    '-o', script], check=True)
                    subprocess.run(['bash', script], check=True)
                gateway = shutil.which('claude-gateway')
            if gateway is None:
                raise ValueError('claude-gateway is missing after installation.')
            for name, paths in missing.items():
                if not all(path.is_file() for path in paths):
                    validate_profiles({name: paths})
                    subprocess.run([gateway, *(['run'] if name == 'claude' else ['codex', 'setup'])], check=True)
                absent = [str(path) for path in paths if not path.is_file()]
                if absent:
                    raise ValueError(f'Gateway did not create the Epic {name} profile. Missing: ' + ', '.join(absent))
                validate_profiles({name: paths})
        finally:
            for name in profiles.keys() - missing.keys():
                restore_complete_profile(snapshots[name])
    preferences = preference_files(claude_home=home / '.claude-epic', codex_home=home / '.codex-epic',
                                   statusline_command=shlex.quote(str(home / '.local/bin/claude-statusline')))
    if migrated:
        preferences.update(preference_files(claude_home=home / '.claude',
                                            statusline_command=shlex.quote(str(home / '.local/bin/claude-statusline'))))
    personal = validate_config_path(home / '.codex/config.toml')
    converted_personal = False
    if personal.is_file():
        original = personal.read_text()
        updated = merge_personal_codex_config(original, portkey_only=True)
        if updated != original:
            preferences[personal] = updated
            converted_personal = True
    apply_preferences(preferences)
    if converted_personal:
        print('Personal Codex now selects OpenAI/ChatGPT. Outside ~/dev/epic run: codex login')
    print('Epic profiles ready. Claude accepts edits; verify identity with claude-epic and codex-epic before working.')


def main():
    try:
        setup(Path.home())
    except subprocess.CalledProcessError as error:
        print(f'Epic setup: gateway/install command exited {error.returncode}; existing profile backups are retained.', file=sys.stderr)
        return error.returncode or 1
    except (ValueError, OSError) as error:
        print('Epic setup: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
