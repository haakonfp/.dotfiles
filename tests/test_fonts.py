"""Installer behavior with local archives and fake external commands only."""
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/install-fonts.sh'
STYLES = ['Thin','ThinItalic','ExtraLight','ExtraLightItalic','Light','LightItalic',
          'Regular','Italic','Medium','MediumItalic','SemiBold','SemiBoldItalic',
          'Bold','BoldItalic','ExtraBold','ExtraBoldItalic']


class FontTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='font fixtures ')
        self.root = Path(self.temp.name)
        self.home = self.root / 'home with spaces'
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'calls'
        self.archive = self.root / 'fixture.tar.xz'
        self.env = {**os.environ, 'HOME':str(self.home), 'PATH':str(self.bin)+':'+os.environ['PATH'],
                    'FONT_TEST_LOG':str(self.log), 'FONT_TEST_ARCHIVE':str(self.archive)}
        self.write_archive()
        self.tool('curl', '''import os, shutil, sys
args=sys.argv[1:]
assert args[-1] == 'https://github.com/ryanoasis/nerd-fonts/releases/download/v3.5.1/JetBrainsMono.tar.xz', args
with open(os.environ['FONT_TEST_LOG'],'a') as f: f.write('download\\n')
shutil.copyfile(os.environ['FONT_TEST_ARCHIVE'], args[args.index('--output')+1])
''')
        # The network fixture cannot have the release archive's digest. Substitute
        # only the crypto command; the real download/verify/extract/copy flow runs.
        self.tool('sha256sum', '''import sys,os
s=sys.stdin.read()
assert s.startswith('04d5e8f903693f9dd13e16f867e994834e681eb3c72c0d337a770dcda09010cf  '),s
sys.exit(1 if os.environ.get('FONT_TEST_BAD_SHA') else 0)
''')
        self.tool('fc-cache', '''import os
with open(os.environ['FONT_TEST_LOG'],'a') as f: f.write('cache\\n')
''')

    def tearDown(self):
        self.temp.cleanup()

    def tool(self,name,body):
        path = self.bin / name
        path.write_text('#!/usr/bin/python3\n'+body)
        path.chmod(0o755)

    def write_archive(self,license=True,missing=False):
        with tarfile.open(self.archive,'w:xz') as archive:
            names = ['JetBrainsMonoNerdFontMono-'+s+'.ttf' for s in STYLES]
            if missing:
                names.pop()
            names += ['JetBrainsMonoNerdFont-Regular.ttf','JetBrainsMonoNLNerdFontMono-Regular.ttf']
            if license:
                names += ['OFL.txt']
            for name in names:
                data = ('fixture '+name).encode()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info,io.BytesIO(data))

    def run_script(self,*args,env=None):
        return subprocess.run(['/bin/bash',str(SCRIPT),*args],capture_output=True,text=True,env=env or self.env)

    def test_dry_run_never_invokes_tools_or_creates_paths(self):
        for name in ['curl','sha256sum','fc-cache','wslpath','powershell.exe','mktemp']:
            self.tool(name,"raise RuntimeError('dry run invoked a side effect')\n")
        result = self.run_script('--dry-run','--windows')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Windows',result.stdout)
        self.assertEqual(list(self.home.iterdir()),[])
        self.assertFalse(self.log.exists())

    def test_install_only_full_mono_family_with_license_and_repeat_avoids_download(self):
        result = self.run_script()
        self.assertEqual(result.returncode,0,result.stderr)
        destination = self.home / '.local/share/fonts/jetbrains-mono-nerd'
        self.assertEqual(sorted(p.name for p in destination.glob('*.ttf')),
                         sorted('JetBrainsMonoNerdFontMono-'+s+'.ttf' for s in STYLES))
        self.assertEqual((destination/'OFL.txt').read_text(),'fixture OFL.txt')
        self.assertEqual(self.log.read_text(),'download\ncache\n')
        result = self.run_script()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.log.read_text(),'download\ncache\n')

    def test_bad_digest_never_creates_font_destination(self):
        result = self.run_script(env={**self.env,'FONT_TEST_BAD_SHA':'1'})
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.home/'.local').exists())
        self.assertEqual(self.log.read_text(),'download\n')

    def test_missing_license_or_variant_does_not_install_partial_family(self):
        for options in [{'license':False}, {'missing':True}]:
            self.write_archive(**options)
            result = self.run_script()
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((self.home/'.local').exists())

    def test_windows_handoff_preserves_arguments_with_spaces(self):
        self.tool('wslpath', '''import sys
assert sys.argv[1] == '-w'
print('C:\\\\Windows Share'+sys.argv[2])
''')
        self.tool('powershell.exe', '''import sys,os,json
with open(os.environ['FONT_TEST_LOG'],'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
''')
        result = self.run_script('--windows')
        self.assertEqual(result.returncode,0,result.stderr)
        args = json.loads(self.log.read_text().splitlines()[-1])
        self.assertIn('-File',args)
        self.assertTrue(args[args.index('-File')+1].endswith('/windows/Install-Fonts.ps1'))
        self.assertEqual(args[args.index('-SourceDirectory')+1],
                         'C:\\Windows Share'+str(self.home / '.local/share/fonts/jetbrains-mono-nerd'))


if __name__ == '__main__':
    unittest.main()
