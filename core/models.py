from django.db import models


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    vehicle_fitment = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.sku} - {self.name}"


class Dealer(models.Model):
    dealer_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    credit_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    def __str__(self):
        return f"{self.dealer_code} - {self.name}"


class Order(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("CONFIRMED", "Confirmed"),
        ("DISPATCHED", "Dispatched"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
    ]

    order_number = models.CharField(
        max_length=30, unique=True, null=True, blank=True
    )
    dealer = models.ForeignKey(
        Dealer, on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="DRAFT"
    )
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    gst_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_number or f"Order {self.pk}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="order_items"
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product"],
                name="unique_product_per_order",
            )
        ]

    def __str__(self):
        return f"{self.product.sku} x {self.quantity}"