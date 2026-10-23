from django.db import migrations
from django.db.models import Count


def recount_likes(apps, schema_editor):
    """The old +1/-1 like counter drifted (some posts showed negative likes).
    Reset every post's likes_count to its real number of likes."""
    Post = apps.get_model('core', 'Post')
    for post in Post.objects.annotate(real=Count('likes')):
        if post.likes_count != post.real:
            Post.objects.filter(pk=post.pk).update(likes_count=post.real)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_chat_messaging_and_blocking'),
    ]

    operations = [
        migrations.RunPython(recount_likes, migrations.RunPython.noop),
    ]
