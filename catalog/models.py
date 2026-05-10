from django.db import models
from django.db.models import Q
from django.utils import timezone


class Project(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Device(models.Model):
    class DeviceType(models.TextChoices):
        PC = 'PC', 'ПК'
        LAPTOP = 'Laptop', 'Ноутбук'
        EXTERNAL_HDD = 'ExternalHDD', 'Внешний HDD/SSD'
        USB = 'USB', 'USB-накопитель'
        OTHER = 'Other', 'Другое'

    name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=20, choices=DeviceType.choices, default=DeviceType.OTHER)
    comment = models.TextField(blank=True)

    machine_uid = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    hostname = models.CharField(max_length=255, blank=True)
    os_name = models.CharField(max_length=64, blank=True)
    platform_name = models.TextField(blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    scanner_token = models.CharField(max_length=128, blank=True, null=True, unique=True)

    class Meta:
        ordering = ['name']
        unique_together = [('name', 'device_type')]
        constraints = [
            models.UniqueConstraint(
                fields=['machine_uid'],
                condition=Q(machine_uid__isnull=False) & ~Q(machine_uid=''),
                name='catalog_device_machine_uid_unique_nonnull',
            ),
        ]

    def __str__(self):
        return self.name


class StorageLocation(models.Model):
    """A rooted scan path reported by a scanner for a given device."""

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='storage_locations')
    name = models.CharField(max_length=255, blank=True)
    root_path = models.CharField(max_length=2048)

    class Meta:
        ordering = ['device_id', 'root_path']
        constraints = [
            models.UniqueConstraint(fields=['device', 'root_path'], name='catalog_storage_device_root_unique'),
        ]

    def __str__(self) -> str:
        return f'{self.device}: {self.root_path}'


class MaterialKind(models.Model):
    """Категория материала (как «тип литературы»): задаётся в справочнике, не захардкожена."""

    code = models.SlugField(
        max_length=32,
        unique=True,
        db_index=True,
        verbose_name='Код',
        help_text='Латиница и дефис; для ссылок (?kind=…) и API. Лучше не менять после создания.',
    )
    name = models.CharField(max_length=128, verbose_name='Название')
    is_literature = models.BooleanField(
        default=False,
        verbose_name='Раздел «литература»',
        help_text='Материалы этого типа попадают в поиск литературы и в общий список по умолчанию.',
    )
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок сортировки')

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Тип материала'
        verbose_name_plural = 'Типы материалов'

    def __str__(self) -> str:
        return self.name


class Material(models.Model):
    """Logical catalog entry: scanned files, literature lists, bibliographies, etc."""

    material_kind = models.ForeignKey(
        MaterialKind,
        on_delete=models.PROTECT,
        related_name='materials',
    )

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='materials')
    topic = models.CharField(
        max_length=512,
        blank=True,
        verbose_name='Тема',
        help_text='Тема или направление (удобно для списков литературы)',
        db_index=True,
    )
    file_name = models.CharField(max_length=255)
    extension = models.CharField(max_length=50, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    checksum_sha256 = models.CharField(max_length=128, blank=True, db_index=True)
    source_path = models.CharField(
        max_length=2048,
        blank=True,
        verbose_name='Локальный путь',
        help_text='Откуда взят файл (часто нужно ввести вручную: браузер не отдаёт полный путь к диску).',
    )
    description = models.TextField(blank=True)
    tags = models.ManyToManyField('Tag', related_name='materials', blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    #: Запись пришла со сканера и ещё не разобрана на странице «Разбор скана» (проект/теги).
    scan_import_pending = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['file_name']),
            models.Index(fields=['extension']),
        ]

    def __str__(self) -> str:
        return self.file_name

    @property
    def display_title(self) -> str:
        return self.file_name


