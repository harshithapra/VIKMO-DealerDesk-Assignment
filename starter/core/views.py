import csv
import json
import math
import statistics
from pathlib import Path
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Product, Dealer, Order, OrderItem


# --------------------------------------------------
# PATHS AND CONSTANTS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
FORECAST_FILE = BASE_DIR / "starter" / "ml" / "forecast.csv"

GST_RATE = Decimal("0.18")


# --------------------------------------------------
# COMMON HELPERS
# --------------------------------------------------

def error_response(code, message, status):
    return JsonResponse(
        {
            "error": {
                "code": code,
                "message": message,
                "details": [],
            }
        },
        status=status,
    )


def read_json(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    return data


def money(value):
    return f"{value:.2f}"


def product_data(product):
    return {
        "sku": product.sku,
        "name": product.name,
        "category": product.category,
        "brand": product.brand,
        "vehicle_fitment": product.vehicle_fitment,
        "price": money(product.price),
        "stock": product.stock,
        "description": product.description,
    }


def dealer_data(dealer):
    return {
        "id": dealer.id,
        "dealer_code": dealer.dealer_code,
        "name": dealer.name,
        "city": dealer.city,
        "phone": dealer.phone,
        "email": dealer.email,
        "gstin": dealer.gstin,
        "credit_limit": money(dealer.credit_limit),
    }


def order_item_data(item):
    line_subtotal = (
        item.unit_price * item.quantity
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    line_tax = (
        item.line_total - line_subtotal
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    return {
        "sku": item.product.sku,
        "name": item.product.name,
        "quantity": item.quantity,
        "unit_price": money(item.unit_price),
        "line_subtotal": money(line_subtotal),
        "line_tax": money(line_tax),
        "line_total": money(item.line_total),
    }


def order_data(order):
    return {
        "id": order.id,
        "order_number": order.order_number,
        "dealer": dealer_data(order.dealer),
        "dealer_id": order.dealer_id,
        "dealer_name": order.dealer.name,
        "status": order.status,
        "items": [
            order_item_data(item)
            for item in order.items.select_related("product").all()
        ],
        "subtotal": money(order.subtotal),
        "tax_total": money(order.gst_amount),
        "gst_amount": money(order.gst_amount),
        "total": money(order.total),
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }


def paginated_response(request, queryset, serializer):
    try:
        page_size = int(request.GET.get("page_size", "20"))
        page_number = int(request.GET.get("page", "1"))

        if page_size < 1 or page_size > 100 or page_number < 1:
            raise ValueError

    except (TypeError, ValueError):
        return error_response(
            "VALIDATION_ERROR",
            "page must be at least 1 and page_size must be between 1 and 100.",
            400,
        )

    paginator = Paginator(queryset, page_size)
    page = paginator.get_page(page_number)

    next_url = None
    previous_url = None

    if page.has_next():
        next_url = request.build_absolute_uri(
            f"?page={page.next_page_number()}&page_size={page_size}"
        )

    if page.has_previous():
        previous_url = request.build_absolute_uri(
            f"?page={page.previous_page_number()}&page_size={page_size}"
        )

    return JsonResponse(
        {
            "count": paginator.count,
            "next": next_url,
            "previous": previous_url,
            "results": [serializer(obj) for obj in page.object_list],
        }
    )


def read_csv_rows(file_path):
    with file_path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def load_forecasts():
    if not FORECAST_FILE.exists():
        raise FileNotFoundError(f"Forecast file not found: {FORECAST_FILE}")

    rows = read_csv_rows(FORECAST_FILE)
    required_columns = {"sku", "week_start", "forecast_units"}

    if not rows and not FORECAST_FILE.exists():
        raise FileNotFoundError("Forecast file does not exist.")

    if rows and not required_columns.issubset(rows[0].keys()):
        raise ValueError("Forecast CSV has incorrect columns.")

    forecasts = {}

    for row in rows:
        sku = row["sku"].strip()
        week_start = row["week_start"].strip()
        units = float(row["forecast_units"])

        if not math.isfinite(units) or units < 0:
            raise ValueError("Forecast units must be finite and non-negative.")

        forecasts.setdefault(sku, []).append(
            {
                "week_start": week_start,
                "forecast_units": units,
            }
        )

    for sku in forecasts:
        forecasts[sku].sort(key=lambda item: item["week_start"])

        if len(forecasts[sku]) != 4:
            raise ValueError(f"SKU {sku} must have exactly four forecast weeks.")

    return forecasts


def load_lead_times():
    lead_times_file = DATA_DIR / "lead_times.csv"

    if not lead_times_file.exists():
        raise FileNotFoundError(f"Lead-time file not found: {lead_times_file}")

    lead_times = {}

    for row in read_csv_rows(lead_times_file):
        sku = row["sku"].strip()
        lead_time = int(row["lead_time_weeks"])

        if lead_time < 1:
            raise ValueError(f"Invalid lead time for {sku}.")

        lead_times[sku] = lead_time

    return lead_times


def load_recent_sales():
    sales_file = DATA_DIR / "sales_history.csv"

    if not sales_file.exists():
        raise FileNotFoundError(f"Sales history file not found: {sales_file}")

    sales_by_sku = {}

    for row in read_csv_rows(sales_file):
        sku = row["sku"].strip()
        week_start = row["week_start"].strip()
        units_sold = float(row["units_sold"])

        if not math.isfinite(units_sold):
            raise ValueError(f"Invalid sales value for {sku}.")

        sales_by_sku.setdefault(sku, []).append(
            (week_start, units_sold)
        )

    recent_sales = {}

    for sku, values in sales_by_sku.items():
        values.sort(key=lambda item: item[0])
        recent_sales[sku] = [
            units for _, units in values[-12:]
        ]

    return recent_sales


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def health(request):
    return JsonResponse({"status": "ok"})


# --------------------------------------------------
# PRODUCTS
# --------------------------------------------------

@csrf_exempt
@require_http_methods(["GET", "POST"])
def product_list(request):
    if request.method == "GET":
        products = Product.objects.all().order_by("sku")

        search = request.GET.get("search", "").strip()

        if search:
            products = products.filter(
                Q(sku__icontains=search)
                | Q(name__icontains=search)
                | Q(brand__icontains=search)
            )

        category = request.GET.get("category", "").strip()

        if category:
            products = products.filter(category__iexact=category)

        vehicle = request.GET.get("vehicle", "").strip()

        if vehicle:
            products = products.filter(
                vehicle_fitment__icontains=vehicle
            )

        return paginated_response(request, products, product_data)

    data = read_json(request)

    if data is None:
        return error_response(
            "VALIDATION_ERROR",
            "A valid JSON object is required.",
            400,
        )

    sku = data.get("sku")
    name = data.get("name")

    if not isinstance(sku, str) or not sku.strip():
        return error_response("VALIDATION_ERROR", "sku is required.", 400)

    if not isinstance(name, str) or not name.strip():
        return error_response("VALIDATION_ERROR", "name is required.", 400)

    if "stock" in data:
        return error_response(
            "VALIDATION_ERROR",
            "Stock cannot be set when creating a product.",
            400,
        )

    try:
        price = Decimal(str(data.get("price")))

        if (
            not price.is_finite()
            or price <= 0
            or price.as_tuple().exponent < -2
        ):
            raise ValueError

    except (InvalidOperation, ValueError, TypeError):
        return error_response(
            "VALIDATION_ERROR",
            "Price must be positive and have at most 2 decimal places.",
            400,
        )

    sku = sku.strip()

    if Product.objects.filter(sku=sku).exists():
        return error_response("DUPLICATE", "Product SKU already exists.", 409)

    product = Product.objects.create(
        sku=sku,
        name=name.strip(),
        category=str(data.get("category", "")).strip(),
        brand=str(data.get("brand", "")).strip(),
        vehicle_fitment=str(data.get("vehicle_fitment", "")).strip(),
        price=price,
        description=str(data.get("description", "")).strip(),
        stock=0,
    )

    return JsonResponse(product_data(product), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def product_detail(request, sku):
    product = Product.objects.filter(sku=sku).first()

    if product is None:
        return error_response(
            "NOT_FOUND",
            "Product not found.",
            404,
        )

    if request.method == "GET":
        return JsonResponse(product_data(product))

    data = read_json(request)

    if data is None:
        return error_response(
            "VALIDATION_ERROR",
            "A valid JSON object is required.",
            400,
        )

    allowed_fields = {
        "name", "category", "brand", "vehicle_fitment", "price", "description"
    }

    if not data or set(data.keys()) - allowed_fields:
        return error_response(
            "VALIDATION_ERROR",
            "Only product fields other than sku and stock may be updated.",
            400,
        )

    if "name" in data:
        if not isinstance(data["name"], str) or not data["name"].strip():
            return error_response(
                "VALIDATION_ERROR", "name cannot be empty.", 400
            )

        product.name = data["name"].strip()

    for field in ("category", "brand", "vehicle_fitment", "description"):
        if field in data:
            setattr(product, field, str(data[field]).strip())

    if "price" in data:
        try:
            price = Decimal(str(data["price"]))

            if (
                not price.is_finite()
                or price <= 0
                or price.as_tuple().exponent < -2
            ):
                raise ValueError

        except (InvalidOperation, ValueError, TypeError):
            return error_response(
                "VALIDATION_ERROR",
                "Price must be positive and have at most 2 decimal places.",
                400,
            )

        product.price = price

    product.save()
    return JsonResponse(product_data(product))


# --------------------------------------------------
# INVENTORY
# --------------------------------------------------

@csrf_exempt
@require_http_methods(["PUT"])
def inventory_update(request, sku):
    product = get_object_or_404(Product, sku=sku)
    data = read_json(request)

    if data is None or "quantity" not in data:
        return error_response(
            "VALIDATION_ERROR",
            "A JSON object with quantity is required.",
            400,
        )

    quantity = data["quantity"]

    if (
        isinstance(quantity, bool)
        or not isinstance(quantity, int)
        or quantity < 0
    ):
        return error_response(
            "VALIDATION_ERROR",
            "quantity must be an integer greater than or equal to 0.",
            400,
        )

    product.stock = quantity
    product.save(update_fields=["stock"])

    return JsonResponse({"sku": product.sku, "quantity": product.stock})


# --------------------------------------------------
# DEALERS
# --------------------------------------------------

@csrf_exempt
@require_http_methods(["GET", "POST"])
def dealer_list(request):
    if request.method == "GET":
        dealers = Dealer.objects.all().order_by("id")
        return paginated_response(request, dealers, dealer_data)

    data = read_json(request)

    if data is None:
        return error_response(
            "VALIDATION_ERROR",
            "A valid JSON object is required.",
            400,
        )

    dealer_code = data.get("dealer_code")
    name = data.get("name")

    if not isinstance(dealer_code, str) or not dealer_code.strip():
        return error_response(
            "VALIDATION_ERROR", "dealer_code is required.", 400
        )

    if not isinstance(name, str) or not name.strip():
        return error_response("VALIDATION_ERROR", "name is required.", 400)

    dealer_code = dealer_code.strip()

    if Dealer.objects.filter(dealer_code=dealer_code).exists():
        return error_response("DUPLICATE", "Dealer code already exists.", 409)

    try:
        credit_limit = Decimal(str(data.get("credit_limit", "0")))

        if (
            not credit_limit.is_finite()
            or credit_limit < 0
            or credit_limit.as_tuple().exponent < -2
        ):
            raise ValueError

    except (InvalidOperation, ValueError, TypeError):
        return error_response(
            "VALIDATION_ERROR",
            "credit_limit must be non-negative with at most 2 decimal places.",
            400,
        )

    dealer = Dealer.objects.create(
        dealer_code=dealer_code,
        name=name.strip(),
        city=str(data.get("city", "")).strip(),
        phone=str(data.get("phone", "")).strip(),
        email=str(data.get("email", "")).strip(),
        gstin=str(data.get("gstin", "")).strip(),
        credit_limit=credit_limit,
    )

    return JsonResponse(dealer_data(dealer), status=201)


@csrf_exempt
@require_http_methods(["GET"])
def dealer_detail(request, dealer_id):
    dealer = get_object_or_404(Dealer, id=dealer_id)
    return JsonResponse(dealer_data(dealer))


# --------------------------------------------------
# ORDERS
# --------------------------------------------------

@csrf_exempt
@require_http_methods(["GET", "POST"])
def order_list(request):
    if request.method == "GET":
        orders = (
            Order.objects
            .select_related("dealer")
            .prefetch_related("items__product")
            .order_by("-created_at", "-id")
        )

        status_filter = request.GET.get("status", "").strip().upper()

        if status_filter:
            valid_statuses = {
                choice[0] for choice in Order.STATUS_CHOICES
            }

            if status_filter not in valid_statuses:
                return error_response(
                    "VALIDATION_ERROR", "Invalid order status.", 400
                )

            orders = orders.filter(status=status_filter)

        return paginated_response(request, orders, order_data)

    data = read_json(request)

    if data is None:
        return error_response(
            "VALIDATION_ERROR",
            "A valid JSON object is required.",
            400,
        )

    dealer_id = data.get("dealer_id")
    items = data.get("items")

    if (
        isinstance(dealer_id, bool)
        or not isinstance(dealer_id, int)
        or dealer_id < 1
    ):
        return error_response(
            "VALIDATION_ERROR",
            "dealer_id must be a valid positive integer.",
            400,
        )

    dealer = Dealer.objects.filter(id=dealer_id).first()

    if dealer is None:
        return error_response(
            "VALIDATION_ERROR",
            "The specified dealer does not exist.",
            400,
        )

    if not isinstance(items, list) or not items:
        return error_response(
            "VALIDATION_ERROR", "items must be a non-empty list.", 400
        )

    requested_items = []
    seen_skus = set()

    for item in items:
        if not isinstance(item, dict):
            return error_response(
                "VALIDATION_ERROR",
                "Each item must be a JSON object containing sku and quantity.",
                400,
            )

        sku = item.get("sku")
        quantity = item.get("quantity")

        if not isinstance(sku, str) or not sku.strip():
            return error_response(
                "VALIDATION_ERROR", "Every item must have a valid SKU.", 400
            )

        sku = sku.strip()

        if sku in seen_skus:
            return error_response(
                "VALIDATION_ERROR",
                "A product SKU may appear only once in an order.",
                400,
            )

        seen_skus.add(sku)

        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity <= 0
        ):
            return error_response(
                "VALIDATION_ERROR",
                f"Quantity for {sku} must be a positive integer.",
                400,
            )

        requested_items.append((sku, quantity))

    with transaction.atomic():
        sku_list = [sku for sku, quantity in requested_items]

        products = {
            product.sku: product
            for product in Product.objects.select_for_update().filter(
                sku__in=sku_list
            )
        }

        for sku, quantity in requested_items:
            product = products.get(sku)

            if product is None:
                return error_response(
                    "VALIDATION_ERROR",
                    f"Product SKU {sku} does not exist.",
                    400,
                )

            if product.stock < quantity:
                return error_response(
                    "INSUFFICIENT_STOCK",
                    f"Insufficient stock for {sku}. Available: "
                    f"{product.stock}, requested: {quantity}.",
                    400,
                )

        subtotal = Decimal("0.00")
        gst_amount = Decimal("0.00")

        for sku, quantity in requested_items:
            line_subtotal = (
                products[sku].price * quantity
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            line_tax = (
                line_subtotal * GST_RATE
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            subtotal += line_subtotal
            gst_amount += line_tax

        total = subtotal + gst_amount

        order = Order.objects.create(
            dealer=dealer,
            status="DRAFT",
            subtotal=subtotal,
            gst_amount=gst_amount,
            total=total,
        )

        order.order_number = f"ORD-{order.id:06d}"
        order.save(update_fields=["order_number"])

        for sku, quantity in requested_items:
            product = products[sku]
            unit_price = product.price

            line_total = (unit_price * quantity).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
            )

        order = (
            Order.objects
            .select_related("dealer")
            .prefetch_related("items__product")
            .get(id=order.id)
        )

    return JsonResponse(order_data(order), status=201)


@csrf_exempt
@require_http_methods(["GET"])
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects
        .select_related("dealer")
        .prefetch_related("items__product"),
        id=order_id,
    )

    return JsonResponse(order_data(order))


# --------------------------------------------------
# FORECAST API
# --------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def forecast_detail(request, sku):
    try:
        forecasts = load_forecasts()
    except (FileNotFoundError, ValueError, KeyError, TypeError):
        return error_response(
            "FORECAST_ERROR",
            "Unable to load the forecast data.",
            500,
        )

    if sku not in forecasts:
        return error_response(
            "NOT_FOUND",
            "No forecast found for this SKU.",
            404,
        )

    return JsonResponse({
        "sku": sku,
        "forecast": forecasts[sku],
    })


# --------------------------------------------------
# REORDER SUGGESTIONS API
# --------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def reorder_suggestions(request):
    try:
        forecasts = load_forecasts()
        lead_times = load_lead_times()
        recent_sales = load_recent_sales()

    except (FileNotFoundError, ValueError, KeyError, TypeError):
        return error_response(
            "REORDER_DATA_ERROR",
            "Unable to load the forecast or source data.",
            500,
        )

    results = []

    for sku in sorted(forecasts):
        if sku not in lead_times:
            continue

        sku_forecasts = forecasts[sku]
        lead_time = lead_times[sku]

        lead_time_demand = sum(
            row["forecast_units"]
            for row in sku_forecasts[:lead_time]
        )

        sales = recent_sales.get(sku, [])

        if len(sales) >= 2:
            sigma = statistics.stdev(sales)
        else:
            sigma = 0.0

        safety_stock = math.ceil(
            1.65 * sigma * math.sqrt(lead_time)
        )

        reorder_point = lead_time_demand + safety_stock

        current_stock = Product.objects.filter(
            sku=sku
        ).values_list("stock", flat=True).first()

        if current_stock is None:
            continue

        reorder_qty = max(
            0,
            math.ceil(reorder_point - current_stock)
        )

        results.append({
            "sku": sku,
            "current_stock": current_stock,
            "lead_time_weeks": lead_time,
            "lead_time_demand": round(lead_time_demand, 1),
            "safety_stock": safety_stock,
            "reorder_point": round(reorder_point, 1),
            "reorder_qty": reorder_qty,
        })

    return JsonResponse({"results": results})