---
description: Instagram post kit (caption, alt text, hashtags, music, hook) for a photo
argument-hint: "[optional photo filename in _attachments/]"
allowed-tools: Read
---

Generate an Instagram **post kit** for a photo using the `instagram-stylist` agent.

Steps:
1. **Pick the target photo.** If `$ARGUMENTS` names a file, use `_attachments/$ARGUMENTS`. Otherwise
   use the most recent image in `_attachments/`.
2. **Reuse analysis if it exists.** If a session note in `01 Sessions/` already critiqued this photo,
   load its genre, mood, scores, evidence, and master lesson so the kit matches the critique. If not,
   let `instagram-stylist` do a quick mood read first.
3. **Invoke `instagram-stylist`** on that photo.
4. **Present the kit**: 📐 format rec, ✍️ 4 captions, 🔑 SEO keywords, 🏷️ alt text, #️⃣ 3–5 hashtags,
   💬 hook, 🎵 music (with trend-verification steps), and 🎬 Reels block if applicable.
5. **(Optional) Log it.** If a session note exists, ask `progress-tracker` to append a `## Post kit`
   section (the chosen caption + alt text + hashtags + sound). Leave an empty `Performance:` line for
   the insights loop (see `scripts/ig_insights.py`) — append-only, never rewrite.

Apply the stylist's guardrails: no lyrics; no engagement bait; 3–5 hashtags; state the music caveat;
ground everything in the actual frame; respect J's voice.
