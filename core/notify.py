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
