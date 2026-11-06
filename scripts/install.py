#!/usr/bin/env python3
"""Preview and transactionally link the explicitly selected Stow-shaped packages."""
import argparse
import configparser
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
SHARED = ('bash', 'common', 'nvim', 'tmux', 'gitconfig', 'gh', 'starship')
MARKER = '# Managed by dotfiles; previous configuration stays local.\n'


def exists(path):
    return path.exists() or path.is_symlink()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ubuntu_wsl():
    try:
        ubuntu = any(line == 'ID=ubuntu' or line == 'ID="ubuntu"'
                     for line in Path('/etc/os-release').read_text().splitlines())
    except OSError:
        ubuntu = False
    return ubuntu and 'microsoft' in platform.release().lower()


def package_files(packages):
    for package in packages:
        root = REPO / package
        if not root.is_dir():
            raise ValueError(f'Missing package: {package}')
        for path in sorted(root.rglob('*')):
            if path.is_file() or path.is_symlink():
                if '.git' in path.relative_to(root).parts or '.bak' in path.name:
                    continue
                yield path.relative_to(root), path


def merge_ini(text, values):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    if text.strip():
        parser.read_string(text)
    for section, entries in values.items():
        if not parser.has_section(section):
            parser.add_section(section)
        for key, value in entries.items():
            parser[section][key] = value
    output = io.StringIO()
    parser.write(output, space_around_delimiters=False)
    return output.getvalue()


def desktop_preferences(home):
    """Only the preferences explicitly agreed in the design; no service changes."""
    userdirs = home / '.config/user-dirs.dirs'
    text = userdirs.read_text() if userdirs.is_file() else ''
    lines = text.splitlines()
    for key, value in [('XDG_DOWNLOAD_DIR', '$HOME/downloads'),
                       ('XDG_PICTURES_DIR', '$HOME/media/screenshots')]:
        lines = [line for line in lines if not line.lstrip().startswith(key + '=')]
        lines.append(f'{key}="{value}"')
    output = {'.config/user-dirs.dirs': '\n'.join(lines) + '\n'}
    bookmarks = home / '.config/gtk-3.0/bookmarks'
    text = bookmarks.read_text() if bookmarks.is_file() else ''
    entry = (home / 'downloads').as_uri() + ' Downloads'
    lines = text.splitlines()
    if not any(line.split(' ', 1)[0] == (home / 'downloads').as_uri() for line in lines):
        lines.append(entry)
    output['.config/gtk-3.0/bookmarks'] = '\n'.join(lines) + '\n'
    terminals = home / '.config/xdg-terminals.list'
    text = terminals.read_text() if terminals.is_file() else ''
    output['.config/xdg-terminals.list'] = 'foot.desktop\n' + '\n'.join(
        line for line in text.splitlines() if line.strip() != 'foot.desktop') + '\n'
    if shutil.which('brave') or shutil.which('brave-browser'):
        mime = home / '.config/mimeapps.list'
        text = mime.read_text() if mime.is_file() else ''
        output['.config/mimeapps.list'] = merge_ini(text, {'Default Applications': {
            'text/html': 'brave-browser.desktop',
            'x-scheme-handler/http': 'brave-browser.desktop',
            'x-scheme-handler/https': 'brave-browser.desktop',
        }})
        # Keep Omarchy's link-opening/focusing wrapper, not a browser profile.
        mime = home / '.config/hyprland-mimeapps.list'
        text = mime.read_text() if mime.is_file() else ''
        output['.config/hyprland-mimeapps.list'] = merge_ini(text, {'Default Applications': {
            'x-scheme-handler/http': 'omarchy-browser.desktop',
            'x-scheme-handler/https': 'omarchy-browser.desktop',
        }})
    else:
        print('Brave prerequisite missing: install brave-bin with `omarchy pkg add brave-bin`; '
              'preserving existing HTML/http/https defaults.', file=sys.stderr)
    local_foot = home / '.config/foot/local.ini'
    if not exists(local_foot):
        output['.config/foot/local.ini'] = '# Local Foot overrides, for example:\n# [main]\n# font=JetBrainsMono Nerd Font Mono:style=Medium:size=11\n'
    return output


