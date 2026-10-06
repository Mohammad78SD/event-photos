import io

import pytest
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.events.models import Event

from .models import Guest, MediaItem
from .phone import normalize_iranian_mobile

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    return get_user_model().objects.create_user(username="couple", password="x")


@pytest.fixture
def event(owner):
    return Event.objects.create(
        owner=owner,
        slug="sara-ali-xyz123",
        title="عقد و نامزدی سارا و علی",
        names_latin="Sara|Ali",
        event_at=timezone.now(),
    )


@pytest.fixture
def guest(event):
    return Guest.objects.create(event=event, name="زهرا احمدی", phone="09121234567")


def guest_cookie(client, event, guest):
    client.cookies[f"guest_{event.slug}"] = signing.dumps(guest.session_token)


# --- phone normalisation ---


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("09121234567", "09121234567"),
        ("+989121234567", "09121234567"),
        ("00989121234567", "09121234567"),
        ("9121234567", "09121234567"),
        ("0912 123 4567", "09121234567"),
        ("0912-123-4567", "09121234567"),
    ],
)
def test_normalize_iranian_mobile_valid(raw, expected):
    assert normalize_iranian_mobile(raw) == expected


@pytest.mark.parametrize("raw", ["123", "0812345678", "not a phone", ""])
def test_normalize_iranian_mobile_invalid(raw):
    with pytest.raises(ValidationError):
        normalize_iranian_mobile(raw)


# --- visibility rule ---


def test_visible_to_excludes_unapproved_guest(event, guest):
    item = MediaItem.objects.create(
        event=event, guest=guest, file="x.jpg", original_name="x.jpg",
        mime="image/jpeg", size=1, sha256="a" * 64,
    )
    assert item not in MediaItem.objects.visible_to()
    assert item in MediaItem.objects.visible_to(guest=guest)


def test_visible_to_includes_approved_guest_when_gallery_shared(event, guest):
    guest.is_approved = True
    guest.save()
    item = MediaItem.objects.create(
        event=event, guest=guest, file="x.jpg", original_name="x.jpg",
        mime="image/jpeg", size=1, sha256="b" * 64,
    )
    assert item in MediaItem.objects.visible_to()


def test_visible_to_hides_everyone_when_gallery_kill_switch_off(event, guest):
    guest.is_approved = True
    guest.save()
    event.gallery_shared = False
    event.save()
    item = MediaItem.objects.create(
        event=event, guest=guest, file="x.jpg", original_name="x.jpg",
        mime="image/jpeg", size=1, sha256="c" * 64,
    )
    assert item not in MediaItem.objects.visible_to()
    assert item in MediaItem.objects.visible_to(guest=guest)


def test_visible_to_excludes_hidden_item(event, guest):
    guest.is_approved = True
    guest.save()
    item = MediaItem.objects.create(
        event=event, guest=guest, file="x.jpg", original_name="x.jpg",
        mime="image/jpeg", size=1, sha256="d" * 64, is_hidden=True,
    )
    assert item not in MediaItem.objects.visible_to()


def test_visible_to_includes_unapproved_guest_when_approval_not_required(event, guest):
    event.require_approval = False
    event.save()
    assert guest.is_approved is False
    item = MediaItem.objects.create(
        event=event, guest=guest, file="x.jpg", original_name="x.jpg",
        mime="image/jpeg", size=1, sha256="k" * 64,
    )
    assert item in MediaItem.objects.visible_to()


def test_visible_to_still_excludes_when_gallery_not_shared_even_without_approval(event, guest):
    event.require_approval = False
    event.gallery_shared = False
    event.save()
    item = MediaItem.objects.create(
        event=event, guest=guest, file="x.jpg", original_name="x.jpg",
        mime="image/jpeg", size=1, sha256="l" * 64,
    )
    assert item not in MediaItem.objects.visible_to()
    assert item in MediaItem.objects.visible_to(guest=guest)


# --- guest hello flow ---


