from django.db import models


class ZipExport(models.Model):
    """A couple's-side "download everything" build. Made async by Celery because
    streaming a live zip of the whole album through Gunicorn is not an option."""

    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="zip_exports")
    file = models.FileField(upload_to="exports/", blank=True, null=True)
    is_ready = models.BooleanField(default=False)
    item_count = models.PositiveIntegerField(default=0)
    requested_at = models.DateTimeField(auto_now_add=True)
    ready_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"export {self.id} for {self.event.slug}"
