import re

from django.core.exceptions import ValidationError

# Accepts 09121234567, +989121234567, 00989121234567, or with spaces/dashes.
_DIGITS_RE = re.compile(r"\D")


def normalize_iranian_mobile(raw: str) -> str:
    """Normalise an Iranian mobile number to the 09xxxxxxxxx form.

    Raises ValidationError if it can't be recognised as one.
    """
    digits = _DIGITS_RE.sub("", raw or "")

    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98"):
        digits = digits[2:]

    if digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits

    if not re.fullmatch(r"09\d{9}", digits):
        raise ValidationError("شماره موبایل معتبر نیست.")

    return digits
