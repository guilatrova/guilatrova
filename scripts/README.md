# Update the AI workshop

Requires Python 3.9+ and OpenSSH for remote sources. No Python packages are needed.

1. Copy `.env.example` to `.env` in the repository root.
2. Set `ORCA_STATS_SOURCES` to a single-line JSON array. Each entry is a local `{"path":"/absolute/path/to/orca-stats.json"}` or an SSH `{"host":"user@ssh-alias","path":"/absolute/remote/path/orca-stats.json","port":22}`. Omit `port` to use 22. Local paths may start with `~/`. Remote paths must be absolute. Use existing SSH keys/config and known hosts; SSH is noninteractive.
3. Run `python3 scripts/update_orca_stats.py` from the repository root, or invoke the script by its absolute path from any directory. Use `--env-file /private/path/to/config` to select another configuration file.

The command pulls current counters from every configured source, sums agent starts, elapsed agent milliseconds, and PR counters, then updates the four `assets/orca-stats-*.svg` images used by the README. It uses the collection time for **Last updated**. All reads must succeed and contain valid nonnegative integer counters; a missing or invalid source exits nonzero and preserves the previous images. It never substitutes zeros for unavailable data.

Only aggregate values and the collection timestamp reach the images. Source identities, paths, counts, event records, and PR URLs remain private. `.env` and its variants are ignored by Git; the example contains placeholders only. Do not configure the same physical source through multiple aliases: its counters would be counted again. PR counters are summed as recorded, without cross-source deduplication.

Commit and push the generated images when you want to publish the refreshed profile. The script does not alter branches, run Git pull, commit, or push. For unattended publication on macOS, use the service below.

The Pixel design, themes, icons, and copy are owned by `scripts/orca-stats.svg`. Desktop and mobile assets are generated from that one template. Do not edit generated images directly.

Run checks with `python3 -m unittest discover -s tests -v`.

## Daily macOS service

Run `python3 scripts/install_orca_stats_service.py` to install or update the user LaunchAgent `dev.guilatrova.orca-stats`. It targets `master` by default; `--branch` and `--env-file` can override the publication branch and private source configuration. Configure remote sources with their Tailscale IP or Tailscale SSH alias in `.env`; the service does not fall back to LAN addresses.

The service checks its local schedule once per minute and performs collection/publication once per day, at the first check at or after **10:30 America/Sao_Paulo**. This keeps the publishing time in Brasilia even if the Mac's system timezone changes. If the Mac is asleep or logged out, it can catch up after waking or logging in. It does not wake or power on the Mac.

If any source is unavailable, the service performs **no commit or push** and records that day's attempt. It tries again the next day. Git/network errors also wait until the next day. A file lock prevents overlapping runs. The last successful public images remain available.

Each publication uses a disposable clone of the target branch, stages only the generated SVGs, and pushes normally. It never force-pushes, switches your working branch, stages your edits, or changes your checkout. Concurrent remote commits can reject a push; it will try again on the next day.

The installer copies the publisher and collector to `~/Library/Application Support/AI Workshop Stats/`. It references the existing private `.env`; source changes take effect on the next run. Re-run the installer to update the installed code. Git authentication and SSH keys must work without prompting. The agent runs in your logged-in macOS user session.

- Status: `launchctl print gui/$(id -u)/dev.guilatrova.orca-stats`
- Logs: `~/Library/Logs/AI Workshop Stats/publisher.log` and `publisher-error.log`
- Last attempt/result: `~/Library/Application Support/AI Workshop Stats/state.json`
- Unload: `launchctl bootout gui/$(id -u)/dev.guilatrova.orca-stats`
- To keep it disabled after login, also remove `~/Library/LaunchAgents/dev.guilatrova.orca-stats.plist`.

Installing after today's scheduled time may publish immediately if no attempt has been recorded today.
