import datetime
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

# How long an event stays "during" after event_at, for landing-page copy.
# The couple's evening runs a few hours; give it slack past midnight.
DURING_WINDOW = datetime.timedelta(hours=12)


def _moderator_token():
    return secrets.token_urlsafe(24)


class Event(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events")
    slug = models.SlugField(unique=True, max_length=64)
    title = models.CharField(max_length=255)
    names_latin = models.CharField(max_length=255, help_text="e.g. 'Sara|Ali'")
    event_at = models.DateTimeField()
    cover_image = models.ImageField(upload_to="covers/", blank=True, null=True)
    welcome_text = models.TextField(blank=True)
    is_open = models.BooleanField(default=True)
    gallery_shared = models.BooleanField(default=True)
    require_approval = models.BooleanField(default=True)
    require_otp = models.BooleanField(default=False)
    max_file_mb = models.PositiveIntegerField(default=25)
    max_files_batch = models.PositiveIntegerField(default=100)
    quota_gb = models.PositiveIntegerField(default=50)
    # Unguessable link a helper uses to moderate without a login (DECISIONS.md §3):
    # the couple won't be at a laptop approving guests during their own عقد.
    moderator_token = models.CharField(max_length=64, unique=True, default=_moderator_token)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def phase(self):
        """'before' | 'during' | 'after' — drives landing page copy."""
        now = timezone.now()
        if now < self.event_at:
            return "before"
        if now < self.event_at + DURING_WINDOW:
            return "during"
        return "after"

    @property
    def names(self):
        return self.names_latin.split("|")
