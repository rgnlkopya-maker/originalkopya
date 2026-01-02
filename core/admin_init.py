from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

def ensure_admin():
    if not settings.CREATE_ADMIN:
        return

    user, created = User.objects.get_or_create(username=settings.ADMIN_USERNAME)

    user.is_staff = True
    user.is_superuser = True
    user.email = settings.ADMIN_EMAIL
    user.set_password(settings.ADMIN_PASSWORD)
    user.save()

    print("✅ Admin ensured (staff+superuser)")