def plan_install(home, profile, epic=False, uninstall=False, preferences_only=False):
    packages = (*SHARED, *(('omarchy',) if profile == 'omarchy' else ()),
                *(('epic',) if epic else ()))
    desired = {} if preferences_only else {
        str(relative): {'kind': 'link', 'source': str(source)}
        for relative, source in package_files(packages)
    }
    if profile == 'omarchy' and not preferences_only:
        # Preserve Omarchy's generated module and its mtime-based hot reload.
        # WSL uses the portable adapter from the shared Neovim package instead.
        desired['.config/nvim/lua/plugins/theme.lua'] = dict(
            kind='link', source=str(home / '.local/state/omarchy/current/theme/neovim.lua'))
    if uninstall:
        return [dict(path=relative, kind='remove') for relative, spec in desired.items()
                if (home / relative).is_symlink() and
                Path(spec['source']).is_relative_to(REPO) and
                (home / relative).resolve() == Path(spec['source']).resolve()]
    blockers = set()
    for relative in desired:
        for parent in (home / relative).parents:
            if parent == home:
                break
            if parent.is_symlink() or (exists(parent) and not parent.is_dir()):
                if parent in (home / '.config', home / '.local'):
                    raise ValueError(f'Refusing to replace top-level config directory: {parent}')
                blockers.add(parent.relative_to(home).as_posix())
    if profile == 'omarchy' and not preferences_only:
        theme = home / '.config/omarchy/themes/agamotto'
        if exists(theme / '.git'):
            # Omarchy rejects linked payloads inside a Git-installed theme.
            # Back up the whole old theme, including its repository metadata,
            # then install our trusted local theme into a clean directory.
            blockers.add(str(theme.relative_to(home)))
    # Only the highest obstructing ancestor needs replacing.
    blockers = {item for item in blockers if not any(
        item.startswith(other + '/') for other in blockers if other != item)}
    def virtual_missing(relative):
        return any(relative == item or relative.startswith(item + '/') for item in blockers)
    operations = [dict(path=relative, kind='remove') for relative in sorted(blockers)]
    if not epic and (REPO / 'epic').is_dir():
        # Opting out removes only our gate/launch links, never private AI homes
        # or account files. An ordinary WSL install cannot retain active routing.
        for relative, source in package_files(('epic',)):
            target = home / relative
            if target.is_symlink() and target.resolve() == source.resolve():
                operations.append(dict(path=str(relative), kind='remove'))
    if not preferences_only:
        login = home / '.bash_profile'
        prior_login = home / '.bash_profile.before-dotfiles'
        if login.is_file() and login.resolve() != (REPO / 'bash/.bash_profile').resolve():
            content = login.read_text()
            if prior_login.is_file() and prior_login.read_text() != content:
                raise ValueError(f'Existing login configuration already saved at {prior_login}')
            desired['.bash_profile.before-dotfiles'] = dict(kind='write', content=content)
        legacy_tmux = home / '.tmux.conf'
        if exists(legacy_tmux):
            operations.append(dict(path='.tmux.conf', kind='remove'))
        git_root = home / '.gitconfig'
        # Keep the old file's parent, so relative Git include paths keep working.
        root_text = git_root.read_text() if git_root.is_file() else ''
        xdg_git = home / '.config/git/config'
        previous_files = {}
        if root_text and not root_text.startswith(MARKER):
            previous_files[home / '.gitconfig.before-dotfiles'] = root_text
        if xdg_git.is_file() and xdg_git.resolve() != (REPO / 'gitconfig/.config/git/config').resolve():
            previous_files[home / '.config/git/previous.config'] = xdg_git.read_text()
        for old, previous in previous_files.items():
            if old.is_file() and old.read_text() != previous:
                raise ValueError(f'Private Git configuration already preserved at {old}; reconcile before replacing it.')
            desired[str(old.relative_to(home))] = dict(kind='write', content=previous)
        loader = MARKER + ('[include]\n\tpath = ~/.config/git/previous.config\n'
                           '[include]\n\tpath = ~/.gitconfig.before-dotfiles\n'
                           '[include]\n\tpath = ~/.config/git/config\n'
                           '[include]\n\tpath = ~/.gitconfig.local\n')
        desired['.gitconfig'] = dict(kind='write', content=loader)
    if profile == 'omarchy':
        for relative, content in desktop_preferences(home).items():
            desired[relative] = dict(kind='write', content=content)
    if not preferences_only:
        # Replacing a whole old directory link must not hide the machine-local
        # files deliberately excluded from the shared packages.
        for relative in ('.config/dotfiles/local.bash', '.config/tmux/local.conf',
                         '.config/foot/local.ini', '.config/dotfiles/git-epic.local',
                         '.config/dotfiles/git-epic-workspace.local'):
            original = home / relative
            if virtual_missing(relative) and original.is_file() and relative not in desired:
                desired[relative] = dict(kind='write', content=original.read_text())
        if profile == 'omarchy':
            relative = '.config/hypr/monitors.lua'
            monitor = home / relative
            if virtual_missing(relative) or not monitor.is_file():
                original = monitor if monitor.is_file() else Path('/usr/share/omarchy/config/hypr/monitors.lua')
                if original.is_file():
                    desired[relative] = dict(kind='write', content=original.read_text())
    for relative, spec in desired.items():
        path = home / relative
        # Generated preference files also participate in complete preflight.
        for parent in path.parents:
            if parent == home:
                break
            if virtual_missing(str(parent.relative_to(home))):
                continue
            if parent.is_symlink() or (exists(parent) and not parent.is_dir()):
                raise ValueError(f'Configuration parent is not a real directory: {parent}')
        if not virtual_missing(relative):
            if spec['kind'] == 'link' and path.is_symlink() and path.resolve() == Path(spec['source']).resolve():
                continue
            if spec['kind'] == 'write' and path.is_file() and not path.is_symlink() and path.read_text() == spec['content']:
                continue
        operations.append(dict(path=relative, **spec))
    return operations


