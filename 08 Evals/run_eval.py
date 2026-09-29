#!/usr/bin/env python3
"""Photo Sensei evaluation harness.

Runs the golden set (``golden.csv``) against the live coach and scores each
report with two evaluator families:

  (A) Code-based, objective  -- deterministic pass/fail on the output contract:
        contract_ok, real_master_named, lowest_dim_first, frontmatter_valid,
        files_exist, expected_tool.
  (B) LLM-as-judge, subjective -- a separate ``claude -p`` call scores
        actionability, grounding and diagnosis 1-5 against ``JUDGE_RUBRIC``.

For each golden row the coach is invoked headless via::

    claude -p "<prompt>" --permission-mode acceptEdits

with cwd set to the vault root, so it reads/writes the real vault. The produced
report, the newest session note in ``01 Sessions/`` and the newest trace in
``_traces/`` are then evaluated. Results are appended to
``results/eval_<runstamp>.json`` and a summary table is printed.

Usage
-----
    python "08 Evals/run_eval.py" --dry-run        # offline self-test, no model calls
    python "08 Evals/run_eval.py"                  # live run against the coach
    python "08 Evals/run_eval.py" --limit 3        # first 3 golden rows only

``--dry-run`` skips every model call: the coach call is replaced by a built-in
sample report fixture and the judge returns stub scores, so the harness is fully
testable offline with zero cost.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# --------------------------------------------------------------------------- #
# Constants & paths
# --------------------------------------------------------------------------- #

EVAL_DIR = Path(__file__).resolve().parent
VAULT_ROOT = EVAL_DIR.parent
GOLDEN_CSV = EVAL_DIR / "golden.csv"
RESULTS_DIR = EVAL_DIR / "results"
SESSIONS_DIR = VAULT_ROOT / "01 Sessions"
TRACES_DIR = VAULT_ROOT / "_traces"

SCORE_DIMENSIONS = ("composition", "light", "colour", "story", "technical")
MIN_SCORE, MAX_SCORE = 1, 5
MAX_LEVERS = 3
SKILL_BARS_EXPECTED = 5
CLAUDE_TIMEOUT_S = 900  # 15 min ceiling for a full pipeline run

# Required section headers in the "Photo Coach Report" (CLAUDE.md output contract).
REQUIRED_SECTIONS = (
    "quick read",
    "what's working",
    "biggest levers",
    "master lesson",
    "skill read",
    "next mission",
    "logged path",
)

# Curated list of real, famous photographers for the real_master_named check.
KNOWN_PHOTOGRAPHERS = (
    "fan ho", "saul leiter", "henri cartier-bresson", "vivian maier",
    "ansel adams", "sebastiao salgado", "steve mccurry", "annie leibovitz",
    "richard avedon", "irving penn", "daido moriyama", "william eggleston",
    "joel meyerowitz", "alex webb", "garry winogrand", "robert frank",
    "dorothea lange", "edward weston", "gregory crewdson", "andreas gursky",
    "michael kenna", "galen rowell", "platon", "yousuf karsh",
    "elliott erwitt", "trent parke", "rinko kawauchi", "ernst haas",
)

# Words that signal a *named technique* was given alongside the photographer.
TECHNIQUE_KEYWORDS = (
    "technique", "zone system", "decisive moment", "negative space",
    "leading line", "rule of thirds", "golden hour", "rim light", "rembrandt",
    "chiaroscuro", "frame within a frame", "layering", "juxtaposition",
    "reflection", "silhouette", "high-key", "low-key", "fill flash",
    "side light", "back light", "shoot through glass", "burst", "panning",
    "focus stack", "long exposure", "available light", "catchlight",
)

# Map a golden score-range token (e.g. "comp") to a frontmatter dimension key.
TOKEN_TO_DIM = {
    "comp": "composition",
    "composition": "composition",
    "light": "light",
    "colour": "colour",
    "color": "colour",
    "story": "story",
    "technical": "technical",
    "tech": "technical",
}

# --------------------------------------------------------------------------- #
# LLM-as-judge rubric (version-controlled, not an ad-hoc prompt)
# --------------------------------------------------------------------------- #

JUDGE_RUBRIC = """\
You are an impartial evaluator of a photography-coaching report. You are NOT the
coach; do not re-coach. Score the report on three axes, each an integer 1-5.

