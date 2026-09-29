---
type: eval-guide
tags: [photo-sensei, evals]
last-updated: 2026-06-20
---

# Photo Sensei — Eval Guide

> "Measure before you ship." Quality of the coach is **testable**, not vibes (CLAUDE.md §0). This
> harness is how we catch regressions before they reach J's vault, and how we watch live quality on
> real sessions. Read this before touching `CLAUDE.md` or any agent in `.claude/agents/`.

## Why this exists

The coach is a multi-agent vision pipeline. A single wrong read (a hallucinated EXIF field, the wrong
genre, a fabricated "technique") cascades into the lesson, the edit, the mission, the logged session
note, and then the trend analysis *reinforces* it. The eval harness is the firewall's smoke detector:
it asserts the **output contract** deterministically and judges the **subjective coaching quality**
with an LLM-as-judge, so a prompt change that quietly breaks grounding or the report contract is caught
by a number, not by a confused student a week later.

## Two modes

### Offline — the golden set (regression gate)

`golden.csv` is a small, hand-curated set of photos with **planted issues** and the coaching points the
coach *must* mention. Each row pins expected score ranges per dimension and whether a specific tool
(e.g. `fuji-recipe-advisor`, `edit-example-generator`) is expected to fire.

- **Run it before AND after any change** to `CLAUDE.md`, the schemas, or any agent prompt.
- Compare pass rates: if a change drops `real_master_named` or `contract_ok`, you regressed the
  contract; if `llm_judge` diagnosis drops, you regressed the coaching itself.
- Deterministic, repeatable, cheap. This is the gate that blocks a bad merge.

```bash
# from the vault root
python "08 Evals/run_eval.py" --dry-run            # offline self-test, no model calls
python "08 Evals/run_eval.py"                      # real run against the live coach
python "08 Evals/run_eval.py" --limit 3            # first 3 golden rows only
```

### Online — sampled real sessions (live quality watch)

Periodically sample real run traces from `_traces/` (and their session notes in `01 Sessions/`) and run
**only the LLM-as-judge** over them — there are no planted issues on real photos, so we score
actionability and grounding rather than diagnosis-of-a-known-fault. This watches whether quality drifts
on the actual distribution of photos J shoots, not just the golden curation. Sampled results land in
the same `results/` folder and feed the trend.

## Two evaluator families

### (A) Code-based, objective — deterministic pass/fail

These never call a model. They assert the things CLAUDE.md keeps in *deterministic code* because "you
don't leave a guarantee to a probability" (§0).

| Evaluator | Asserts |
|---|---|
| `contract_ok` | The "📸 Photo Coach Report" has all required sections (Quick read, What's working, Biggest levers, Master lesson, Skill read, Next mission, Logged path …); Skill read has 5 bars with integer scores 1–5; **≤ 3** biggest levers. |
| `real_master_named` | **Exactly one** named, real photographer (matched against a curated list) **and** a specific named technique present in the Master lesson. |
| `lowest_dim_first` | The dimension the coach pushes (Biggest levers / Next mission) is the **lowest-scoring** dimension in the Skill read — fundamentals-first, weakest-rung-first (§2). |
| `frontmatter_valid` | The session-note YAML conforms to the Schemas.md contract: all five `scores` keys present, each an int 1–5; `date` ISO; `time` 4-char `HHMM`; `genre` non-empty; `masters` non-empty list. |
| `files_exist` | Every annotated / edit path referenced in the report (`*_annotated.jpg`, `*_edit.jpg`) actually exists on disk (the consistency guardrail, §4c). |
| `expected_tool` | If the golden row sets `expect_tool`, that tool fired (per the trace's `tool_calls` / `agents_dispatched`); if `none`, no surprise tool was needed. |

A code-based evaluator returns `(passed: bool, reason: str)` so a failure is self-explaining in the
results file — no spelunking required.

### (B) LLM-as-judge, subjective — scored 1–5 against a rubric

Some qualities cannot be regex'd. A separate judging model (a fresh `claude -p` call, *not* the coach)
scores the report on:

- **Actionability** — are the levers concrete, controllable capture habits, or vague platitudes?
- **Grounding** — does the report cite real, visible evidence / EXIF rather than inventing detail? This
  is the primary anti-hallucination signal.
- **Diagnosis** — did the coach actually surface the **planted issue** for this golden photo?

The rubric is kept in the repo as a module-level constant (`JUDGE_RUBRIC` in `run_eval.py`) so the
judging standard is version-controlled and reviewable, never an ad-hoc prompt. Online runs use the same
rubric minus the diagnosis axis (no planted issue on real photos).

## How a run works

`run_eval.py`:

1. Loads `golden.csv`.
2. For each row, asks the coach to run the full pipeline on the photo via
   `claude -p "<prompt>" --permission-mode acceptEdits` with cwd = vault root (so it writes into the
   real vault structure). With `--dry-run` it skips the call and evaluates a built-in sample report
   fixture so the harness is testable offline with zero cost.
3. Reads the produced report text, the newest session note in `01 Sessions/`, and the newest trace in
   `_traces/`.
4. Runs all family-(A) code evaluators and the family-(B) `llm_judge`.
5. Aggregates per-item and overall pass rates and appends a timestamped row to
   `results/eval_<runstamp>.json`, then prints a summary table.

## Where results land

- `results/eval_<runstamp>.json` — one file per run: per-item evaluator outcomes, judge scores, and the
  overall pass rate. `results/.gitkeep` keeps the folder tracked even when empty.
- Diff two result files across a `CLAUDE.md` change to prove you improved (or at least did not regress).

## Reading a failure

- `contract_ok` fail → the report shape drifted (missing section, >3 levers, non-int score). Fix the
  output contract in CLAUDE.md §4 / the `progress-tracker` agent.
- `real_master_named` fail → the Master lesson named zero, two, or a fictional photographer, or omitted
  a technique. The single hardest, most-regressed rule — guard it.
- `frontmatter_valid` fail → `progress-tracker` emitted YAML that violates Schemas.md. **Never** let
  this reach the vault; the agent must repair or flag, not write broken YAML.
- Low `llm_judge` grounding → the coach is inventing detail. Tighten the grounding gate (§4 step 4).

Related: [[Schemas]] · [[Agent Contract]] · CLAUDE.md §11
