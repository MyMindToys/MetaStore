from django.db import models
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
        PC = 'PC', 'PC'
        LAPTOP = 'Laptop', 'Laptop'
        EXTERNAL_HDD = 'ExternalHDD', 'External HDD/SSD'
        USB = 'USB', 'USB Drive'
        OTHER = 'Other', 'Other'

    name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=20, choices=DeviceType.choices, default=DeviceType.OTHER)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        unique_together = [('name', 'device_type')]

    def __str__(self):
        return self.name


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
        return f"{self.device.name}: {self.relative_path}"
