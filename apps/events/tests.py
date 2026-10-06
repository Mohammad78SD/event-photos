import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import DURING_WINDOW, Event


@pytest.fixture
def owner(db):
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


def test_phase_before(event):
    event.event_at = timezone.now() + datetime.timedelta(days=1)
    assert event.phase == "before"


def test_phase_during_right_at_start(event):
    event.event_at = timezone.now()
    assert event.phase == "during"


def test_phase_during_just_before_window_ends(event):
    event.event_at = timezone.now() - (DURING_WINDOW - datetime.timedelta(minutes=1))
    assert event.phase == "during"


def test_phase_after_just_past_window(event):
    event.event_at = timezone.now() - (DURING_WINDOW + datetime.timedelta(minutes=1))
    assert event.phase == "after"


def test_names_split(event):
    assert event.names == ["Sara", "Ali"]


# Tests for operator screens (Phase 3)


def test_create_event_requires_login(client):
    """Create event view requires login."""
    response = client.get("/create/")
    assert response.status_code == 302  # Redirect to login
    assert response.url.startswith("/accounts/login/")


def test_create_event_post_requires_login(client):
    """Create event POST requires login."""
    response = client.post(
        "/create/",
        {"title": "Test", "names_latin": "A|B", "event_at": "2026-09-24T19:00"},
    )
    assert response.status_code == 302


def test_create_event_sets_owner_from_request_user(client, owner):
    """Create event sets owner from request.user, not form data."""
    client.force_login(owner)
    response = client.post(
        "/create/",
        {
            "title": "Test Event",
            "names_latin": "Alice|Bob",
            "event_at": "2026-09-24T19:00:00",
            "is_open": True,
            "gallery_shared": True,
            "require_approval": True,
            "max_file_mb": 25,
            "max_files_batch": 30,
            "quota_gb": 50,
        },
    )
    assert response.status_code == 302
    assert response.url == "/dashboard/"

    created_event = Event.objects.get(title="Test Event")
    assert created_event.owner_id == owner.id


def test_create_event_slug_auto_generated(client, owner):
    """Create event auto-generates slug, not from form data."""
    client.force_login(owner)
    response = client.post(
        "/create/",
        {
            "title": "Another Event",
            "names_latin": "Charlie|Dana",
            "event_at": "2026-09-24T19:00:00",
            "is_open": True,
            "gallery_shared": True,
            "require_approval": True,
            "max_file_mb": 25,
            "max_files_batch": 30,
            "quota_gb": 50,
        },
    )
    assert response.status_code == 302

    created_event = Event.objects.get(title="Another Event")
    # Slug should be auto-generated (long and unguessable)
    assert len(created_event.slug) > 10
    assert created_event.slug != "another-event"
    # Should be URL-safe
    assert all(c.isalnum() or c in "-_" for c in created_event.slug)


def test_create_event_redirects_to_dashboard(client, owner):
    """Create event redirects to dashboard after success."""
    client.force_login(owner)
    response = client.post(
        "/create/",
        {
            "title": "Redirect Test",
            "names_latin": "Eve|Frank",
            "event_at": "2026-09-24T19:00:00",
            "is_open": True,
            "gallery_shared": True,
            "require_approval": True,
            "max_file_mb": 25,
            "max_files_batch": 30,
            "quota_gb": 50,
        },
    )
    assert response.status_code == 302
    assert response.url == "/dashboard/"


def test_create_event_get_renders_form(client, owner):
    """Create event GET renders form."""
    client.force_login(owner)
    response = client.get("/create/")
    assert response.status_code == 200
    assert b"name=\"title\"" in response.content


def test_edit_event_requires_login(client, event):
    """Edit event requires login."""
    response = client.get(f"/e/{event.slug}/edit/")
    assert response.status_code == 302
    assert response.url.startswith("/accounts/login/")


def test_edit_event_rejects_non_owner(client, owner, event):
    """Edit event returns 404 for non-owner."""
    other_user = get_user_model().objects.create_user(username="other", password="x")
    client.force_login(other_user)
    response = client.get(f"/e/{event.slug}/edit/")
    assert response.status_code == 404


