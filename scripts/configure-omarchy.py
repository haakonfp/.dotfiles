#!/usr/bin/env python3
"""Preview/apply just the one-time desktop preferences, with installer backups."""
import subprocess
import sys
from pathlib import Path

sys.exit(subprocess.call([sys.executable, str(Path(__file__).with_name('install.py')),
                          '--profile', 'omarchy', '--preferences-only', *sys.argv[1:]]))
