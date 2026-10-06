from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.events import views as events_views
from apps.uploads.media import serve_media

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("dashboard/", events_views.dashboard, name="dashboard"),
    path("create/", events_views.create_event, name="create"),
    path("api/e/<slug:slug>/", include("apps.uploads.api_urls")),
    path("e/<slug:slug>/", include("apps.uploads.urls")),
    path("e/<slug:slug>/", include("apps.gallery.urls")),
    path("e/<slug:slug>/", include("apps.events.urls")),
    # Access-controlled — served for real by nginx via X-Accel-Redirect, same
    # in dev and prod. Not gated by DEBUG: there is no path under MEDIA_URL
    # that should ever bypass the visibility check.
    path(settings.MEDIA_URL.lstrip("/") + "<path:path>", serve_media, name="media"),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]

handler404 = "config.views.page_not_found"
handler500 = "config.views.server_error"
