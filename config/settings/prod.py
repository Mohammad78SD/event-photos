import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *  # noqa: F401,F403

DEBUG = False

# TLS terminates at the shared edge nginx on the host, not at our own nginx —
# trust the X-Forwarded-Proto it sets so is_secure()/CSRF's Origin check and
# SECURE_SSL_REDIRECT see the request as https. Our own nginx.prod.conf
# passes this header through unchanged rather than recomputing it.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

sentry_dsn = env("SENTRY_DSN", default="")  # noqa: F405
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
    )
