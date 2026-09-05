from django.conf import settings
from django.db import models


class WorkplaceSettings(models.Model):
    name = models.CharField(max_length=120, default="Moli Tekstil")
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    second_location_name = models.CharField(max_length=120, default="Gaziemir", blank=True)
    second_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    second_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    normal_radius_m = models.PositiveIntegerField(default=50)
    overtime_radius_m = models.PositiveIntegerField(default=100)
    work_start = models.TimeField(default="08:30")
    work_end = models.TimeField(default="19:00")
    late_tolerance_minutes = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "İşyeri puantaj ayarı"
        verbose_name_plural = "İşyeri puantaj ayarları"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def location_ready(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def second_location_ready(self):
        return self.second_latitude is not None and self.second_longitude is not None

    def active_locations(self):
        locations = []
        if self.location_ready:
            locations.append(("Çankaya", self.latitude, self.longitude))
        if self.second_location_ready:
            locations.append((self.second_location_name or "Gaziemir", self.second_latitude, self.second_longitude))
        return locations

    def __str__(self):
        return self.name


class EmployeeHRProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hr_profile",
    )
    phone_number = models.CharField(max_length=30, blank=True, default="")
    national_id = models.CharField(max_length=11, blank=True, default="")
    emergency_contact_name = models.CharField(max_length=120, blank=True, default="")
    emergency_contact_phone = models.CharField(max_length=30, blank=True, default="")
    employment_start_date = models.DateField(null=True, blank=True)
    employment_end_date = models.DateField(null=True, blank=True)
    sgk_start_date = models.DateField(null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    annual_leave_carryover = models.PositiveIntegerField(default=0)
    note = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} özlük profili"


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ("worked", "Çalıştı"),
        ("leave", "İzinli"),
        ("annual_leave", "Yıllık İzin"),
        ("sick", "Raporlu"),
        ("other", "Diğer"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_records")
    work_date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="worked")
    note = models.TextField(blank=True, default="")
    report_image_url = models.URLField(blank=True, default="")
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    check_in_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    check_in_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    check_out_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    check_out_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    check_in_distance_m = models.PositiveIntegerField(null=True, blank=True)
    check_out_distance_m = models.PositiveIntegerField(null=True, blank=True)
    late_minutes = models.PositiveIntegerField(default=0)
    overtime_minutes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-work_date", "user__username"]
        constraints = [
            models.UniqueConstraint(fields=["user", "work_date"], name="unique_user_attendance_day")
        ]
        indexes = [models.Index(fields=["work_date", "user"])]

    @property
    def is_complete(self):
        return bool(self.check_in and self.check_out)

    @property
    def work_minutes(self):
        if not self.check_in or not self.check_out:
            return 0
        return max(0, int((self.check_out - self.check_in).total_seconds() // 60))

    def __str__(self):
        return f"{self.user} - {self.work_date}"
