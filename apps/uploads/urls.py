from django.urls import path

from . import views

app_name = "uploads"

urlpatterns = [
    path("hello/", views.hello, name="hello"),
    path("upload/", views.upload, name="upload"),
    path("done/", views.done, name="done"),
]
