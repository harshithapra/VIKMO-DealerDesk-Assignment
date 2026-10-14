# DECISIONS.md

## 1. Database Schema and Relationships

The application uses Django models and PostgreSQL for structured
application data.

The database contains four main models:

- Product: Stores SKU, product name, category, brand, vehicle fitment,
  price, stock, and product description.
- Dealer: Stores the dealer code, name, contact information, GSTIN,
  city, and credit limit.
- Order: Stores the dealer associated with an order, order number,
  status, subtotal, GST amount, total, and timestamps.
- OrderItem: Stores the product, quantity, unit price, and line total
  for each order item.

The relationships are implemented using Django foreign keys:

- Dealer to Order: One dealer can have multiple orders.
- Order to OrderItem: One order can contain multiple order items.
- Product to OrderItem: One product can appear in multiple order items.

The foreign-key deletion policies preserve data integrity.
Order.dealer uses PROTECT so a dealer referenced by an order cannot
be deleted. OrderItem.order uses CASCADE so deleting an order also
deletes its items. OrderItem.product uses PROTECT so a product
referenced by an order item cannot be deleted.

Product SKUs, dealer codes, and order numbers have unique constraints.
OrderItem also has a unique constraint on (order, product), preventing
the same product from being added twice to one order.

Prices and monetary totals use DecimalField instead of floating-point
fields, supporting accurate monetary calculations.

Implementation: core/models.py:4-16 (Product),
core/models.py:18-31 (Dealer),
core/models.py:33-65 (Order),
core/models.py:67-84 (OrderItem and constraints).


## 2. Product Retrieval

The assistant exposes a search_parts tool to retrieve relevant
products from the product catalogue.

The search implementation uses database queries against product
attributes, including SKU, name, brand, category, and vehicle fitment.
This provides a straightforward keyword-based retrieval method without
requiring an embedding model or vector database.

The search results contain catalogue information such as SKU, name,
brand, category, vehicle fitment, price, and stock. The assistant can
use the returned product records to answer a dealer's query.

This approach is simple to operate and keeps retrieval grounded in
the application database. However, keyword-based retrieval has
limitations: synonyms, misspellings, ambiguous vehicle names, and
requests that use different wording from the catalogue may not return
the best matches.

For example, a query containing a vehicle model may fail to find the
correct part if the relevant vehicle information is missing from the
catalogue or does not match the search terms.

A future improvement would be to combine keyword retrieval with
semantic embeddings and a ranking stage, while retaining database
validation for all returned product information.

Implementation: core/assistant.py, search_parts()


## 3. AI Tool-Calling Loop

The dealer assistant is implemented in core/assistant.py and uses
Google Gemini through the Google GenAI SDK.

The assistant exposes three tools:

1. search_parts: Searches the product catalogue.
2. check_stock: Retrieves current stock and price for an exact SKU.
3. create_draft_order: Creates a draft order when explicitly requested.

The tool-calling process is:

1. The client submits a POST request to /api/assistant/chat/.
2. The endpoint validates the request and identifies the dealer and
   conversation session.
3. The application sends the conversation and tool declarations to
   the configured Gemini model.
4. Gemini can request one of the declared tools.
5. The application dispatches the requested tool through execute_tool().
6. The tool executes application-side database operations.
7. The result is returned to the model so it can prepare a response.
8. The endpoint returns the final reply, cited SKUs, tool calls, and
   any actions performed.

The tool loop is limited to six rounds to prevent an unbounded sequence
of tool calls. Conversation history is also limited.

The application reports tool calls in the response, making it possible
to inspect which tools were requested.

Tool calling is important because the language model decides which
application operation is needed, while the application executes that
operation against its own data.

Implementation: core/assistant.py,
TOOL_DECLARATIONS, execute_tool(), and assistant_chat()


## 4. Live Stock and Price Grounding

The assistant must not rely on the language model's prior knowledge
to determine current inventory or catalogue prices.

The check_stock() function queries the Product model using the
requested SKU and returns the product's SKU, name, price, stock, and
vehicle fitment from the database.

The search_parts() function also retrieves catalogue records through
database queries.

The application returns the results to Gemini as tool results. This
allows the model to formulate a natural-language response using
application data instead of inventing stock quantities or prices.

During testing, SKU BRK-1001 returned the following database values:

- Product: Brake Shoe Set - Suzuki Gixxer SF
- Price value: 514.25
- Stock: 0
- Vehicle fitment: Suzuki Gixxer SF

The direct check_stock() function and an AI assistant request both
returned these values successfully.

The price field does not itself specify a currency symbol, so the
assistant should not assume a currency unless it is defined by the
application's requirements.

This design reduces the risk of fabricated inventory information.
However, the application must still handle provider errors, malformed
tool calls, and database failures. A failed provider request should
not be presented as a successful stock lookup.

Implementation: core/assistant.py, check_stock(), search_parts(),
and assistant_chat()


## 5. Untrusted Supplier Descriptions and Safety

Product descriptions may contain text supplied by external sources.
Such text must be treated as data, not as instructions that can
override the assistant's system instructions.

