"""
WSGI config for demo_app project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'demo_app.settings')

application = get_wsgi_application()

import os
from django.contrib.auth import get_user_model

try:
    from django.conf import settings
    if getattr(settings, "CREATE_ADMIN", False):
        User = get_user_model()
        if not User.objects.filter(username=settings.ADMIN_USERNAME).exists():
            User.objects.create_superuser(
                username=settings.ADMIN_USERNAME,
                email=settings.ADMIN_EMAIL,
                password=settings.ADMIN_PASSWORD
            )
            print("✅ Admin user created successfully")
        else:
            print("ℹ️ Admin already exists")
except Exception as e:
    print("❌ Admin creation error:", e)

