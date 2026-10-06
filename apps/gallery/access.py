def _session_key(event):
    return f"moderator_{event.id}"


def is_event_owner(request, event):
    """True only for the logged-in couple who own this event.

    Strictly narrower than has_moderation_access: a helper holding the
    moderator link can approve and hide, but downloading the whole album is
    the owners' alone. The link is meant to be handed to someone for one
    evening, and it carries no password.
    """
    return request.user.is_authenticated and event.owner_id == request.user.id


def has_moderation_access(request, event):
    """True for the event's owner (logged in) or a browser that already used
    the moderator link (DECISIONS.md §3) for this event."""
    if is_event_owner(request, event):
        return True
    return request.session.get(_session_key(event)) is True


def grant_moderator_session(request, event):
    request.session[_session_key(event)] = True
