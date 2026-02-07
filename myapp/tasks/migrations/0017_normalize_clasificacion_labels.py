from django.db import migrations


def normalize_labels(apps, schema_editor):
    Clasificacion = apps.get_model('tasks', 'Clasificacion')
    for c in Clasificacion.objects.all():
        label = (c.label or '').strip()
        if not label:
            continue
        if '-' in label:
            # tomar la parte derecha después del primer guion
            new_label = label.split('-', 1)[1].strip()
            if new_label and new_label != label:
                c.label = new_label
                c.save(update_fields=['label'])


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0016_delete_materia'),
    ]

    operations = [
        migrations.RunPython(normalize_labels, reverse_code=migrations.RunPython.noop),
    ]
