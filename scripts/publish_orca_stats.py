#!/usr/bin/env python3
"""Publish workshop counters once daily after 10:30 in Brasilia."""

from datetime import datetime, time, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

from update_orca_stats import (
    StatsError, collect_totals, load_sources, render_images, write_images,
)

BRASILIA = ZoneInfo('America/Sao_Paulo')
PUBLISH_TIME = time(10, 30)


class PublishError(Exception):
    pass


def is_due(now, last_attempt):
    local = now.astimezone(BRASILIA)
    return local.time() >= PUBLISH_TIME and last_attempt != local.date().isoformat()


def save_state(path, state):
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        json.dump(state, file)
    temporary.replace(path)


def git(arguments, env, cwd=None, allow_changed=False):
    try:
        result = subprocess.run(['git', *arguments], cwd=cwd, env=env,
                                text=True, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        raise PublishError('Git operation did not confirm completion.') from None
    if result.returncode not in ({0, 1} if allow_changed else {0}):
        raise PublishError('Git operation failed; check remote access and branch status.')
    return result.returncode


def publish(config, totals, collected_at):
    """Create a fresh checkout, commit generated images only, and push normally."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never',
               GIT_AUTHOR_NAME=config['git_name'], GIT_AUTHOR_EMAIL=config['git_email'],
               GIT_COMMITTER_NAME=config['git_name'], GIT_COMMITTER_EMAIL=config['git_email'])
    with tempfile.TemporaryDirectory(prefix='publish-', dir=config['state_dir']) as folder:
        checkout = Path(folder) / 'checkout'
        git(['clone', '--quiet', '--depth', '1', '--single-branch',
             '--branch', config['branch'], '--', config['remote'], str(checkout)], env)
        template = checkout / 'scripts/orca-stats.svg'
        if not template.is_file():
            raise PublishError('The publication branch does not contain the workshop template.')
        images = render_images(totals, collected_at, template.read_text())
        write_images(images, checkout / 'assets')
        git(['add', '--', *('assets/' + name for name in images)], env, checkout)
        if git(['diff', '--cached', '--quiet'], env, checkout, allow_changed=True) == 0:
            return 'unchanged'
        git(['-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null',
             'commit', '--quiet', '-m', 'Update AI workshop statistics'], env, checkout)
        git(['push', '--quiet', 'origin', 'HEAD:refs/heads/' + config['branch']], env, checkout)
    return 'published'


def run_scheduled(config, now=None):
    now = now or datetime.now(timezone.utc)
    directory = Path(config['state_dir'])
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / 'run.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 'busy'
        state_path = directory / 'state.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        if not is_due(now, state.get('last_attempt_date')):
            return 'not_due'
        state = {'last_attempt_date': now.astimezone(BRASILIA).date().isoformat(),
                 'attempted_at': now.isoformat(), 'result': 'started'}
        save_state(state_path, state)
        try:
            totals = collect_totals(load_sources(Path(config['env_file'])))
        except StatsError:
            state['result'] = 'skipped'
            print('Skipped: source collection failed. No commit or push; next attempt is tomorrow.', flush=True)
        else:
            try:
                state['result'] = publish(config, totals, datetime.now(timezone.utc))
                print('Workshop stats: ' + state['result'] + '.', flush=True)
            except (PublishError, OSError, ValueError, KeyError):
                state['result'] = 'failed'
                print('Publication did not confirm completion. No force push; next attempt is tomorrow.', flush=True)
        state['finished_at'] = datetime.now(timezone.utc).isoformat()
        save_state(state_path, state)
        return state['result']


def main():
    if len(sys.argv) != 2:
        print('Usage: publish_orca_stats.py /private/path/service.json', file=sys.stderr)
        return 1
    try:
        config = json.loads(Path(sys.argv[1]).read_text())
        required = {'state_dir', 'env_file', 'remote', 'branch', 'git_name', 'git_email'}
        if set(config) != required or any(not isinstance(value, str) or not value for value in config.values()):
            raise ValueError('Invalid service configuration')
        result = run_scheduled(config)
        return 1 if result == 'failed' else 0
    except (OSError, ValueError, KeyError):
        print('Service could not complete; check private configuration, state, and remote status.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
