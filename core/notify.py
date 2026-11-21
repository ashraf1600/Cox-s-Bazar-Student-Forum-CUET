"""Emails the forum sends to members."""
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


def notify_approved(request, user):
    login_url = request.build_absolute_uri(reverse('core:login'))
    send_mail(
        subject='Your CSF-CUET membership has been approved',
        message=(
            f"Hi {user.full_name},\n\n"
            f"Your Cox's Bazar Student Forum (CUET) account has been approved.\n"
            f"Your member serial number is {user.serial_no}.\n\n"
            f"You can now log in: {login_url}\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


def email_reply_alerts(request, comment, recipients):
    """Email members who opted in that someone replied in a topic they follow."""
    thread_url = request.build_absolute_uri(reverse('core:post_detail', args=[comment.post_id])) + f'#reply-{comment.id}'
    settings_url = request.build_absolute_uri(reverse('core:update_profile'))
    topic = ' '.join(comment.post.content.split())[:80]
    reply = ' '.join(comment.content.split())[:300]
    for user in recipients:
        if not user.email_on_reply or not user.email:
            continue
        whose = 'your topic' if comment.post.user_id == user.id else 'a topic you joined'
        send_mail(
            subject=f'{comment.user.full_name} replied in {whose}',
            message=(
                f"Hi {user.full_name},\n\n"
                f"{comment.user.full_name} replied in {whose}:\n"
                f"  \"{topic}\"\n\n"
                f"{reply}\n\n"
                f"Read and reply: {thread_url}\n\n"
                f"You will not get another email about this topic until you open it.\n"
                f"To stop these emails, untick \"Email me about replies\": {settings_url}\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
