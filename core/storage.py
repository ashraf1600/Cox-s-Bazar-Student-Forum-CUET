"""Photo storage on Cloudinary, used when CLOUDINARY_URL is set.

Free hosts like Render wipe the server's disk on every deploy, restart and idle spin-down,
so uploaded photos must live somewhere else. This stores them on Cloudinary (free plan,
no card needed) and serves them from its CDN. Without CLOUDINARY_URL the site keeps using
the local media/ folder, which is what you want on your own computer.

The name saved in the database is "<public_id>.<format>", e.g. "csf/post_images/x_ab12.jpg",
so a URL can be rebuilt without asking Cloudinary.
"""
import os
import secrets

import cloudinary
import cloudinary.uploader
import cloudinary.api
import cloudinary.utils
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

FOLDER = os.environ.get('CLOUDINARY_FOLDER', 'csf').strip('/')


def _split(name):
    """'csf/post_images/x.jpg' -> ('csf/post_images/x', 'jpg')"""
    stem, dot, ext = name.rpartition('.')
    return (stem, ext) if dot else (name, '')


@deconstructible
class CloudinaryMediaStorage(Storage):
    def _save(self, name, content):
        stem, _ext = _split(name.replace('\\', '/'))
        # A short random suffix keeps two uploads called "photo.jpg" from replacing each other.
        public_id = f"{FOLDER}/{stem}_{secrets.token_hex(3)}"
        content.seek(0)
        result = cloudinary.uploader.upload(
            content, public_id=public_id, resource_type='image', overwrite=False, unique_filename=False,
        )
        return f"{result['public_id']}.{result['format']}"

    def url(self, name):
        if not name:
            return ''
        public_id, ext = _split(name)
        return cloudinary.utils.cloudinary_url(public_id, format=ext or None, secure=True, resource_type='image')[0]

    def delete(self, name):
        if name:
            public_id, _ext = _split(name)
            cloudinary.uploader.destroy(public_id, resource_type='image', invalidate=True)

    def exists(self, name):
        # Names are made unique in _save(), so there is never a clash to avoid.
        return False

    def size(self, name):
        public_id, _ext = _split(name)
        return cloudinary.api.resource(public_id, resource_type='image').get('bytes', 0)

    def path(self, name):
        raise NotImplementedError('Photos on Cloudinary have no local path; use .url instead.')


def cloudinary_configured():
    return bool(os.environ.get('CLOUDINARY_URL', '').strip())
