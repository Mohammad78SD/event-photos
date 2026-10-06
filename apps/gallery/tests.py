import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event
from apps.uploads.models import Guest, MediaItem

from .models import ZipExport

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


def make_item(event, guest, sha="a" * 64):
    return MediaItem.objects.create(
        event=event, guest=guest, file="x.jpg", original_name="x.jpg",
        mime="image/jpeg", size=1, sha256=sha,
    )


# --- access control ---


def test_moderation_queue_requires_login_for_anonymous(client, event):
    resp = client.get(reverse("gallery:moderation_queue", kwargs={"slug": event.slug}))
    assert resp.status_code == 302
    assert resp.url.startswith(reverse("login"))


def test_moderation_queue_404s_for_logged_in_stranger(client, event):
    get_user_model().objects.create_user(username="stranger", password="x")
    client.login(username="stranger", password="x")
    resp = client.get(reverse("gallery:moderation_queue", kwargs={"slug": event.slug}))
    assert resp.status_code == 404


def test_moderation_queue_open_to_owner(client, owner, event):
    client.login(username="couple", password="x")
    resp = client.get(reverse("gallery:moderation_queue", kwargs={"slug": event.slug}))
    assert resp.status_code == 200


def test_moderator_link_grants_session_access(client, event):
    entry_url = reverse("gallery:moderator_entry", kwargs={"slug": event.slug, "token": event.moderator_token})
    resp = client.get(entry_url)
    assert resp.status_code == 302
    resp = client.get(reverse("gallery:moderation_queue", kwargs={"slug": event.slug}))
    assert resp.status_code == 200


def test_wrong_moderator_token_404s(client, event):
    entry_url = reverse("gallery:moderator_entry", kwargs={"slug": event.slug, "token": "not-the-token"})
    assert client.get(entry_url).status_code == 404


# --- approve / reject ---


def test_approve_guest_marks_approved(client, owner, event, guest):
    client.login(username="couple", password="x")
    resp = client.post(reverse("gallery:approve_guest", kwargs={"slug": event.slug, "guest_id": guest.id}))
    assert resp.status_code == 302
    guest.refresh_from_db()
    assert guest.is_approved
    assert guest.approved_at is not None


def test_reject_guest_deletes_guest_and_media(client, owner, event, guest):
    item = make_item(event, guest)
    client.login(username="couple", password="x")
    client.post(reverse("gallery:reject_guest", kwargs={"slug": event.slug, "guest_id": guest.id}))
    assert not Guest.objects.filter(id=guest.id).exists()
    assert not MediaItem.objects.filter(id=item.id).exists()


def test_reject_refuses_already_approved_guest(client, owner, event, guest):
    guest.is_approved = True
    guest.save()
    client.login(username="couple", password="x")
    resp = client.post(reverse("gallery:reject_guest", kwargs={"slug": event.slug, "guest_id": guest.id}))
    assert resp.status_code == 404
    assert Guest.objects.filter(id=guest.id).exists()


# --- kill switch, hide, delete ---


def test_toggle_gallery_shared_flips_flag(client, owner, event):
    assert event.gallery_shared is True
    client.login(username="couple", password="x")
    client.post(reverse("gallery:toggle_gallery_shared", kwargs={"slug": event.slug}))
    event.refresh_from_db()
    assert event.gallery_shared is False


def test_hide_item_toggles_is_hidden(client, owner, event, guest):
    item = make_item(event, guest)
    client.login(username="couple", password="x")
    client.post(reverse("gallery:hide_item", kwargs={"slug": event.slug, "item_id": item.id}))
    item.refresh_from_db()
    assert item.is_hidden is True


def test_delete_item_removes_it(client, owner, event, guest):
    item = make_item(event, guest)
    client.login(username="couple", password="x")
    client.post(reverse("gallery:delete_item", kwargs={"slug": event.slug, "item_id": item.id}))
    assert not MediaItem.objects.filter(id=item.id).exists()


# --- public gallery ---


def test_public_gallery_only_shows_approved(client, event, guest):
    guest.is_approved = True
    guest.save()
    approved_item = make_item(event, guest, sha="a" * 64)

    other_guest = Guest.objects.create(event=event, name="Pending", phone="09129999999")
    make_item(event, other_guest, sha="b" * 64)

    resp = client.get(reverse("gallery:gallery", kwargs={"slug": event.slug}))
    assert resp.status_code == 200
    items = list(resp.context["items"])
    assert items == [approved_item]


# --- zip export ---


def test_request_zip_builds_synchronously_in_tests(client, owner, event, guest):
    guest.is_approved = True
    guest.save()
    item = make_item(event, guest)
    item.file.save("real.jpg", ContentFile(b"fake image bytes"), save=True)

    client.login(username="couple", password="x")
    resp = client.post(reverse("gallery:request_zip", kwargs={"slug": event.slug}))
    export_id = resp.url.split("export=")[1]
    export = ZipExport.objects.get(id=export_id)
    assert export.is_ready
    assert export.item_count == 1


def test_download_zip_rejects_bad_token(client, owner, event):
    export = ZipExport.objects.create(event=event, is_ready=True)
    client.login(username="couple", password="x")
    url = reverse("gallery:download_zip", kwargs={"slug": event.slug, "export_id": export.id, "token": "bogus"})
    assert client.get(url).status_code == 404


