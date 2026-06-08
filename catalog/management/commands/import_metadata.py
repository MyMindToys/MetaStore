import csv
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from catalog.models import Device, FileResource, Project, Tag


class Command(BaseCommand):
    help = 'Import file metadata from a CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Path to the CSV file with metadata')

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        created_files = 0
        updated_files = 0

        try:
            with open(csv_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    project_name = row.get('project_name')
                    device_name = row.get('device_name')
                    device_type = row.get('device_type') or Device.DeviceType.OTHER
                    if not project_name or not device_name:
                        self.stdout.write(self.style.WARNING('Skipping row with missing project or device'))
                        continue

                    project, _ = Project.objects.get_or_create(name=project_name)
                    device, _ = Device.objects.get_or_create(
                        name=device_name,
                        device_type=device_type if device_type in dict(Device.DeviceType.choices) else Device.DeviceType.OTHER,
                    )

                    fr_values = {
                        'extension': row.get('extension', ''),
                        'size_bytes': self.parse_int(row.get('size_bytes')),
                        'created_at_fs': self.parse_datetime(row.get('created_at_fs')),
                        'updated_at_fs': self.parse_datetime(row.get('updated_at_fs')),
                        'checksum': row.get('checksum', ''),
                        'description': row.get('description', ''),
                    }

                    file_resource, created = FileResource.objects.update_or_create(
                        project=project,
                        device=device,
                        relative_path=row.get('relative_path', ''),
                        file_name=row.get('file_name', ''),
                        defaults=fr_values,
                    )

                    tag_names = [tag.strip() for tag in (row.get('tags') or '').split(',') if tag.strip()]
                    if tag_names:
                        tags = [Tag.objects.get_or_create(name=name)[0] for name in tag_names]
                        file_resource.tags.set(tags)
                    else:
                        file_resource.tags.clear()

                    if created:
                        created_files += 1
                    else:
                        updated_files += 1

            self.stdout.write(self.style.SUCCESS(f'Import completed: {created_files} created, {updated_files} updated'))
        except FileNotFoundError as exc:
            raise CommandError(f'File not found: {csv_path}') from exc

    def parse_datetime(self, value):
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        return timezone.make_aware(dt) if timezone.is_naive(dt) else dt

    def parse_int(self, value):
        try:
            return int(value) if value not in (None, '') else None
        except ValueError:
            return None
