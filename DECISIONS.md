# DECISIONS.md

## 1. Track Selection
I selected the AI/ML track because it combines backend development, inventory forecasting, and an AI-powered dealer assistant.

## 2. Database Design
PostgreSQL is used as the primary database. Django models and migrations manage application data.

## 3. Inventory Forecasting
The forecasting component generates four weeks of demand predictions for 40 products, producing 160 SKU-week records in `ml/forecast.csv`.

## 4. Reorder Suggestions
Reorder suggestions use current inventory information and product data to help dealers identify products that may need replenishment.

## 5. AI Dealer Assistant
The assistant is implemented in `core/assistant.py`. It uses tool-based interactions to retrieve relevant product and inventory information.

## 6. Supplier Integration
The supplier mock service provides product data through an API. The supplier URL and API key are configured through environment variables.

## 7. Safety and Reliability
The assistant is designed to create draft orders rather than automatically placing orders. API credentials are configured through environment variables and should not be committed to the repository.

## 8. Limitations and Future Improvements
Live AI responses require a valid provider API key. Future improvements include additional automated tests, stronger production security, monitoring, and deployment configuration.