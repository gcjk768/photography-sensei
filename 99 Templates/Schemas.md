---
type: schema
about: Canonical state object and data shapes for the Photo Sensei pipeline
last-updated: 2026-06-20
---

# Schemas — Canonical State & Data Shapes

> The Head Coach reads/writes this structure. `progress-tracker` serialises the relevant fields into
> session-note frontmatter. **Keep field names stable** — Dataview queries (`00 Dashboard.md`) and the
> eval harness (`08 Evals/run_eval.py`) depend on them.

## The `session` object

One per photo. The Head Coach owns it; each agent receives only the slice it needs (state design
drives reasoning quality, and limits the blast radius of a bad read).

```jsonc
session = {
  "photo_path": "str",                 // _attachments/<timestamp>.jpg — the ORIGINAL, never mutated
  "genre": "str | null",               // set at classify; MAY be corrected on replan (step 5)
  "intent": "str | null",              // what J was going for (stated or inferred)
  "evidence": [                        // grounded observations — the anti-hallucination ledger
    { "claim": "str", "region": "str|null", "exif_field": "str|null", "confidence": "low|med|high" }
  ],
  "scores": {                          // ints 1–5, owned by perception analysts
    "composition": "int", "light": "int", "colour": "int", "story": "int", "technical": "int"
  },
  "masters": [
    { "name": "str", "technique": "str", "apply_to_this_shot": "str" }
  ],
  "annotations": [
    { "n": "int", "type": "circle|arrow|box|dashed_box|grid", "colour": "red|green|yellow|cyan",
      "region": "str", "label": "str" }
  ],
  "edit":    { "path": "str", "changes": "str" },        // or null
  "mission": { "title": "str", "constraint": "str", "targets_dimension": "str" },  // or null
  "guardrails": { "input_ok": "bool", "output_ok": "bool", "notes": "str" },
  "trace":      { "agents_run": ["str"], "model": "str", "started": "iso8601", "ended": "iso8601" }
}
```

### Field rules

- **`photo_path`** — points at the ORIGINAL. Annotated/edited files are *new* paths under
  `_attachments/` (`*_annotated.jpg`, `*_edit.jpg`). Originals are never overwritten.
- **`genre`** — free-text but should be one of the coached genres (street, landscape, portrait, macro,
  architecture, wildlife, still-life, food, night, astro, abstract, documentary, travel,
  long-exposure, …). Corrected in place on replan.
- **`evidence`** — every analyst claim must land here with a `region` and/or `exif_field`. Ungrounded
  claims are discarded or down-weighted. This is the cascading-hallucination firewall.
- **`scores`** — exactly the five dimensions that map to frontmatter. The 7-dimension level system
  (Composition, Light, Colour/Tone, Subject/Story, Technical, **Post-processing**, **Genre-craft**) is
  used in prose/Skill Profile; only the five quantified at capture time are serialised per session.
- **`annotations[].colour`** — fixed code: **red=fix, green=keep, yellow=consider, cyan=guide**.

## Session-note frontmatter (written by `progress-tracker`)

```yaml
---
date: 2026-06-20
time: "1430"
genre: street
gear: Fujifilm X100VI         # or "OPPO Find N5"
film_sim: Classic Negative
aperture: 5.6                 # f-number, or null
shutter: "1/500"              # or null
iso: 400                      # or null
focal: 23                     # mm (true), or null
exposure_comp: -0.3           # stops, or null
scores:
  composition: 4
  light: 3
  colour: 4
  story: 3
  technical: 4
masters: ["Saul Leiter"]
mission_given: "Shoot 10 frames through glass; one subject each"
tags: [photo-sensei, session, street]
---
```

Validation (deterministic, enforced before write):
- `scores.*` ∈ integers 1–5; all five keys present.
- `date` ISO `YYYY-MM-DD`; `time` a 4-char `HHMM` string.
- `genre` non-empty; `masters` a non-empty list of strings.
- EXIF numerics are numbers or `null` (never invented).

## Trace object (written by `bot.py` → `_traces/<timestamp>.json`)

```jsonc
{
  "photo": "_attachments/<timestamp>.jpg",
  "session_note": "01 Sessions/<...>.md",
  "model": "claude-opus-4-8",
  "agents_dispatched": ["composition-analyst", "light-exposure-analyst", "..."],
  "replan": { "occurred": false, "from_genre": null, "to_genre": null, "reason": null },
  "stage_latency_ms": { "input_guardrail": 12, "analysts": 8400, "annotate": 2100, "report": 5200 },
  "guardrails": { "input_ok": true, "output_ok": true, "notes": "" },
  "tool_calls": ["annotation-artist", "progress-tracker"],
  "started": "2026-06-20T14:30:01+08:00",
  "ended": "2026-06-20T14:30:21+08:00"
}
```

## Golden-set row (see `08 Evals/golden.csv`)

```
id, photo_file, genre, planted_issues, must_mention, expected_scores_min, expected_scores_max, expect_tool
```

Related: [[Agent Contract]] · [[Session Template]] · [[00 Dashboard]]
