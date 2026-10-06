# Design spec

**Guiding principle: this app is page two of the invitation.**

The design matches the couple's printed invitation: a pearl-white textured card with near-black high-contrast
serif for the Latin names, a script "And", letterspaced small-caps micro-labels, scattered
3D pearls as the only ornament, and photos in white polaroid frames tilted a few degrees.
Entirely monochrome — **no accent colour anywhere**.

A guest scans the QR roughly ninety seconds after closing that card. If the app looks like
a different product, the spell breaks and it becomes a form. Visual continuity is most of
the polish here.

There is a clickable prototype (Claude artifact "Wedding Upload — Guest UI", 7 artboards)
— ask Michael for the link if you need to see it.

---

## Tokens

```css
--pearl:      #F7F5F2;   /* page background */
--paper:      #FDFCFA;   /* cards, inputs */
--card:       #FAF8F5;   /* printed card background */
--ink:        #1A1A1A;   /* text, buttons — never pure black */
--ink-soft:   #46403A;   /* secondary text */
--muted:      #6B6560;   /* captions, helper text (4.8:1 on pearl — do not lighten) */
--muted-2:    #8C857E;   /* optional-field hints only, never body text */
--hairline:   #DCD6CE;   /* dividers */
--border:     #E8E3DB;   /* card borders */
--border-2:   #CFC8BE;   /* input borders, outline buttons */
--track:      #E6E1D9;   /* progress track */
--on-ink:     #FAF8F5;   /* text on black */
```

No other colours. No gradients except the pearl sheen and the hero photo fade.

