# Profile design interview

## Confirmed direction

The profile uses the existing CV pixel art as its header. The user selected a clean portfolio: prominent pixel art, few badges, and organized projects. The header actions are Hire me, Install my skills with the Claude icon, and Follow on X.

## Orca statistics — visual exploration

The user requests a beautiful visual based only on `orca-stats.json`, summing an arbitrary number of host sources. There are currently two sources, the Mac and Dell. They explicitly requested visual design before implementation.

The visual shows combined recorded agent starts, agent hours, and PRs created. It does not introduce token usage, cost, invented trends, or claims of unique agents. The current mockups use a read-only snapshot of the two hosts collected on October 14, 2026, at approximately 22:48 UTC. Host totals can cover different periods. The future implementation must accept N sources rather than hardcode these two machines.

### Question: visual treatment

- **A — Studio:** open spacing, large numerals, restrained outline icons, a warm accent rule, and a single continuous surface.
- **B — Pixel workshop:** the same metrics and layout hierarchy, with pixel iconography and subtle stepped accents related to the profile illustration.

Both are shown in profile context, with light/dark and mobile preview controls. They share the same collected totals. The mockup is static and labels its snapshot; no refresh job has been implemented.

**Answer:** Pending. No direction is approved yet.

Preview: `design/mockups/orca-stats.html`.
