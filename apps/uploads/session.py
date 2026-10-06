from django.core import signing

from .models import Guest

COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # a year — the album lives for months, cookie should outlive it


def _cookie_name(event):
    return f"guest_{event.slug}"


def get_guest(request, event):
    """Return the Guest for this browser+event, or None."""
    raw = request.COOKIES.get(_cookie_name(event))
    if not raw:
        return None
    try:
        token = signing.loads(raw, max_age=COOKIE_MAX_AGE)
    except signing.BadSignature:
        return None
    return Guest.objects.filter(event=event, session_token=token).first()


def set_guest_cookie(response, event, guest):
    signed = signing.dumps(guest.session_token)
    response.set_cookie(
        _cookie_name(event),
        signed,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
    )
