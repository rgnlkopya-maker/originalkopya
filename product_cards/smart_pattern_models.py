from django.conf import settings
from django.db import models


class SmartPatternMaster(models.Model):
    MODEL_TYPES = [('ACIK', 'Açık'), ('TESETTUR', 'Tesettür')]
    product = models.OneToOneField('core.UrunKod', on_delete=models.PROTECT, related_name='smart_pattern_master')
    model_type = models.CharField(max_length=12, choices=MODEL_TYPES)
    reference_size = models.CharField(max_length=12, default='38')
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['product__kod']

    def __str__(self):
        return f'{self.product.kod} - {self.reference_size}'
