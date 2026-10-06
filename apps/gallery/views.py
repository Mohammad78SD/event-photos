import datetime

import segno
from django.contrib.auth.views import redirect_to_login
from django.core import signing
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_POST

GALLERY_PAGE_SIZE = 60
LATEST_WINDOW = datetime.timedelta(hours=24)

# The live wall runs unattended on a venue projector for hours. Keep the working
# set small enough that the browser never accumulates hundreds of decoded images.
LIVE_FEED_LIMIT = 60

from apps.events.models import Event
from apps.uploads.models import Guest, MediaItem
from apps.uploads.session import get_guest

from .access import grant_moderator_session, has_moderation_access, is_event_owner
from .models import ZipExport
from .tasks import build_zip_export

DOWNLOAD_LINK_MAX_AGE = 60 * 60 * 24  # a day — long enough for a slow connection, short enough to not be forever


def _moderation_gate(request, event):
    """None if allowed, else the response to return."""
    if has_moderation_access(request, event):
        return None
    if request.user.is_authenticated:
        raise Http404
    return redirect_to_login(request.get_full_path())


def _owner_gate(request, event):
    """None if allowed, else the response to return. Owner-only — see
    access.is_event_owner for why the moderator link does not clear this."""
    if is_event_owner(request, event):
        return None
    if request.user.is_authenticated:
        raise Http404
    return redirect_to_login(request.get_full_path())


def gallery(request, slug):
    event = get_object_or_404(Event, slug=slug, is_open=True)
    guest = get_guest(request, event)
    items = MediaItem.objects.filter(event=event).visible_to(guest).select_related("guest")

    view = request.GET.get("view", "all")
    if view == "guest" and guest is not None:
        items = items.filter(guest=guest)
    elif view == "latest":
        items = items.filter(created_at__gte=timezone.now() - LATEST_WINDOW)
    items = items.order_by("-created_at")

    guest_count = Guest.objects.filter(event=event, is_approved=True).count()
    page_obj = Paginator(items, GALLERY_PAGE_SIZE).get_page(request.GET.get("page"))

    return render(
        request,
        "gallery/gallery.html",
        {
            "event": event,
            "guest": guest,
            "items": page_obj,
            "view": view,
            "guest_count": guest_count,
            "can_moderate": has_moderation_access(request, event),
            "can_download": is_event_owner(request, event),
            "zip_status_url_template": reverse(
                "gallery:zip_export_status", kwargs={"slug": event.slug, "export_id": 0}
            ),
        },
    )


def _live_items(event):
    return (
        MediaItem.objects.filter(event=event)
        .visible_to()
        .select_related("guest")
        .order_by("-created_at")[:LIVE_FEED_LIMIT]
    )


def _live_payload(item):
    return {
        "id": item.id,
        "url": item.preview.url if item.preview else item.file.url,
        "name": item.guest.name,
        "caption": item.caption,
    }


def live(request, slug):
    """Full-screen slideshow for a projector at the venue.

    Deliberately public on the slug: the QR on every table already leads here,
    and the wall shows strictly less than the gallery does — `visible_to()` with
    no guest, so approved-and-shared items only, never anything pending. If the
    couple flip the gallery kill switch the wall empties too, which is the
    behaviour you want from a switch labelled "stop showing our photos"."""
    event = get_object_or_404(Event, slug=slug)
    landing_url = request.build_absolute_uri(
        reverse("events:landing", kwargs={"slug": event.slug})
    )
    return render(
        request,
        "gallery/live.html",
        {
            "event": event,
            "items": [_live_payload(item) for item in _live_items(event)],
            "feed_url": reverse("gallery:live_feed", kwargs={"slug": event.slug}),
            "qr_svg": segno.make(landing_url, micro=False).svg_data_uri(),
        },
    )


def live_feed(request, slug):
    event = get_object_or_404(Event, slug=slug)
    return JsonResponse({"items": [_live_payload(item) for item in _live_items(event)]})


def moderator_entry(request, slug, token):
    event = get_object_or_404(Event, slug=slug)
    if not constant_time_compare(token, event.moderator_token):
        raise Http404
    grant_moderator_session(request, event)
    return redirect("gallery:moderation_queue", slug=slug)


