from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "event_at", "is_open", "gallery_shared")
    prepopulated_fields = {}
    readonly_fields = ("created_at", "moderator_token")
