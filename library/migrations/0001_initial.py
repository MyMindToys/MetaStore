from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='BibliographicTag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=150, unique=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='BibliographicRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=500)),
                ('authors', models.CharField(blank=True, max_length=500)),
                ('publication_year', models.PositiveIntegerField(blank=True, null=True)),
                ('source', models.CharField(blank=True, max_length=255)),
                ('abstract', models.TextField(blank=True)),
                ('content', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tags', models.ManyToManyField(blank=True, related_name='records', to='library.bibliographictag')),
            ],
            options={'ordering': ['title']},
        ),
        migrations.AddIndex(
            model_name='bibliographicrecord',
            index=models.Index(fields=['title'], name='library_rec_record_t_67e004_idx'),
        ),
        migrations.AddIndex(
            model_name='bibliographicrecord',
            index=models.Index(fields=['authors'], name='library_rec_authors__463dd6_idx'),
        ),
    ]
