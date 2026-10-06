import secrets

import segno
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import EventForm
from .models import Event

# One line for every phase, by the couple's choice. It used to switch on
# Event.phase (before/during/after) but they wanted this sentence from now on —
# it's the one that tells a guest why they're here, which is just as true in
# November as it is on the night. Event.phase is left in place, currently unused.
WELCOME_LINE = "عکسای قشنگ مراسم‌مون رو باهامون به اشتراک بذارین."


@login_required
def dashboard(request):
    events = Event.objects.filter(owner=request.user).order_by("-event_at")
    return render(request, "events/dashboard.html", {"events": events})


def landing(request, slug):
    event = get_object_or_404(Event, slug=slug, is_open=True)
    return render(
        request,
        "events/landing.html",
        {
            "event": event,
            "headline": WELCOME_LINE,
        },
    )


@login_required
def create_event(request):
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.owner = request.user
            event.slug = secrets.token_urlsafe(24)
            event.save()
            return redirect("dashboard")
    else:
        form = EventForm()

    return render(request, "events/create_event.html", {"form": form})


@login_required
def edit_event(request, slug):
    """Edit an existing event. The slug is captured from the URL (e/<slug>/).
    Only the event owner can edit it."""
    event = get_object_or_404(Event, slug=slug)
    # Only the owner can edit
    if event.owner_id != request.user.id:
        raise Http404

    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            return redirect("dashboard")
    else:
        form = EventForm(instance=event)

    return render(request, "events/edit_event.html", {"form": form, "event": event})


@login_required
def table_card(request, slug):
    """Display a printable A6 table card with event QR code.
    Only the event owner can view/print it."""
    event = get_object_or_404(Event, slug=slug)
    # Only the owner can view/print the table card
    if event.owner_id != request.user.id:
        raise Http404

    # Generate QR code for the event's landing page
    event_url = f"{request.scheme}://{request.get_host()}{reverse('events:landing', kwargs={'slug': event.slug})}"
    qr = segno.make(event_url, micro=False)
    qr_svg = qr.svg_data_uri()

    return render(
        request,
        "events/table_card.html",
        {
            "event": event,
            "qr_svg": qr_svg,
            "event_url": event_url,
        },
    )