## Type

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;700&family=Pinyon+Script&family=Vazirmatn:wght@300;400;500;700&display=swap">
```

| Role | Font | Notes |
|---|---|---|
| Latin display (names) | Playfair Display 400 | 42px on phone, 32px on the printed card |
| Script accent ("And") | Pinyon Script | 26px, only for joining words |
| Micro-labels (Latin) | Playfair Display 400 | 10px, `letter-spacing: 3.6px`, uppercase, `--muted` — `.micro-label` |
| Micro-labels (Persian) | Vazirmatn 500 | 12px, **no tracking, no uppercase**, `--muted` — `.micro-label-fa` |
| Persian body/UI | Vazirmatn 300/400/500 | 300 for body, 500 for labels and buttons |

**Numerals:** Persian digits (۱۲ عکس) in Persian body text; Latin numerals in display type
(`1405/01/01`). The invitation does exactly this — it's what makes it read as designed
rather than generic.

**Micro-labels are Persian everywhere** — «قدم اول», «قدم دوم», «سپاس»,
«عقد و نامزدی», «بررسی», «۲۴۷ عکس · ۳۸ مهمان». `.micro-label-fa` is deliberately not a
restyled `.micro-label`: `uppercase` is a no-op in Persian, and the 3.6px tracking that
makes the Latin label read as engraved small-caps prises apart Persian's joined
letterforms instead. `.micro-label` is kept for a future Latin-labelled event but is
currently unused. The only Latin type left in the product is the couple's own names and
the Jalali date.

`<html lang="fa" dir="rtl">`. Latin runs inside RTL text (URLs, filenames) need
`direction: ltr` on their own element.

---

## Component recipes

**Pearl** — the only ornament. Scatter 4–6 per screen, 5–11px, absolutely positioned, away
from text and touch targets.

```css
border-radius: 50%;
background: radial-gradient(circle at 32% 28%, #fff 0%, #f2efe9 38%, #d9d3c9 78%, #b9b2a6 100%);
box-shadow: 0 1px 2px rgba(0,0,0,.12);
```

**Divider** — hairline, pearl, hairline. Used between sections.

**Polaroid** — every photo in the product wears one.

```css
background: #FFF; padding: 6px 6px 8px; box-shadow: 0 3px 9px rgba(0,0,0,.1);
transform: rotate(-2deg);   /* alternate −2.6° … +2.2°, never 0 */
```
Caption (guest name) sits in the bottom padding: 10.5px, `--muted`, weight 300.

**Primary button** — `height: 54px; border-radius: 27px; background: var(--ink); color: var(--on-ink); font-size: 16px; font-weight: 500`. Full width.

**Secondary** — same shape, `height: 50px`, transparent, `1px solid var(--border-2)`, ink text.

**Input** — `height: 52px; border-radius: 10px; border: 1px solid var(--border-2); background: var(--paper); padding: 0 16px; font-size: 15px`. Always a real `<label>`.

**Toggle** — 50×30 pill, `border-radius: 15px`; knob 22px white circle, `box-shadow: 0 1px 3px rgba(0,0,0,.22)`. On = ink fill, knob at the start (RTL). Off = `--track` fill, `--border-2` border.

**Progress bar** — 3px, `border-radius: 2px`, track `--track`, fill `--ink`.

Touch targets ≥44px. Icons: inline stroke SVG, `stroke-width: 1.2–1.5`, never emoji.

---

## Screens

### 1 — خوش‌آمد (landing, `/e/<slug>/`)
**The whole screen is exactly one viewport** — `h-[100svh]`, no scrolling to reach the
button. `svh`, not `vh`: mobile Safari's large viewport unit is taller than what you can
actually see until the URL bar retracts, which would push the button off the bottom on
arrival. Laid out as a flex column: the text block takes its natural height and the hero
photo takes whatever is left (`flex-1 min-h-0`), so on a short phone the photo shrinks
instead of the text getting clipped.

Hero photo full-bleed, `object-position: 50% 40%`, fading into pearl over the bottom
110px. Then centred: «عقد و نامزدی» → `Sara` / `And` / `Ali` → `1405/01/01`
→ divider → one line of Persian → primary button.

`50% 40%` is tuned to this couple's cover, a tall portrait (941×1672) whose subject — her
hands and the ring on his shoulder — sits around 60% down, with nothing but jacket below.
A different cover needs a different value; there is no per-event focal control yet.

**One headline, not three.** This used to switch on `Event.phase` (before/during/after),
on the reasoning that «امشب» is wrong two thirds of the time. The couple asked for a
single line instead:

> عکسای قشنگ مراسم‌مون رو باهامون به اشتراک بذارین.

It says why the guest is here, which is as true in November as on the night.
`Event.phase` still exists and is still tested, but nothing consumes it.

Needs OG tags: `og:image` the couple photo, `og:title` their names, `og:description` one
Persian line.

### 2 — نام و شماره (`/e/<slug>/hello/`)
«قدم اول» label, «اسمتون رو بنویسین», then: اسم و فامیل (required) · شماره موبایل
(required) · یادداشت (optional). Under the phone field, a plain sentence saying what it's
for — people hesitate at phone fields, and a reason converts better than an asterisk:

> فقط برای اینکه بتونیم ازتون تشکر کنیم. جای دیگه‌ای استفاده نمی‌شه.

Returning guest matched by phone → skip straight to upload.

### 3 — ارسال عکس (`/e/<slug>/upload/`)
«قدم دوم», «عکساتون رو انتخاب کنین», «تا ۳۰ عکس · هر عکس حداکثر ۲۵ مگابایت», then a
«دیدن آلبوم مراسم» link — a returning guest is sent straight here by their cookie, so
without it the album is unreachable for them. Dashed picker box («انتخاب از گالری»,
«یا همین‌جا عکس بگیرین»). Then the quality toggle card, «ارسال با کیفیت اصلی», hint
text switching on state:

- off: «عکسا یه‌کم کوچیک‌تر و خیلی سریع‌تر فرستاده می‌شن. کیفیتش برای چاپ هم کافیه.»
- on: «عکسا دست‌نخورده فرستاده می‌شن. روی اینترنت ضعیف کندتره.»

Then per-file rows: 46px thumb, filename, an optional caption field
(«یه چیزی درباره‌ش بنویسین…», locked once the file is on the wire), progress bar, and a
state on the right (✓ / «۶۲٪» / «در صف»). **Progress is not decoration** — on a congested
network, the only thing a guest wants to know is whether it's moving or stuck. Submit is
«فرستادن عکسا».

### 4 — سپاس (`/e/<slug>/done/`)
Pearl seal with a check, «سپاس», «۱۲ تا عکس رسید», two lines of thanks, three tilted
polaroids of what they just sent, then «عکس بیشتری بفرستین» and «دیدن عکسای من»
(→ gallery `?view=guest`). Pending photos carry a «در انتظار تأیید» badge here.

### 5 — گالری (`/e/<slug>/gallery/`)
`Sara & Ali` in Pinyon Script at the top, «آلبوم مراسم‌مون»,
«۲۴۷ عکس · ۳۸ مهمان» in micro-label style. Filter chips: همه / تازه‌ترین / عکسای من.
Two-column polaroid grid, guest name and caption under each. Fixed bottom bar over a
pearl fade: for a guest, «عکس بفرستین» primary with «دانلود همه‌ی عکسا» secondary —
**the gallery must never be a dead end**, a guest arrives here from the done screen and
sending more is what they want next. For a non-guest the download is the only button.

### 6 — تأیید مهمان‌ها (moderation, couple + moderator link)
«بررسی», «تأیید مهمان‌ها», then one card per pending guest: avatar initial, name,
`phone · N عکس · time`, a row of up to 4 thumbs with a `+۵` overlay on the last, and
«تأیید مهمان» / «رد». Empty state: «همه تأیید شدند».

Fixed at the bottom: the gallery kill switch, «نمایش گالری برای مهمان‌ها», hint switching
between «مهمان‌ها می‌توانند عکس‌های تأییدشده‌ی بقیه را ببینند.» and «هر مهمان فقط عکس‌های خودش را می‌بیند.»

### 7 — کارت روی میز (print, A6 105×148mm)
Ivory `--card`, 1px inset border 18px in, names, divider, «عکسایی که امشب می‌گیرین رو باهامون قسمت بذارین»,
QR (generated with `segno`), the URL in Playfair with `direction: ltr`, and
«دوربین گوشی‌تون رو روی کد بگیرین». Print CSS — the couple print to PDF themselves, no WeasyPrint.

### 8 — نمایش روی پرده (`/e/<slug>/live/`)
Full-screen slideshow for a projector at the venue. **The only dark screen in the
product** — ink background, not pearl: a white projection in a dim hall is blinding and
photos read better on ink. Public on the slug, showing `visible_to()` with no guest, so
approved-and-shared photos only and never anything pending. Crossfade between two layers
with the incoming image decoded before the swap; blurred fill behind portrait shots;
caption and guest name on a gradient plate; a scan card top-left with the QR and
«برای فرستادن عکس، کد رو اسکن کنین». Empty state «هنوز عکسی نیومده» / «اولین عکس رو شما بفرستین».

---

## Copy rules

- Persian in the prototype is **Claude's, not a copywriter's**. It needs a pass from
  Michael or the couple before the event. Flag any new string you have to invent.
- Warm and plain. No exclamation marks, no emoji, no «لطفاً» padding.
- Never call them "users" — مهمان.
