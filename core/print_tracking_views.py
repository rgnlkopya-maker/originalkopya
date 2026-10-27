from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from .models import Order, OrderImage

@login_required
@require_POST
def mark_order_print(request, pk):
    order = get_object_or_404(Order, pk=pk)
    kind = request.POST.get("kind")
    if kind == "detail":
        Order.objects.filter(pk=pk).update(detail_printed=True)
    elif kind == "main_image":
        if not order.resim:
            return JsonResponse({"ok": False, "error": "Ana görsel bulunamadı."}, status=400)
        Order.objects.filter(pk=pk).update(main_image_printed=True)
    elif kind == "extra_image":
        image = OrderImage.objects.filter(order_id=pk, pk=request.POST.get("image_id")).first()
        if not image or not (image.image_url or image.image):
            return JsonResponse({"ok": False, "error": "Görsel bulunamadı."}, status=400)
        OrderImage.objects.filter(pk=image.pk).update(printed=True)
    else:
        return JsonResponse({"ok": False, "error": "Geçersiz yazdırma türü."}, status=400)
    return JsonResponse({"ok": True})
