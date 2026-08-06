"""In-memory caching utilities backed by ``cachetools``.

Provides a process-local TTL cache with thread-safe helpers used by the
event and venue routers to serve hot, shared read endpoints without
repeated database queries. Entries expire after 60 seconds and can be
evicted by key prefix when the underlying data changes.

Note:
    The cache is per-process: it is not shared across uvicorn workers or
    containers, and it is lost on restart.
"""
import threading

from cachetools import TTLCache

_cache = TTLCache(maxsize=512, ttl=60)
_lock = threading.RLock()


def cache_get(key: str):
    """Return the cached value for ``key``, or ``None`` on a miss.

    Args:
        key: Cache key (prefixed, e.g. ``"event:detail:3"``).

    Returns:
        The cached serialized payload, or ``None`` if absent or expired.
    """
    with _lock:
        return _cache.get(key)


def cache_set(key: str, value):
    """Store ``value`` under ``key`` with the cache's default TTL (60s).

    Args:
        key: Cache key to write.
        value: Serialized payload (JSON-serializable dict or list).
    """
    with _lock:
        _cache[key] = value


def invalidate(prefix: str):
    """Evict every cache entry whose key starts with ``prefix``.

    Args:
        prefix: Key prefix to purge, e.g. ``"event"`` or ``"venue"``.
    """
    with _lock:
        for key in [k for k in _cache if k.startswith(prefix)]:
            _cache.pop(key, None)
