"""Print what is still missing before the site is safe to launch.

Runs at the end of every deploy (build.sh), so the answer is in the host's build log.
It never fails the deploy; it only reports.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from core.models import CommitteeMember, User


class Command(BaseCommand):
    help = 'Report launch readiness: database, photo storage, email, admins, committee.'

    def handle(self, *args, **options):
        rows = []

        def check(ok, label, fix):
            rows.append((ok, label, fix))

        vendor = connection.vendor
        check(not settings.DEBUG, 'Debug mode is off', 'Remove DJANGO_DEBUG or set it to False on the host.')
        check(vendor == 'postgresql', f'Database is PostgreSQL (now: {vendor})',
              'Set DATABASE_URL. With SQLite on a free host, all members and posts are erased on every restart.')
        check(settings.USE_CLOUDINARY or settings.SERVE_MEDIA, 'Uploaded photos are stored permanently',
              'Set CLOUDINARY_URL. Otherwise photos are erased on every restart.')
        check('smtp' in settings.EMAIL_BACKEND and bool(settings.EMAIL_HOST_USER),
              'Email is configured', 'Set DJANGO_EMAIL_BACKEND, EMAIL_HOST and the EMAIL_* values. Without it, '
              '"Forgot password", approval and reply emails are never delivered.')
        admins = User.objects.filter(status='active').filter(is_superuser=True).count() + \
            User.objects.filter(status='active', role='admin', is_superuser=False).count()
        check(admins > 0, f'There is an admin who can approve members ({admins})',
              'Set DJANGO_ADMIN_EMAIL and DJANGO_ADMIN_PASSWORD and deploy again.')
        sessions = sorted(set(CommitteeMember.objects.filter(is_current=True).values_list('session_year', flat=True)))
        check(len(sessions) <= 1, f'Only one committee session is current ({", ".join(sessions) or "none"})',
              'In Admin panel > Committee and admins, move old sessions to past. Their President, GS and AGS '
              'otherwise keep admin access.')

        self.stdout.write('\n== Launch check ==')
        for ok, label, fix in rows:
            mark = self.style.SUCCESS('OK  ') if ok else self.style.WARNING('TODO')
            self.stdout.write(f'{mark} {label}')
            if not ok:
                self.stdout.write(f'      -> {fix}')
        todo = sum(not ok for ok, _, _ in rows)
        self.stdout.write(self.style.SUCCESS('Ready to launch.') if not todo else self.style.WARNING(f'{todo} item(s) left. See DEPLOY.md.'))