ACTIONABILITY (1-5)
  5 = every lever is a concrete, controllable capture habit the student can do
      next time (e.g. "stop down to f8", "level the horizon on the grid").
  3 = mixed: some concrete, some vague.
  1 = abstract platitudes ("be more creative", "improve composition").

GROUNDING (1-5)
  5 = claims cite real, visible evidence in the frame and/or actual EXIF; no
      invented detail.
  3 = mostly grounded but some unsupported assertions.
  1 = fabricates detail or EXIF the report could not actually know.

DIAGNOSIS (1-5)  -- did the report surface the PLANTED ISSUE below?
  5 = clearly identifies and addresses the planted issue.
  3 = touches it indirectly.
  1 = misses it entirely.
  (If PLANTED_ISSUE is "N/A", score DIAGNOSIS as 3 and ignore this axis.)

Return ONLY a JSON object, no prose, exactly:
{"actionability": <int>, "grounding": <int>, "diagnosis": <int>, "notes": "<short reason>"}
"""

# --------------------------------------------------------------------------- #
# Sample fixtures for --dry-run (so the harness is testable offline)
# --------------------------------------------------------------------------- #

SAMPLE_REPORT = """\
# 📸 Photo Coach Report

**Quick read** — A strong graphic street frame let down by blown highlights in
the harsh midday sun.

**What's working** — The diagonal of the shophouse five-foot-way leads the eye
cleanly to the lone figure; the Classic Negative palette holds the shadows well.

**Biggest levers**
1. Expose for the highlights — the white shirt has clipped to paper; dial -0.7 EV.
2. Wait for the shade-edge light where the awning meets open sun.
3. Protect the white channel; let the shadows fall.

**Master lesson** — Saul Leiter built quiet street frames around reflection and
the shoot-through-glass technique; here, find a window or wet surface to layer
the figure behind glass and tame that direct sun.

**Annotated + edited** — see `_attachments/golden01_annotated.jpg` and
`_attachments/golden01_edit.jpg`; notice the recovered highlight on the shirt.

**Recipe note** — Classic Negative, Highlight -2 to hold midday whites.

**Skill read**
- Composition: 4
- Light: 2
- Colour: 4
- Story: 3
- Technical: 4

**Trend** — Light remains your lowest rung across the last 6 sessions.

**Next mission** — Shoot 10 midday frames exposing for the brightest highlight;
one keeper where no channel clips.

