# DECISIONS.md

## 1. Track Selection

I selected the AI/ML track because it combines backend development,
inventory forecasting, and an AI-powered dealer assistant.

The solution uses Django for backend APIs, PostgreSQL for application
data, a forecasting component for weekly demand predictions, and an
LLM-powered assistant that can use application tools to answer dealer
queries and create draft orders.

## 2. Database Design

PostgreSQL is used as the primary database, with Django models and
migrations managing application data.

Keeping products, inventory, dealers, and orders in structured database
tables allows the application to retrieve current information and
maintain consistency across backend operations.

The assistant should use the application's database operations rather
than inventing product availability, prices, or order information.

Model relationships and deletion behaviour should follow the actual
Django model definitions and their configured on_delete rules.

## 3. Inventory Forecasting

The forecasting component generates four weeks of demand predictions
for 40 products, producing 160 SKU-week records in ml/forecast.csv.

The implementation uses weighted historical demand averages over
multiple windows: 4, 8, 13, and 26 weeks. The weights are 0.4, 0.3,
0.2, and 0.1 respectively.

A trend adjustment compares recent demand with the preceding period,
with the trend ratio capped between 0.7 and 1.5. Promotion information
is used to adjust predictions for planned promotional weeks.

This is a weighted historical forecasting approach rather than a
trained machine-learning model.

Further improvements could include time-based backtesting, comparison
against a seasonal-naive baseline, and evaluation using MAE and WAPE.

## 4. Reorder Suggestions

The application exposes reorder suggestions through its backend API.
These suggestions use inventory and product information to help dealers
identify items that may require replenishment.

Forecast demand, available stock, and supplier lead times are relevant
to replenishment decisions. The precise calculation and thresholds
should be interpreted from the implemented reorder-suggestion logic.

Future improvements could include configurable safety stock, service
level targets, and more explicit handling of uncertain demand.

## 5. AI Dealer Assistant

The assistant is implemented in core/assistant.py and uses the
Gemini model configured by the application.

The model can request application tools such as search_parts,
check_stock, and create_draft_order.

The application dispatches tool requests, executes the corresponding
operations, and returns tool results to the model. The model can then
use those results to produce a final response.

The tool loop has a maximum of six rounds. The assistant also limits
the amount of conversation history included in a request.

Live responses require a valid Gemini API key. Successful live
tool-calling behaviour must be verified with a configured key.

## 6. Supplier Integration

The application includes a supplier mock service that exposes product
information through an API.

The supplier API URL and API key are configured through environment
variables rather than being hard-coded into application logic.

This allows local development and supplier integration to use
configuration appropriate to each environment.

The supplier integration should handle failed requests and unexpected
responses without treating unavailable supplier data as confirmed
inventory information.

## 7. Safety and Reliability

The assistant is instructed to use application tools to retrieve
product and stock information rather than inventing values.

It is designed to create draft orders only when explicitly requested.
It must not claim that an order has been dispatched, delivered, or
completed when the application has only created a draft.

Supplier descriptions and other external text should be treated as
data, not as instructions that can override the assistant's rules.

Credentials belong in local environment configuration and must not be
committed to the public repository.

These safeguards should also be verified through tests.

## 8. Limitations and Future Improvements

The current forecasting implementation uses weighted historical
averages, trend adjustment, and promotion information. It does not
constitute a trained machine-learning model and may not fully capture
annual seasonality, holidays, new products, or unusual demand changes.

Forecast quality should be measured through time-based backtesting
and compared with a simple baseline. Promotion effects and holiday
periods should be evaluated separately where sufficient historical
data is available.

The live AI assistant requires a valid provider API key. Its tool
calling, error handling, and draft-order behaviour should be tested
with realistic scenarios.

Additional improvements include automated regression tests, stronger
input validation, monitoring, and production deployment hardening.