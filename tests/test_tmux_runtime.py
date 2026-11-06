"""Acceptance check in a private tmux server; never connects to the user's server."""
import os
from pathlib import Path
import pty
import shutil
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('tmux'), 'tmux unavailable')
class TmuxRuntimeTests(unittest.TestCase):
    def test_last_pane_exits_its_client_and_preserves_other_session(self):
        with tempfile.TemporaryDirectory(prefix='tmux acceptance ') as directory:
            root = Path(directory)
            home = root / 'home with spaces'
            home.mkdir()
            env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
                       XDG_CACHE_HOME=str(home / '.cache'), TERM='xterm-256color')
            env.pop('TMUX', None)
            env.pop('TMUX_PANE', None)
            subprocess.run([str(REPO / 'install'), '--profile', 'wsl', '--home', str(home), '--apply'],
                           env=env, capture_output=True, check=True)
            base = ['tmux', '-S', str(root / 'private.sock')]
            master = slave = None
            client = None
            try:
                result = subprocess.run([*base, '-f', str(home / '.config/tmux/tmux.conf'),
                                         'new-session', '-d', '-s', 'zero', '--', '/usr/bin/sleep', '60'],
                                        env=env, text=True, capture_output=True)
                if result.returncode and 'Operation not permitted' in result.stderr:
                    self.skipTest('sandbox blocks private Unix sockets; run this test outside the sandbox')
                self.assertEqual(result.returncode, 0, result.stderr)
                subprocess.run([*base, 'new-session', '-d', '-s', 'one', '--', '/usr/bin/sleep', '60'],
                               env=env, check=True, capture_output=True)
                master, slave = pty.openpty()
                client = subprocess.Popen([*base, 'attach-session', '-t', 'one'], env=env,
                                          stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
                for _ in range(100):
                    result = subprocess.run([*base, 'list-clients', '-F', '#{session_name}'],
                                            env=env, text=True, capture_output=True)
                    if 'one' in result.stdout.splitlines():
                        break
                    time.sleep(0.03)
                else:
                    self.fail('isolated tmux client did not attach')
                # Kill the actual last pane, matching closing the final shell.
                subprocess.run([*base, 'kill-pane', '-t', 'one:'], env=env, check=True, capture_output=True)
                try:
                    status = client.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.fail('closing the final pane moved this client into another session')
                self.assertEqual(status, 0)
                result = subprocess.run([*base, 'has-session', '-t', '=zero'], env=env, capture_output=True)
                self.assertEqual(result.returncode, 0)
            finally:
                if client and client.poll() is None:
                    client.terminate()
                    client.wait(timeout=3)
                for descriptor in (master, slave):
                    if descriptor is not None:
                        os.close(descriptor)
                subprocess.run([*base, 'kill-server'], env=env, capture_output=True)


if __name__ == '__main__':
    unittest.main()
