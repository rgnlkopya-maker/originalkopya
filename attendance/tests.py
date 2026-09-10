from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


class AttendanceDashboardRoleFilterTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        patron_group, _ = Group.objects.get_or_create(name="patron")
        manager_group, _ = Group.objects.get_or_create(name="mudur")

        self.manager = user_model.objects.create_user(
            username="takvim-yoneticisi",
            password="test",
        )
        self.manager.groups.add(manager_group)

        self.mustafa = user_model.objects.create_user(
            username="mustafa-hesabi",
            first_name="Mustafa",
            last_name="Kanyış",
            password="test",
        )
        self.mustafa.groups.add(patron_group)

        self.emine = user_model.objects.create_user(
            username="emine-hesabi",
            first_name="Emine",
            last_name="Kanyış",
            password="test",
        )
        self.emine.groups.add(patron_group)

        self.employee = user_model.objects.create_user(
            username="normal-personel",
            first_name="Normal",
            last_name="Personel",
            password="test",
        )
        self.client.force_login(self.manager)

    def test_patrons_are_not_listed_in_attendance_calendar(self):
        response = self.client.get(reverse("attendance_dashboard"))

        self.assertEqual(response.status_code, 200)
        listed_user_ids = {user.id for user in response.context["users"]}
        self.assertIn(self.employee.id, listed_user_ids)
        self.assertNotIn(self.mustafa.id, listed_user_ids)
        self.assertNotIn(self.emine.id, listed_user_ids)
