from django.contrib import admin

from .models import ZipExport


@admin.register(ZipExport)
class ZipExportAdmin(admin.ModelAdmin):
    list_display = ("event", "is_ready", "item_count", "requested_at", "ready_at")
    list_filter = ("event", "is_ready")
    readonly_fields = ("requested_at",)
