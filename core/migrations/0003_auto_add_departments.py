from django.db import migrations


def create_default_departments(apps, schema_editor):
    Department = apps.get_model('core', 'Department')
    department_names = [
        'CSE',
        'EEE',
        'ME',
        'CE',
        'ETE',
        'BME',
        'MME',
        'PME',
        'IPE',
        'ChE',
        'FET',
        'URP',
        'Other',
    ]
    for name in department_names:
        Department.objects.get_or_create(name=name)


def reverse_default_departments(apps, schema_editor):
    Department = apps.get_model('core', 'Department')
    department_names = [
        'CSE',
        'EEE',
        'ME',
        'CE',
        'ETE',
        'BME',
        'MME',
        'PME',
        'IPE',
        'ChE',
        'FET',
        'URP',
        'Other',
    ]
    Department.objects.filter(name__in=department_names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_user_batch'),
    ]

    operations = [
        migrations.RunPython(create_default_departments, reverse_default_departments),
    ]