def test_edit_event_owner_can_edit(client, owner, event):
    """Edit event owner can edit the event."""
    client.force_login(owner)
    response = client.get(f"/e/{event.slug}/edit/")
    assert response.status_code == 200
    assert b"name=\"title\"" in response.content
    assert event.title.encode() in response.content


def test_edit_event_post_updates_event(client, owner, event):
    """Edit event POST updates the event."""
    client.force_login(owner)
    response = client.post(
        f"/e/{event.slug}/edit/",
        {
            "title": "Updated Title",
            "names_latin": event.names_latin,
            "event_at": event.event_at.strftime("%Y-%m-%dT%H:%M:%S"),
            "is_open": True,
            "gallery_shared": False,
            "require_approval": True,
            "max_file_mb": 50,
            "max_files_batch": 30,
            "quota_gb": 100,
        },
    )
    assert response.status_code == 302

    event.refresh_from_db()
    assert event.title == "Updated Title"
    assert event.gallery_shared is False
    assert event.max_file_mb == 50
    assert event.quota_gb == 100


def test_edit_event_post_redirects_to_dashboard(client, owner, event):
    """Edit event POST redirects to dashboard."""
    client.force_login(owner)
    response = client.post(
        f"/e/{event.slug}/edit/",
        {
            "title": event.title,
            "names_latin": event.names_latin,
            "event_at": event.event_at.strftime("%Y-%m-%dT%H:%M:%S"),
            "is_open": True,
            "gallery_shared": True,
            "require_approval": True,
            "max_file_mb": 25,
            "max_files_batch": 30,
            "quota_gb": 50,
        },
    )
    assert response.status_code == 302
    assert response.url == "/dashboard/"


def test_table_card_requires_login(client, event):
    """Table card view requires login."""
    response = client.get(f"/e/{event.slug}/table-card/")
    assert response.status_code == 302
    assert response.url.startswith("/accounts/login/")


def test_table_card_rejects_non_owner(client, owner, event):
    """Table card returns 404 for non-owner."""
    other_user = get_user_model().objects.create_user(username="other2", password="x")
    client.force_login(other_user)
    response = client.get(f"/e/{event.slug}/table-card/")
    assert response.status_code == 404


def test_table_card_owner_can_view(client, owner, event):
    """Table card owner can view it."""
    client.force_login(owner)
    response = client.get(f"/e/{event.slug}/table-card/")
    assert response.status_code == 200
    # Check for expected content: the class name of the card container
    assert b"table-card" in response.content
    # Check for the names in the response (they appear in the template)
    assert b"Sara" in response.content or b"Ali" in response.content


def test_table_card_contains_qr_code(client, owner, event):
    """Table card renders QR code as SVG."""
    client.force_login(owner)
    response = client.get(f"/e/{event.slug}/table-card/")
    assert response.status_code == 200
    # QR code should be embedded as SVG data URI
    assert b"data:image/svg+xml" in response.content or b"<svg" in response.content


def test_table_card_contains_event_url(client, owner, event):
    """Table card contains the event's public URL."""
    client.force_login(owner)
    response = client.get(f"/e/{event.slug}/table-card/")
    assert response.status_code == 200
    assert event.slug.encode() in response.content


# --- static cache busting ---


def test_static_v_appends_content_hash():
    from apps.events.templatetags.event_extras import _asset_digest, static_v

    _asset_digest.cache_clear()
    url = static_v("dist/app.css")
    assert "?v=" in url
    assert len(url.split("?v=")[1]) == 8


def test_static_v_falls_back_when_asset_missing():
    """A missing file must not 500 a page — the link just goes out unversioned."""
    from apps.events.templatetags.event_extras import _asset_digest, static_v

    _asset_digest.cache_clear()
    assert "?v=" not in static_v("dist/does-not-exist.css")


def test_landing_serves_versioned_css(client, event):
    from django.urls import reverse

    body = client.get(reverse("events:landing", kwargs={"slug": event.slug})).content.decode()
    assert "dist/app.css?v=" in body
