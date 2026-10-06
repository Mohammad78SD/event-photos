import secrets
import uuid

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone


def _session_token():
    return secrets.token_urlsafe(32)


def guest_upload_path(instance, filename):
    # instance.created_at isn't populated yet at this point (auto_now_add runs
    # later in Model.save()), so bucket by the actual upload moment instead.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    name = f"{uuid.uuid4()}.{ext}" if ext else str(uuid.uuid4())
    month = timezone.now().strftime("%Y-%m")
    return f"events/{instance.event_id}/{month}/{name}"


class Guest(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="guests")
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=11)
    message = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    session_token = models.CharField(max_length=64, unique=True, default=_session_token)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("event", "phone")]

    def __str__(self):
        return f"{self.name} ({self.phone})"


class MediaItemQuerySet(models.QuerySet):
    def visible_to(self, guest=None):
        """Publicly-visible items, plus the given guest's own items regardless of status."""
        # An item clears the approval gate if the event doesn't require approval at
        # all, or if the guest who posted it has been approved. Either way it still
        # needs to not be hidden and the event's gallery still needs to be shared.
        public = (
            models.Q(event__require_approval=False) | models.Q(guest__is_approved=True)
        ) & models.Q(is_hidden=False, event__gallery_shared=True)
        if guest is not None:
            public |= models.Q(guest=guest)
        return self.filter(public)


class MediaItem(models.Model):
    STATUS_UPLOADING = "uploading"
    STATUS_READY = "ready"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_UPLOADING, "uploading"),
        (STATUS_READY, "ready"),
        (STATUS_FAILED, "failed"),
    ]

    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="media_items")
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name="media_items")
    file = models.FileField(upload_to=guest_upload_path)
    thumb = models.ImageField(upload_to=guest_upload_path, blank=True, null=True)
    preview = models.ImageField(upload_to=guest_upload_path, blank=True, null=True)
    original_name = models.CharField(max_length=255)
    caption = models.TextField(blank=True, default="", max_length=280)
    mime = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    is_hidden = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_UPLOADING)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MediaItemQuerySet.as_manager()

    class Meta:
        unique_together = [("event", "sha256")]

    def __str__(self):
        return self.original_name


@receiver(post_delete, sender=MediaItem)
def _delete_media_files(sender, instance, **kwargs):
    # A rejected guest's files shouldn't linger on disk forever (they were
    # never public). Runs for cascaded Guest deletes too — Django's collector
    # fires post_delete per instance either way.
    for field in (instance.file, instance.thumb, instance.preview):
        if field:
            field.storage.delete(field.name)
