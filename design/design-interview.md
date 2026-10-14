# Profile design direction

## Profile

The profile uses the existing CV pixel art as its header. The user selected a clean portfolio: prominent pixel art, few badges, and organized projects. The header actions are Hire me, Install my skills with the Claude icon, and Follow on X.

## My AI workshop

The user chose **Pixel workshop** after comparing it with Studio. The approved visual uses restrained pixel icons, stepped corners, monospaced numerals, and warm orange accents that match the profile illustration. Keep a single surface with three metrics, arranged horizontally on desktop and vertically on mobile. Provide light and dark themes.

The heading is **My AI workshop**. The footer contains only **Last updated:** followed by the data capture timestamp. Do not expose source counts, machine names, source-combination wording, or automatic-update messaging in the public visual or its surrounding copy.

## Data scope

Use only aggregate fields from `orca-stats.json`: agent starts, agent hours, and PRs created. Sum an arbitrary number of sources. Do not add token usage or costs; the user explicitly confirmed this scope after asking about tokens.

The approved Pixel design is now rendered from `scripts/orca-stats.svg`. The updater collects aggregate counters from private configuration and generates the light/dark desktop/mobile images embedded in the README. The image timestamp describes the latest successful collection.

The profile README is the live preview source. The earlier standalone comparison was removed to keep one visual implementation.
