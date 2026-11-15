from .models import Message, Notification, Report, User


def unread_count(request):
    """Badge counts shown in the top bar on every page."""
    user = request.user
    if not user.is_authenticated:
        return {'unread_count': 0, 'notification_count': 0, 'moderation_count': 0}
    counts = {
        'unread_count': Message.objects.filter(recipient=user, is_read=False).count(),
        'notification_count': Notification.objects.filter(recipient=user, is_read=False).count(),
        'moderation_count': 0,
    }
    if user.is_site_admin:
        counts['moderation_count'] = (
            User.objects.filter(status='pending').count() + Report.objects.filter(is_resolved=False).count()
        )
    return counts