def safe_relative(value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or str(path) in ('', '.'):
        raise ValueError(f'Unsafe manifest path: {value}')
    return path


def matches(path, record):
    if record['kind'] == 'link':
        return path.is_symlink() and os.readlink(path) == record['source']
    if record['kind'] == 'write':
        return path.is_file() and not path.is_symlink() and digest(path) == record['sha256']
    return not exists(path)


def validate_parent(home, path):
    for parent in path.parents:
        if parent == home:
            break
        if parent.is_symlink():
            raise ValueError(f'Refusing to write through directory symlink: {parent}')


def restore_manifest(home, manifest_path, apply=False, automatic=False):
    data = json.loads(manifest_path.read_text())
    if data.get('version') != 1 or Path(data.get('home', '')).resolve() != home:
        raise ValueError('Manifest version/home does not match this installation.')
    if data.get('status') == 'restored':
        print('Already restored.')
        return
    backup_root = manifest_path.parent
    if (backup_root / 'files').is_symlink():
        raise ValueError('Backup files directory must not be a symlink.')
    records = data['records']
    managed = {home / safe_relative(record['path']) for record in records}
    for record in records:
        path = home / safe_relative(record['path'])
        backup = backup_root / 'files' / safe_relative(record['path'])
        had_original = record.get('had_original', False)
        if had_original and not backup.parent.resolve().is_relative_to((backup_root / 'files').resolve()):
            raise ValueError('Unsafe backup directory symlink.')
        if had_original and not automatic and not exists(backup):
            raise ValueError(f'Original backup is missing; nothing restored: {backup}')
        if exists(path) and not matches(path, record):
            # An original symlink/file may have been replaced by a new directory.
            if record['kind'] == 'remove' and path.is_dir() and not path.is_symlink():
                if any(child not in managed for child in path.rglob('*')
                       if child.is_file() or child.is_symlink()):
                    raise ValueError(f'New files prevent restoration: {path}')
            elif automatic and (not had_original or not exists(backup)):
                continue  # this operation failed before moving the original
            else:
                raise ValueError(f'Changed since installation; refusing to overwrite: {path}')
        validate_parent(home, path)
    restored_directories = set()
    for record in reversed(records):
        path = home / record['path']
        backup = backup_root / 'files' / record['path']
        print(f'Restore: {path}')
        if not apply:
            continue
        if exists(path) and matches(path, record):
            path.unlink()
        if record.get('had_original', False) and exists(backup):
            if backup.is_dir():
                restored_directories.add(path)
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)  # fully checked owned directory contents above
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(backup), str(path))
    if apply:
        for relative in sorted(data.get('created_dirs', []), key=lambda item: len(Path(item).parts), reverse=True):
            path = home / safe_relative(relative)
            if any(path == directory or directory in path.parents for directory in restored_directories):
                continue  # the original whole directory has already been restored
            try:
                validate_parent(home, path)
                path.rmdir()
            except (OSError, ValueError):
                pass  # new screenshots/downloads or other user files stay put
        data['status'] = 'restored'
        manifest_path.write_text(json.dumps(data, indent=2) + '\n')


