from django.urls import path

from . import views

app_name = "gallery"

urlpatterns = [
    path("gallery/", views.gallery, name="gallery"),
    path("live/", views.live, name="live"),
    path("live/feed/", views.live_feed, name="live_feed"),
    path("moderate/<str:token>/", views.moderator_entry, name="moderator_entry"),
    path("moderation/", views.moderation_queue, name="moderation_queue"),
    path("moderation/<int:guest_id>/approve/", views.approve_guest, name="approve_guest"),
    path("moderation/<int:guest_id>/reject/", views.reject_guest, name="reject_guest"),
    path("moderation/toggle-shared/", views.toggle_gallery_shared, name="toggle_gallery_shared"),
    path("gallery/<int:item_id>/hide/", views.hide_item, name="hide_item"),
    path("gallery/<int:item_id>/delete/", views.delete_item, name="delete_item"),
    path("guests/", views.guest_list, name="guest_list"),
    path("export/", views.request_zip, name="request_zip"),
    path("export/<int:export_id>/status/", views.zip_export_status, name="zip_export_status"),
    path("export/<int:export_id>/download/<str:token>/", views.download_zip, name="download_zip"),
]
