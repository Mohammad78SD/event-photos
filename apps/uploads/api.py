import hashlib

import magic
from django.db import IntegrityError
from django.db.models import Sum
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.models import Event

from .models import MediaItem
from .session import get_guest
from .throttling import RateLimitExceeded, check_rate_limit

ALLOWED_IMAGE_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}


def _serialize(item):
    return {
        "id": item.id,
        "status": item.status,
        "url": item.file.url if item.file else None,
    }


class UploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request, slug):
        event = Event.objects.filter(slug=slug, is_open=True).first()
        if event is None:
            return Response({"detail": "رویداد یافت نشد."}, status=404)

        guest = get_guest(request, event)
        if guest is None:
            return Response({"detail": "نشست شما منقضی شده. دوباره وارد شوید."}, status=401)

        try:
            check_rate_limit(guest, request)
        except RateLimitExceeded:
            return Response({"detail": "تعداد درخواست‌ها زیاد است. کمی صبر کنید."}, status=429)

        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "فایلی ارسال نشده."}, status=400)

        max_bytes = event.max_file_mb * 1024 * 1024
        if upload.size > max_bytes:
            return Response(
                {"detail": f"حجم فایل بیشتر از {event.max_file_mb} مگابایت است."}, status=413
            )

        head = upload.read(2048)
        upload.seek(0)
        mime = magic.from_buffer(head, mime=True)
        if mime not in ALLOWED_IMAGE_MIMES:
            return Response({"detail": "فقط عکس پذیرفته می‌شود."}, status=415)

        hasher = hashlib.sha256()
        for chunk in upload.chunks():
            hasher.update(chunk)
        sha256 = hasher.hexdigest()
        upload.seek(0)

        # Never trust the client's length — Uppy sends this as a plain form field
        # alongside the file, so it arrives as ordinary (and unvalidated) text.
        caption = str(request.data.get("caption", "")).strip()[:280]

        existing = MediaItem.objects.filter(event=event, sha256=sha256).first()
        if existing is not None:
            # A retried upload of the same file shouldn't lose the words the guest
            # typed, but it also shouldn't clobber a caption that's already set.
            if caption and not existing.caption:
                existing.caption = caption
                existing.save(update_fields=["caption"])
            return Response(_serialize(existing), status=200)

        current_bytes = MediaItem.objects.filter(event=event).aggregate(total=Sum("size"))["total"] or 0
        quota_bytes = event.quota_gb * 1024 * 1024 * 1024
        if current_bytes + upload.size > quota_bytes:
            return Response({"detail": "ظرفیت رویداد پر شده."}, status=507)

        try:
            item = MediaItem.objects.create(
                event=event,
                guest=guest,
                file=upload,
                original_name=upload.name[:255],
                caption=caption,
                mime=mime,
                size=upload.size,
                sha256=sha256,
                status=MediaItem.STATUS_READY,
            )
        except IntegrityError:
            # Lost a race with a parallel retry of the same file.
            existing = MediaItem.objects.get(event=event, sha256=sha256)
            if caption and not existing.caption:
                existing.caption = caption
                existing.save(update_fields=["caption"])
            return Response(_serialize(existing), status=200)

        from .tasks import process_media_item

        process_media_item.delay(item.id)

        return Response(_serialize(item), status=201)
