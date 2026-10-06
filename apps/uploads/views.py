from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.events.models import Event

from .forms import GuestForm
from .models import Guest, MediaItem
from .session import get_guest, set_guest_cookie


def hello(request, slug):
    event = get_object_or_404(Event, slug=slug, is_open=True)

    guest = get_guest(request, event)
    if guest is not None:
        return redirect("uploads:upload", slug=slug)

    if request.method == "POST":
        form = GuestForm(request.POST)
        if form.is_valid():
            guest, _created = Guest.objects.get_or_create(
                event=event,
                phone=form.cleaned_data["phone"],
                defaults={
                    "name": form.cleaned_data["name"],
                    "message": form.cleaned_data["message"],
                    "ip": request.META.get("REMOTE_ADDR"),
                    "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
                },
            )
            response = redirect("uploads:upload", slug=slug)
            set_guest_cookie(response, event, guest)
            return response
    else:
        form = GuestForm()

    return render(request, "uploads/hello.html", {"event": event, "form": form})


def upload(request, slug):
    event = get_object_or_404(Event, slug=slug, is_open=True)
    guest = get_guest(request, event)
    if guest is None:
        return redirect("uploads:hello", slug=slug)

    return render(
        request,
        "uploads/upload.html",
        {
            "event": event,
            "guest": guest,
            "upload_url": reverse("uploads_api:upload", kwargs={"slug": slug}),
        },
    )


def done(request, slug):
    event = get_object_or_404(Event, slug=slug, is_open=True)
    guest = get_guest(request, event)
    if guest is None:
        return redirect("uploads:hello", slug=slug)

    items = MediaItem.objects.filter(event=event, guest=guest).order_by("-created_at")
    return render(request, "uploads/done.html", {"event": event, "guest": guest, "items": items})
