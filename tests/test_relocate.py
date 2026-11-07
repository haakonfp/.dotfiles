"""Move copied checkouts and real installer state only inside temporary homes."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]


class RelocateTests(unittest.TestCase):
    def setUp(self):
        implementation = REPO / 'scripts/relocate.py'
        self.assertTrue(implementation.is_file(), 'scripts/relocate.py is not implemented yet')
        spec = importlib.util.spec_from_file_location('dotfiles_relocation_test', implementation)
        self.relocator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.relocator)
        self.tmp = tempfile.TemporaryDirectory(prefix='dotfiles relocation ')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'home with spaces'
        self.home.mkdir()
        self.source = self.copy_checkout(self.home / '.dotfiles-next')
        self.destination = self.home / '.dotfiles'
        self.output = io.StringIO()

    def copy_checkout(self, target):
        return Path(shutil.copytree(REPO, target, symlinks=True,
                    ignore=shutil.ignore_patterns('.git', '.worktrees', '.superpowers', '__pycache__')))

    def move(self, **kwargs):
        with contextlib.redirect_stdout(self.output), contextlib.redirect_stderr(self.output):
            return self.relocator.relocate(self.source, self.home, profile='wsl', **kwargs)

    def manifests(self):
        return sorted((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))

    def install_from(self, checkout, epic=False):
        installer = self.relocator.load_installer(checkout)
        before = set(self.manifests())
        with mock.patch.object(installer, 'ubuntu_wsl', return_value=True), \
                contextlib.redirect_stdout(self.output), contextlib.redirect_stderr(self.output):
            operations = installer.plan_install(self.home, 'wsl', epic=epic)
            installer.apply_plan(self.home, operations)
        created = set(self.manifests()) - before
        self.assertEqual(len(created), 1)
        return created.pop()

    def restore(self, manifest):
        installer = self.relocator.load_installer(self.destination)
        with contextlib.redirect_stdout(self.output), contextlib.redirect_stderr(self.output):
            installer.restore_manifest(self.home, manifest, apply=True)

    def snapshot(self, root):
        result = {}
        for path in sorted(root.rglob('*')):
            relative = str(path.relative_to(root))
            if path.is_symlink():
                result[relative] = ('link', os.readlink(path))
            elif path.is_file():
                result[relative] = ('file', path.read_bytes())
            elif path.is_dir():
                result[relative] = ('directory',)
        return result

    def assert_live_links_use_canonical_checkout(self):
        for relative, source in (('.bashrc', 'bash/.bashrc'),
                                 ('.config/tmux/tmux.conf', 'tmux/.config/tmux/tmux.conf'),
                                 ('.config/nvim/init.lua', 'nvim/.config/nvim/init.lua')):
            with self.subTest(link=relative):
                path = self.home / relative
                self.assertTrue(path.is_symlink())
                self.assertEqual(path.resolve(), self.destination / source)
        self.assertFalse(self.source.exists())

    def test_preview_before_install_writes_no_configuration_or_state(self):
        before = self.snapshot(self.home)
        result = self.move()
        self.assertEqual(result['destination'], self.destination)
        self.assertIsNone(result['archive'])
        self.assertEqual(self.snapshot(self.home), before)

    def test_first_install_archives_dirty_old_checkout_and_links_new_canonical(self):
        old = self.copy_checkout(self.destination)
        (old / '.git').mkdir()
        (old / '.git/local-marker').write_text('old clone metadata')
        (old / 'bash/.bashrc').write_text('# old locally modified configuration\n')
        (old / 'untracked personal file').write_text('keep untracked data')
        private = self.home / '.codex/auth.json'
        private.parent.mkdir()
        private.write_text('private account fixture')
        result = self.move(apply=True)
        archive = result['archive']
        self.assertIsInstance(archive, Path)
        self.assertEqual(archive.parent, self.home / '.local/state/dotfiles/checkouts')
        self.assertEqual((archive / '.git/local-marker').read_text(), 'old clone metadata')
        self.assertEqual((archive / 'bash/.bashrc').read_text(), '# old locally modified configuration\n')
        self.assertEqual((archive / 'untracked personal file').read_text(), 'keep untracked data')
        self.assertEqual(private.read_text(), 'private account fixture')
        self.assert_live_links_use_canonical_checkout()

    def test_first_install_without_old_canonical_still_enrolls_configuration(self):
        result = self.move(apply=True)
        self.assertIsNone(result['archive'])
        self.assert_live_links_use_canonical_checkout()
        self.assertTrue(self.manifests())

    def test_unselected_github_authentication_link_follows_archived_old_checkout(self):
        old = self.copy_checkout(self.destination)
        original = old / 'gh/.config/gh/hosts.yml'
        original.write_text('github.com:\n  oauth_token: fixture-only\n')
        active = self.home / '.config/gh/hosts.yml'
        active.parent.mkdir(parents=True)
        active.symlink_to(original)
        result = self.move(apply=True)
        self.assertEqual(active.resolve(), result['archive'] / 'gh/.config/gh/hosts.yml')
        self.assertEqual(active.read_text(), 'github.com:\n  oauth_token: fixture-only\n')

    def test_archive_internal_relative_link_keeps_external_private_target(self):
        old = self.copy_checkout(self.destination)
        private = self.home / 'private/token'
        private.parent.mkdir()
        private.write_text('private token fixture')
        (old / 'legacy-private').symlink_to('../private', target_is_directory=True)
        active = self.home / '.legacy-private'
        active.symlink_to('.dotfiles/legacy-private')
        result = self.move(apply=True)
        self.assertTrue((active / 'token').is_file(), 'archive-relative private link broke')
        self.assertEqual((active / 'token').read_text(), 'private token fixture')
        self.assertEqual((result['archive'] / 'legacy-private/token').read_text(), 'private token fixture')

    def test_private_agent_and_ssh_links_follow_old_checkout_credentials(self):
        old = self.copy_checkout(self.destination)
        for folder, name in (('.codex', 'auth.json'), ('.claude', '.credentials.json'), ('.ssh', 'id_work')):
            original = old / ('private-' + folder[1:]) / name
            original.parent.mkdir()
            original.write_text('private ' + folder + ' fixture')
            active = self.home / folder / name
            active.parent.mkdir()
            active.symlink_to(original)
        result = self.move(apply=True)
        for folder, name in (('.codex', 'auth.json'), ('.claude', '.credentials.json'), ('.ssh', 'id_work')):
            active = self.home / folder / name
            self.assertTrue(active.is_file(), 'relocation disconnected ' + folder)
            self.assertEqual(active.read_text(), 'private ' + folder + ' fixture')
            self.assertEqual(active.resolve(), result['archive'] / ('private-' + folder[1:]) / name)

    def test_unrelated_relative_project_link_is_not_rewritten(self):
        target = self.home / 'dev/personal/package/tool'
        target.parent.mkdir(parents=True)
        target.write_text('project fixture')
        link = self.home / 'dev/personal/bin/tool'
        link.parent.mkdir()
        link.symlink_to('../package/tool')
        loop = self.home / 'dev/personal/loop'
        loop.symlink_to('loop', target_is_directory=True)
        broken = self.home / 'dev/personal/broken'
        broken.symlink_to('loop/missing')
        self.move(apply=True)
        self.assertEqual(os.readlink(link), '../package/tool')
        self.assertEqual(link.read_text(), 'project fixture')
        self.assertEqual(os.readlink(broken), 'loop/missing')

    def test_nested_source_checkout_rebases_its_external_relative_links(self):
        nested = self.home / 'staging/new checkout'
        nested.parent.mkdir()
        self.source.rename(nested)
        self.source = nested
        private = nested.parent / 'private/token'
        private.parent.mkdir()
        private.write_text('source private fixture')
        (self.source / 'private-link').symlink_to('../private', target_is_directory=True)
        self.move(apply=True)
        self.assertTrue((self.destination / 'private-link/token').is_file())
        self.assertEqual((self.destination / 'private-link/token').read_text(), 'source private fixture')

    def test_existing_next_install_manifest_restores_original_after_move(self):
        original = self.home / '.bashrc'
        original.write_text('# personal bash before dotfiles\n')
        manifest = self.install_from(self.source)
        self.assertEqual(original.resolve(), self.source / 'bash/.bashrc')
        self.move(apply=True)
        self.assert_live_links_use_canonical_checkout()
        data = json.loads(manifest.read_text())
        self.assertEqual(Path(data['repo']), self.destination)
        self.assertNotIn(str(self.source), json.dumps(data))
        self.restore(manifest)
        self.assertFalse(original.is_symlink())
        self.assertEqual(original.read_text(), '# personal bash before dotfiles\n')

    def assert_original_checkout_link_restores_archive(self, relative):
        old = self.copy_checkout(self.destination)
        (old / 'bash/.bashrc').write_text('# archived original\n')
        original = self.home / '.bashrc'
        original.symlink_to('.dotfiles/bash/.bashrc' if relative else old / 'bash/.bashrc')
        result = self.move(apply=True)
        archive_target = result['archive'] / 'bash/.bashrc'
        candidates = []
        for manifest in self.manifests():
            backup = manifest.parent / 'files/.bashrc'
            if backup.is_symlink() and backup.resolve() == archive_target:
                candidates.append(manifest)
        self.assertEqual(len(candidates), 1, 'original checkout link must resolve into its archive')
        self.restore(candidates[0])
        self.assertTrue(original.is_symlink())
        self.assertEqual(original.resolve(), archive_target)
        self.assertEqual(original.read_text(), '# archived original\n')

    def test_original_absolute_checkout_symlink_restores_archived_checkout(self):
        self.assert_original_checkout_link_restores_archive(relative=False)

    def test_original_relative_checkout_symlink_restores_archived_checkout(self):
        self.assert_original_checkout_link_restores_archive(relative=True)

    def test_relative_original_external_link_restores_its_original_target(self):
        target = self.home / 'original config/bashrc'
        target.parent.mkdir()
        target.write_text('# external personal bash\n')
        original = self.home / '.bashrc'
        original.symlink_to('original config/bashrc')
        self.move(apply=True)
        candidates = [manifest for manifest in self.manifests()
                      if (manifest.parent / 'files/.bashrc').is_symlink()
                      and (manifest.parent / 'files/.bashrc').resolve() == target]
        self.assertEqual(len(candidates), 1, 'relative original must stay resolvable in backup storage')
        self.restore(candidates[0])
        self.assertEqual(original.resolve(), target)
        self.assertEqual(original.read_text(), '# external personal bash\n')

    def assert_second_enrollment_failure_rolls_back(self, operation):
        old = self.copy_checkout(self.destination)
        (old / 'untracked file').write_text('old checkout survives')
        original = self.home / '.bashrc'
        original.symlink_to(old / 'bash/.bashrc')
        private_git = self.home / '.gitconfig'
        private_git.write_text('[user]\n name = Private Person\n')
        load = self.relocator.load_installer
        injected = []

        def instrument(checkout):
            installer = load(checkout)
            actual = getattr(installer, operation)

            def fail_in_second(*args, **kwargs):
                if installer.REPO == self.destination and not self.source.exists():
                    injected.append(operation)
                    if operation == 'plan_install':
                        raise OSError('injected second enrollment failure')
                    symlink = Path.symlink_to

                    def fail_link(path, target, *link_args, **link_kwargs):
                        if path == self.home / '.config/tmux/tmux.conf':
                            raise OSError('injected second enrollment failure')
                        return symlink(path, target, *link_args, **link_kwargs)

                    with mock.patch.object(Path, 'symlink_to', fail_link):
                        return actual(*args, **kwargs)
                return actual(*args, **kwargs)

            setattr(installer, operation, fail_in_second)
            return installer

        with mock.patch.object(self.relocator, 'load_installer', side_effect=instrument), \
                self.assertRaisesRegex((OSError, RuntimeError, ValueError), 'injected second enrollment failure'):
            self.move(apply=True)
        self.assertTrue(injected, 'failure must occur after the checkout was moved')
        self.assertTrue(self.source.is_dir())
        self.assertTrue(self.destination.is_dir())
        self.assertEqual((self.destination / 'untracked file').read_text(), 'old checkout survives')
        self.assertEqual(original.resolve(), self.destination / 'bash/.bashrc')
        self.assertEqual(private_git.read_text(), '[user]\n name = Private Person\n')
        self.assertFalse((self.home / '.config/tmux/tmux.conf').exists())

    def test_second_plan_failure_rolls_back_checkouts_and_configuration(self):
        self.assert_second_enrollment_failure_rolls_back('plan_install')

    def test_partial_second_apply_failure_rolls_back_checkouts_and_configuration(self):
        self.assert_second_enrollment_failure_rolls_back('apply_plan')

    def test_manifest_repair_failure_rolls_back_checkouts_and_configuration(self):
        self.copy_checkout(self.destination)
        original = self.home / '.bashrc'
        original.write_text('# original personal bash\n')
        write = self.relocator.atomic_file
        failures = []
        def fail_once(path, content, mode):
            if path.name == 'manifest.json' and not failures:
                failures.append(path)
                raise OSError('fixture metadata update failed')
            return write(path, content, mode)
        with mock.patch.object(self.relocator, 'atomic_file', side_effect=fail_once), \
                self.assertRaisesRegex(OSError, 'fixture metadata update failed'):
            self.move(apply=True)
        self.assertTrue(failures)
        self.assertTrue(self.source.is_dir())
        self.assertTrue(self.destination.is_dir())
        self.assertEqual(original.read_text(), '# original personal bash\n')
        self.assertFalse(original.is_symlink())

    def test_late_failure_restores_original_relative_and_credential_links(self):
        old = self.copy_checkout(self.destination)
        private = self.home / 'private/token'
        private.parent.mkdir()
        private.write_text('private fixture')
        link = old / 'legacy-private'
        link.symlink_to('../private', target_is_directory=True)
        active = self.home / '.codex/auth.json'
        active.parent.mkdir()
        active.symlink_to(old / 'legacy-private/token')
        raw_auth = os.readlink(active)
        write = self.relocator.atomic_file
        failures = []
        def fail_once(path, content, mode):
            if path.name == 'manifest.json' and not failures:
                failures.append(path)
                raise OSError('fixture late repair failed')
            return write(path, content, mode)
        with mock.patch.object(self.relocator, 'atomic_file', side_effect=fail_once), \
                self.assertRaisesRegex(OSError, 'fixture late repair failed'):
            self.move(apply=True)
        self.assertEqual(os.readlink(link), '../private')
        self.assertEqual(os.readlink(active), raw_auth)
        self.assertEqual(active.read_text(), 'private fixture')
        self.assertTrue(self.source.is_dir())

    def test_canonical_repeat_is_noop_without_first_install(self):
        self.source.rename(self.destination)
        before = self.snapshot(self.home)
        with contextlib.redirect_stdout(self.output):
            result = self.relocator.relocate(self.destination, self.home, profile='wsl', apply=True)
        self.assertEqual(result['destination'], self.destination)
        self.assertIsNone(result['archive'])
        self.assertEqual(self.snapshot(self.home), before)

    def test_existing_epic_opt_in_is_inferred_and_relinked(self):
        self.install_from(self.source, epic=True)
        loader = self.relocator.load_installer

        def wsl_installer(checkout):
            installer = loader(checkout)
            installer.ubuntu_wsl = lambda: True
            return installer

        with mock.patch.object(self.relocator, 'load_installer', side_effect=wsl_installer):
            self.move(apply=True)
        for relative in ('.config/dotfiles/epic.enabled', '.config/dotfiles/git-epic-include.conf',
                         '.config/dotfiles/shell/epic.bash', '.local/bin/epic-ai-setup'):
            path = self.home / relative
            self.assertTrue(path.is_symlink(), relative)
            self.assertEqual(path.resolve(), self.destination / 'epic' / relative)

    def test_explicit_personal_profile_disables_old_checkout_epic_links(self):
        old = self.copy_checkout(self.destination)
        self.install_from(old, epic=True)
        private = self.home / '.codex-epic/auth.json'
        private.parent.mkdir()
        private.write_text('private work account remains')
        self.move(epic=False, apply=True)
        self.assertFalse((self.home / '.config/dotfiles/epic.enabled').exists())
        self.assertFalse((self.home / '.local/bin/codex-epic').exists())
        self.assertEqual(private.read_text(), 'private work account remains')

    def test_source_inside_canonical_checkout_is_rejected_before_writes(self):
        self.destination.mkdir()
        nested = self.destination / 'next'
        self.source.rename(nested)
        before = self.snapshot(self.home)
        with self.assertRaises((ValueError, OSError)), contextlib.redirect_stdout(self.output):
            self.relocator.relocate(nested, self.home, profile='wsl', apply=True)
        self.assertEqual(self.snapshot(self.home), before)

    def test_destination_inside_source_checkout_is_rejected_before_writes(self):
        nested_home = self.source / 'machine home'
        nested_home.mkdir()
        before = self.snapshot(self.home)
        with self.assertRaises((ValueError, OSError)), contextlib.redirect_stdout(self.output):
            self.relocator.relocate(self.source, nested_home, profile='wsl', apply=True)
        self.assertEqual(self.snapshot(self.home), before)

    def test_checkout_containing_its_backup_state_is_rejected_before_writes(self):
        self.source.rename(self.home / '.local')
        self.source = self.home / '.local'
        before = self.snapshot(self.home)
        with self.assertRaises((ValueError, OSError)), contextlib.redirect_stdout(self.output):
            self.move(apply=True)
        self.assertEqual(self.snapshot(self.home), before)

    def test_linked_worktree_source_is_rejected_before_writes(self):
        (self.source / '.git').write_text('gitdir: ../repository/.git/worktrees/next\n')
        before = self.snapshot(self.home)
        with self.assertRaises((ValueError, OSError)), contextlib.redirect_stdout(self.output):
            self.move(apply=True)
        self.assertEqual(self.snapshot(self.home), before)


if __name__ == '__main__':
    unittest.main()
