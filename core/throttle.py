"""Small cache-backed rate limiter.

Keeps spam and password guessing in check without an extra dependency. Counts live in
Django's cache, so with several server processes each one counts separately; the limits
are therefore approximate, which is fine for abuse control.
"""
from functools import wraps

from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR', 'unknown')


def over_limit(key, limit, window):
    """Record one hit for `key`; True once there are more than `limit` hits in `window` seconds."""
    key = f'throttle:{key}'
    if cache.add(key, 1, timeout=window):
        return False
    try:
        return cache.incr(key) > limit
    except ValueError:  # expired between add() and incr()
        cache.set(key, 1, timeout=window)
        return False


def hits(key):
    return cache.get(f'throttle:{key}', 0)


def clear(key):
    cache.delete(f'throttle:{key}')


def rate_limit(scope, limit, window, message='You are doing that too often. Wait a minute and try again.'):
    """Limit POSTs to a view per signed-in user (or per IP for visitors)."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.method == 'POST':
                who = f'u{request.user.pk}' if request.user.is_authenticated else f'ip{client_ip(request)}'
                if over_limit(f'{scope}:{who}', limit, window):
                    wants_json = (request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                                  or 'application/json' in request.headers.get('Accept', ''))
                    if wants_json:
                        return JsonResponse({'success': False, 'error': message}, status=429)
                    messages.error(request, message)
                    return redirect(request.META.get('HTTP_REFERER') or '/')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
