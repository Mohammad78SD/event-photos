import functools
import hashlib

import jdatetime
from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils import timezone

register = template.Library()

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


@register.filter
def jalali(value):
    """'1405/01/01' — Latin numerals in display type, per docs/DESIGN.md copy rules."""
    if value is None:
        return ""
    local = timezone.localtime(value)
    j = jdatetime.date.fromgregorian(date=local.date())
    return f"{j.year}/{j.month:02d}/{j.day:02d}"


@functools.lru_cache(maxsize=32)
def _asset_digest(path):
    """Short content hash of a static file, or '' if it can't be read."""
    found = finders.find(path)
    if not found:
        return ""
    try:
        with open(found, "rb") as fh:
            return hashlib.md5(fh.read()).hexdigest()[:8]
    except OSError:
        return ""


@register.simple_tag
def static_v(path):
    """`static`, plus a content hash query string.

    nginx sets no explicit Cache-Control on /static/, so browsers cache
    heuristically and a guest who opened the link yesterday can keep the old
    CSS after a deploy. Changing headers does not help — a copy already in
    someone's cache is only displaced by a different URL. The hash changes
    exactly when the file's bytes change, so a deploy busts the cache and an
    unchanged asset still gets a free 304. Computed once per process; the
    container is replaced on every deploy, so the cache can't go stale.
    """
    url = static(path)
    digest = _asset_digest(path)
    return f"{url}?v={digest}" if digest else url


@register.filter
def persian_digits(value):
    """Persian digits for counts inside Persian body text (۱۲ عکس), per
    docs/DESIGN.md's numeral rule — display-type numerals stay Latin."""
    return str(value).translate(_PERSIAN_DIGITS)
