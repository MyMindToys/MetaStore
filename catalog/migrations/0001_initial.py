from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Device',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('device_type', models.CharField(choices=[('PC', 'PC'), ('Laptop', 'Laptop'), ('ExternalHDD', 'External HDD/SSD'), ('USB', 'USB Drive'), ('Other', 'Other')], default='Other', max_length=20)),
                ('comment', models.TextField(blank=True)),
            ],
            options={'ordering': ['name'], 'unique_together': {('name', 'device_type')}},
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=100, unique=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='FileResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('relative_path', models.CharField(max_length=1024)),
                ('file_name', models.CharField(max_length=255)),
                ('extension', models.CharField(max_length=50)),
                ('size_bytes', models.BigIntegerField(blank=True, null=True)),
                ('created_at_fs', models.DateTimeField(blank=True, null=True)),
                ('updated_at_fs', models.DateTimeField(blank=True, null=True)),
                ('checksum', models.CharField(blank=True, max_length=255)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='catalog.device')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='catalog.project')),
                ('tags', models.ManyToManyField(blank=True, related_name='files', to='catalog.tag')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='fileresource',
            index=models.Index(fields=['file_name'], name='catalog_fil_file_na_b4e4a1_idx'),
        ),
        migrations.AddIndex(
            model_name='fileresource',
            index=models.Index(fields=['extension'], name='catalog_fil_extensi_5b6c41_idx'),
        ),
        migrations.AddIndex(
            model_name='fileresource',
            index=models.Index(fields=['relative_path'], name='catalog_fil_relativ_ff3759_idx'),
        ),
    ]