class LinkedResource(models.Model):
    """Links URLs, DOIs, notes, and legacy FileResource rows to a Material (e.g. literature list)."""

    class ResourceType(models.TextChoices):
        PDF = 'pdf', 'PDF'
        BOOK = 'book', 'Книга'
        ARTICLE = 'article', 'Статья'
        DOI = 'doi', 'DOI'
        ARXIV = 'arxiv', 'arXiv'
        URL = 'url', 'Ссылка (URL)'
        GITHUB = 'github', 'GitHub'
        LOCAL_FILE = 'local_file', 'Локальный файл'
        LOCAL_FOLDER = 'local_folder', 'Локальная папка'
        NOTE = 'note', 'Заметка'
        OTHER = 'other', 'Другое'

    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='linked_resources')
    resource_type = models.CharField(max_length=32, choices=ResourceType.choices, default=ResourceType.URL)
    title = models.CharField(max_length=512)
    url = models.CharField(
        max_length=2048,
        blank=True,
        help_text='URL, DOI, идентификатор arXiv или другой текст',
    )
    file_resource = models.ForeignKey(
        'FileResource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_from_materials',
    )
    description = models.TextField(blank=True)
    tags = models.ManyToManyField(
        'Tag',
        related_name='linked_resource_links',
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['material_id', 'created_at']
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['url']),
            models.Index(fields=['resource_type']),
        ]

    def __str__(self) -> str:
        return f'{self.title} ({self.get_resource_type_display()})'


class MaterialLocation(models.Model):
    """Concrete placement of a material on a device / storage root."""

    class SyncStatus(models.TextChoices):
        PENDING = 'pending', 'В очереди'
        SYNCED = 'synced', 'Синхронизировано'
        ERROR = 'error', 'Ошибка'

    class Availability(models.TextChoices):
        PRESENT = 'present', 'Есть'
        MISSING = 'missing', 'Отсутствует'

    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='locations')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='material_locations')
    storage_location = models.ForeignKey(
        StorageLocation, on_delete=models.CASCADE, related_name='material_locations'
    )
    relative_path = models.CharField(max_length=2048)
    checksum = models.CharField(max_length=128, blank=True)
    sync_status = models.CharField(max_length=20, choices=SyncStatus.choices, default=SyncStatus.SYNCED)
    availability = models.CharField(max_length=20, choices=Availability.choices, default=Availability.PRESENT)
    tags = models.ManyToManyField(
        'Tag',
        related_name='material_location_paths',
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['device_id', 'relative_path']
        constraints = [
            models.UniqueConstraint(
                fields=['device', 'storage_location', 'relative_path'],
                name='catalog_materialloc_unique_path',
            ),
        ]
        indexes = [
            models.Index(fields=['relative_path']),
            models.Index(fields=['availability']),
        ]

    def __str__(self) -> str:
        return f'{self.material.file_name} @ {self.device}: {self.relative_path}'


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class FileResource(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='files')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='files')
    relative_path = models.CharField(max_length=1024)
    file_name = models.CharField(max_length=255)
    extension = models.CharField(max_length=50)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    created_at_fs = models.DateTimeField(null=True, blank=True)
    updated_at_fs = models.DateTimeField(null=True, blank=True)
    checksum = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, related_name='files', blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['file_name']),
            models.Index(fields=['extension']),
            models.Index(fields=['relative_path']),
        ]

    def __str__(self):
        return f"{self.file_name} ({self.project})"

    @property
    def full_path(self):
        """Краткая строка для списков: устройство каталога + относительный путь в учёте."""
        return f"{self.device.name}: {self.relative_path}"


class FileResourceLocation(models.Model):
    """Копии файла на диске, найденные metastore-scanner (несколько путей возможно)."""

    file_resource = models.ForeignKey(FileResource, on_delete=models.CASCADE, related_name='disk_locations')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='file_resource_locations')
    storage_location = models.ForeignKey(
        StorageLocation, on_delete=models.CASCADE, related_name='file_resource_locations'
    )
    relative_path = models.CharField(max_length=2048)
    size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='Размер (байт)',
        help_text='Размер копии на диске на момент сканирования',
    )
    mtime_fs = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Изменён на диске',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['device_id', 'relative_path']
        constraints = [
            models.UniqueConstraint(
                fields=['file_resource', 'device', 'storage_location', 'relative_path'],
                name='catalog_fileresloc_unique_path',
            ),
        ]

    def display_absolute_path(self) -> str:
        from pathlib import Path

        return str(Path(self.storage_location.root_path) / self.relative_path)

    def __str__(self) -> str:
        return self.display_absolute_path()
