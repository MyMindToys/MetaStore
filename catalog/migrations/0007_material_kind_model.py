import django.db.models.deletion
from django.db import migrations, models


def seed_material_kinds(apps, schema_editor):
    MaterialKind = apps.get_model('catalog', 'MaterialKind')
    seed = [
        ('generic', 'Обычная запись каталога', False, 0),
        ('literature_list', 'Список литературы', True, 10),
        ('bibliography', 'Библиография', True, 20),
        ('reading_list', 'Список для чтения', True, 30),
        ('article_collection', 'Подборка статей', True, 40),
        ('research_material', 'Исследовательские материалы', True, 50),
    ]
    for code, name, is_lit, order in seed:
        MaterialKind.objects.update_or_create(
            code=code,
            defaults={'name': name, 'is_literature': is_lit, 'sort_order': order},
        )


def copy_char_kind_to_fk(apps, schema_editor):
    Material = apps.get_model('catalog', 'Material')
    MaterialKind = apps.get_model('catalog', 'MaterialKind')
    code_to_id = {k.code: k.pk for k in MaterialKind.objects.all()}
    generic_id = code_to_id['generic']
    for m in Material.objects.all():
        code = m.material_kind
        fk_id = code_to_id.get(code, generic_id)
        Material.objects.filter(pk=m.pk).update(material_kind_ref_id=fk_id)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_material_source_path'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaterialKind',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(db_index=True, max_length=32, unique=True)),
                ('name', models.CharField(max_length=128)),
                ('is_literature', models.BooleanField(default=False)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Тип материала',
                'verbose_name_plural': 'Типы материалов',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.RunPython(seed_material_kinds, noop_reverse),
        migrations.AddField(
            model_name='material',
            name='material_kind_ref',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='catalog.materialkind',
            ),
        ),
        migrations.RunPython(copy_char_kind_to_fk, noop_reverse),
        migrations.RemoveField(
            model_name='material',
            name='material_kind',
        ),
        migrations.RenameField(
            model_name='material',
            old_name='material_kind_ref',
            new_name='material_kind',
        ),
        migrations.AlterField(
            model_name='material',
            name='material_kind',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='materials',
                to='catalog.materialkind',
            ),
        ),
    ]