**Logged path** — `01 Sessions/2026-06-20_1430_street-midday.md`
"""

SAMPLE_FRONTMATTER = {
    "date": "2026-06-20",
    "time": "1430",
    "genre": "street",
    "gear": "Fujifilm X100VI",
    "film_sim": "Classic Negative",
    "aperture": 5.6,
    "shutter": "1/500",
    "iso": 400,
    "focal": 23,
    "exposure_comp": -0.3,
    "scores": {"composition": 4, "light": 2, "colour": 4, "story": 3, "technical": 4},
    "masters": ["Saul Leiter"],
    "mission_given": "Shoot 10 midday frames exposing for the brightest highlight",
    "tags": ["photo-sensei", "session", "street"],
}

SAMPLE_TRACE = {
    "photo": "_attachments/golden01.jpg",
    "session_note": "01 Sessions/2026-06-20_1430_street-midday.md",
    "model": "claude-opus-4-8",
    "agents_dispatched": [
        "composition-analyst", "light-exposure-analyst",
        "subject-story-analyst", "street-light-master", "annotation-artist",
    ],
    "tool_calls": ["annotation-artist", "progress-tracker"],
    "guardrails": {"input_ok": True, "output_ok": True, "notes": ""},
}


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #


@dataclass
class GoldenRow:
    """One row of the golden set."""

    id: str
    photo_file: str
    genre: str
    planted_issues: str
    must_mention: list[str]
    expected_scores_min: dict[str, int]
    expected_scores_max: dict[str, int]
    expect_tool: str


@dataclass
class EvalResult:
    """Per-item evaluation outcome."""

    item_id: str
    code_checks: dict[str, dict[str, object]] = field(default_factory=dict)
    judge_scores: dict[str, object] = field(default_factory=dict)

    @property
    def code_pass_rate(self) -> float:
        """Fraction of code-based evaluators that passed for this item."""
        if not self.code_checks:
            return 0.0
        passed = sum(1 for c in self.code_checks.values() if c["passed"])
        return passed / len(self.code_checks)


# --------------------------------------------------------------------------- #
# Golden-set loading
# --------------------------------------------------------------------------- #


def _parse_bound(token_string: str, pick: int) -> dict[str, int]:
    """Parse ``comp:2-4;light:1-3`` and return one bound per dimension.

    Args:
        token_string: compact per-dimension range string.
        pick: ``0`` for the low bound, ``1`` for the high bound.

    Returns:
        Mapping of canonical dimension name -> integer bound.
    """
    out: dict[str, int] = {}
    for chunk in token_string.split(";"):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        token, rng = chunk.split(":", 1)
        dim = TOKEN_TO_DIM.get(token.strip().lower())
        if dim is None:
            continue
        bounds = rng.strip().split("-")
        try:
            out[dim] = int(bounds[pick] if len(bounds) > pick else bounds[0])
        except (ValueError, IndexError):
            continue
    return out


def load_golden(path: Path, limit: Optional[int] = None) -> list[GoldenRow]:
    """Load and parse the golden CSV into ``GoldenRow`` objects."""
    rows: list[GoldenRow] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, skipinitialspace=True)
        for raw in reader:
            clean = {(k.strip() if k else k): (v.strip() if v else "")
                     for k, v in raw.items()}
            rows.append(
                GoldenRow(
                    id=clean["id"],
                    photo_file=clean["photo_file"],
                    genre=clean["genre"],
                    planted_issues=clean["planted_issues"],
                    must_mention=[m.strip() for m in clean["must_mention"].split(";")
                                  if m.strip()],
                    expected_scores_min=_parse_bound(clean["expected_scores_min"], 0),
                    expected_scores_max=_parse_bound(clean["expected_scores_max"], 1),
                    expect_tool=clean["expect_tool"].lower(),
                )
            )
    if limit is not None:
        rows = rows[:limit]
    return rows


# --------------------------------------------------------------------------- #
# Coach invocation + artefact reading
# --------------------------------------------------------------------------- #


def build_coach_prompt(row: GoldenRow) -> str:
    """Build the prompt that asks the coach to run the full pipeline."""
    return (
        f"Run the full Photo Sensei pipeline on the photo at "
        f"'_attachments/{row.photo_file}' (genre hint: {row.genre}). "
        "Dispatch the agents this photo needs, ground every claim, write the "
        "session note and trace, then deliver the complete '📸 Photo Coach "
        "Report' with all applicable sections."
    )


def call_coach(row: GoldenRow, dry_run: bool) -> str:
    """Invoke the coach headless and return the report text.

    In ``--dry-run`` the model call is skipped and a sample fixture is returned.
    """
    if dry_run:
        return SAMPLE_REPORT
    prompt = build_coach_prompt(row)
    proc = subprocess.run(
        ["claude", "-p", prompt, "--permission-mode", "acceptEdits"],
        cwd=str(VAULT_ROOT),
        capture_output=True,
        text=True,
        timeout=CLAUDE_TIMEOUT_S,
        check=False,
    )
    if proc.returncode != 0:
        return f"[coach call failed rc={proc.returncode}] {proc.stderr.strip()}"
    return proc.stdout


def _newest_file(directory: Path, pattern: str) -> Optional[Path]:
    """Return the most-recently-modified file matching ``pattern``, or None."""
    if not directory.is_dir():
        return None
    candidates = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime,
                        reverse=True)
    return candidates[0] if candidates else None


def read_latest_frontmatter(dry_run: bool) -> Optional[dict[str, object]]:
    """Read and parse YAML frontmatter from the newest session note."""
    if dry_run:
        return dict(SAMPLE_FRONTMATTER)
    note = _newest_file(SESSIONS_DIR, "*.md")
    if note is None:
        return None
    return parse_frontmatter(note.read_text(encoding="utf-8"))


def read_latest_trace(dry_run: bool) -> Optional[dict[str, object]]:
    """Read and parse the newest trace JSON from ``_traces/``."""
    if dry_run:
        return dict(SAMPLE_TRACE)
    trace = _newest_file(TRACES_DIR, "*.json")
    if trace is None:
        return None
    try:
        return json.loads(trace.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- #
# Minimal YAML frontmatter parser (stdlib only)
# --------------------------------------------------------------------------- #


def _coerce_scalar(value: str) -> object:
    """Best-effort coercion of a YAML scalar string to a Python value."""
    value = value.strip()
    if value in ("null", "~", ""):
        return None
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def parse_frontmatter(text: str) -> Optional[dict[str, object]]:
    """Parse the leading ``--- ... ---`` YAML block.

    Supports the flat keys, the nested ``scores:`` mapping and inline-list values
    used by the Photo Sensei session-note schema. Not a general YAML parser.
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not match:
        return None
    body = match.group(1)
    result: dict[str, object] = {}
    current_map: Optional[str] = None
    for line in body.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, _, raw = stripped.partition(":")
        key = key.strip()
        raw = raw.strip()
        if indent > 0 and current_map is not None:
            result[current_map][key] = _coerce_scalar(raw)  # type: ignore[index]
            continue
        if raw == "":
            current_map = key
            result[key] = {}
            continue
        current_map = None
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            items = [_coerce_scalar(p) for p in inner.split(",")] if inner else []
            result[key] = items
        else:
            result[key] = _coerce_scalar(raw)
    return result


