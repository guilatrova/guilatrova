from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import publish_orca_stats as publisher
from update_orca_stats import StatsError


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.state.mkdir()
        self.config = {'state_dir': str(self.state), 'env_file': str(self.root / '.env'),
                       'remote': str(self.root / 'remote.git'), 'branch': 'master',
                       'git_name': 'Test Publisher', 'git_email': 'test@example.invalid'}
        self.now = datetime(2026, 10, 15, 13, 30, tzinfo=timezone.utc)
        self.totals = {'totalAgentsSpawned': 12, 'totalAgentTimeMs': 7200000, 'totalPRsCreated': 4}

    def git(self, *args, cwd=None):
        return subprocess.check_output(['git', *args], cwd=cwd, stderr=subprocess.DEVNULL, text=True).strip()

    def test_due_uses_brasilia_and_runs_once_per_date(self):
        self.assertFalse(publisher.is_due(datetime(2026, 10, 15, 13, 29, tzinfo=timezone.utc), None))
        self.assertTrue(publisher.is_due(self.now, None))
        self.assertFalse(publisher.is_due(self.now, '2026-10-15'))
        self.assertTrue(publisher.is_due(datetime(2026, 10, 15, 20, 0, tzinfo=timezone.utc), '2026-10-14'))

    def test_offline_source_never_invokes_git_and_is_not_retried_today(self):
        with patch.object(publisher, 'load_sources', return_value=[{}]), \
             patch.object(publisher, 'collect_totals', side_effect=StatsError('unavailable')) as collect, \
             patch.object(publisher, 'git') as git:
            self.assertEqual(publisher.run_scheduled(self.config, self.now), 'skipped')
            self.assertEqual(publisher.run_scheduled(self.config, self.now), 'not_due')
            self.assertEqual(collect.call_count, 1)
            git.assert_not_called()
            tomorrow = datetime(2026, 10, 16, 13, 30, tzinfo=timezone.utc)
            self.assertEqual(publisher.run_scheduled(self.config, tomorrow), 'skipped')
            self.assertEqual(collect.call_count, 2)

    def test_before_due_time_does_not_collect(self):
        with patch.object(publisher, 'collect_totals') as collect:
            early = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
            self.assertEqual(publisher.run_scheduled(self.config, early), 'not_due')
            collect.assert_not_called()

    def seed_remote(self):
        self.git('init', '--bare', self.config['remote'])
        seed = self.root / 'seed'
        self.git('init', str(seed))
        self.git('checkout', '-b', 'master', cwd=seed)
        self.git('config', 'user.name', 'Test Publisher', cwd=seed)
        self.git('config', 'user.email', 'test@example.invalid', cwd=seed)
        (seed / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/orca-stats.svg', seed / 'scripts/orca-stats.svg')
        (seed / 'README.md').write_text('Unrelated content stays intact.\n')
        self.git('add', '.', cwd=seed)
        self.git('-c', 'commit.gpgsign=false', 'commit', '-m', 'Seed', cwd=seed)
        self.git('remote', 'add', 'origin', self.config['remote'], cwd=seed)
        self.git('push', 'origin', 'master', cwd=seed)
        return seed

    def test_real_git_publication_changes_only_generated_images(self):
        seed = self.seed_remote()
        original_head = self.git('rev-parse', 'HEAD', cwd=seed)
        self.assertEqual(publisher.publish(self.config, self.totals, self.now), 'published')
        changes = self.git('--git-dir=' + self.config['remote'], 'diff-tree', '--no-commit-id', '--name-only', '-r', 'master').splitlines()
        self.assertEqual(set(changes), {
            'assets/orca-stats-dark.svg', 'assets/orca-stats-light.svg',
            'assets/orca-stats-dark-mobile.svg', 'assets/orca-stats-light-mobile.svg'})
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=seed), original_head)
        self.assertEqual(publisher.publish(self.config, self.totals, self.now), 'unchanged')
        self.assertEqual(list(self.state.glob('publish-*')), [])

    def test_rejected_push_does_not_change_remote_or_retry(self):
        self.seed_remote()
        head = self.git('--git-dir=' + self.config['remote'], 'rev-parse', 'master')
        hook = Path(self.config['remote']) / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        with patch.object(publisher, 'load_sources', return_value=[{}]), \
             patch.object(publisher, 'collect_totals', return_value=self.totals):
            self.assertEqual(publisher.run_scheduled(self.config, self.now), 'failed')
            self.assertEqual(publisher.run_scheduled(self.config, self.now), 'not_due')
        self.assertEqual(self.git('--git-dir=' + self.config['remote'], 'rev-parse', 'master'), head)
        self.assertEqual(json.loads((self.state / 'state.json').read_text())['result'], 'failed')


if __name__ == '__main__':
    unittest.main()
