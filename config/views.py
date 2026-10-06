from django.conf import settings
from django.shortcuts import render


def page_not_found(request, exception):
    return render(request, "404.html", {"support_phone": settings.SUPPORT_PHONE}, status=404)


def server_error(request):
    return render(request, "500.html", {"support_phone": settings.SUPPORT_PHONE}, status=500)
