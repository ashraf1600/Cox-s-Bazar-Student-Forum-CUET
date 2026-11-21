"""Make sure the site has an admin account, using environment variables.

A fresh production database starts empty, so nobody could log in to approve members.
Set these on the host and this runs on every deploy (see build.sh):

    DJANGO_ADMIN_EMAIL      your email (required)
    DJANGO_ADMIN_PASSWORD   used only when the account is first created
    DJANGO_ADMIN_NAME       optional, defaults to "CSF Admin"

If the account already exists it is left alone, except that it is made sure to be an
active superuser. Without DJANGO_ADMIN_EMAIL the command does nothing.
"""
import os

from django.core.management.base import BaseCommand, CommandError

from core.models import User


class Command(BaseCommand):
    help = 'Create (or repair) the admin account named in DJANGO_ADMIN_EMAIL.'

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_ADMIN_EMAIL', '').strip().lower()
        if not email:
            self.stdout.write('ensure_admin: DJANGO_ADMIN_EMAIL is not set, skipping.')
            return
        user = User.objects.filter(email__iexact=email).first()
        if user:
            changed = []
            for field, value in (('is_superuser', True), ('is_staff', True), ('status', 'active'), ('role', 'admin')):
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed.append(field)
            if changed:
                user.save()
            self.stdout.write(f'ensure_admin: {email} exists{" (fixed: " + ", ".join(changed) + ")" if changed else ""}.')
            return
        password = os.environ.get('DJANGO_ADMIN_PASSWORD', '')
        if len(password) < 10:
            raise CommandError('ensure_admin: set DJANGO_ADMIN_PASSWORD (at least 10 characters) to create the admin account.')
        User.objects.create_superuser(
            email=email, full_name=os.environ.get('DJANGO_ADMIN_NAME', 'CSF Admin'), password=password, role='admin',
        )
        self.stdout.write(self.style.SUCCESS(f'ensure_admin: created admin account {email}.'))
