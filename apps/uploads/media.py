from django.db.models import Q
from django.http import Http404, HttpResponse

from apps.events.models import Event
from apps.gallery.access import has_moderation_access

from .models import MediaItem
from .session import get_guest


def _accel_redirect(path):
    response = HttpResponse()
    response["X-Accel-Redirect"] = f"/protected-media/{path}"
    return response


def serve_media(request, path):
    """Gate every file under MEDIA_URL behind the same visibility rule as the
    gallery, then hand the actual bytes to nginx via X-Accel-Redirect — Django
    never reads the file. See CLAUDE.md: "never stream media through Django".

    Event.cover_image is the exception: it's the couple's own hero/OG image,
    meant to be publicly fetchable (Telegram/WhatsApp link previews included),
    not guest-uploaded content, so it's never gated."""
    if Event.objects.filter(cover_image=path).exists():
        return _accel_redirect(path)

    item = (
        MediaItem.objects.select_related("event", "guest")
        .filter(Q(file=path) | Q(thumb=path) | Q(preview=path))
        .first()
    )
    if item is None:
        raise Http404

    event = item.event
    guest = get_guest(request, event)
    allowed = has_moderation_access(request, event) or MediaItem.objects.visible_to(guest).filter(
        pk=item.pk
    ).exists()
    if not allowed:
        raise Http404

    return _accel_redirect(path)
