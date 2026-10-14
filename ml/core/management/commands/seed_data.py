import csv
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Product, Dealer


class Command(BaseCommand):
    help = "Load catalogue and dealer CSV files safely and efficiently."

    @transaction.atomic
    def handle(self, *args, **options):
        data_dir = Path(__file__).resolve().parents[3] / "data"

        catalogue_file = data_dir / "catalogue.csv"
        dealers_file = data_dir / "dealers.csv"

        if not catalogue_file.exists():
            raise CommandError(f"Catalogue file not found: {catalogue_file}")

        if not dealers_file.exists():
            raise CommandError(f"Dealers file not found: {dealers_file}")

        # Load products efficiently without overwriting existing stock.
        products = []

        with catalogue_file.open(
            "r", encoding="utf-8-sig", newline=""
        ) as file:
            reader = csv.DictReader(file)

            for row in reader:
                products.append(
                    Product(
                        sku=row["sku"].strip(),
                        name=row["name"].strip(),
                        category=row.get("category", "").strip(),
                        brand=row.get("brand", "").strip(),
                        vehicle_fitment=row.get("vehicle_fitment", "").strip(),
                        price=Decimal(row["price"].strip()),
                        description=row.get("description", "").strip(),
                    )
                )

        Product.objects.bulk_create(
            products,
            batch_size=200,
            update_conflicts=True,
            unique_fields=["sku"],
            update_fields=[
                "name",
                "category",
                "brand",
                "vehicle_fitment",
                "price",
                "description",
            ],
        )

        # Load dealers efficiently.
        dealers = []

        with dealers_file.open(
            "r", encoding="utf-8-sig", newline=""
        ) as file:
            reader = csv.DictReader(file)

            for row in reader:
                dealers.append(
                    Dealer(
                        dealer_code=row["dealer_code"].strip(),
                        name=row["name"].strip(),
                        city=row.get("city", "").strip(),
                        phone=row.get("phone", "").strip(),
                        email=row.get("email", "").strip(),
                        gstin=row.get("gstin", "").strip(),
                        credit_limit=Decimal(
                            row.get("credit_limit", "0").strip() or "0"
                        ),
                    )
                )

        Dealer.objects.bulk_create(
            dealers,
            batch_size=200,
            update_conflicts=True,
            unique_fields=["dealer_code"],
            update_fields=[
                "name",
                "city",
                "phone",
                "email",
                "gstin",
                "credit_limit",
            ],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeding complete! Products: {Product.objects.count()}, "
                f"Dealers: {Dealer.objects.count()}"
            )
        )