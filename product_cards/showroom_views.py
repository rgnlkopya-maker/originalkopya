from .price_list_views import price_list


def showroom_page(request):
    request._showroom_mode = True
    return price_list(request)
