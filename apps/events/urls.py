from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("edit/", views.edit_event, name="edit"),
    path("table-card/", views.table_card, name="table_card"),
]
