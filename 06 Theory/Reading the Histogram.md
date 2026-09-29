---
type: theory
tags: [photo-sensei, theory, fundamentals, technical]
---

# Reading the Histogram

The histogram is the only *objective* judge of exposure. Your LCD lies — it changes with screen brightness and ambient light. The graph doesn't. Learn to read it and you never guess again.

## What the graph means

It's a bar chart of brightness. Left edge = pure black, right edge = pure white, middle = mid-grey. The height at each point = how many pixels are that bright.

- A hump on the **left** = a dark/shadowy image (normal for your moody style).
- A hump on the **right** = a bright/high-key image.
- Spikes **slammed against either wall** = **clipping** — detail lost, gone forever.

There is no single "correct" shape. A night street scene *should* pile up on the left. A bright beach *should* sit right. The shape should match the scene.

## Clipping (the thing to watch)

- **Clipped highlights** (right wall): pure white with no texture — a blown sky, a bright shirt gone featureless.
- **Clipped shadows** (left wall): pure black with no detail.

For your light-and-shadow style, **clipped shadows are usually fine** — black shadow is a design element ([[Fan Ho]] lets shadows go to true black on purpose). **Clipped highlights are the enemy** — a blown-out Singapore sky or a glaring reflection looks cheap and can't be fixed.

## Expose to the right (ETTR) — and its limit

In theory, pushing the exposure as far right as possible *without clipping* captures the most data and least noise, then you pull it back in editing. This works with **RAW** files (your [[OPPO Find N5]] in Pro mode).

**But the X100VI shoots JPEG only.** A JPEG is already "baked":

- Once a highlight clips to pure white in a JPEG, **there is no hidden data to recover.** RAW holds extra headroom; JPEG throws it away.
- On **DR100** (no dynamic-range expansion), the X100VI gives the least highlight protection — so in harsh SG sun, blown skies happen fast.
- The fix: use **DR200 / DR400 / D Range Priority** to protect highlights *at capture* (it underexposes then lifts shadows in-camera), and watch the live histogram / blinkies. Dial in **−2/3 EV** exposure compensation as insurance. See [[Fujifilm X100VI]].

**Rule of thumb:** with JPEG, protect highlights first; let shadows fall where they may. You can always crush shadows in post, but you cannot un-blow a highlight.

## Practice mission

**"Read before you click."** For one shoot, check the histogram on every single frame *before* moving on, and never let the highlight end clip (turn on highlight blinkies). Targets the **Technical** dimension. (See [[_Mission Library]] → Fundamentals Track.)
