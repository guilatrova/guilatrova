#!/usr/bin/env python3
"""Install the daily AI workshop publisher as a macOS user LaunchAgent."""

import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

from update_orca_stats import ROOT, load_sources

LABEL = 'dev.guilatrova.orca-stats'


def git_value(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def install(env_file, branch):
    if sys.platform != 'darwin':
        raise SystemExit('This installer requires macOS.')
    load_sources(env_file)
    remote = git_value('remote', 'get-url', 'origin')
    git_name, git_email = git_value('config', 'user.name'), git_value('config', 'user.email')
    if not remote or not git_name or not git_email:
        raise SystemExit('Configure the repository remote and Git author identity first.')
    subprocess.run(['git', 'check-ref-format', '--branch', branch], check=True, capture_output=True)
    support = Path.home() / 'Library/Application Support/AI Workshop Stats'
    logs = Path.home() / 'Library/Logs/AI Workshop Stats'
    agents = Path.home() / 'Library/LaunchAgents'
    for path in [support, logs, agents]:
        path.mkdir(parents=True, exist_ok=True)
    support.chmod(0o700)
    for name in ['publish_orca_stats.py', 'update_orca_stats.py']:
        shutil.copyfile(ROOT / 'scripts' / name, support / name)
    config = {'state_dir': str(support), 'env_file': str(env_file.resolve()),
              'remote': remote, 'branch': branch, 'git_name': git_name, 'git_email': git_email}
    config_file = support / 'service.json'
    config_file.write_text(json.dumps(config, indent=2) + '\n')
    config_file.chmod(0o600)
    plist = {
        'Label': LABEL,
        'ProgramArguments': [sys.executable, str(support / 'publish_orca_stats.py'), str(config_file)],
        'WorkingDirectory': str(support),
        'EnvironmentVariables': {'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'},
        'StartInterval': 60,
        'RunAtLoad': True,
        'ProcessType': 'Background',
        'StandardOutPath': str(logs / 'publisher.log'),
        'StandardErrorPath': str(logs / 'publisher-error.log'),
    }
    plist_file = agents / (LABEL + '.plist')
    with plist_file.open('wb') as file:
        plistlib.dump(plist, file)
    subprocess.run(['plutil', '-lint', str(plist_file)], check=True, capture_output=True)
    domain = 'gui/' + str(os.getuid())
    target = domain + '/' + LABEL
    loaded = subprocess.run(['launchctl', 'print', target], capture_output=True).returncode == 0
    if loaded:
        subprocess.run(['launchctl', 'bootout', target], check=True)
    subprocess.run(['launchctl', 'bootstrap', domain, str(plist_file)], check=True)
    print('Installed daily publication at 10:30 America/Sao_Paulo.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--branch', default='master')
    args = parser.parse_args()
    install(args.env_file, args.branch)


if __name__ == '__main__':
    main()
