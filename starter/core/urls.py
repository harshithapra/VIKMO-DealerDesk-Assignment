from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("products/", views.product_list, name="product-list"),
    path("products/<str:sku>/", views.product_detail, name="product-detail"),
    path("inventory/<str:sku>/", views.inventory_update, name="inventory-update"),
    path("dealers/", views.dealer_list, name="dealer-list"),
    path("dealers/<int:dealer_id>/", views.dealer_detail, name="dealer-detail"),
    path("orders/", views.order_list, name="order-list"),
    path("orders/<int:order_id>/", views.order_detail, name="order-detail"),
    path("forecast/<str:sku>/", views.forecast_detail, name="forecast-detail"),
    path("reorder-suggestions/", views.reorder_suggestions, name="reorder-suggestions"),
]