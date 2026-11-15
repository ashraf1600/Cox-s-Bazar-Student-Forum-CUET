"""Upload checks and resizing for photos members add.

Phone cameras produce 5-12 MB images; storing them as-is fills the disk and makes the
forum slow on mobile data. Every upload is size-checked, rotated upright using its EXIF
data, shrunk to a sensible maximum and re-encoded.
"""
from io import BytesIO

from django import forms
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_MB = 10
POST_MAX_SIDE = 1600
AVATAR_MAX_SIDE = 640
GALLERY_MAX_SIDE = 2000
COVER_MAX_SIDE = 1800


def prepare_image(upload, max_side):
    """Validate an uploaded image and return a resized copy (or the original if it's already small)."""
    if not upload or not hasattr(upload, 'size'):
        return upload  # no new file (e.g. existing image left unchanged)
    if upload.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise forms.ValidationError(f'That image is larger than {MAX_UPLOAD_MB} MB. Choose a smaller one.')
    try:
        upload.seek(0)
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise forms.ValidationError('That file is not an image we can read. Use a JPG, PNG or WebP.')

    if getattr(image, 'is_animated', False):
        upload.seek(0)
        return upload  # keep animated GIFs as they are

    image = ImageOps.exif_transpose(image)
    has_alpha = image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info)
    small_enough = max(image.size) <= max_side and upload.size <= 400 * 1024
    if small_enough and image.format in ('JPEG', 'PNG', 'WEBP'):
        upload.seek(0)
        return upload

    image.thumbnail((max_side, max_side), Image.LANCZOS)
    buffer = BytesIO()
    if has_alpha:
        image.save(buffer, format='PNG', optimize=True)
        extension, content_type = 'png', 'image/png'
    else:
        image.convert('RGB').save(buffer, format='JPEG', quality=84, optimize=True, progressive=True)
        extension, content_type = 'jpg', 'image/jpeg'
    buffer.seek(0)
    stem = (upload.name.rsplit('.', 1)[0] or 'photo')[:60]
    return InMemoryUploadedFile(buffer, getattr(upload, 'field_name', None), f'{stem}.{extension}',
                                content_type, buffer.getbuffer().nbytes, None)