The assistant's system instructions direct it not to invent product
names, SKUs, stock quantities, or prices. They also restrict order
creation to draft orders and prohibit claims that an order has been
dispatched, delivered, or completed when only a draft exists.

The application defines a limited set of tools instead of allowing
the language model to execute arbitrary database operations.
Tool execution is dispatched through execute_tool().

The create_draft_order() function validates the dealer, order items,
SKUs, and quantities before creating an order. It uses database
operations to retrieve products and their current prices.

These measures reduce the risk of incorrect or unsafe actions.

However, instructions in a prompt are not a complete defence against
prompt injection. The model may still be influenced by malicious
catalogue text. A stronger implementation would separate untrusted
retrieved content from trusted instructions, validate tool arguments
strictly, add adversarial tests, and enforce all business rules in
application code rather than relying on the model.

Credentials must remain in environment configuration and must not
be committed to the public repository.

Implementation: core/assistant.py,
SYSTEM_INSTRUCTION, execute_tool(), and create_draft_order()


## 6. Forecasting Approach and Validation

The forecasting component generates four weeks of demand predictions
for 40 SKUs and stores them in ml/forecast.csv.

The current approach uses weighted historical demand averages over
four windows: 4, 8, 13, and 26 weeks. The respective weights are
0.4, 0.3, 0.2, and 0.1.

A trend adjustment compares recent demand with the preceding period.
The trend ratio is capped between 0.7 and 1.5 to limit extreme
adjustments. Promotion information is also used to adjust predictions
for planned promotional weeks.

This is a weighted historical forecasting approach rather than a
trained machine-learning model.

The forecast file was checked for its structure and contains 160
records covering 40 unique SKUs across four weekly forecast periods.
The checked forecast values were non-negative.

These checks establish the structure of the forecast file, but they
do not establish forecast accuracy.

A proper validation process should use rolling-origin or time-based
backtesting. Each validation forecast must use only information that
would have been available at the forecast date. Future sales must not
be used to calculate historical predictions.

The forecasts should be compared with the assignment's baselines:
last observed value, recent average, and the same week last year.
MAE and WAPE can be used to measure forecast errors.

I have not established a verified backtesting score or demonstrated
that the current forecast beats the required baselines. This remains
an area for improvement.

Implementation: ml/forecasting.py:104-195 (forecast_sku),
ml/forecasting.py:204-247 (main), and ml/forecast.csv.
The exact historical cutoff and validation logic must be verified
against the implementation before claiming that future-data leakage
is prevented.


## 7. Weakest SKUs, Promotions, Diwali, Rare Demand, and New Products

The forecasting component uses multiple historical demand windows,
a bounded trend adjustment, and promotion information.

The shorter historical window gives more weight to recent demand,
while longer windows provide additional historical context. The
trend cap limits the magnitude of the trend adjustment.

Promotions are included as an adjustment when planned promotion
information is available for the forecast period.

The implementation does not constitute a trained seasonal model.
Consequently, annual seasonality and a moving festive period such as
Diwali may not be fully represented by the historical averages and
trend adjustment alone.

Rarely sold SKUs can be difficult to forecast because long periods
of zero demand may be interrupted by occasional sales. New SKUs
present a different problem because they have limited or no sales
history.

The current forecast file was checked for record count and
non-negative values. However, I have not calculated per-SKU backtest
errors, so I cannot reliably identify the worst-performing SKUs or
claim that the model handles every special case well.

A future improvement would be to report per-SKU MAE and WAPE,
evaluate promotional and festive periods separately, and compare
the current method with seasonal-naive and intermittent-demand
baselines. New products would need an explicit fallback based on
available product or category information.

Implementation: ml/forecasting.py:53-94 (sales, promotions,
and forecast SKU loading), ml/forecasting.py:104-195
(forecast logic), and the relevant input data files.


## 8. Weakest Part and Future Improvements

The main limitation of the forecasting component is that its current
weighted historical approach has not been validated against the
assignment's baselines using a verified time-based backtest.

The method includes trend and promotion adjustments, but annual
seasonality, Diwali-related demand changes, intermittent sales, and
new products may require more specialised handling.

The AI assistant also depends on an external LLM provider, so
temporary service unavailability can prevent a request from
completing even when the application's database tools work correctly.

With two additional days, I would prioritise:

1. Implementing and running time-based forecast backtests without
   future-data leakage.
2. Comparing forecasts against all required baselines and reporting
   overall and per-SKU errors.
3. Testing the exact reorder-suggestion formula against the API
   contract, including live stock and supplier lead times.
4. Adding regression tests for assistant tool calls, invalid inputs,
   provider errors, and draft-order safety.
5. Testing supplier-description prompt injection and verifying that
   the application never treats external text as trusted instructions.
6. Running the AI/ML smoke test on a freshly seeded PostgreSQL
   database and resolving every failure.
7. Adding exact file and line references to this document so each
   implementation decision can be verified quickly.

The goal is to improve correctness, reliability, and the ability to
explain every technical decision, rather than adding features before
the required behaviour has been validated.