# Decisions and why

Each of these was argued through and settled. If you want to change one, raise it — don't
route around it.

---

## 1. No server-side recompression; client resizes instead

**Decision:** the browser downsizes to 2560px long edge before upload (default ON, with a
«کیفیت اصلی» toggle). The server stores exactly what arrives and never re-encodes it.

**Why:** two different problems get confused here. Server compression saves *disk*;
upload payload size decides whether the upload *finishes at all*. At a venue with 200
people on one cell tower, the second problem is the one that ruins the night. Resizing on
the phone solves both at once, and means there is only ever **one** lossy step instead of
two.

**Consequence to remember:** the uploaded file IS the archive copy. There is no
higher-resolution original sitting on the server. 2560px ≈ 6.5MP, sharp enough for an
8×10 print, which is the right ceiling for guests' phone snapshots.

**Do not** add a "compress originals to save space" job. It was considered and rejected:
the failure mode is "the only good photo of the grandmother is now soft", with no undo.

---

## 2. No SMS OTP

**Decision:** name + phone, unverified.

**Why:** an unverified phone number prevents nothing — anyone can type `09120000000`. Its
value is *attribution* (who sent what, thank-you notes) and re-identifying a returning
guest on a new device. OTP would add per-message cost, a registered sender line, and 30–60
seconds of friction for every guest at a party, in exchange for security it doesn't
actually provide.

Keep a `require_otp` flag on `Event` so it can be added later without touching `Guest`.

---

## 3. Moderation is per guest, not per photo

**Decision:** a new uploader's first batch appears in the queue as ONE card
(«زهرا احمدی، ۸ عکس»). The couple taps once. That guest's later uploads publish directly.

**Why:** per-photo approval was the original request and it collapses under its own weight.
200 guests × 4 hours ≈ 2000 photos, and the only two people who can approve them are
getting married. The queue never gets cleared, the gallery stays empty, guests who
uploaded see nothing and assume it's broken. Per-guest approval preserves the actual
requirement — nothing unvetted is ever publicly visible — at roughly 2% of the effort.

**Required alongside it:**
- A guest always sees their own photos, approved or not, with a «در انتظار تأیید» badge.
- A **moderator link** so a sibling or friend can do this. The couple will not be
  moderating during their own عقد.

---

## 4. The link lives indefinitely

**Decision:** no upload time window. Open until the couple says stop.

**Why:** they want to share it before the wedding and keep it alive afterwards.

**What this broke:** the time window was the single strongest abuse control — "opens
Thursday 17:00, closes Sunday" meant a dead link 362 days a year. An indefinitely-live
link forwarded through Telegram and WhatsApp groups eventually reaches people who were
never invited. Replacement controls, all required:

1. Per-guest approval queue (§3)
2. Long unguessable slug
3. Rate limits per guest token and per IP, hard cap per guest
4. Real MIME sniffing with `python-magic`
5. Per-event quota — uploads pause and the host is notified at the ceiling
6. Gallery kill switch — couple can drop everyone to own-photos-only instantly

---

## 5. Shared gallery, with a kill switch

Guests see each other's approved photos by default. The couple can turn this off, which
immediately drops everyone to their own uploads only.

---

## 6. No videos

**Why:** videos are the entire disk risk. 100 guests × one 90-second clip ≈ 15GB, versus
~4GB for all the photos put together. They also can't be compressed client-side, so
there's no brake on them. Reject by sniffed MIME.

---

## 7. Django templates, not an SPA

The guest flow is three screens, opened once, on a phone, on a bad network. Tailwind
provides the polish; an SPA would add a bundle to download and a second deploy to debug.
If the couple-facing dashboard grows rich later, add a Vue island on that page alone.

---

## 8. Open Graph tags are a requirement, not a nicety

The link gets pasted into Telegram and WhatsApp groups. With no preview card it reads as
spam and nobody taps it. With `og:image` (the couple's photo), `og:title` (their names) and
one line of Persian in `og:description`, it renders as a little invitation card in the chat.

---

## Commercial note

An indefinitely-live link means hosting, backups, TLS and support for months. That's a
retainer, not a one-off fee, and who pays in month eight should be agreed in writing.
