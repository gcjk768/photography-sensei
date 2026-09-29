#!/usr/bin/env python3
"""Instagram insights loop — pull post performance and write it back to session notes.

This closes the agentic "online evaluation" loop: post → measure → learn. After a post is live, this
script pulls reach / saves / shares (sends) via the Instagram Graph API and fills the empty
``Performance:`` line inside each session note's ``## Post kit`` section. Over time, weekly-review /
exif-pattern-style mining can then tell which caption styles, sounds, formats and genres actually earn
reach for *this* audience — and the stylist leans into what works.

What it does NOT do: attach music or detect trending sounds (no API exists for that — keep the
music/posting step manual in-app). Use this purely for the insights feedback loop.

Setup (see README.md → "Evaluate & trace"):
  - A Business/Creator IG account linked to a Facebook Page, in a Meta developer app with a long-lived
    token and `instagram_content_publish` / insights permissions (app review ~2–4 weeks).
  - Put credentials in .env (gitignored):
        IG_ACCESS_TOKEN=...        # long-lived token
        IG_USER_ID=...             # the IG Business user id
  - Run:  python scripts/ig_insights.py            (live)
          python scripts/ig_insights.py --dry-run  (offline, uses a fixture)

Matching: a media item is matched to a session note that has a `## Post kit` block whose
`Performance:` line is still empty — primarily by an explicit `Permalink:` line in the kit, otherwise
by date proximity (media timestamp within --days of the session date). Append-only: it never rewrites
an already-filled Performance line.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

try:
    import httpx
except ImportError:  # keep --dry-run usable without httpx
    httpx = None  # type: ignore

VAULT_ROOT = Path(__file__).resolve().parent.parent
SESSIONS = VAULT_ROOT / "01 Sessions"
GRAPH = "https://graph.facebook.com/v23.0"
# Static-image insight metrics + Reel/video metrics (the API rejects unknown metrics, so request the
# common safe set; Reels expose `plays`/`reach`, feed posts expose `reach`/`saved`/`shares`).
PHOTO_METRICS = "reach,saved,shares,total_interactions"
REEL_METRICS = "reach,saved,shares,plays,total_interactions"


def load_env(path: Path = VAULT_ROOT / ".env") -> dict[str, str]:
    """Read KEY=VALUE pairs from .env (the file is gitignored — never commit credentials)."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def fetch_media(token: str, ig_user_id: str, limit: int) -> list[dict]:
    """List recent media for the IG user (id, caption, timestamp, permalink, media_type)."""
    if httpx is None:
        raise RuntimeError("httpx is required for live mode: pip install httpx")
    url = f"{GRAPH}/{ig_user_id}/media"
    params = {
        "fields": "id,caption,timestamp,permalink,media_type,media_product_type",
        "limit": str(limit),
        "access_token": token,
    }
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def fetch_insights(token: str, media: dict) -> dict[str, int]:
    """Per-post actuals. Returns {} on any error so one bad post doesn't abort the run."""
    if httpx is None:
        return {}
    is_reel = (media.get("media_product_type") == "REELS") or (media.get("media_type") == "VIDEO")
    metrics = REEL_METRICS if is_reel else PHOTO_METRICS
    url = f"{GRAPH}/{media['id']}/insights"
    try:
        resp = httpx.get(url, params={"metric": metrics, "access_token": token}, timeout=30)
        resp.raise_for_status()
        out: dict[str, int] = {}
        for item in resp.json().get("data", []):
            values = item.get("values") or [{}]
            out[item["name"]] = values[0].get("value", 0)
        return out
    except Exception as exc:  # noqa: BLE001 - report, keep going
        print(f"  ! insights failed for {media.get('id')}: {exc}", file=sys.stderr)
        return {}


