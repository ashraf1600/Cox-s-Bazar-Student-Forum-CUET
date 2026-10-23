from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import User, Post, Event, Announcement, PhotoGallery

# Model -> name of its file field. Files are removed from storage when the row is
# deleted or when the file is replaced, so uploads don't pile up on disk.
FILE_FIELDS = {
    User: 'profile_photo',
    Post: 'image',
    Event: 'cover_image',
    Announcement: 'image',
    PhotoGallery: 'image',
}


def _delete_file(file_field):
    if file_field and file_field.name:
        file_field.storage.delete(file_field.name)


def _on_delete(sender, instance, **kwargs):
    _delete_file(getattr(instance, FILE_FIELDS[sender]))


def _on_replace(sender, instance, **kwargs):
    if not instance.pk:
        return
    field = FILE_FIELDS[sender]
    old = sender.objects.filter(pk=instance.pk).values_list(field, flat=True).first()
    new = getattr(instance, field)
    if old and old != (new.name if new else None):
        getattr(sender, field).field.storage.delete(old)


for model in FILE_FIELDS:
    receiver(post_delete, sender=model, weak=False)(_on_delete)
    receiver(pre_save, sender=model, weak=False)(_on_replace)
