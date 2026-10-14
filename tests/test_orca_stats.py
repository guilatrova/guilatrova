import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('orca_stats', ROOT / 'scripts/update_orca_stats.py')
stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stats)


def payload(starts=2, hours_ms=3600000, prs=1):
    return {'schemaVersion': 1, 'aggregates': {
        'totalAgentsSpawned': starts, 'totalAgentTimeMs': hours_ms, 'totalPRsCreated': prs,
        'countedPRs': ['https://private.example/repository/pull/1']},
        'events': [{'worktreeId': '/private/host/project'}]}


class StatsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = self.root / '.env'
        self.output = self.root / 'assets'

    def configure(self, count):
        sources = []
        for index in range(count):
            path = self.root / f'private host {index}.json'
            path.write_text(json.dumps(payload(starts=index + 1)))
            sources.append({'path': str(path)})
        self.env.write_text('ORCA_STATS_SOURCES=\'' + json.dumps(sources) + '\'\n')
        return sources

    def test_any_number_of_sources_and_no_private_metadata_in_svg(self):
        self.configure(5)
        stats.update(self.env, self.output, ROOT / 'scripts/orca-stats.svg')
        files = list(self.output.glob('*.svg'))
        self.assertEqual(len(files), 4)
        for file in files:
            text = file.read_text()
            ET.fromstring(text)
            self.assertIn('15 agent starts, 5.0 agent hours, 5 PRs created.', text)
            for forbidden in ['private.example', '/private/host', str(self.root), 'machines', 'countedPRs']:
                self.assertNotIn(forbidden, text)

    def test_bad_source_preserves_all_existing_images(self):
        sources = self.configure(3)
        self.output.mkdir()
        for name in stats.VARIANTS:
            (self.output / f'orca-stats-{name}.svg').write_text('previous image')
        Path(sources[-1]['path']).write_text('{broken')
        with self.assertRaises(stats.StatsError):
            stats.update(self.env, self.output, ROOT / 'scripts/orca-stats.svg')
        self.assertTrue(all(file.read_text() == 'previous image' for file in self.output.iterdir()))

    def test_missing_negative_boolean_and_unknown_schema_are_rejected(self):
        for value in [None, -1, True, 1.25]:
            with self.subTest(value=value), self.assertRaises(stats.StatsError):
                stats.parse_counters(json.dumps(payload(starts=value)))
        with self.assertRaises(stats.StatsError):
            stats.parse_counters('{"schemaVersion":2,"aggregates":{}}')

    def test_zero_is_valid(self):
        self.assertEqual(stats.parse_counters(json.dumps(payload(0, 0, 0))), dict.fromkeys(stats.FIELDS, 0))

    def test_duplicate_local_source_and_invalid_host_are_rejected(self):
        sources = self.configure(1)
        for values in [sources * 2, [{'host': '-oProxyCommand=bad', 'path': '/stats.json'}]]:
            self.env.write_text('ORCA_STATS_SOURCES=' + json.dumps(values))
            with self.assertRaises(stats.StatsError):
                stats.load_sources(self.env)

    def test_ssh_path_is_quoted_and_failures_do_not_expose_host(self):
        source = {'host': 'private-host', 'path': "/data/a 'quote' $(touch BAD).json"}
        with patch.object(stats.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{}')) as run:
            stats.read_ssh(source)
        args, kwargs = run.call_args
        self.assertIsInstance(args[0], list)
        self.assertEqual(stats.shlex.split(args[0][-1]), ['cat', '--', source['path']])
        self.assertFalse(kwargs.get('shell', False))
        self.assertEqual(kwargs['timeout'], 25)
        with patch.object(stats.subprocess, 'run', side_effect=subprocess.TimeoutExpired('private-host', 25)):
            with self.assertRaises(stats.StatsError) as error:
                stats.collect_one(source)
        self.assertNotIn('private-host', str(error.exception))

    def test_missing_config_creates_no_artifacts(self):
        with self.assertRaises(stats.StatsError):
            stats.update(self.env, self.output, ROOT / 'scripts/orca-stats.svg')
        self.assertFalse(self.output.exists())

    def test_explicit_timestamp_and_large_totals_render(self):
        values = {field: 123456789012 for field in stats.FIELDS}
        result = stats.render_images(values, datetime(2026, 10, 14, 22, 48, tzinfo=timezone.utc),
                                     (ROOT / 'scripts/orca-stats.svg').read_text())
        for text in result.values():
            ET.fromstring(text)
            self.assertIn('Last updated: Oct 14, 2026 · 22:48 UTC', text)
            self.assertNotIn('$value', text)


if __name__ == '__main__':
    unittest.main()