def test_hello_creates_guest_and_sets_cookie(client, event):
    response = client.post(
        reverse("uploads:hello", kwargs={"slug": event.slug}),
        {"name": "زهرا احمدی", "phone": "0912 123 4567", "message": ""},
    )
    assert response.status_code == 302
    assert Guest.objects.filter(event=event, phone="09121234567").exists()
    assert f"guest_{event.slug}" in response.cookies


def test_hello_returning_guest_matched_by_phone_reuses_row(client, event, guest):
    client.post(
        reverse("uploads:hello", kwargs={"slug": event.slug}),
        {"name": "اسم دیگر", "phone": guest.phone, "message": ""},
    )
    assert Guest.objects.filter(event=event, phone=guest.phone).count() == 1


def test_hello_skips_to_upload_when_cookie_present(client, event, guest):
    guest_cookie(client, event, guest)
    response = client.get(reverse("uploads:hello", kwargs={"slug": event.slug}))
    assert response.status_code == 302
    assert response.url == reverse("uploads:upload", kwargs={"slug": event.slug})


def test_upload_screen_requires_guest(client, event):
    response = client.get(reverse("uploads:upload", kwargs={"slug": event.slug}))
    assert response.status_code == 302
    assert response.url == reverse("uploads:hello", kwargs={"slug": event.slug})


# --- upload API ---


def _jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="JPEG")
    return buf.getvalue()


def test_upload_api_happy_path(client, event, guest):
    guest_cookie(client, event, guest)
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile("photo.jpg", _jpeg_bytes(), content_type="image/jpeg")
    response = client.post(
        reverse("uploads_api:upload", kwargs={"slug": event.slug}), {"file": upload}
    )
    assert response.status_code == 201
    item = MediaItem.objects.get(event=event, guest=guest)
    # CELERY_TASK_ALWAYS_EAGER=True in test settings — this must have run inline,
    # not been left sitting unprocessed on a broker no test worker ever drains.
    assert item.thumb
    assert item.preview
    assert item.width == 10 and item.height == 10


def test_upload_api_rejects_without_guest_cookie(client, event):
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile("photo.jpg", _jpeg_bytes(), content_type="image/jpeg")
    response = client.post(
        reverse("uploads_api:upload", kwargs={"slug": event.slug}), {"file": upload}
    )
    assert response.status_code == 401


def test_upload_api_dedupes_identical_file(client, event, guest):
    guest_cookie(client, event, guest)
    from django.core.files.uploadedfile import SimpleUploadedFile

    data = _jpeg_bytes()
    reverse_url = reverse("uploads_api:upload", kwargs={"slug": event.slug})

    r1 = client.post(reverse_url, {"file": SimpleUploadedFile("a.jpg", data, content_type="image/jpeg")})
    r2 = client.post(reverse_url, {"file": SimpleUploadedFile("a.jpg", data, content_type="image/jpeg")})

    assert r1.status_code == 201
    assert r2.status_code == 200
    assert MediaItem.objects.filter(event=event).count() == 1


def test_upload_api_stores_caption(client, event, guest):
    guest_cookie(client, event, guest)
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile("photo.jpg", _jpeg_bytes(), content_type="image/jpeg")
    response = client.post(
        reverse("uploads_api:upload", kwargs={"slug": event.slug}),
        {"file": upload, "caption": "شب فوق‌العاده‌ای بود!"},
    )
    assert response.status_code == 201
    item = MediaItem.objects.get(event=event, guest=guest)
    assert item.caption == "شب فوق‌العاده‌ای بود!"


def test_upload_api_truncates_long_caption(client, event, guest):
    guest_cookie(client, event, guest)
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile("photo.jpg", _jpeg_bytes(), content_type="image/jpeg")
    response = client.post(
        reverse("uploads_api:upload", kwargs={"slug": event.slug}),
        {"file": upload, "caption": "a" * 500},
    )
    assert response.status_code == 201
    item = MediaItem.objects.get(event=event, guest=guest)
    assert len(item.caption) == 280