def _media_date(media: dict) -> dt.date | None:
    ts = media.get("timestamp")
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _session_date(text: str) -> dt.date | None:
    m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    if not m:
        return None
    try:
        return dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def find_target_note(media: dict, notes: list[Path], days: int) -> Path | None:
    """Find a session note with a Post kit whose Performance line is empty, matching this media."""
    permalink = (media.get("permalink") or "").strip()
    mdate = _media_date(media)
    best: tuple[int, Path] | None = None
    for note in notes:
        text = note.read_text(encoding="utf-8")
        if "## Post kit" not in text:
            continue
        if re.search(r"^Performance:\s*\S", text, re.MULTILINE):
            continue  # already filled — append-only, leave it
        # 1) explicit permalink match wins
        if permalink and permalink in text:
            return note
        # 2) else date proximity
        sdate = _session_date(text)
        if mdate and sdate:
            delta = abs((mdate - sdate).days)
            if delta <= days and (best is None or delta < best[0]):
                best = (delta, note)
    return best[1] if best else None


def write_performance(note: Path, insights: dict[str, int], permalink: str) -> None:
    """Fill the empty `Performance:` line under `## Post kit` (append-only; never rewrite a filled one)."""
    text = note.read_text(encoding="utf-8")
    perf = (
        f"Performance: reach {insights.get('reach', '–')} · "
        f"saves {insights.get('saved', '–')} · "
        f"sends {insights.get('shares', '–')} · "
        f"interactions {insights.get('total_interactions', '–')}"
        + (f" · {permalink}" if permalink else "")
    )
    if re.search(r"^Performance:\s*$", text, re.MULTILINE):
        text = re.sub(r"^Performance:\s*$", perf, text, count=1, flags=re.MULTILINE)
    else:  # no placeholder line — append one under the Post kit heading
        text = text.replace("## Post kit", f"## Post kit\n\n{perf}", 1)
    note.write_text(text, encoding="utf-8")


def dry_run_fixture() -> list[tuple[dict, dict[str, int]]]:
    """Offline sample so the script is testable without API access."""
    media = {"id": "SAMPLE", "permalink": "https://instagram.com/p/SAMPLE",
             "timestamp": "2026-06-20T18:30:00+0000", "media_type": "IMAGE",
             "media_product_type": "FEED", "caption": "moody street, classic negative"}
    insights = {"reach": 1234, "saved": 88, "shares": 41, "total_interactions": 210}
    return [(media, insights)]


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull IG post performance into session notes.")
    ap.add_argument("--dry-run", action="store_true", help="use a fixture; no API calls")
    ap.add_argument("--limit", type=int, default=25, help="how many recent posts to scan")
    ap.add_argument("--days", type=int, default=3, help="date-match window (days) when no permalink")
    args = ap.parse_args()

    notes = sorted(SESSIONS.glob("*.md"))
    if not notes:
        print("No session notes found.")
        return 0

    if args.dry_run:
        pairs = dry_run_fixture()
        print("DRY RUN — using fixture data (no API calls).")
    else:
        env = load_env()
        token, ig_user_id = env.get("IG_ACCESS_TOKEN"), env.get("IG_USER_ID")
        if not token or not ig_user_id:
            print("Missing IG_ACCESS_TOKEN / IG_USER_ID in .env. See README.md, or use --dry-run.")
            return 2
        media_list = fetch_media(token, ig_user_id, args.limit)
        print(f"Fetched {len(media_list)} media items.")
        pairs = [(m, fetch_insights(token, m)) for m in media_list]

    updated = 0
    for media, insights in pairs:
        if not insights:
            continue
        note = find_target_note(media, notes, args.days)
        if note is None:
            print(f"  - no matching session note for {media.get('permalink') or media.get('id')}")
            continue
        write_performance(note, insights, media.get("permalink", ""))
        print(f"  ✓ {note.name}: reach={insights.get('reach')} saves={insights.get('saved')} "
              f"sends={insights.get('shares')}")
        updated += 1

    print(f"Done — {updated} session note(s) updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
