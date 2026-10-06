from django.contrib import admin

from .models import Guest, MediaItem


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "event", "is_approved", "created_at")
    list_filter = ("event", "is_approved")
    search_fields = ("name", "phone")
    readonly_fields = ("session_token", "created_at")


@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ("original_name", "guest", "event", "status", "is_hidden", "created_at")
    list_filter = ("event", "status", "is_hidden")
    readonly_fields = ("sha256", "created_at")
