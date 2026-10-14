from django.urls import path

from . import views
from .assistant import assistant_chat

urlpatterns = [
    path("health/", views.health, name="health"),
    path("assistant/chat/", assistant_chat, name="assistant-chat"),

    path("products/", views.product_list, name="product-list"),
    path("products/<str:sku>/", views.product_detail, name="product-detail"),

    path("inventory/<str:sku>/", views.inventory_update, name="inventory-update"),

    path("dealers/", views.dealer_list, name="dealer-list"),
    path("dealers/<int:dealer_id>/", views.dealer_detail, name="dealer-detail"),

    path("orders/", views.order_list, name="order-list"),
    path("orders/<str:order_number>/", views.order_detail, name="order-detail"),
    path("orders/<str:order_number>/confirm/", views.confirm_order, name="confirm-order"),
    path("orders/<str:order_number>/dispatch/", views.dispatch_order, name="dispatch-order"),
    path("orders/<str:order_number>/deliver/", views.deliver_order, name="deliver-order"),
    path("orders/<str:order_number>/cancel/", views.cancel_order, name="cancel-order"),

    path("forecast/<str:sku>/", views.forecast_detail, name="forecast-detail"),
    path("reorder-suggestions/", views.reorder_suggestions, name="reorder-suggestions"),

    path("sync/supplier/", views.supplier_sync, name="supplier-sync"),
]