def moderation_queue(request, slug):
    event = get_object_or_404(Event, slug=slug)
    gate = _moderation_gate(request, event)
    if gate is not None:
        return gate

    pending = (
        Guest.objects.filter(event=event, is_approved=False)
        .prefetch_related("media_items")
        .order_by("created_at")
    )
    return render(request, "gallery/moderation.html", {"event": event, "pending": pending})


@require_POST
def approve_guest(request, slug, guest_id):
    event = get_object_or_404(Event, slug=slug)
    gate = _moderation_gate(request, event)
    if gate is not None:
        return gate

    guest = get_object_or_404(Guest, event=event, id=guest_id)
    guest.is_approved = True
    guest.approved_at = timezone.now()
    guest.save(update_fields=["is_approved", "approved_at"])
    return redirect("gallery:moderation_queue", slug=slug)


@require_POST
def reject_guest(request, slug, guest_id):
    event = get_object_or_404(Event, slug=slug)
    gate = _moderation_gate(request, event)
    if gate is not None:
        return gate

    # Never-approved guest: nothing was ever public, so drop them and their files entirely.
    get_object_or_404(Guest, event=event, id=guest_id, is_approved=False).delete()
    return redirect("gallery:moderation_queue", slug=slug)


@require_POST
def toggle_gallery_shared(request, slug):
    event = get_object_or_404(Event, slug=slug)
    gate = _moderation_gate(request, event)
    if gate is not None:
        return gate

    event.gallery_shared = not event.gallery_shared
    event.save(update_fields=["gallery_shared"])
    return redirect("gallery:gallery", slug=slug)


@require_POST
def hide_item(request, slug, item_id):
    event = get_object_or_404(Event, slug=slug)
    gate = _moderation_gate(request, event)
    if gate is not None:
        return gate

    item = get_object_or_404(MediaItem, event=event, id=item_id)
    item.is_hidden = not item.is_hidden
    item.save(update_fields=["is_hidden"])
    return redirect("gallery:gallery", slug=slug)


@require_POST
def delete_item(request, slug, item_id):
    event = get_object_or_404(Event, slug=slug)
    gate = _moderation_gate(request, event)
    if gate is not None:
        return gate

    get_object_or_404(MediaItem, event=event, id=item_id).delete()
    return redirect("gallery:gallery", slug=slug)


def guest_list(request, slug):
    event = get_object_or_404(Event, slug=slug)
    gate = _moderation_gate(request, event)
    if gate is not None:
        return gate

    guests = Guest.objects.filter(event=event).annotate(photo_count=Count("media_items")).order_by("-created_at")
    return render(request, "gallery/guest_list.html", {"event": event, "guests": guests})


@require_POST
def request_zip(request, slug):
    event = get_object_or_404(Event, slug=slug)
    gate = _owner_gate(request, event)
    if gate is not None:
        return gate

    export = ZipExport.objects.create(event=event)
    build_zip_export.delay(export.id)
    return redirect(f"{reverse('gallery:gallery', kwargs={'slug': slug})}?export={export.id}")


def zip_export_status(request, slug, export_id):
    event = get_object_or_404(Event, slug=slug)
    gate = _owner_gate(request, event)
    if gate is not None:
        return gate

    export = get_object_or_404(ZipExport, event=event, id=export_id)
    data = {"ready": export.is_ready}
    if export.is_ready:
        token = signing.TimestampSigner().sign(export.id)
        data["url"] = reverse("gallery:download_zip", kwargs={"slug": slug, "export_id": export.id, "token": token})
    return JsonResponse(data)


def download_zip(request, slug, export_id, token):
    event = get_object_or_404(Event, slug=slug)
    # The signature proves the URL was minted by us, not who is asking for it.
    # Without this gate anyone holding (or guessing) a link could pull the whole
    # album, and the slug is on every table card.
    gate = _owner_gate(request, event)
    if gate is not None:
        return gate

    export = get_object_or_404(ZipExport, event=event, id=export_id, is_ready=True)
    try:
        value = signing.TimestampSigner().unsign(token, max_age=DOWNLOAD_LINK_MAX_AGE)
    except signing.BadSignature:
        raise Http404
    if value != str(export.id):
        raise Http404

    response = HttpResponse()
    response["X-Accel-Redirect"] = f"/protected-media/{export.file.name}"
    response["Content-Disposition"] = f'attachment; filename="{event.slug}.zip"'
    return response