# --------------------------------------------------------------------------- #
# Report parsing helpers
# --------------------------------------------------------------------------- #


def extract_skill_scores(report: str) -> dict[str, int]:
    """Extract the 5 Skill read bars as ``{dimension: int}``."""
    scores: dict[str, int] = {}
    pattern = re.compile(
        r"(composition|light|colou?r(?:/tone)?|subject/story|story|technical)\s*[:\-]?\s*(\d)",
        re.IGNORECASE,
    )
    for raw_dim, raw_val in pattern.findall(report):
        dim = raw_dim.lower()
        if dim.startswith("colo"):
            dim = "colour"
        elif "story" in dim:
            dim = "story"
        if dim in SCORE_DIMENSIONS and dim not in scores:
            scores[dim] = int(raw_val)
    return scores


def extract_levers(report: str) -> list[str]:
    """Extract the ranked 'Biggest levers' as a list of action strings."""
    block = re.search(
        r"biggest levers\b.*?\n(.*?)(?:\n\s*\*?\*?(?:master lesson|annotated|recipe|skill read)\b|$)",
        report,
        re.IGNORECASE | re.DOTALL,
    )
    if not block:
        return []
    levers: list[str] = []
    for line in block.group(1).splitlines():
        item = re.match(r"\s*(?:\d+[.)]|[-*])\s+(.*)", line)
        if item and item.group(1).strip():
            levers.append(item.group(1).strip())
    return levers


def referenced_image_paths(report: str) -> list[str]:
    """Return annotated/edit image paths referenced in the report."""
    return re.findall(r"[`'\"]?([^\s`'\"]+_(?:annotated|edit)\.(?:jpg|jpeg|png))",
                     report, re.IGNORECASE)


# --------------------------------------------------------------------------- #
# (A) Code-based, objective evaluators -> (passed, reason)
# --------------------------------------------------------------------------- #


