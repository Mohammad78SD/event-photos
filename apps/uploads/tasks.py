import io
from datetime import datetime

import pillow_heif
from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import ExifTags, Image, ImageOps

pillow_heif.register_heif_opener()

THUMB_SIZE = (400, 400)
PREVIEW_SIZE = (1600, 1600)

_DATETIME_ORIGINAL_TAG = next(
    (tag for tag, name in ExifTags.TAGS.items() if name == "DateTimeOriginal"), None
)


def _extract_taken_at(image):
    exif = image.getexif()
    if not exif or _DATETIME_ORIGINAL_TAG not in exif:
        return None
    raw = exif.get(_DATETIME_ORIGINAL_TAG)
    try:
        naive = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    return timezone.make_aware(naive, timezone.get_default_timezone())


def _resized_webp(image, size):
    # .save(..., "WEBP") never copies EXIF unless passed explicitly, so these
    # derivatives carry no GPS (or any other EXIF) by construction. The original
    # file on disk is never touched — see CLAUDE.md constraint #1.
    resized = image.copy()
    resized.thumbnail(size, Image.LANCZOS)
    buf = io.BytesIO()
    resized.convert("RGB").save(buf, format="WEBP", quality=82)
    return ContentFile(buf.getvalue())


@shared_task
def process_media_item(media_item_id):
    from .models import MediaItem

    item = MediaItem.objects.get(id=media_item_id)

    with item.file.open("rb") as fh:
        image = Image.open(fh)
        image = ImageOps.exif_transpose(image)  # bake in rotation before anything else
        item.taken_at = _extract_taken_at(image)
        item.width, item.height = image.size

        thumb = _resized_webp(image, THUMB_SIZE)
        preview = _resized_webp(image, PREVIEW_SIZE)

    item.thumb.save(f"{item.id}_thumb.webp", thumb, save=False)
    item.preview.save(f"{item.id}_preview.webp", preview, save=False)
    item.save(update_fields=["width", "height", "taken_at", "thumb", "preview"])
