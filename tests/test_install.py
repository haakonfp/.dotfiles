"""Exercise real filesystem changes; never install into the developer's home."""
import json
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import shutil
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dotfiles_install', REPO / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='dotfiles test ')
        self.home = Path(self.tmp.name) / 'home with spaces'
        self.home.mkdir()
        self.addCleanup(self.tmp.cleanup)

    def run_install(self, *args, ok=True):
        result = subprocess.run(['python3', str(REPO / 'scripts/install.py'), '--home', str(self.home), *args],
                                text=True, capture_output=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_preview_changes_nothing_and_rejects_epic_on_omarchy(self):
        self.run_install('--profile', 'omarchy')
        self.assertEqual(list(self.home.iterdir()), [])
        bad = self.run_install('--profile', 'omarchy', '--epic', ok=False)
        self.assertNotEqual(bad.returncode, 0)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_apply_backups_repeat_and_restore(self):
        original = self.home / '.bashrc'
        original.write_text('personal bash\n')
        self.run_install('--profile', 'omarchy', '--apply')
        self.assertTrue(original.is_symlink())
        self.assertEqual(os.readlink(original), str(REPO / 'bash/.bashrc'))
        backups = list((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        self.assertEqual(len(backups), 1)
        self.run_install('--profile', 'omarchy', '--apply')
        self.assertEqual(list((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json')), backups)
        self.run_install('--restore', str(backups[0]), '--apply')
        self.assertFalse(original.is_symlink())
        self.assertEqual(original.read_text(), 'personal bash\n')

    def test_restore_does_not_remove_user_replacement(self):
        self.run_install('--profile', 'omarchy', '--apply')
        manifest = next((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        path = self.home / '.bashrc'
        path.unlink()
        path.write_text('new work\n')
        result = self.run_install('--restore', str(manifest), '--apply', ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(path.read_text(), 'new work\n')
        self.assertTrue((self.home / '.bash_profile').is_symlink())  # complete preflight

    def test_shadowed_tmux_and_git_credentials_are_preserved(self):
        (self.home / '.tmux.conf').write_text('old tmux')
        (self.home / '.gitconfig').write_text('[user]\n name = Local User\n email = local@example.test\n[credential]\n helper = example-helper\n')
        self.run_install('--profile', 'omarchy', '--apply')
        self.assertFalse((self.home / '.tmux.conf').exists())
        env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'))
        env.pop('GIT_CONFIG_GLOBAL', None)
        for key, expected in [('user.name', 'Local User'), ('credential.helper', 'example-helper')]:
            result = subprocess.run(['git', 'config', '--global', '--includes', '--get', key], env=env, text=True, capture_output=True)
            self.assertEqual(result.stdout.strip(), expected)

    def test_copied_managed_login_profile_does_not_replace_original_initializer(self):
        login = self.home / '.bash_profile'
        prior = self.home / '.bash_profile.before-dotfiles'
        login.write_bytes((REPO / 'bash/.bash_profile').read_bytes())
        original = 'export LOGIN_SENTINEL=original\n'
        prior.write_text(original)
        self.run_install('--profile', 'omarchy', '--apply')
        self.assertEqual(prior.read_text(), original)
        env = dict(os.environ, HOME=str(self.home), DOTFILES_BASHRC_LOADED='1')
        result = subprocess.run(['bash', '--noprofile', '--norc', '-c',
                                 'source "$HOME/.bash_profile"; printf "%s" "$LOGIN_SENTINEL"'],
                                env=env, text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'original')

    def test_changed_personal_login_replaces_saved_initializer_with_transactional_backup(self):
        login = self.home / '.bash_profile'
        prior = self.home / '.bash_profile.before-dotfiles'
        login.write_text('export LOGIN_SENTINEL=newer\n')
        prior.write_text('export LOGIN_SENTINEL=older\n')
        self.run_install('--profile', 'wsl', '--apply')
        self.assertEqual(prior.read_text(), 'export LOGIN_SENTINEL=newer\n')
        manifest = next((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        backup = manifest.parent / 'files/.bash_profile.before-dotfiles'
        self.assertEqual(backup.read_text(), 'export LOGIN_SENTINEL=older\n')
        self.run_install('--profile', 'wsl', '--apply')
        self.assertEqual(len(list((manifest.parent.parent).glob('*/manifest.json'))), 1)
        self.run_install('--restore', str(manifest), '--apply')
        self.assertEqual(login.read_text(), 'export LOGIN_SENTINEL=newer\n')
        self.assertEqual(prior.read_text(), 'export LOGIN_SENTINEL=older\n')

    def test_login_link_from_other_checkout_keeps_saved_initializer(self):
        old_checkout = Path(self.tmp.name) / 'old dotfiles'
        old_checkout.mkdir()
        old_login = old_checkout / '.bash_profile'
        old_login.write_bytes((REPO / 'bash/.bash_profile').read_bytes())
        login = self.home / '.bash_profile'
        login.symlink_to(old_login)
        prior = self.home / '.bash_profile.before-dotfiles'
        prior.write_text('export LOGIN_SENTINEL=original\n')
        self.run_install('--profile', 'omarchy', '--apply')
        self.assertEqual(login.resolve(), REPO / 'bash/.bash_profile')
        self.assertEqual(prior.read_text(), 'export LOGIN_SENTINEL=original\n')
        manifest = next((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        self.run_install('--restore', str(manifest), '--apply')
        self.assertEqual(login.resolve(), old_login)

    def test_custom_login_referencing_saved_initializer_is_not_made_recursive(self):
        login = self.home / '.bash_profile'
        prior = self.home / '.bash_profile.before-dotfiles'
        content = 'source "$HOME/.bash_profile.before-dotfiles"\nexport CUSTOM_LOGIN=yes\n'
        login.write_text(content)
        prior.write_text('export LOGIN_SENTINEL=original\n')
        result = self.run_install('--profile', 'omarchy', '--apply', ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('recursive startup', result.stderr)
        self.assertEqual(login.read_text(), content)
        self.assertEqual(prior.read_text(), 'export LOGIN_SENTINEL=original\n')
        self.assertFalse((self.home / '.local/state/dotfiles/backups').exists())

    def test_desktop_preferences_preserve_unrelated_and_existing_files(self):
        config = self.home / '.config'
        config.mkdir()
        (config / 'user-dirs.dirs').write_text('XDG_MUSIC_DIR="$HOME/Music"\nXDG_DOWNLOAD_DIR="$HOME/Downloads"\n')
        (self.home / 'Downloads').mkdir()
        (self.home / 'Downloads/keep.txt').write_text('keep')
        self.run_install('--profile', 'omarchy', '--apply')
        dirs = (config / 'user-dirs.dirs').read_text()
        self.assertIn('XDG_MUSIC_DIR="$HOME/Music"', dirs)
        self.assertIn('XDG_DOWNLOAD_DIR="$HOME/downloads"', dirs)
        self.assertIn('XDG_PICTURES_DIR="$HOME/media/screenshots"', dirs)
        self.assertEqual((self.home / 'Downloads/keep.txt').read_text(), 'keep')
        self.assertTrue((self.home / 'media/screenshots').is_dir())

    def test_omarchy_transparency_replaces_glassy_or_opaque_mode_and_restores(self):
        toggles = self.home / '.local/state/omarchy/toggles/hypr'
        toggles.mkdir(parents=True)
        for name in ('window-glassy.lua', 'window-opaque.lua', 'no-animations.lua'):
            (toggles / name).write_text('-- original ' + name)
        self.run_install('--profile', 'omarchy')
        self.assertTrue((toggles / 'window-glassy.lua').is_file(), 'preview changed transparency')
        self.run_install('--profile', 'omarchy', '--apply')
        self.assertFalse((toggles / 'window-glassy.lua').exists())
        self.assertFalse((toggles / 'window-opaque.lua').exists())
        self.assertEqual((toggles / 'no-animations.lua').read_text(), '-- original no-animations.lua')
        manifest = next((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        self.run_install('--restore', str(manifest), '--apply')
        for name in ('window-glassy.lua', 'window-opaque.lua'):
            self.assertEqual((toggles / name).read_text(), '-- original ' + name)

    def test_wsl_install_leaves_desktop_transparency_alone(self):
        flag = self.home / '.local/state/omarchy/toggles/hypr/window-glassy.lua'
        flag.parent.mkdir(parents=True)
        flag.write_text('-- original mode')
        self.run_install('--profile', 'wsl', '--apply')
        self.assertEqual(flag.read_text(), '-- original mode')

    def test_absent_brave_preserves_browser_defaults_and_warns(self):
        config = self.home / '.config'
        config.mkdir()
        existing = '[Default Applications]\ntext/html=chromium.desktop\nx-scheme-handler/http=chromium.desktop\nx-scheme-handler/https=chromium.desktop\napplication/pdf=reader.desktop\n'
        (config / 'mimeapps.list').write_text(existing)
        (config / 'hyprland-mimeapps.list').write_text(existing)
        with mock.patch.object(installer.shutil, 'which', return_value=None), contextlib.redirect_stderr(io.StringIO()) as warning:
            preferences = installer.desktop_preferences(self.home)
        for filename in ('.config/mimeapps.list', '.config/hyprland-mimeapps.list'):
            self.assertEqual(preferences.get(filename, existing), existing)
        self.assertIn('Brave', warning.getvalue())
        self.assertIn('brave-bin', warning.getvalue())

    def test_foreign_directory_symlink_is_backed_up_without_touching_its_target(self):
        external = Path(self.tmp.name) / 'other config'
        external.mkdir()
        (external / 'init.lua').write_text('foreign')
        (self.home / '.config').mkdir()
        (self.home / '.config/nvim').symlink_to(external, target_is_directory=True)
        self.run_install('--profile', 'omarchy', '--apply')
        self.assertEqual((external / 'init.lua').read_text(), 'foreign')
        self.assertFalse((self.home / '.config/nvim').is_symlink())
        self.assertTrue((self.home / '.config/nvim/init.lua').is_symlink())

    def test_restore_keeps_empty_directories_behind_original_directory_symlink(self):
        external = Path(self.tmp.name) / 'outside'
        (external / 'lua/config').mkdir(parents=True)
        (self.home / '.config').mkdir()
        (self.home / '.config/nvim').symlink_to(external, target_is_directory=True)
        self.run_install('--profile', 'omarchy', '--apply')
        manifest = next((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        self.run_install('--restore', str(manifest), '--apply')
        self.assertTrue((external / 'lua/config').is_dir())
        self.assertTrue((self.home / '.config/nvim').is_symlink())

    def test_uninstall_leaves_foreign_links_and_local_files(self):
        self.run_install('--profile', 'omarchy', '--apply')
        path = self.home / '.bashrc'
        path.unlink()
        path.symlink_to('/unrelated')
        self.run_install('--profile', 'omarchy', '--uninstall', '--apply')
        self.assertEqual(os.readlink(path), '/unrelated')
        self.assertFalse((self.home / '.bash_profile').exists())

    def test_previous_git_relative_include_keeps_its_original_base_directory(self):
        (self.home / 'private-git.conf').write_text('[user]\n name = Included User\n')
        (self.home / '.gitconfig').write_text('[include]\n path = private-git.conf\n')
        self.run_install('--profile', 'wsl', '--apply')
        env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'))
        env.pop('GIT_CONFIG_GLOBAL', None)
        result = subprocess.run(['git', 'config', '--global', '--includes', '--get', 'user.name'],
                                env=env, text=True, capture_output=True)
        self.assertEqual(result.stdout.strip(), 'Included User')

    def test_generated_preference_parent_conflict_fails_before_any_mutation(self):
        (self.home / '.config').mkdir()
        (self.home / '.config/gtk-3.0').write_text('not a directory')
        result = self.run_install('--profile', 'omarchy', '--apply', ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / '.bashrc').exists())
        self.assertFalse((self.home / '.local/state/dotfiles/backups').exists())

    def test_effective_git_preserves_both_global_files_in_original_precedence(self):
        gitdir = self.home / '.config/git'
        gitdir.mkdir(parents=True)
        (gitdir / 'config').write_text('[credential]\n helper = xdg-helper\n[user]\n name = XDG User\n')
        (self.home / '.gitconfig').write_text('[credential]\n helper = root-helper\n[user]\n name = Root User\n')
        self.run_install('--profile', 'wsl', '--apply')
        env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'), GIT_CONFIG_NOSYSTEM='1')
        env.pop('GIT_CONFIG_GLOBAL', None)
        for key, want in [('credential.helper', ['xdg-helper', 'root-helper']), ('user.name', ['XDG User', 'Root User'])]:
            result = subprocess.run(['git', 'config', '--get-all', key], cwd=self.home, env=env, text=True, capture_output=True)
            self.assertEqual(result.stdout.splitlines(), want)

    def git_values(self, key):
        env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'),
                   GIT_CONFIG_NOSYSTEM='1')
        env.pop('GIT_CONFIG_GLOBAL', None)
        result = subprocess.run(['git', 'config', '--global', '--includes', '--get-all', key],
                                cwd=self.home, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()

    def test_copied_shared_git_configs_keep_saved_private_configs_active(self):
        gitdir = self.home / '.config/git'
        gitdir.mkdir(parents=True)
        shared = (REPO / 'gitconfig/.config/git/config').read_bytes()
        (self.home / '.gitconfig').write_bytes(shared)
        (gitdir / 'config').write_bytes(shared)
        root_private = '[user]\n name = Root Private\n[credential]\n helper = root-private\n'
        xdg_private = '[user]\n name = XDG Private\n[credential]\n helper = xdg-private\n'
        (self.home / '.gitconfig.before-dotfiles').write_text(root_private)
        (gitdir / 'previous.config').write_text(xdg_private)
        self.run_install('--profile', 'omarchy')
        self.run_install('--profile', 'omarchy', '--apply')
        self.assertEqual(self.git_values('user.name'), ['XDG Private', 'Root Private'])
        self.assertEqual(self.git_values('credential.helper'), ['xdg-private', 'root-private'])
        self.assertEqual((self.home / '.gitconfig.before-dotfiles').read_text(), root_private)
        self.assertEqual((gitdir / 'previous.config').read_text(), xdg_private)

    def test_git_link_from_other_checkout_keeps_saved_private_config(self):
        gitdir = self.home / '.config/git'
        gitdir.mkdir(parents=True)
        old_config = Path(self.tmp.name) / 'old checkout/gitconfig/.config/git/config'
        old_config.parent.mkdir(parents=True)
        shared = (REPO / 'gitconfig/.config/git/config').read_bytes()
        old_config.write_bytes(shared)
        (gitdir / 'config').symlink_to(old_config)
        saved = '[user]\n name = Private User\n'
        (gitdir / 'previous.config').write_text(saved)
        self.run_install('--profile', 'wsl', '--apply')
        self.assertEqual(self.git_values('user.name'), ['Private User'])
        self.assertEqual(old_config.read_bytes(), shared)
        self.assertEqual((gitdir / 'previous.config').read_text(), saved)
        manifest = next((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        self.run_install('--restore', str(manifest), '--apply')
        self.assertEqual((gitdir / 'config').resolve(), old_config)

    def test_changed_private_git_configs_keep_relative_includes_and_rollback(self):
        gitdir = self.home / '.config/git'
        gitdir.mkdir(parents=True)
        root_current = '[include]\n path = root-private.conf\n'
        xdg_current = '[include]\n path = xdg-private.conf\n'
        root_old = '[user]\n name = Older Root\n'
        xdg_old = '[user]\n name = Older XDG\n'
        (self.home / 'root-private.conf').write_text('[user]\n name = New Root\n[credential]\n helper = new-root\n')
        (gitdir / 'xdg-private.conf').write_text('[user]\n name = New XDG\n[credential]\n helper = new-xdg\n')
        (self.home / '.gitconfig').write_text(root_current)
        (self.home / '.gitconfig.before-dotfiles').write_text(root_old)
        (gitdir / 'config').write_text(xdg_current)
        (gitdir / 'previous.config').write_text(xdg_old)
        self.run_install('--profile', 'wsl', '--apply')
        self.assertEqual(self.git_values('user.name'), ['New XDG', 'New Root'])
        self.assertEqual(self.git_values('credential.helper'), ['new-xdg', 'new-root'])
        manifest = next((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        self.assertEqual((self.home / '.gitconfig.before-dotfiles').read_text(), root_old)
        self.assertEqual((gitdir / 'previous.config').read_text(), xdg_old)
        self.run_install('--profile', 'wsl', '--apply')
        self.assertEqual(len(list(manifest.parent.parent.glob('*/manifest.json'))), 1)
        self.run_install('--restore', str(manifest), '--apply')
        for path, content in [('.gitconfig', root_current), ('.gitconfig.before-dotfiles', root_old),
                              ('.config/git/config', xdg_current), ('.config/git/previous.config', xdg_old)]:
            self.assertEqual((self.home / path).read_text(), content)

    def test_current_git_configs_can_include_their_saved_predecessors(self):
        gitdir = self.home / '.config/git'
        gitdir.mkdir(parents=True)
        (self.home / '.gitconfig.before-dotfiles').write_text('[user]\n name = Root Original\n')
        (gitdir / 'previous.config').write_text('[credential]\n helper = xdg-original\n')
        (self.home / '.gitconfig').write_text('[include]\n path = .gitconfig.before-dotfiles\n')
        (gitdir / 'config').write_text('[include]\n path = previous.config\n')
        self.assertEqual(self.git_values('user.name'), ['Root Original'])
        self.run_install('--profile', 'wsl', '--apply')
        self.assertEqual(self.git_values('user.name'), ['Root Original'])
        self.assertEqual(self.git_values('credential.helper'), ['xdg-original'])
        manifest = next((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        self.run_install('--profile', 'wsl', '--apply')
        self.assertEqual(self.git_values('user.name'), ['Root Original'])
        self.assertEqual(len(list(manifest.parent.parent.glob('*/manifest.json'))), 1)
        self.run_install('--restore', str(manifest), '--apply')
        self.assertEqual(self.git_values('user.name'), ['Root Original'])

    def test_git_directory_link_keeps_saved_predecessor_available(self):
        old_dir = Path(self.tmp.name) / 'old Git directory'
        old_dir.mkdir()
        (old_dir / 'config').write_text('[include]\n path = identity.conf\n')
        (old_dir / 'previous.config').write_text('[user]\n name = Older User\n')
        (old_dir / 'identity.conf').write_text('[user]\n name = Original User\n')
        helper = old_dir / 'credential-helper'
        helper.write_bytes(b'#!/bin/sh\nexit 0\n')
        helper.chmod(0o755)
        (old_dir / 'private-data').write_bytes(b'\x00\xfffixture')
        (self.home / '.config').mkdir()
        (self.home / '.config/git').symlink_to(old_dir, target_is_directory=True)
        self.run_install('--profile', 'wsl', '--apply')
        self.assertEqual(self.git_values('user.name'), ['Original User'])
        self.assertEqual((self.home / '.config/git/credential-helper').stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.home / '.config/git/private-data').read_bytes(), b'\x00\xfffixture')
        manifest = next((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        self.run_install('--profile', 'wsl', '--apply')
        self.assertEqual(self.git_values('user.name'), ['Original User'])
        self.assertEqual(len(list(manifest.parent.parent.glob('*/manifest.json'))), 1)
        self.run_install('--restore', str(manifest), '--apply')
        self.assertEqual(self.git_values('user.name'), ['Original User'])
        self.assertEqual((self.home / '.config/git').resolve(), old_dir)

    def test_failed_private_git_dependency_copy_rolls_back_directory_migration(self):
        old_dir = Path(self.tmp.name) / 'old Git directory'
        old_dir.mkdir()
        original = '[include]\n path = identity.conf\n'
        (old_dir / 'config').write_text(original)
        (old_dir / 'identity.conf').write_text('[user]\n name = Original User\n')
        (self.home / '.config').mkdir()
        (self.home / '.config/git').symlink_to(old_dir, target_is_directory=True)
        operations = installer.plan_install(self.home, 'wsl')
        def fail_copy(source, destination):
            Path(destination).write_bytes(b'partial')
            raise OSError('fixture copy failure')
        with mock.patch.object(installer.shutil, 'copy2', side_effect=fail_copy), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(OSError, 'fixture copy failure'):
                installer.apply_plan(self.home, operations)
        self.assertEqual((self.home / '.config/git').resolve(), old_dir)
        self.assertEqual((old_dir / 'config').read_text(), original)
        self.assertEqual(self.git_values('user.name'), ['Original User'])
        self.assertFalse((self.home / '.bashrc').exists())

    def test_missing_original_backup_rejects_restore_before_unlinking(self):
        (self.home / '.bashrc').write_text('original')
        self.run_install('--profile', 'wsl', '--apply')
        manifest = next((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        (manifest.parent / 'files/.bashrc').unlink()
        result = self.run_install('--restore', str(manifest), '--apply', ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.home / '.bashrc').is_symlink())

    def test_backup_root_symlink_cannot_import_and_remove_foreign_files(self):
        (self.home / '.bashrc').write_text('original')
        self.run_install('--profile', 'wsl', '--apply')
        manifest = next((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        files = manifest.parent / 'files'
        files.rename(manifest.parent / 'original-files')
        foreign = Path(self.tmp.name) / 'foreign'
        foreign.mkdir()
        (foreign / '.bashrc').write_text('foreign file')
        files.symlink_to(foreign, target_is_directory=True)
        result = self.run_install('--restore', str(manifest), '--apply', ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((foreign / '.bashrc').read_text(), 'foreign file')

    def test_partial_generated_write_rolls_back_all_installed_links(self):
        (self.home / '.bashrc').write_text('original bash')
        (self.home / '.gitconfig').write_text('[user]\n name = Original\n')
        operations = installer.plan_install(self.home, 'wsl')
        original_write = Path.write_text
        def broken_write(path, text, *args, **kwargs):
            if text.startswith(installer.MARKER):
                original_write(path, text[:5], *args, **kwargs)
                raise OSError('simulated disk failure')
            return original_write(path, text, *args, **kwargs)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with mock.patch.object(Path, 'write_text', broken_write):
                with self.assertRaises(OSError):
                    installer.apply_plan(self.home, operations)
        self.assertEqual((self.home / '.bashrc').read_text(), 'original bash')
        self.assertFalse((self.home / '.bashrc').is_symlink())
        self.assertEqual((self.home / '.gitconfig').read_text(), '[user]\n name = Original\n')

    def test_login_keeps_existing_ubuntu_profile_initialization(self):
        (self.home / '.profile').write_text('export PROFILE_SENTINEL=preserved\n')
        self.run_install('--profile', 'wsl', '--apply')
        env = dict(os.environ, HOME=str(self.home))
        result = subprocess.run(['bash', '--noprofile', '--norc', '-c',
                                 'source "$HOME/.bash_profile"; printf "%s" "${PROFILE_SENTINEL:-missing}"'],
                                env=env, text=True, capture_output=True)
        self.assertEqual(result.stdout, 'preserved')

    def test_non_epic_profile_removes_owned_work_links_and_keeps_credentials(self):
        operations = installer.plan_install(self.home, 'wsl', epic=True)
        with contextlib.redirect_stdout(io.StringIO()):
            installer.apply_plan(self.home, operations)
        private = self.home / '.codex-epic/auth.json'
        private.parent.mkdir()
        private.write_text('private account stays here')
        self.assertTrue((self.home / '.config/dotfiles/epic.enabled').is_symlink())
        self.run_install('--profile', 'wsl', '--apply')
        for name in ['.config/dotfiles/epic.enabled', '.config/dotfiles/shell/epic.bash',
                     '.config/dotfiles/git-epic-include.conf', '.local/bin/codex-epic']:
            self.assertFalse((self.home / name).exists())
        self.assertEqual(private.read_text(), 'private account stays here')

    def test_preexisting_git_theme_is_backed_up_whole_and_restored_intact(self):
        theme = self.home / '.config/omarchy/themes/agamotto'
        (theme / '.git').mkdir(parents=True)
        (theme / '.git/private-marker').write_text('keep repository metadata')
        (theme / 'backgrounds').mkdir()  # original empty directory must also survive restore
        (theme / 'colors.toml').write_text('old theme content')
        self.run_install('--profile', 'omarchy', '--apply')
        self.assertFalse((theme / '.git').exists(), 'foreign Git marker would make Omarchy reject linked payloads')
        self.assertTrue((theme / 'colors.toml').is_symlink())
        manifests = list((self.home / '.local/state/dotfiles/backups').glob('*/manifest.json'))
        self.assertEqual(len(manifests), 1)
        self.run_install('--restore', str(manifests[0]), '--apply')
        self.assertEqual((theme / '.git/private-marker').read_text(), 'keep repository metadata')
        self.assertEqual((theme / 'colors.toml').read_text(), 'old theme content')
        self.assertTrue((theme / 'backgrounds').is_dir())

    @unittest.skipUnless(shutil.which('omarchy') and shutil.which('foot') and Path('/usr/share/omarchy').is_dir(),
                         'Omarchy desktop tools unavailable')
    def test_existing_git_theme_can_generate_real_omarchy_and_foot_configuration(self):
        (self.home / '.config/omarchy/themes/agamotto/.git').mkdir(parents=True)
        runtime = self.home / 'runtime'
        runtime.mkdir(mode=0o700)
        self.run_install('--profile', 'omarchy', '--apply')
        env = dict(os.environ, HOME=str(self.home), OMARCHY_PATH='/usr/share/omarchy',
                   OMARCHY_THEME_HEADLESS='1', XDG_RUNTIME_DIR=str(runtime))
        for key in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME',
                    'HYPRLAND_INSTANCE_SIGNATURE', 'WAYLAND_DISPLAY', 'DISPLAY'):
            env.pop(key, None)
        result = subprocess.run(['omarchy', 'theme', 'set', 'agamotto'], env=env, text=True,
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        generated = self.home / '.local/state/omarchy/current/theme/foot.ini'
        self.assertTrue(generated.is_file(), result.stderr)
        result = subprocess.run(['foot', '--check-config', '--config', str(self.home / '.config/foot/foot.ini')],
                                env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        if shutil.which('hyprland'):
            # Omarchy 4.5's cold-start cursor hook needs a running compositor;
            # disable that startup effect in this headless parsing fixture.
            verify_env = dict(env, HYPRLAND_INSTANCE_SIGNATURE='dotfiles-config-verification')
            verify_config = self.home / 'verify.lua'
            verify_config.write_text('omarchy_startup_cursor_pending = false\ndofile(' +
                                     repr(str(self.home / '.config/hypr/hyprland.lua')) + ')\n')
            result = subprocess.run(['hyprland', '--verify-config', '--config', str(verify_config)],
                                    env=verify_env, text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_directory_link_migration_preserves_unselected_private_preferences(self):
        config = self.home / '.config'
        config.mkdir()
        previous = Path(self.tmp.name) / 'old managed config'
        values = {'hypr/monitors.lua': '-- personal monitor setup\n',
                  'foot/local.ini': '[colors-dark]\nalpha=0.85\n',
                  'tmux/local.conf': 'set -g status-position bottom\n',
                  'dotfiles/local.bash': 'export PRIVATE_SENTINEL=keep\n'}
        for relative, content in values.items():
            old_file = previous / relative
            old_file.parent.mkdir(parents=True, exist_ok=True)
            old_file.write_text(content)
        for name in ['hypr', 'foot', 'tmux', 'dotfiles']:
            (config / name).symlink_to(previous / name, target_is_directory=True)
        self.run_install('--profile', 'omarchy', '--apply')
        for relative, content in values.items():
            self.assertTrue((config / relative).is_file(), relative)
            self.assertEqual((config / relative).read_text(), content)
            self.assertEqual((previous / relative).read_text(), content)


if __name__ == '__main__':
    unittest.main()