def contract_ok(report: str) -> tuple[bool, str]:
    """All required sections present; 5 integer score bars; <= 3 levers."""
    low = report.lower()
    missing = [s for s in REQUIRED_SECTIONS if s not in low]
    if missing:
        return False, f"missing sections: {', '.join(missing)}"
    scores = extract_skill_scores(report)
    if len(scores) != SKILL_BARS_EXPECTED:
        return False, f"expected {SKILL_BARS_EXPECTED} skill bars, found {len(scores)}"
    bad = {d: v for d, v in scores.items() if not (MIN_SCORE <= v <= MAX_SCORE)}
    if bad:
        return False, f"scores out of 1-5 range: {bad}"
    levers = extract_levers(report)
    if len(levers) > MAX_LEVERS:
        return False, f"{len(levers)} levers (max {MAX_LEVERS})"
    return True, f"5 bars, {len(levers)} levers, all sections present"


def real_master_named(report: str) -> tuple[bool, str]:
    """Exactly one real, named photographer + a named technique in the lesson."""
    lesson = re.search(
        r"master lesson\b.*?\n?(.*?)(?:\n\s*\*?\*?(?:annotated|recipe|skill read)\b|$)",
        report,
        re.IGNORECASE | re.DOTALL,
    )
    scope = lesson.group(1) if lesson else report
    scope_low = scope.lower()
    found = [name for name in KNOWN_PHOTOGRAPHERS if name in scope_low]
    if len(found) == 0:
        return False, "no known photographer named in Master lesson"
    if len(found) > 1:
        return False, f"more than one photographer named: {found}"
    has_technique = any(kw in scope_low for kw in TECHNIQUE_KEYWORDS)
    if not has_technique:
        return False, f"'{found[0].title()}' named but no specific technique"
    return True, f"{found[0].title()} + named technique"


def lowest_dim_first(report: str) -> tuple[bool, str]:
    """The coached dimension must be the lowest-scoring one."""
    scores = extract_skill_scores(report)
    if len(scores) != SKILL_BARS_EXPECTED:
        return False, "cannot locate all 5 skill scores"
    lowest = min(scores.values())
    lowest_dims = {d for d, v in scores.items() if v == lowest}
    coached_text = " ".join(extract_levers(report)).lower()
    mission = re.search(r"next mission\b.*", report, re.IGNORECASE | re.DOTALL)
    if mission:
        coached_text += " " + mission.group(0).lower()
    aliases = {
        "composition": ("composition", "compose", "frame", "horizon", "negative space"),
        "light": ("light", "exposure", "highlight", "shadow", "expose"),
        "colour": ("colour", "color", "tone", "white balance", "saturation"),
        "story": ("story", "subject", "moment", "narrative", "gesture"),
        "technical": ("technical", "focus", "sharp", "noise", "tripod", "blur"),
    }
    for dim in lowest_dims:
        if any(a in coached_text for a in aliases[dim]):
            return True, f"lowest dim '{dim}' ({lowest}) is coached"
    return False, f"lowest dim(s) {sorted(lowest_dims)} ({lowest}) not coached"


def frontmatter_valid(fm: Optional[dict[str, object]]) -> tuple[bool, str]:
    """Session-note YAML conforms to the Schemas.md contract."""
    if not fm:
        return False, "no frontmatter found"
    scores = fm.get("scores")
    if not isinstance(scores, dict):
        return False, "missing 'scores' mapping"
    for dim in SCORE_DIMENSIONS:
        if dim not in scores:
            return False, f"missing score dimension '{dim}'"
        val = scores[dim]
        if not isinstance(val, int) or isinstance(val, bool):
            return False, f"score '{dim}' is not an int: {val!r}"
        if not (MIN_SCORE <= val <= MAX_SCORE):
            return False, f"score '{dim}'={val} out of 1-5"
    date = str(fm.get("date", ""))
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return False, f"bad date: {date!r}"
    time_val = str(fm.get("time", ""))
    if not re.match(r"^\d{4}$", time_val):
        return False, f"bad time (need HHMM): {time_val!r}"
    if not str(fm.get("genre", "")).strip():
        return False, "empty genre"
    masters = fm.get("masters")
    if not isinstance(masters, list) or not masters:
        return False, "masters must be a non-empty list"
    return True, "frontmatter conforms to schema"