def test_upload_api_retry_with_caption_backfills_existing_item(client, event, guest):
    guest_cookie(client, event, guest)
    from django.core.files.uploadedfile import SimpleUploadedFile

    data = _jpeg_bytes()
    reverse_url = reverse("uploads_api:upload", kwargs={"slug": event.slug})

    r1 = client.post(reverse_url, {"file": SimpleUploadedFile("a.jpg", data, content_type="image/jpeg")})
    assert r1.status_code == 201

    r2 = client.post(
        reverse_url,
        {"file": SimpleUploadedFile("a.jpg", data, content_type="image/jpeg"), "caption": "یادگاری"},
    )
    assert r2.status_code == 200
    assert MediaItem.objects.filter(event=event).count() == 1
    item = MediaItem.objects.get(event=event)
    assert item.caption == "یادگاری"


def test_upload_api_accepts_heic(client, event, guest):
    import pillow_heif

    pillow_heif.register_heif_opener()
    guest_cookie(client, event, guest)
    from django.core.files.uploadedfile import SimpleUploadedFile

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="green").save(buf, format="HEIF")
    upload = SimpleUploadedFile("photo.heic", buf.getvalue(), content_type="image/heic")
    response = client.post(
        reverse("uploads_api:upload", kwargs={"slug": event.slug}), {"file": upload}
    )
    assert response.status_code == 201
    item = MediaItem.objects.get(event=event, guest=guest)
    assert item.mime == "image/heic"
    assert item.thumb  # pillow-heif fallback let the derivative pipeline open it


def test_upload_api_rejects_oversized_file(client, event, guest):
    event.max_file_mb = 0
    event.save()
    guest_cookie(client, event, guest)
    from django.core.files.uploadedfile import SimpleUploadedFile

    too_big = SimpleUploadedFile("a.jpg", b"0" * 1024, content_type="image/jpeg")
    response = client.post(
        reverse("uploads_api:upload", kwargs={"slug": event.slug}), {"file": too_big}
    )
    assert response.status_code == 413


def test_upload_api_rejects_when_quota_exceeded(client, event, guest):
    event.quota_gb = 1  # keep quota_bytes well under MediaItem.size's int32 range
    event.save()
    quota_bytes = event.quota_gb * 1024 * 1024 * 1024
    MediaItem.objects.create(
        event=event, guest=guest, file="x.jpg", original_name="x.jpg",
        mime="image/jpeg", size=quota_bytes, sha256="e" * 64,
    )
    guest_cookie(client, event, guest)
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile("new.jpg", _jpeg_bytes(), content_type="image/jpeg")
    response = client.post(
        reverse("uploads_api:upload", kwargs={"slug": event.slug}), {"file": upload}
    )
    assert response.status_code == 507


# --- rate limiting ---


def test_upload_api_enforces_per_guest_rate_limit(client, event, guest):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from .throttling import RATE_LIMIT_PER_GUEST_PER_MINUTE

    guest_cookie(client, event, guest)
    url = reverse("uploads_api:upload", kwargs={"slug": event.slug})
    data = _jpeg_bytes()

    for i in range(RATE_LIMIT_PER_GUEST_PER_MINUTE):
        upload = SimpleUploadedFile(f"photo{i}.jpg", data, content_type="image/jpeg")
        response = client.post(url, {"file": upload})
        assert response.status_code in (200, 201)

    overflow = SimpleUploadedFile("overflow.jpg", data, content_type="image/jpeg")
    response = client.post(url, {"file": overflow})
    assert response.status_code == 429


