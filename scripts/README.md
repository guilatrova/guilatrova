# Update the AI workshop

Requires Python 3.9+ and OpenSSH for remote sources. No Python packages are needed.

1. Copy `.env.example` to `.env` in the repository root.
2. Set `ORCA_STATS_SOURCES` to a single-line JSON array. Each entry is a local `{"path":"/absolute/path/to/orca-stats.json"}` or an SSH `{"host":"user@ssh-alias","path":"/absolute/remote/path/orca-stats.json","port":22}`. Omit `port` to use 22. Local paths may start with `~/`. Remote paths must be absolute. Use existing SSH keys/config and known hosts; SSH is noninteractive.
3. Run `python3 scripts/update_orca_stats.py` from the repository root, or invoke the script by its absolute path from any directory. Use `--env-file /private/path/to/config` to select another configuration file.

The command pulls current counters from every configured source, sums agent starts, elapsed agent milliseconds, and PR counters, then updates the four `assets/orca-stats-*.svg` images used by the README. It uses the collection time for **Last updated**. All reads must succeed and contain valid nonnegative integer counters; a missing or invalid source exits nonzero and preserves the previous images. It never substitutes zeros for unavailable data.

Only aggregate values and the collection timestamp reach the images. Source identities, paths, counts, event records, and PR URLs remain private. `.env` and its variants are ignored by Git; the example contains placeholders only. Do not configure the same physical source through multiple aliases: its counters would be counted again. PR counters are summed as recorded, without cross-source deduplication.

Commit and push the generated images when you want to publish the refreshed profile. The script does not alter branches, run Git pull, commit, or push. It can be invoked by your existing scheduler; no scheduler is installed by this repository.

The Pixel design, themes, icons, and copy are owned by `scripts/orca-stats.svg`. Desktop and mobile assets are generated from that one template. Do not edit generated images directly.

Run checks with `python3 -m unittest discover -s tests -v`.
