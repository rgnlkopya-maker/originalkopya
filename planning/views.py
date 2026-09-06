import calendar
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import PlanningEntry


SECTIONS = [
    ("kesim", "Kesim Planlaması"),
    ("dikim", "Dikim Planlaması"),
    ("susleme", "Süsleme Planlaması"),
]


def _month_value(request):
    today = date.today()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month
    return year, month


@login_required
def planning_page(request):
    year, month = _month_value(request)
    first_weekday, day_count = calendar.monthrange(year, month)
    cells = [None] * first_weekday + list(range(1, day_count + 1))
    while len(cells) % 7:
        cells.append(None)
    weeks = [cells[i:i + 7] for i in range(0, len(cells), 7)]

    entries = PlanningEntry.objects.filter(date__year=year, date__month=month)
    entry_map = {
        f"{entry.section}-{entry.date.day}": {
            "note": entry.note,
            "text_color": entry.text_color,
            "background_color": entry.background_color,
        }
        for entry in entries
    }

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    return render(request, "planning/planning.html", {
        "year": year,
        "month": month,
        "month_label": f"{month:02d}/{year}",
        "weeks": weeks,
        "sections": SECTIONS,
        "entry_map": entry_map,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
    })


@login_required
def shipment_planning_page(request):
    today = date.today()
    raw_date = request.GET.get("date")
    try:
        selected = date.fromisoformat(raw_date) if raw_date else today
    except ValueError:
        selected = today

    monday = selected - timedelta(days=selected.weekday())
    weekdays = [monday + timedelta(days=i) for i in range(5)]
    friday = weekdays[-1]

    month_names = {
        1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
        7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
    }
    if monday.month == friday.month:
        week_label = f"{monday.day}–{friday.day} {month_names[monday.month]} {monday.year}"
    else:
        week_label = f"{monday.day} {month_names[monday.month]} – {friday.day} {month_names[friday.month]} {friday.year}"

    return render(request, "planning/shipment_planning.html", {
        "weekdays": weekdays,
        "week_label": week_label,
        "prev_date": (monday - timedelta(days=7)).isoformat(),
        "next_date": (monday + timedelta(days=7)).isoformat(),
        "today": today,
    })


@login_required
@require_POST
def save_entry(request):
    try:
        section = request.POST["section"]
        entry_date = date.fromisoformat(request.POST["date"])
    except (KeyError, ValueError):
        return JsonResponse({"ok": False, "error": "Geçersiz kayıt."}, status=400)

    valid_sections = {item[0] for item in SECTIONS}
    if section not in valid_sections:
        return JsonResponse({"ok": False, "error": "Geçersiz planlama bölümü."}, status=400)

    note = request.POST.get("note", "").strip()
    text_color = request.POST.get("text_color", "#182033")[:7]
    background_color = request.POST.get("background_color", "#ffffff")[:7]

    if not note and background_color.lower() == "#ffffff":
        PlanningEntry.objects.filter(section=section, date=entry_date).delete()
        return JsonResponse({"ok": True, "deleted": True})

    PlanningEntry.objects.update_or_create(
        section=section,
        date=entry_date,
        defaults={
            "note": note,
            "text_color": text_color,
            "background_color": background_color,
            "updated_by": request.user,
        },
    )
    return JsonResponse({"ok": True})
