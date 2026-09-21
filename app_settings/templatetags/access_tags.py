from django import template

from app_settings.access import has_access, has_feature_access, has_full_access
from app_settings.models import SystemSettings
from app_settings.middleware import staff_break_active

register = template.Library()


@register.filter
def can(user, permission_name):
    return has_access(user, permission_name)


@register.filter
def can_feature(user, feature_key):
    return has_feature_access(user, feature_key)


@register.filter
def is_management(user):
    return has_full_access(user)


@register.simple_tag
def staff_access_enabled():
    return SystemSettings.get_solo().staff_access_enabled


@register.simple_tag
def staff_break_is_active():
    return staff_break_active()
