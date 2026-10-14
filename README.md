# VIKMO DealerDesk — AI/ML Assignment

An AI/ML-enabled DealerDesk application built with Django and PostgreSQL. The project provides product catalogue access, inventory forecasting, reorder suggestions, and an AI-powered dealer assistant.

## Features

### 1. Django Backend
- Django-based REST API.
- PostgreSQL database integration.
- Health-check endpoint.
- Product catalogue and inventory APIs.
- Reorder suggestions based on inventory data.

### 2. AI Dealer Assistant
- Assistant implementation in `core/assistant.py`.
- Tool-based interactions for product search, stock checking, and draft order creation.
- Product and inventory information grounded in application data.
- Draft-order workflow designed to avoid automatically placing orders.

**Note:** Configure a supported LLM provider and API key before testing live assistant responses.

### 3. Inventory Forecasting
- Forecasting implementation in `ml/forecasting.py`.
- Forecast data in `ml/forecast.csv`.
- Four-week forecasts for 40 SKUs.
- Total forecast records: 160.
- Reorder suggestions use current inventory information.

### 4. Supplier Integration
- Supplier mock service in `supplier_mock/mock_supplier.py`.
- Configurable supplier URL and API key.
- Supplier integration can be tested locally.

## Technology Stack

- Python
- Django
- Django REST Framework
- PostgreSQL
- Machine Learning / Forecasting
- External LLM integration
- REST APIs

## Project Structure

```text
VIKMO DealerDesk Assignment/
├── core/
│   ├── assistant.py
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── management/commands/seed_data.py
├── dealerdesk/
│   ├── settings.py
│   └── urls.py
├── data/
├── ml/
│   ├── forecasting.py
│   └── forecast.csv
├── supplier_mock/
│   └── mock_supplier.py
├── starter/
├── requirements.txt
├── manage.py
├── smoke_test.py
├── API_CONTRACT.md
├── .env.example
└── DECISIONS.md
```

## Setup

### Prerequisites

- Python 3.11 or newer
- PostgreSQL database
- Git
- API key for a supported LLM provider when testing the AI assistant

### 1. Clone the repository

```bash
git clone https://github.com/harshithapra/VIKMO-DealerDesk-Assignment.git
cd VIKMO-DealerDesk-Assignment
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a local `.env` file using `.env.example` as a reference.

Configure the following variables as required:

- `DATABASE_URL`
- `SUPPLIER_API_URL`
- `SUPPLIER_API_KEY`
- The API key for your chosen LLM provider

Never commit `.env` or actual API keys to GitHub.

### 5. Apply migrations and seed data

```bash
python manage.py migrate
python manage.py seed_data
```

Run the application:

```bash
python manage.py runserver
```

The development server runs at `http://127.0.0.1:8000/`.

## API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/health/` | Check application health |
| `GET /api/products/` | Retrieve products |
| `GET /api/forecast/<sku>/` | Retrieve a product forecast |
| `GET /api/reorder-suggestions/` | Retrieve reorder suggestions |

Refer to `API_CONTRACT.md` for the expected API contract.

## Forecast Data

The generated forecast CSV is located at `ml/forecast.csv`.

It contains 160 records covering 40 SKUs across four forecast weeks.

## Supplier Mock

Start the supplier mock service in a separate terminal using the project's configured Python environment and the appropriate command for `supplier_mock/mock_supplier.py`.

Configure the supplier URL and API key in your local environment before testing supplier integration.

## Testing

Check Django configuration:

```bash
python manage.py check
```

Check database connectivity:

```bash
python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print('Database connection successful')"
```

The provided smoke test can be run against a freshly prepared test database:

```bash
python smoke_test.py --base-url http://localhost:8000 --track aiml
```

**Warning:** The smoke test can modify database records. Use a disposable test database, not a database containing data you need to preserve.

## Design Decisions

See `DECISIONS.md` for the design decisions, assumptions, trade-offs, and implementation details for this assignment.

## Limitations

- Live LLM responses require a valid provider API key.
- The project is configured for local development and assignment evaluation.
- Production deployment requires additional security, monitoring, and configuration.

## Author

Harshitha Prakash

## Repository

https://github.com/harshithapra/VIKMO-DealerDesk-Assignment