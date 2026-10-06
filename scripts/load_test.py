#!/usr/bin/env python3
"""Pre-flight load rehearsal: N guests uploading a ~5MB photo at once.

Stdlib only (no requests/locust dependency) so it runs anywhere Python 3 does,
including straight from a laptop against the real domain.

Usage:
    python3 scripts/load_test.py <base_url> <event_slug> [concurrency]

Example:
    python3 scripts/load_test.py https://photos.example.com sara-ali-xyz123 30
"""
import io
import os
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.cookiejar import CookieJar
from urllib.request import build_opener, HTTPCookieProcessor, Request

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow required: pip install Pillow (it's already in requirements/base.txt)")

CSRF_RE = re.compile(rb'name="csrfmiddlewaretoken" value="([^"]+)"')


def make_noise_jpeg(target_bytes=5 * 1024 * 1024):
    """A real, fully-decodable JPEG that's hard to compress (~target_bytes),
    so the rehearsal moves roughly as much data as an actual guest photo."""
    side = int((target_bytes) ** 0.5)
    img = Image.effect_noise((side, side), 60).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def multipart_body(fields, file_field, filename, file_bytes):
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n".encode()
        + file_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    return body, f"multipart/form-data; boundary={boundary}"


def run_one_guest(base_url, slug, photo_bytes, index):
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    hello_url = f"{base_url}/e/{slug}/hello/"

    resp = opener.open(hello_url)
    html = resp.read()
    match = CSRF_RE.search(html)
    if not match:
        return index, "no csrf token on hello page (already has a guest cookie?)", False
    csrf = match.group(1).decode()

    phone = f"0912{index:07d}"[:11]
    # Django accepts multipart for plain POST forms too, so the same helper
    # that encodes the file upload below works here.
    body, content_type = multipart_body(
        {"csrfmiddlewaretoken": csrf, "name": f"Load Test {index}", "phone": phone, "message": ""},
        "_unused", "unused.txt", b"",
    )
    # Django requires a same-origin Referer for CSRF on HTTPS requests that
    # lack an Origin header, and urllib never sends Origin — omitting this
    # 403s every POST once the site's actually served over TLS.
    req = Request(
        hello_url,
        data=body,
        headers={"Content-Type": content_type, "X-CSRFToken": csrf, "Referer": hello_url},
        method="POST",
    )
    opener.open(req)  # follows the redirect to /upload/, sets the guest cookie

    upload_url = f"{base_url}/api/e/{slug}/upload/"
    unique_bytes = photo_bytes + os.urandom(16)  # distinct sha256 per guest
    body, content_type = multipart_body({}, "file", f"loadtest-{index}.jpg", unique_bytes)
    req = Request(
        upload_url,
        data=body,
        headers={"Content-Type": content_type, "X-CSRFToken": csrf, "Referer": hello_url},
        method="POST",
    )

    started = time.monotonic()
    try:
        resp = opener.open(req)
        elapsed = time.monotonic() - started
        return index, f"{resp.status} in {elapsed:.2f}s", resp.status in (200, 201)
    except Exception as exc:  # noqa: BLE001 - report every failure, this is a rehearsal
        elapsed = time.monotonic() - started
        return index, f"FAILED after {elapsed:.2f}s: {exc}", False


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    base_url = sys.argv[1].rstrip("/")
    slug = sys.argv[2]
    concurrency = int(sys.argv[3]) if len(sys.argv) > 3 else 30

    print("Generating a ~5MB test photo...")
    photo_bytes = make_noise_jpeg()
    print(f"Test photo: {len(photo_bytes) / 1024 / 1024:.1f}MB")
    print(f"Firing {concurrency} concurrent guest uploads at {base_url} ...")

    failures = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(run_one_guest, base_url, slug, photo_bytes, i) for i in range(concurrency)]
        for future in as_completed(futures):
            index, message, ok = future.result()
            print(f"guest {index:>3}: {message}")
            if not ok:
                failures += 1

    print(f"\n{concurrency - failures}/{concurrency} succeeded.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
