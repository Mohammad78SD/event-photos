import os
import uuid
import zipfile

from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone


@shared_task
def build_zip_export(export_id):
    from apps.uploads.models import MediaItem

    from .models import ZipExport

    export = ZipExport.objects.get(id=export_id)
    items = MediaItem.objects.filter(event=export.event).visible_to().order_by("guest__name", "created_at")

    tmp_path = f"/tmp/export-{uuid.uuid4()}.zip"
    seen_names = set()
    count = 0
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_STORED) as zf:
        for item in items:
            if not item.file:
                continue
            arcname = f"{item.guest.name}/{item.original_name}"
            # two guests uploading "IMG_001.jpg" shouldn't clobber each other in the zip
            base = arcname
            n = 1
            while arcname in seen_names:
                stem, ext = os.path.splitext(base)
                arcname = f"{stem} ({n}){ext}"
                n += 1
            seen_names.add(arcname)
            with item.file.open("rb") as fh:
                zf.writestr(arcname, fh.read())
            count += 1

    with open(tmp_path, "rb") as fh:
        export.file.save(f"{export.event.slug}.zip", ContentFile(fh.read()), save=False)
    os.remove(tmp_path)

    export.item_count = count
    export.is_ready = True
    export.ready_at = timezone.now()
    export.save(update_fields=["file", "item_count", "is_ready", "ready_at"])
