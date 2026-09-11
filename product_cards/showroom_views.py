from .price_list_views import price_list


def showroom_page(request):
    return price_list(request)
