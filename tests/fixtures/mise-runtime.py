#!/usr/bin/python3
"""Offline command-boundary fixture for mise's installer and environment output."""
import json
import os
from pathlib import Path
import re
import shlex
import sys

args = sys.argv[1:]
if args[:1] == ['-C']:
    args = args[2:]
home = Path(os.environ['HOME'])
root = home / '.test-mise'
root.mkdir(exist_ok=True)
with (root / 'calls.jsonl').open('a') as stream:
    stream.write(json.dumps(args) + '\n')
if args[0] == 'use':
    if os.environ.get('FAKE_MISE_FAIL'):
        sys.exit(42)
    target = Path(args[args.index('--path') + 1])
    target.parent.mkdir(parents=True, exist_ok=True)
    text = target.read_text() if target.exists() else '[tools]\n'
    for spec in (arg for arg in args if '@' in arg):
        name, version = spec.split('@', 1)
        if name == 'dotnet':
            version = '10.0.100'
        line = f'{name} = "{version}"'
        pattern = rf'(?m)^{name}\s*=.*$'
        text = re.sub(pattern, line, text) if re.search(pattern, text) else text + line + '\n'
        binary = root / 'bin' / name
        binary.parent.mkdir(exist_ok=True)
        if name == 'dotnet':
            body = 'if [[ $1 == --list-sdks ]]; then echo "10.0.100 [/fixture/sdk]"; else echo 10.0.100; fi'
        else:
            body = 'echo ' + shlex.quote(('v' if name == 'node' else '') + version)
        binary.write_text('#!/bin/bash\n' + body + '\n')
        binary.chmod(0o755)
    target.write_text(text)
elif args[0] == 'env':
    if os.environ.get('FAKE_MISE_ENV_FAIL'):
        sys.exit(43)
    print('export PATH=' + shlex.quote(str(root / 'bin') + ':' + os.environ['PATH']))
    if (root / 'bin/dotnet').exists():
        print('export DOTNET_ROOT=/fixture/sdk')
elif args[0] == 'which':
    binary = root / 'bin' / args[1]
    if not binary.exists():
        sys.exit(1)
    print(binary)
elif args[0] != 'reshim':
    sys.exit('Unexpected mise command: ' + repr(args))
