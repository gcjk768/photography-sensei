---
description: Pull Instagram post performance (reach/saves/sends) into session notes
argument-hint: "[--dry-run] [--days N] [--limit N]"
allowed-tools: Bash
---

Run the Instagram insights loop to close the post → measure → learn cycle.

Steps:
1. Run `python scripts/ig_insights.py $ARGUMENTS` from the vault root.
   - Live mode needs `IG_ACCESS_TOKEN` and `IG_USER_ID` in `.env` (Business/Creator account — see
     `README.md`). If they're missing, tell J and suggest `--dry-run` to preview the flow.
2. The script matches each live post to a session note that has a `## Post kit` block with an empty
   `Performance:` line (by permalink, else by date proximity) and fills in reach / saves / sends.
   It is **append-only** — it never overwrites an already-filled `Performance:` line.
3. Summarise what was updated. If several posts now have performance data, suggest J run
   `weekly-review-coach` so it can spot which caption styles, sounds, formats, and genres actually earn
   reach/sends/saves for their audience.

Caveat to state: the API cannot attach music or detect trending sounds — that step stays manual
in-app. This command is the **insights feedback loop** only.
