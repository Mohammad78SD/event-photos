import redis
from django.conf import settings

RATE_LIMIT_PER_GUEST_PER_MINUTE = 150  # above max_files_batch (100) so a full batch plus retries never trips it
RATE_LIMIT_PER_IP_PER_MINUTE = 600  # a venue full of guests shares one NAT IP


class RateLimitExceeded(Exception):
    pass


def _client():
    return redis.from_url(settings.REDIS_URL)


def _hit(key, limit, window=60):
    client = _client()
    count = client.incr(key)
    if count == 1:
        client.expire(key, window)
    if count > limit:
        raise RateLimitExceeded


def check_rate_limit(guest, request):
    _hit(f"rl:guest:{guest.id}", RATE_LIMIT_PER_GUEST_PER_MINUTE)
    ip = request.META.get("REMOTE_ADDR") or "unknown"
    _hit(f"rl:ip:{ip}", RATE_LIMIT_PER_IP_PER_MINUTE)