def test_upload_api_enforces_per_ip_rate_limit_across_guests(client, event):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from .throttling import RATE_LIMIT_PER_GUEST_PER_MINUTE, RATE_LIMIT_PER_IP_PER_MINUTE

    url = reverse("uploads_api:upload", kwargs={"slug": event.slug})
    data = _jpeg_bytes()

    # Django's test client keeps a single REMOTE_ADDR, so several guests
    # posting from "the same phone's wifi" share one IP bucket even though
    # each guest's own per-guest bucket stays under its limit.
    guests_needed = -(-RATE_LIMIT_PER_IP_PER_MINUTE // RATE_LIMIT_PER_GUEST_PER_MINUTE) + 1
    made_requests = 0
    saw_429 = False
    for g in range(guests_needed):
        guest = Guest.objects.create(event=event, name=f"Guest {g}", phone=f"0912000{g:04d}")
        guest_cookie(client, event, guest)
        for i in range(RATE_LIMIT_PER_GUEST_PER_MINUTE):
            upload = SimpleUploadedFile(f"g{g}-{i}.jpg", data, content_type="image/jpeg")
            response = client.post(url, {"file": upload})
            made_requests += 1
            if response.status_code == 429:
                saw_429 = True
                break
        if saw_429:
            break

    assert saw_429
    assert made_requests <= RATE_LIMIT_PER_IP_PER_MINUTE + 1


# --- protected media serving (X-Accel-Redirect) ---


def test_media_serves_x_accel_redirect_for_own_pending_item(client, event, guest):
    item = MediaItem.objects.create(
        event=event, guest=guest, file="events/1/2026-09/a.jpg", original_name="a.jpg",
        mime="image/jpeg", size=1, sha256="f" * 64,
    )
    guest_cookie(client, event, guest)
    response = client.get(f"/media/{item.file.name}")
    assert response.status_code == 200
    assert response["X-Accel-Redirect"] == f"/protected-media/{item.file.name}"


def test_media_404s_for_unapproved_item_to_stranger(client, event, guest):
    item = MediaItem.objects.create(
        event=event, guest=guest, file="events/1/2026-09/b.jpg", original_name="b.jpg",
        mime="image/jpeg", size=1, sha256="g" * 64,
    )
    response = client.get(f"/media/{item.file.name}")
    assert response.status_code == 404


def test_media_visible_to_everyone_once_guest_approved_and_shared(client, event, guest):
    guest.is_approved = True
    guest.save()
    item = MediaItem.objects.create(
        event=event, guest=guest, file="events/1/2026-09/c.jpg", original_name="c.jpg",
        mime="image/jpeg", size=1, sha256="h" * 64,
    )
    response = client.get(f"/media/{item.file.name}")
    assert response.status_code == 200


def test_media_404s_for_hidden_item_to_stranger(client, event, guest):
    guest.is_approved = True
    guest.save()
    item = MediaItem.objects.create(
        event=event, guest=guest, file="events/1/2026-09/d.jpg", original_name="d.jpg",
        mime="image/jpeg", size=1, sha256="i" * 64, is_hidden=True,
    )
    response = client.get(f"/media/{item.file.name}")
    assert response.status_code == 404


def test_media_visible_to_owner_even_when_unapproved(client, owner, event, guest):
    item = MediaItem.objects.create(
        event=event, guest=guest, file="events/1/2026-09/e.jpg", original_name="e.jpg",
        mime="image/jpeg", size=1, sha256="j" * 64,
    )
    client.login(username="couple", password="x")
    response = client.get(f"/media/{item.file.name}")
    assert response.status_code == 200


def test_media_404s_for_unknown_path(client):
    response = client.get("/media/events/does/not/exist.jpg")
    assert response.status_code == 404


def test_media_serves_event_cover_image_publicly(client, event):
    from django.core.files.base import ContentFile

    event.cover_image.save("cover.jpg", ContentFile(b"fake cover bytes"), save=True)
    # No guest cookie, not logged in — link-preview bots and guests who
    # haven't said hello yet must still be able to fetch the OG image.
    response = client.get(f"/media/{event.cover_image.name}")
    assert response.status_code == 200
    assert response["X-Accel-Redirect"] == f"/protected-media/{event.cover_image.name}"
