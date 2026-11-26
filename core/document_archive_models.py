from uuid import uuid4

from django.conf import settings
from django.db import models


class ArchiveFolder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="subfolders")
    name = models.CharField(max_length=120)
    name_key = models.CharField(max_length=240, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["parent", "name_key"], name="evrak_unique_child_name"),
            models.UniqueConstraint(fields=["name_key"], condition=models.Q(parent__isnull=True), name="evrak_unique_root_name"),
        ]


class ArchiveDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    folder = models.ForeignKey(ArchiveFolder, null=True, blank=True, on_delete=models.PROTECT, related_name="documents")
    name = models.CharField(max_length=200)
    content_type = models.CharField(max_length=40)
    byte_size = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at", "id"]

    @property
    def storage_path(self):
        # No document or folder name in URL or object key.
        return f"evrak/{self.pk.hex}"