def files_exist(report: str, dry_run: bool) -> tuple[bool, str]:
    """Every annotated/edit path referenced in the report exists on disk."""
    refs = referenced_image_paths(report)
    if not refs:
        return True, "no annotated/edit paths referenced"
    if dry_run:
        return True, f"dry-run: {len(refs)} path(s) not checked"
    missing = [r for r in refs if not (VAULT_ROOT / r).exists()]
    if missing:
        return False, f"missing files: {missing}"
    return True, f"all {len(refs)} referenced file(s) exist"


def expected_tool(trace: Optional[dict[str, object]], expect: str) -> tuple[bool, str]:
    """The golden-expected tool fired (or none was needed)."""
    fired: set[str] = set()
    if isinstance(trace, dict):
        for key in ("tool_calls", "agents_dispatched"):
            val = trace.get(key)
            if isinstance(val, list):
                fired.update(str(x).lower() for x in val)
    if expect in ("", "none"):
        return True, "no specific tool expected"
    if trace is None:
        return False, f"expected '{expect}' but no trace available"
    if expect in fired:
        return True, f"expected tool '{expect}' fired"
    return False, f"expected '{expect}' not in trace tools {sorted(fired)}"


# --------------------------------------------------------------------------- #
# (B) LLM-as-judge, subjective
# --------------------------------------------------------------------------- #


def llm_judge(report: str, planted_issue: str, must_mention: list[str],
              dry_run: bool) -> dict[str, object]:
    """Score actionability / grounding / diagnosis 1-5 via a separate model call.

    In ``--dry-run`` returns deterministic stub scores so the harness is testable
    offline. The rubric lives in the module-level ``JUDGE_RUBRIC`` constant.
    """
    if dry_run:
        return {"actionability": 4, "grounding": 4, "diagnosis": 4,
                "notes": "stub (dry-run)"}
    mention = "; ".join(must_mention) if must_mention else "N/A"
    prompt = (
        f"{JUDGE_RUBRIC}\n\n"
        f"PLANTED_ISSUE: {planted_issue or 'N/A'}\n"
        f"MUST_MENTION: {mention}\n\n"
        f"REPORT:\n{report}\n"
    )
    try:
        proc = subprocess.run(
            ["claude", "-p", prompt],
            cwd=str(VAULT_ROOT),
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"actionability": 0, "grounding": 0, "diagnosis": 0,
                "notes": f"judge call error: {exc}"}
    if proc.returncode != 0:
        return {"actionability": 0, "grounding": 0, "diagnosis": 0,
                "notes": f"judge rc={proc.returncode}"}
    json_match = re.search(r"\{.*\}", proc.stdout, re.DOTALL)
    if not json_match:
        return {"actionability": 0, "grounding": 0, "diagnosis": 0,
                "notes": "judge returned no JSON"}
    try:
        return json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return {"actionability": 0, "grounding": 0, "diagnosis": 0,
                "notes": "judge JSON parse failed"}


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def evaluate_item(row: GoldenRow, dry_run: bool) -> EvalResult:
    """Run the full pipeline + all evaluators for one golden row."""
    report = call_coach(row, dry_run)
    frontmatter = read_latest_frontmatter(dry_run)
    trace = read_latest_trace(dry_run)

    result = EvalResult(item_id=row.id)

    def record(name: str, outcome: tuple[bool, str]) -> None:
        passed, reason = outcome
        result.code_checks[name] = {"passed": passed, "reason": reason}

    record("contract_ok", contract_ok(report))
    record("real_master_named", real_master_named(report))
    record("lowest_dim_first", lowest_dim_first(report))
    record("frontmatter_valid", frontmatter_valid(frontmatter))
    record("files_exist", files_exist(report, dry_run))
    record("expected_tool", expected_tool(trace, row.expect_tool))

    result.judge_scores = llm_judge(report, row.planted_issues, row.must_mention,
                                    dry_run)
    return result


