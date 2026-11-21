"""Upload photos from the local media/ folder to Cloudinary and point the database at them.

Run this once, on your own computer, after your data is in the production database:

    set DATABASE_URL and CLOUDINARY_URL to the production values, then
    python manage.py move_media_to_cloud            (add --dry-run to only list what would happen)

Photos already on Cloudinary are skipped, so it is safe to run more than once.
"""
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from core.models import Announcement, Event, PhotoGallery, Post, User
from core.storage import FOLDER

FILE_FIELDS = [
    (User, 'profile_photo'),
    (Post, 'image'),
    (Event, 'cover_image'),
    (Announcement, 'image'),
    (PhotoGallery, 'image'),
]


class Command(BaseCommand):
    help = 'Copy local media files to Cloudinary and update the database to use them.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='List what would be uploaded, change nothing.')

    def handle(self, *args, dry_run=False, **options):
        if not settings.USE_CLOUDINARY:
            raise CommandError('CLOUDINARY_URL is not set, so photos would just stay on this computer. Set it first.')
        moved = skipped = missing = 0
        for model, field in FILE_FIELDS:
            for pk, name in model.objects.exclude(**{field: ''}).exclude(**{f'{field}__isnull': True}).values_list('pk', field):
                if name.startswith(f'{FOLDER}/'):
                    skipped += 1
                    continue
                local = Path(settings.MEDIA_ROOT) / name
                if not local.is_file():
                    missing += 1
                    self.stdout.write(self.style.WARNING(f'  missing on this computer: {name} ({model.__name__} {pk})'))
                    continue
                if dry_run:
                    self.stdout.write(f'  would upload {name}')
                    moved += 1
                    continue
                with local.open('rb') as handle:
                    new_name = default_storage.save(name, File(handle, name=local.name))
                # .update() skips save() signals, which would otherwise try to delete the "old" file.
                model.objects.filter(pk=pk).update(**{field: new_name})
                moved += 1
                self.stdout.write(f'  uploaded {name} -> {new_name}')
        verb = 'Would upload' if dry_run else 'Uploaded'
        self.stdout.write(self.style.SUCCESS(f'{verb} {moved}, already on Cloudinary {skipped}, missing locally {missing}.'))