def test_download_zip_hands_off_to_nginx_via_x_accel_redirect(client, owner, event):
    from django.core import signing

    export = ZipExport.objects.create(event=event, is_ready=True)
    export.file.save("test.zip", ContentFile(b"zip bytes"), save=True)
    client.login(username="couple", password="x")
    token = signing.TimestampSigner().sign(export.id)
    url = reverse(
        "gallery:download_zip", kwargs={"slug": event.slug, "export_id": export.id, "token": token}
    )
    response = client.get(url)
    assert response.status_code == 200
    assert response["X-Accel-Redirect"] == f"/protected-media/{export.file.name}"


# --- live wall ---


def _feed(client, event):
    return client.get(reverse("gallery:live_feed", kwargs={"slug": event.slug})).json()["items"]


def test_live_wall_renders_with_a_scan_code(client, event):
    response = client.get(reverse("gallery:live", kwargs={"slug": event.slug}))
    assert response.status_code == 200
    # The QR is the whole reason the wall earns its place on a projector.
    assert b"data:image/svg+xml" in response.content


def test_live_feed_hides_unapproved_guests_photos(client, event, guest):
    make_item(event, guest)
    assert _feed(client, event) == []


def test_live_feed_shows_approved_photos_with_caption(client, event, guest):
    guest.is_approved = True
    guest.save()
    item = make_item(event, guest)
    item.caption = "چه شب قشنگی بود"
    item.save()

    payload = _feed(client, event)
    assert [i["id"] for i in payload] == [item.id]
    assert payload[0]["caption"] == "چه شب قشنگی بود"
    assert payload[0]["name"] == guest.name


def test_live_feed_empties_when_the_gallery_kill_switch_is_off(client, event, guest):
    guest.is_approved = True
    guest.save()
    make_item(event, guest)
    event.gallery_shared = False
    event.save()
    assert _feed(client, event) == []


def test_live_feed_excludes_a_hidden_photo(client, event, guest):
    guest.is_approved = True
    guest.save()
    item = make_item(event, guest)
    item.is_hidden = True
    item.save()
    assert _feed(client, event) == []


def test_live_feed_does_not_leak_a_guests_own_pending_photo(client, event, guest):
    """The wall must never show pending work, even to the browser that uploaded
    it — unlike the gallery, where a guest always sees their own photos."""
    make_item(event, guest)
    from django.core import signing

    client.cookies[f"guest_{event.slug}"] = signing.dumps(guest.session_token)
    assert _feed(client, event) == []


# --- the whole-album download is the owner's alone ---


def _signed_download_url(event, export):
    from django.core import signing

    token = signing.TimestampSigner().sign(export.id)
    return reverse(
        "gallery:download_zip",
        kwargs={"slug": event.slug, "export_id": export.id, "token": token},
    )


@pytest.fixture
def ready_export(event):
    export = ZipExport.objects.create(event=event, is_ready=True)
    export.file.save("test.zip", ContentFile(b"zip bytes"), save=True)
    return export


def test_anonymous_cannot_download_the_album(client, owner, event, ready_export):
    """A valid signature proves we minted the URL, not who is asking. The slug is
    printed on every table card, so without an owner check a stranger could pull
    the entire album."""
    resp = client.get(_signed_download_url(event, ready_export))
    assert resp.status_code == 302
    assert "/login" in resp.url


def test_anonymous_cannot_mint_a_download_url(client, owner, event, ready_export):
    url = reverse(
        "gallery:zip_export_status", kwargs={"slug": event.slug, "export_id": ready_export.id}
    )
    resp = client.get(url)
    assert resp.status_code == 302
    assert b"protected-media" not in resp.content


def test_guest_cannot_download_the_album(client, owner, event, guest, ready_export):
    from django.core import signing

    client.cookies[f"guest_{event.slug}"] = signing.dumps(guest.session_token)
    assert client.get(_signed_download_url(event, ready_export)).status_code == 302


def test_moderator_link_holder_cannot_download_the_album(client, owner, event, ready_export):
    """The helper can approve and hide, but not walk off with every photo."""
    client.get(
        reverse("gallery:moderator_entry", kwargs={"slug": event.slug, "token": event.moderator_token})
    )
    assert client.get(reverse("gallery:moderation_queue", kwargs={"slug": event.slug})).status_code == 200
    assert client.get(_signed_download_url(event, ready_export)).status_code == 302


def test_logged_in_stranger_cannot_download_the_album(client, owner, event, ready_export):
    get_user_model().objects.create_user(username="stranger", password="x")
    client.login(username="stranger", password="x")
    assert client.get(_signed_download_url(event, ready_export)).status_code == 404


def test_moderator_link_holder_cannot_request_a_build(client, owner, event):
    client.get(
        reverse("gallery:moderator_entry", kwargs={"slug": event.slug, "token": event.moderator_token})
    )
    resp = client.post(reverse("gallery:request_zip", kwargs={"slug": event.slug}))
    assert resp.status_code == 302 and "/login" in resp.url
    assert ZipExport.objects.count() == 0


def test_owner_still_downloads(client, owner, event, ready_export):
    client.login(username="couple", password="x")
    resp = client.get(_signed_download_url(event, ready_export))
    assert resp.status_code == 200
    assert resp["X-Accel-Redirect"] == f"/protected-media/{ready_export.file.name}"