def aggregate(results: list[EvalResult]) -> dict[str, object]:
    """Compute per-evaluator and overall pass rates across all items."""
    per_evaluator: dict[str, dict[str, int]] = {}
    total_checks = passed_checks = 0
    for res in results:
        for name, outcome in res.code_checks.items():
            bucket = per_evaluator.setdefault(name, {"passed": 0, "total": 0})
            bucket["total"] += 1
            total_checks += 1
            if outcome["passed"]:
                bucket["passed"] += 1
                passed_checks += 1
    judge_axes = ("actionability", "grounding", "diagnosis")
    judge_means: dict[str, float] = {}
    for axis in judge_axes:
        vals = [float(r.judge_scores.get(axis, 0) or 0) for r in results]
        judge_means[axis] = round(sum(vals) / len(vals), 2) if vals else 0.0
    return {
        "items": len(results),
        "code_pass_rate": round(passed_checks / total_checks, 3) if total_checks else 0.0,
        "per_evaluator": {
            k: {**v, "rate": round(v["passed"] / v["total"], 3) if v["total"] else 0.0}
            for k, v in per_evaluator.items()
        },
        "judge_means": judge_means,
    }


def write_results(results: list[EvalResult], summary: dict[str, object],
                  runstamp: str, dry_run: bool) -> Path:
    """Append a timestamped result file to ``results/`` and return its path."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"eval_{runstamp}.json"
    payload = {
        "runstamp": runstamp,
        "timestamp": datetime.now().astimezone().isoformat(),
        "dry_run": dry_run,
        "summary": summary,
        "items": [
            {"id": r.item_id, "code_checks": r.code_checks,
             "judge_scores": r.judge_scores, "code_pass_rate": round(r.code_pass_rate, 3)}
            for r in results
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def print_summary(results: list[EvalResult], summary: dict[str, object],
                  out_path: Path) -> None:
    """Print a human-readable summary table to stdout."""
    print("\n" + "=" * 72)
    print("Photo Sensei — Eval Summary")
    print("=" * 72)
    header = f"{'item':<6}{'code':>6}  checks"
    print(header)
    print("-" * 72)
    for res in results:
        fails = [n for n, c in res.code_checks.items() if not c["passed"]]
        status = "OK" if not fails else "FAIL: " + ", ".join(fails)
        print(f"{res.item_id:<6}{res.code_pass_rate:>6.0%}  {status}")
    print("-" * 72)
    print(f"items={summary['items']}  overall code pass rate="
          f"{summary['code_pass_rate']:.1%}")
    print("per-evaluator:")
    for name, stats in summary["per_evaluator"].items():
        print(f"  {name:<20} {stats['passed']}/{stats['total']} ({stats['rate']:.0%})")
    print(f"judge means (1-5): {summary['judge_means']}")
    print(f"\nresults written to: {out_path}")
    print("=" * 72)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Photo Sensei evaluation harness (golden set + LLM-as-judge).",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="skip model calls; evaluate built-in sample fixtures")
    parser.add_argument("--limit", type=int, default=None, metavar="N",
                        help="evaluate only the first N golden rows")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point: load golden set, evaluate, aggregate, persist, print."""
    args = parse_args(argv)
    if not GOLDEN_CSV.exists():
        print(f"error: golden set not found at {GOLDEN_CSV}", file=sys.stderr)
        return 2
    rows = load_golden(GOLDEN_CSV, limit=args.limit)
    if not rows:
        print("error: golden set is empty", file=sys.stderr)
        return 2

    mode = "DRY-RUN (offline)" if args.dry_run else "LIVE"
    print(f"Running {len(rows)} golden item(s) in {mode} mode...")

    results: list[EvalResult] = []
    for row in rows:
        print(f"  - {row.id} ({row.genre}) ...")
        results.append(evaluate_item(row, args.dry_run))

    summary = aggregate(results)
    runstamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = write_results(results, summary, runstamp, args.dry_run)
    print_summary(results, summary, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
