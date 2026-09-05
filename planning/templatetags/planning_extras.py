from django import template

register = template.Library()


@register.filter
def planning_entry(entry_map, key):
    return entry_map.get(key, {})


@register.simple_tag
def planning_entry_for(entry_map, section, day):
    """Return a saved planning entry for a calendar section/day."""
    return entry_map.get(f"{section}-{day}", {})
