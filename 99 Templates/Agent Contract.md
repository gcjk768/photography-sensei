---
type: schema
about: The structured return contract every subagent must satisfy
last-updated: 2026-06-20
---

# Agent Contract — Structured-Output Schema

> The lesson: move from "please return JSON" → a defined schema → a **programmatic** check. Every
> subagent returns a compact, parseable block (not just prose). The Head Coach validates and repairs
> it before any of it reaches the vault.

## The return block

```
AGENT: <name>
FINDING: <≤120 words, plain language — what you see and why it matters>
EVIDENCE: <region(s) of frame and/or EXIF field(s) supporting the finding>   # grounding, required
SCORE: <dimension>=<int 1–5>            # ONLY perception agents that own a dimension
ONE_CHANGE: <the single highest-impact action, imperative voice>
CONFIDENCE: <low|med|high>
```

### Field rules

| Field | Rule |
|---|---|
| `AGENT` | exact agent name (matches the file in `.claude/agents/`). |
| `FINDING` | ≤ 120 words, plain language. No filler, no generic tips. |
| `EVIDENCE` | **required for every claim** — a frame region ("lower-left third", "subject's eyes") and/or a named EXIF field ("ShutterSpeed=1/30"). If you cannot see it, do not claim it. |
| `SCORE` | only the five perception analysts emit this; `<dimension>` ∈ {composition, light, colour, story, technical}; value is an **int 1–5**. |
| `ONE_CHANGE` | exactly one action, imperative, controllable at capture (or in post for edit/recipe agents). |
| `CONFIDENCE` | `low` / `med` / `high`. Low-confidence reads trigger the Head Coach's cross-reflection. |

## Who owns which SCORE

| Agent | Owns dimension |
|---|---|
| `composition-analyst` | `composition` |
| `light-exposure-analyst` | `light` |
| `colour-tone-analyst` | `colour` |
| `subject-story-analyst` | `story` |
| `technical-analyst` | `technical` |

Master, craft, and meta agents do **not** emit `SCORE`.

## Validation & repair (Head Coach, deterministic)

1. Parse each returned block. If a required field is missing → re-prompt that agent once, then coerce.
2. If `SCORE` is out of range or non-integer → clamp to 1–5 and flag in the trace.
3. If `EVIDENCE` is empty or doesn't reference a region/EXIF field → **discard the claim** (treat as
   ungrounded; cascading-hallucination defense).
4. Only validated `SCORE` fields feed the report's "Skill read" bars and the frontmatter `scores:` map.
5. `progress-tracker` writes frontmatter only if it conforms to [[Schemas]]; otherwise it fixes or
   flags, never emits broken YAML.

## Example (valid)

```
AGENT: light-exposure-analyst
FINDING: Hard equatorial top-light at ~noon blows the white shophouse wall (upper-right) while the
five-foot-way stays muddy. The light flattens the scene rather than shaping it. Backlight on the
figure is the one redeeming directional cue.
EVIDENCE: upper-right wall clipped to paper-white; EXIF ExposureCompensation=0; histogram right-edge spike
SCORE: light=2
ONE_CHANGE: Expose for the highlights (−1 stop) and return at the 45-minute golden window.
CONFIDENCE: high
```

Related: [[Schemas]] · [[Session Template]]
