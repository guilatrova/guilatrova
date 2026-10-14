#!/usr/bin/env python3
"""Fetch private Orca counters and render public aggregate images."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
from string import Template
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('totalAgentsSpawned', 'totalAgentTimeMs', 'totalPRsCreated')
VARIANTS = {
    'dark': ('dark', 900, 330),
    'light': ('light', 900, 330),
    'dark-mobile': ('dark mobile', 400, 560),
    'light-mobile': ('light mobile', 400, 560),
}


class StatsError(Exception):
    """An actionable error that contains no private source identifiers."""


def load_sources(env_file):
    """Read a JSON-valued dotenv entry without executing shell expressions."""
    try:
        entries = [line.strip() for line in env_file.read_text().splitlines()
                   if line.strip() and not line.lstrip().startswith('#')]
    except OSError:
        raise StatsError('Cannot read the private configuration file.') from None
    values = []
    for line in entries:
        key, separator, value = line.partition('=')
        if key.strip() == 'ORCA_STATS_SOURCES' and separator:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values.append(value)
    if len(values) != 1:
        raise StatsError('Set exactly one ORCA_STATS_SOURCES JSON array in the private configuration.')
    try:
        sources = json.loads(values[0])
    except ValueError:
        raise StatsError('ORCA_STATS_SOURCES must be a valid JSON array.') from None
    if not isinstance(sources, list) or not sources:
        raise StatsError('ORCA_STATS_SOURCES must contain at least one source.')
    seen = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) - {'path', 'host', 'port'}:
            raise StatsError('A source accepts only path, host, and port.')
        path = source.get('path')
        if not isinstance(path, str) or not path or '\x00' in path or '\n' in path:
            raise StatsError('Every source needs a valid path.')
        if 'host' in source:
            host = source['host']
            if not isinstance(host, str) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.:@-]*', host):
                raise StatsError('An SSH source needs a valid host or SSH alias.')
            port = source.get('port', 22)
            if type(port) is not int or not 1 <= port <= 65535 or not path.startswith('/'):
                raise StatsError('SSH sources need an absolute path and a valid port.')
            identity = (host, port, path)
        else:
            if 'port' in source:
                raise StatsError('Only SSH sources accept a port.')
            resolved = Path(path).expanduser()
            if not resolved.is_absolute():
                raise StatsError('Local sources need an absolute path or a ~/ path.')
            source['path'] = str(resolved.resolve())
            identity = (source['path'],)
        if identity in seen:
            raise StatsError('The private configuration contains a duplicate source.')
        seen.add(identity)
    return sources


def read_local(source):
    return Path(source['path']).read_text()


def read_ssh(source):
    result = subprocess.run(
        ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
         '-o', 'StrictHostKeyChecking=yes', '-p', str(source.get('port', 22)),
         '--', source['host'], 'cat -- ' + shlex.quote(source['path'])],
        capture_output=True, text=True, timeout=25, check=True,
    )
    return result.stdout


def parse_counters(payload):
    try:
        data = json.loads(payload)
    except ValueError:
        raise StatsError('A source returned invalid JSON; previous images were preserved.') from None
    if not isinstance(data, dict) or data.get('schemaVersion') != 1:
        raise StatsError('Unsupported Orca stats schema; previous images were preserved.')
    aggregates = data.get('aggregates')
    if not isinstance(aggregates, dict):
        raise StatsError('A source is missing its aggregate counters; previous images were preserved.')
    counters = {}
    for field in FIELDS:
        value = aggregates.get(field)
        if type(value) is not int or value < 0:
            raise StatsError('A source contains missing or invalid counters; previous images were preserved.')
        counters[field] = value
    return counters


def collect_one(source):
    reader = read_ssh if 'host' in source else read_local
    try:
        payload = reader(source)
    except (OSError, UnicodeError, subprocess.SubprocessError):
        raise StatsError('Cannot read a configured source. Check private paths, SSH access, and connectivity; previous images were preserved.') from None
    return parse_counters(payload)


def collect_totals(sources):
    with ThreadPoolExecutor(max_workers=min(8, len(sources))) as pool:
        counters = list(pool.map(collect_one, sources))
    return {field: sum(counter[field] for counter in counters) for field in FIELDS}


def render_images(totals, updated_at, template):
    values = [f"{totals[FIELDS[0]]:,}",
              f"{Decimal(totals[FIELDS[1]]) / Decimal(3600000):,.1f}",
              f"{totals[FIELDS[2]]:,}"]
    timestamp = updated_at.astimezone(timezone.utc).strftime('%b %d, %Y · %H:%M UTC')
    result = {}
    for name, (theme, width, height) in VARIANTS.items():
        replacements = dict(theme=theme, width=width, height=height,
                            right=width - 10, bottom=height - 10, updated=timestamp,
                            rule_width=width - (48 if "mobile" in theme else 64))
        for index, value in enumerate(values):
            replacements[f'value{index}'] = value
            replacements[f'size{index}'] = min(44, 240 / (len(value) * .64))
        result[f'orca-stats-{name}.svg'] = Template(template).substitute(replacements)
    return result


def write_images(images, output_dir):
    """Stage every completed render before replacing published images."""
    output_dir.mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        for name, content in images.items():
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output_dir,
                                             suffix='.tmp', delete=False) as file:
                staged.append((Path(file.name), output_dir / name))
                file.write(content)
            os.chmod(file.name, 0o644)
        for temporary, destination in staged:
            temporary.replace(destination)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def update(env_file, output_dir, template_path):
    sources = load_sources(env_file)
    totals = collect_totals(sources)
    template = template_path.read_text()
    images = render_images(totals, datetime.now(timezone.utc), template)
    write_images(images, output_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    args = parser.parse_args()
    try:
        update(args.env_file, ROOT / 'assets', ROOT / 'scripts/orca-stats.svg')
    except StatsError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print('Could not render or write the stats images. Check template and output permissions.', file=sys.stderr)
        return 1
    print('Updated the AI workshop images.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
