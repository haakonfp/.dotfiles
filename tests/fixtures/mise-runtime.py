#!/usr/bin/python3
"""Offline command-boundary fixture for mise's installer and environment output."""
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tomllib

args = sys.argv[1:]
if args[:1] == ['-C']:
    args = args[2:]
home = Path(os.environ['HOME'])
root = home / '.test-mise'
root.mkdir(exist_ok=True)
with (root / 'calls.jsonl').open('a') as stream:
    stream.write(json.dumps(args) + '\n')
with (root / 'invocations.jsonl').open('a') as stream:
    stream.write(json.dumps({'args': args, 'versions_host': os.environ.get('MISE_USE_VERSIONS_HOST'),
                             'cache_dir': os.environ['MISE_CACHE_DIR']}) + '\n')
config_dir = Path(os.environ.get('MISE_CONFIG_DIR', Path(os.environ.get('XDG_CONFIG_HOME', home / '.config')) / 'mise'))
global_config = Path(os.environ.get('MISE_GLOBAL_CONFIG_FILE', config_dir / 'config.toml'))
cache = Path(os.environ['MISE_CACHE_DIR'])


def set_key(target, table, name, value):
    target.parent.mkdir(parents=True, exist_ok=True)
    text = target.read_text() if target.exists() else ''
    heading = re.search(rf'(?m)^\[{re.escape(table)}\]\s*$', text)
    if not heading:
        text += f'\n[{table}]\n'
        heading = re.search(rf'(?m)^\[{re.escape(table)}\]\s*$', text)
    start = heading.end()
    following = re.search(r'(?m)^\[', text[start:])
    end = start + following.start() if following else len(text)
    section = text[start:end]
    line = f'{name} = {json.dumps(value)}'
    pattern = rf'(?m)^{re.escape(name)}\s*=.*$'
    section = re.sub(pattern, lambda _: line, section) if re.search(pattern, section) else section.rstrip() + '\n' + line + '\n'
    target.write_text(text[:start] + section + text[end:])


def exclusions():
    return tomllib.loads(global_config.read_text()).get('settings', {}).get('minimum_release_age_excludes', []) if global_config.exists() else []


if args[0] == 'use':
    if os.environ.get('FAKE_MISE_FAIL'):
        sys.exit(42)
    target = Path(args[args.index('--path') + 1])
    target.parent.mkdir(parents=True, exist_ok=True)
    for spec in (arg for arg in args if '@' in arg):
        name, version = spec.split('@', 1)
        if name == 'dotnet':
            version = '10.0.100'
        elif name == 'claude' and version == 'latest':
            version = '2.7.4'
        elif name == 'codex' and version == 'latest':
            version = '0.167.0'
        elif name == 'neovim' and version == 'latest':
            version = os.environ.get('FAKE_MISE_NVIM_LATEST', '0.12.7')
        if os.environ.get('FAKE_MISE_REQUIRE_FRESH') and spec.endswith('@latest'):
            if (name not in exclusions() or (cache / name).exists() or (cache / 'github').exists()
                    or os.environ.get('MISE_USE_VERSIONS_HOST') != '0'):
                version = {'claude': '2.7.3', 'codex': '0.166.0', 'neovim': '0.12.6'}[name]
        set_key(target, 'tools', name, version)
        binary = root / 'bin' / ('nvim' if name == 'neovim' else name)
        binary.parent.mkdir(exist_ok=True)
        if name == 'dotnet':
            body = 'if [[ $1 == --list-sdks ]]; then echo "10.0.100 [/fixture/sdk]"; else echo 10.0.100; fi'
        elif name == 'neovim':
            body = ('if [[ $1 == --version ]]; then echo ' + shlex.quote('NVIM v' + version) +
                    '; elif [[ "$*" == *nvim-0.12.0* ]]; then ' + ('exit 0' if tuple(map(int, version.split('.'))) >= (0, 12, 0) else 'exit 1') + '; fi')
        else:
            body = 'echo ' + shlex.quote(('v' if name == 'node' else '') + version)
        binary.write_text('#!/bin/bash\n' + body + '\n')
        binary.chmod(0o755)
elif args[0] == 'settings':
    if os.environ.get('FAKE_MISE_SETTINGS_FAIL'):
        sys.exit(45)
    assert args[2] == 'minimum_release_age_excludes', args
    if args[1] == 'get':
        print(json.dumps(exclusions()))
    elif args[1] == 'add':
        set_key(global_config, 'settings', args[2], exclusions() + [args[3]])
    else:
        sys.exit('Unexpected settings command: ' + repr(args))
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
elif args[0] == 'reshim':
    data = Path(os.environ.get('MISE_DATA_DIR', Path(os.environ.get('XDG_DATA_HOME', home / '.local/share')) / 'mise'))
    shims = data / 'shims'
    shims.mkdir(parents=True, exist_ok=True)
    for binary in (root / 'bin').glob('*'):
        shim = shims / binary.name
        shim.unlink(missing_ok=True)
        shim.symlink_to(binary)
else:
    sys.exit('Unexpected mise command: ' + repr(args))
