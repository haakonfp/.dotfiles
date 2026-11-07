#!/usr/bin/env python3
"""Preview or move this checkout to ~/.dotfiles, preserving config and rollback."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import uuid


def load_installer(repo):
    spec = importlib.util.spec_from_file_location('dotfiles_relocation_installer', repo / 'scripts/install.py')
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def atomic_file(path, content, mode):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.relocate-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_link(path, target):
    temporary = path.with_name('.relocate-' + uuid.uuid4().hex)
    try:
        temporary.symlink_to(target)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def mapped_path(value, mapping):
    path = Path(value)
    if not path.is_absolute():
        return value
    for old, new in mapping:
        if path == old or old in path.parents:
            return str(new / path.relative_to(old))
    return value


def manifests(home):
    return sorted((home / '.local/state/dotfiles/backups').glob('*/manifest.json'))


def read_manifest(path, home):
    if path.is_symlink() or path.parent.is_symlink() or (path.parent / 'files').is_symlink():
        raise ValueError(f'Refusing symlinked backup metadata: {path}')
    data = json.loads(path.read_text())
    if data.get('version') != 1 or Path(data.get('home', '')).resolve() != home:
        raise ValueError(f'Backup belongs to another installation: {path}')
    return data


def symlinks(root):
    if not root.is_dir():
        return
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            if path.is_symlink():
                yield path


def link_reference(path, original=None):
    raw = os.readlink(path)
    location = original if original is not None else path
    target = Path(os.path.join(location.parent, raw))
    # Resolve ancestor symlinks while retaining the final link's identity.
    # This keeps both multi-link chains and symlink/../path semantics intact.
    try:
        absolute = os.path.normpath(target.parent.resolve() / target.name)
    except (OSError, RuntimeError):
        # Unrelated broken/looping links do not block checkout relocation.
        absolute = os.path.abspath(target)
    return raw, absolute


def home_symlinks(home, excluded):
    for directory, dirs, files in os.walk(home, followlinks=False):
        parent = Path(directory)
        for name in dirs + files:
            path = parent / name
            if path.is_symlink():
                yield path
        dirs[:] = [name for name in dirs
                   if parent / name not in excluded and not (parent / name).is_symlink()]


def backup_references(home):
    references = {}
    for manifest in manifests(home):
        read_manifest(manifest, home)
        files = manifest.parent / 'files'
        for link in symlinks(files):
            references[link] = link_reference(link, home / link.relative_to(files))
    return references


def repair_changes(home, source, destination, archive, final_manifests, managed_paths,
                   checkout_refs, live_refs, backup_refs):
    """Compute changes first; callers journal old values before atomic updates."""
    new_mapping = [(source, destination)]
    mapping = new_mapping + ([(destination, archive)] if archive else [])
    changes = []
    for root, relative, raw, absolute in checkout_refs:
        relocated = destination if root == source else archive
        link = relocated / relative
        target = mapped_path(absolute, mapping)
        value = target if os.path.isabs(raw) else os.path.relpath(target, link.parent)
        if value != raw:
            changes.append((link, 'link', value))
    for manifest in manifests(home):
        data = read_manifest(manifest, home)
        installed_mapping = new_mapping if manifest in final_manifests else mapping
        data['repo'] = mapped_path(data['repo'], installed_mapping)
        for record in data['records']:
            if 'source' in record:
                record['source'] = mapped_path(record['source'], installed_mapping)
        rendered = (json.dumps(data, indent=2) + '\n').encode()
        if rendered != manifest.read_bytes():
            changes.append((manifest, 'file', rendered))
        files = manifest.parent / 'files'
        for link in symlinks(files):
            # A backed-up relative link must be interpreted at its original
            # home location, not relative to the backup directory.
            original = home / link.relative_to(files)
            raw = os.readlink(link)
            before = backup_refs.get(link)
            absolute = before[1] if before and before[0] == raw else link_reference(link, original)[1]
            target = mapped_path(absolute, installed_mapping)
            if target != raw:
                changes.append((link, 'link', target))
    excluded = {source, destination, home / '.local/state/dotfiles'}
    for link in sorted(home_symlinks(home, excluded)):
        raw = os.readlink(link)
        before = live_refs.get(link)
        absolute = before[1] if before and before[0] == raw else os.path.normpath(os.path.join(link.parent, raw))
        # Selected links now point into the new canonical checkout. Other
        # legacy links still pointing at the old checkout follow its archive.
        applicable = new_mapping if link.relative_to(home) in managed_paths else mapping
        target = mapped_path(absolute, applicable)
        logical = os.path.normpath(os.path.join(link.parent, raw))
        if target == absolute and mapped_path(logical, applicable) == logical:
            continue
        if target != raw:
            changes.append((link, 'link', target))
    return changes


def apply_changes(changes, undo):
    for path, kind, value in changes:
        if kind == 'link':
            old = os.readlink(path)
            atomic_link(path, value)
            undo.append((path, kind, old, None))
        else:
            old = path.read_bytes()
            mode = stat.S_IMODE(path.stat().st_mode)
            atomic_file(path, value, mode)
            undo.append((path, kind, old, mode))


def check_checkout(path):
    gitdir = path / '.git'
    if gitdir.is_file() or gitdir.is_symlink():
        raise ValueError(f'Use a regular clone, not a linked worktree: {path}')
    worktrees = gitdir / 'worktrees'
    if worktrees.is_dir() and any(worktrees.iterdir()):
        raise ValueError(f'Checkout has linked worktrees; move them before relocation: {path}')


def relocate(source, home, profile, epic=None, apply=False):
    source, home = Path(source).resolve(), Path(home).resolve()
    destination = home / '.dotfiles'
    result = {'destination': destination, 'archive': None}
    if profile not in ('wsl', 'omarchy'):
        raise ValueError('Choose --profile wsl or --profile omarchy')
    if source == destination:
        print(f'Already at {destination}.')
        return result
    if source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError('Source and destination cannot contain one another')
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError(f'Canonical destination is not a regular directory: {destination}')
    if not (source / 'scripts/install.py').is_file():
        raise ValueError(f'Not a dotfiles checkout: {source}')
    check_checkout(source)
    if destination.exists():
        check_checkout(destination)
    installer = load_installer(source)
    if epic is None:
        epic = profile == 'wsl' and (home / '.config/dotfiles/epic.enabled').is_file()
    if epic and (profile != 'wsl' or not installer.ubuntu_wsl()):
        raise ValueError('Epic relocation requires Ubuntu WSL')
    state = home / '.local/state/dotfiles'
    if state.is_relative_to(source):
        raise ValueError('Checkout cannot contain its own relocation/backup state')
    installer.validate_parent(home, state / 'checkouts/placeholder')
    for manifest in manifests(home):
        read_manifest(manifest, home)
    operations = installer.plan_install(home, profile, epic=epic)
    installer.installation_directories(home, desktop=profile == 'omarchy')
    checkout_refs = [(root, link.relative_to(root), *link_reference(link))
                     for root in (source, destination) if root.is_dir()
                     for link in symlinks(root)]
    excluded = {source, destination, state}
    live_refs = {link: link_reference(link) for link in home_symlinks(home, excluded)}
    print(f'Checkout: {source} -> {destination}')
    if destination.exists():
        print(f'Old checkout will be archived under {state / "checkouts"}.')
    print(f'Profile: {profile}' + (' with Epic.' if epic else '.'))
    if not apply:
        print(f'{len(operations)} enrollment changes; preview only. Add --apply to move and relink.')
        return result

    stamp = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:12]
    archive = state / 'checkouts' / stamp if destination.exists() else None
    phases, undo = [], []
    archived = moved = False
    journal = state / 'relocations' / (stamp + '.json')
    journal.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    details = dict(source=str(source), destination=str(destination),
                   archive=str(archive) if archive else None, status='enrolling')

    def save_status(status):
        details['status'] = status
        atomic_file(journal, (json.dumps(details, indent=2) + '\n').encode(), 0o600)

    def enroll(module, plan):
        phase = {'installer': module, 'manifests': [], 'before': set(manifests(home))}
        phases.append(phase)
        try:
            module.apply_plan(home, plan, desktop=profile == 'omarchy')
        finally:
            phase['manifests'] = sorted(set(manifests(home)) - phase['before'])

    try:
        save_status('enrolling')
        enroll(installer, operations)
        backup_refs = backup_references(home)
        if archive:
            archive.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination.rename(archive)
            archived = True
        save_status('old checkout archived')
        source.rename(destination)
        moved = True
        save_status('checkout moved')
        current = load_installer(destination)
        enroll(current, current.plan_install(home, profile, epic=epic))
        packages = (*current.SHARED, *(('omarchy',) if profile == 'omarchy' else ()),
                    *(('epic',) if epic else ()))
        managed = {relative for relative, _ in current.package_files(packages)}
        final = set(phases[-1]['manifests'])
        changes = repair_changes(home, source, destination, archive, final, managed,
                                 checkout_refs, live_refs, backup_refs)
        apply_changes(changes, undo)
        details['rewritten_links'] = [dict(path=str(path), original=old)
                                      for path, kind, old, _ in undo if kind == 'link']
        save_status('complete')
    except BaseException as error:
        failures = []
        for path, kind, old, mode in reversed(undo):
            try:
                atomic_link(path, old) if kind == 'link' else atomic_file(path, old, mode)
            except OSError as rollback_error:
                failures.append(str(rollback_error))
        try:
            if len(phases) > 1:
                for manifest in reversed(phases[-1]['manifests']):
                    phases[-1]['installer'].restore_manifest(home, manifest, apply=True, automatic=True)
            if moved:
                destination.rename(source)
            if archived:
                archive.rename(destination)
            if phases:
                for manifest in reversed(phases[0]['manifests']):
                    installer.restore_manifest(home, manifest, apply=True, automatic=True)
        except (OSError, ValueError) as rollback_error:
            failures.append(str(rollback_error))
        try:
            save_status('rollback incomplete' if failures else 'rolled back')
        except OSError as rollback_error:
            failures.append(str(rollback_error))
        if failures:
            raise RuntimeError(f'{error}; recovery details: {journal}; ' + '; '.join(failures)) from error
        raise
    result['archive'] = archive
    print(f'Checkout is now {destination}. Open a new shell or run: cd ~/.dotfiles')
    if archive:
        print(f'Old checkout preserved at {archive}')
    print(f'Relocation record: {journal}')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, choices=('wsl', 'omarchy'))
    parser.add_argument('--epic', action=argparse.BooleanOptionalAction, default=None,
                        help='preserve existing Epic opt-in by default')
    parser.add_argument('--apply', action='store_true', help='move and repair; default previews only')
    args = parser.parse_args()
    try:
        relocate(Path(__file__).resolve().parents[1], Path.home(), args.profile, args.epic, args.apply)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Relocation interrupted; rollback attempted.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