def installation_directories(home, desktop=False, projects=True):
    directories = (['dev'] if projects else []) + (['downloads', 'media/screenshots'] if desktop else [])
    for relative in directories:
        path = home / relative
        validate_parent(home, path)
        if exists(path) and not path.is_dir():
            raise ValueError(f'Installation folder path is not a directory: {path}')
    return directories


def apply_plan(home, operations, desktop=False, projects=True):
    directories = installation_directories(home, desktop, projects)
    if not operations and all((home / relative).is_dir() for relative in directories):
        print('Already up to date.')
        return
    state = home / '.local/state/dotfiles/backups'
    validate_parent(home, state / 'placeholder')
    stamp = f'{time.strftime("%Y%m%d-%H%M%S")}-{os.getpid()}-{time.time_ns() % 1000000}'
    backup_root = state / stamp
    backup_root.mkdir(parents=True, mode=0o700)
    backup_root.chmod(0o700)
    manifest = backup_root / 'manifest.json'
    data = dict(version=1, home=str(home), repo=str(REPO), status='applying', records=[], created_dirs=[])
    def save():
        temporary = manifest.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, indent=2) + '\n')
        temporary.chmod(0o600)
        temporary.replace(manifest)
    def mkdir(path):
        missing = []
        while not exists(path) and path != home:
            missing.append(path)
            path = path.parent
        for directory in reversed(missing):
            directory.mkdir()
            data['created_dirs'].append(str(directory.relative_to(home)))
            save()
    save()
    try:
        for spec in operations:
            path = home / safe_relative(spec['path'])
            validate_parent(home, path)
            record = {key: value for key, value in spec.items() if key != 'content'}
            record['had_original'] = exists(path)
            if spec['kind'] == 'write':
                record['sha256'] = hashlib.sha256(spec['content'].encode()).hexdigest()
            data['records'].append(record)
            save()
            if exists(path):
                backup = backup_root / 'files' / spec['path']
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(backup))
            if spec['kind'] != 'remove':
                mkdir(path.parent)
                if spec['kind'] == 'link':
                    path.symlink_to(spec['source'])
                else:
                    # A failed write must not leave partial output mistaken for
                    # a user edit during rollback. Stage beside the target.
                    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f'.{path.name}.dotfiles-', delete=False) as stream:
                        temporary = Path(stream.name)
                    try:
                        temporary.write_text(spec['content'], encoding='utf-8')
                        temporary.chmod(0o600)
                        temporary.replace(path)
                    finally:
                        temporary.unlink(missing_ok=True)
            save()
        for relative in directories:
            mkdir(home / relative)
        data['status'] = 'applied'
        save()
    except Exception:
        print(f'Apply failed; restoring from {manifest}', file=sys.stderr)
        restore_manifest(home, manifest, apply=True, automatic=True)
        raise
    print(f'Backup manifest: {manifest}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('omarchy', 'wsl'))
    parser.add_argument('--epic', action='store_true')
    parser.add_argument('--apply', action='store_true', help='apply; without this flag only preview')
    parser.add_argument('--dry-run', action='store_true', help='explicit preview (default)')
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--restore', type=Path, metavar='MANIFEST')
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--preferences-only', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    home = args.home.expanduser().resolve()
    if args.apply and args.dry_run:
        parser.error('--apply and --dry-run are mutually exclusive')
    if args.epic and args.profile != 'wsl':
        parser.error('Epic is available only with --profile wsl')
    if args.epic and not ubuntu_wsl():
        parser.error('Epic setup requires Ubuntu running inside WSL')
    try:
        if args.restore:
            restore_manifest(home, args.restore.resolve(), args.apply)
            return 0
        if not args.profile:
            parser.error('--profile is required')
        operations = plan_install(home, args.profile, args.epic, args.uninstall, args.preferences_only)
        desktop = args.profile == 'omarchy' and not args.uninstall
        projects = not args.uninstall and not args.preferences_only
        directories = installation_directories(home, desktop, projects)
        for relative in directories:
            if not (home / relative).is_dir():
                print(f'Create directory: {home / relative}')
        for operation in operations:
            print(f'{operation["kind"].capitalize()}: {home / operation["path"]}')
        print(f'{len(operations)} changes; ' + ('applying.' if args.apply else 'preview only. Add --apply to install.'))
        if args.apply:
            apply_plan(home, operations, desktop=desktop, projects=projects)
        return 0
    except (OSError, ValueError, configparser.Error) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
