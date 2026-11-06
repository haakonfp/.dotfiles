"""WSL clipboard provider behavior with an isolated stand-in for Windows IPC."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('nvim'), 'Neovim is needed for clipboard integration checks')
class ClipboardTests(unittest.TestCase):
    def test_wsl_without_wayland_copies_and_reads_windows_unicode_clipboard(self):
        with tempfile.TemporaryDirectory(prefix='clipboard test ') as directory:
            root = Path(directory)
            binary = root / 'bin'
            binary.mkdir()
            script = binary / 'powershell.exe'
            script.write_text('''#!/usr/bin/python3
import os,sys
from pathlib import Path
p=Path(os.environ['CLIPBOARD_TEST_FILE'])
if 'Set-Clipboard' in sys.argv[-1]: p.write_bytes(sys.stdin.buffer.read())
elif 'Get-Clipboard' in sys.argv[-1]: sys.stdout.buffer.write(p.read_bytes().replace(b'\\n',b'\\r\\n'))
''')
            script.chmod(0o755)
            clipboard = root / 'clipboard'
            result_file = root / 'result.json'
            lua = root / 'verify.lua'
            module = REPO / 'nvim/.config/nvim/lua/config/remote_clipboard.lua'
            lua.write_text(f'''
vim.env.WSL_DISTRO_NAME = "Ubuntu"
vim.env.WAYLAND_DISPLAY = nil
vim.env.TMUX = nil
vim.env.SSH_TTY = nil
vim.env.SSH_CONNECTION = nil
vim.g.omarchy_remote_clipboard_osc52 = false
vim.g.omarchy_remote_clipboard_sync = false
local provider = dofile({json.dumps(str(module))})
provider.setup()
assert(vim.g.clipboard, "WSL direct launch must configure clipboard")
vim.g.clipboard.copy["+"]({{"héllo", "世界"}}, "v")
local copied = vim.fn.readfile(vim.env.CLIPBOARD_TEST_FILE)
vim.fn.writefile({{"external", "世界"}}, vim.env.CLIPBOARD_TEST_FILE, "b")
local pasted = vim.g.clipboard.paste["+"]()
vim.fn.writefile({{vim.fn.json_encode({{ copied = copied, pasted = pasted }})}}, {json.dumps(str(result_file))})
''')
            env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(root / '.config'),
                       XDG_DATA_HOME=str(root / '.local/share'), XDG_STATE_HOME=str(root / '.local/state'),
                       XDG_CACHE_HOME=str(root / '.cache'), PATH=str(binary) + os.pathsep + os.defpath,
                       CLIPBOARD_TEST_FILE=str(clipboard))
            process = subprocess.run(['nvim', '--headless', '-u', 'NONE', '-i', 'NONE',
                                      '-c', 'lua dofile(' + json.dumps(str(lua)) + ')', '-c', 'qa!'],
                                     env=env, text=True, capture_output=True, timeout=20)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(result_file.exists(), process.stderr)
            self.assertEqual(json.loads(result_file.read_text()),
                             {'copied': ['héllo', '世界'], 'pasted': ['external', '世界']})


if __name__ == '__main__':
    unittest.main()
