from django.urls import path

from .api import UploadView

app_name = "uploads_api"

urlpatterns = [
    path("upload/", UploadView.as_view(), name="upload"),
]
