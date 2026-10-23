from django import template
from django.utils import timezone
from django.utils.dateformat import format as format_date

register = template.Library()


@register.filter
def initials(name):
    """'Ashraful Islam' -> 'AI', 'jafor' -> 'J'."""
    parts = [p for p in str(name or '').split() if p[:1].isalpha()]
    if not parts:
        return '?'
    letters = parts[0][0] + (parts[-1][0] if len(parts) > 1 else '')
    return letters.upper()


@register.inclusion_tag('core/partials/avatar.html')
def avatar(user, size=48, ring=False, css=''):
    """Profile photo, or coloured initials when the member has no photo."""
    name = getattr(user, 'full_name', '') or ''
    photo = getattr(user, 'profile_photo', None)
    return {
        'name': name,
        'photo_url': photo.url if photo else '',
        'initials': initials(name),
        'size': size,
        'ring': ring,
        'css': css,
        # Stable colour per person so the same member always gets the same tint.
        'hue': sum(map(ord, name)) % 6,
    }


@register.filter
def ago(value):
    """Compact relative time: 'just now', '5m', '3h', '2d', then a date."""
    if not value:
        return ''
    seconds = (timezone.now() - value).total_seconds()
    if seconds < 60:
        return 'just now'
    if seconds < 3600:
        return f'{int(seconds // 60)}m'
    if seconds < 86400:
        return f'{int(seconds // 3600)}h'
    if seconds < 7 * 86400:
        return f'{int(seconds // 86400)}d'
    local = timezone.localtime(value)
    return format_date(local, 'M j' if local.year == timezone.localdate().year else 'M j, Y')


CATEGORY_TONES = {
    'Blood Request': 'danger',
    'Help Needed': 'gold',
    'Job Opportunity': 'success',
    'Tuition Offer': 'success',
    'Event': 'primary',
    'Success Story': 'gold',
    'Celebrations': 'gold',
    'Sports': 'primary',
}


@register.filter
def category_tone(category):
    """Chip colour for a post category."""
    return CATEGORY_TONES.get(category, '')


@register.simple_tag(takes_context=True)
def page_url(context, page):
    """Current query string with ?page= replaced, so filters survive pagination."""
    params = context['request'].GET.copy()
    params['page'] = page
    return '?' + params.urlencode()


@register.filter
def board(category):
    """Board metadata (slug, icon, blurb) for a post category."""
    from core.boards import board_for
    return board_for(category)



@register.filter
def tail(items, n):
    """Last n items of a (prefetched) queryset or list, which |slice can't do."""
    items = list(items)
    return items[-int(n):] if items else []
