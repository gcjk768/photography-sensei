---
type: dashboard
about: Home / map-of-content for the Photo Sensei vault
tags: [photo-sensei, dashboard]
---

# 📸 Photo Sensei — Dashboard

Your home base. Send a photo to the Telegram bot; everything below fills in automatically as you shoot.

> [!info] Requires the **Dataview** community plugin (Settings → Community plugins → Browse →
> "Dataview" → Install → Enable, then turn on "Enable JavaScript Queries" is *not* needed — these are
> DQL blocks). Calendar & Templater are optional.

## How to use
1. `export TELEGRAM_BOT_TOKEN=…` then `python bot.py`.
2. DM the bot a photo → get the 📸 Photo Coach Report + an annotated image (+ sometimes an edit).
3. Each photo is logged to `01 Sessions/`; your levels roll forward in [[Skill Profile]].
4. Ask the bot for a **"weekly review"** or **"my habits"** any time.

## Jump to
- [[Skill Profile]] — your 7-dimension levels & growth edge
- [[_Recipe Index]] — which Fujifilm recipe when · [[Classic Negative C7]] (baseline)
- [[_Mission Library]] — practice drills (fundamentals first)
- [[_Masters Index]] — who to study by genre · [[Fan Ho]] · [[Saul Leiter]]
- [[Fujifilm X100VI]] · [[OPPO Find N5]] — gear notes
- Theory: [[Exposure Triangle]] · [[Composition Basics]] · [[Reading the Histogram]] · [[Seeing Light]]
- [[_Eval Guide]] — how quality is measured (golden set + LLM-judge)

## Recent sessions
```dataview
TABLE WITHOUT ID
  file.link AS "Session",
  genre AS "Genre",
  scores.composition AS "Comp",
  scores.light AS "Light",
  scores.colour AS "Col",
  scores.story AS "Story",
  scores.technical AS "Tech",
  mission_given AS "Mission"
FROM "01 Sessions"
WHERE date
SORT date DESC, time DESC
LIMIT 15
```

## Score trend (averages across all logged sessions)
```dataview
TABLE WITHOUT ID
  "Composition" AS Dimension, round(average(rows.scores.composition), 2) AS "Avg"
FROM "01 Sessions"
WHERE date
GROUP BY true
```
> The full per-dimension running averages, best, trend, and your **growth edge** live in
> [[Skill Profile]] (maintained by `progress-tracker`).

## This week
```dataview
LIST
FROM "01 Sessions"
WHERE date >= date(today) - dur(7 days)
SORT date DESC
```

## Streak & milestones
- Sessions logged: see [[Skill Profile]] frontmatter `sessions:`.
- Milestones (first Lv4, 10-session streak, first time shooting a new genre) are tracked in
  [[Skill Profile]] → **Milestones**.

---
*Workflow per photo:* input guardrail → see it → classify & route (cost-aware) → **ground every
claim** → monitor/replan → annotate → edit-if-it-teaches → **reflect** → schema-validate → **log** →
assign mission. Defense in depth against cascading hallucination.
