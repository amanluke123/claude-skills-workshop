# Database schema

SQLite, created automatically by `inventory.py` (any command). Timestamps are
UTC text `YYYY-MM-DD HH:MM:SS`, so `created_at >= datetime('now','-30 days')`
works for date filters.

## suppliers
| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT UNIQUE | |
| contact_email, phone, notes | TEXT | |
| lead_time_days | INTEGER | default 14; drives reorder urgency and PO expected date |
| created_at | TEXT | |

## products  (one row per style)
| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| style_code | TEXT UNIQUE | e.g. `SW-RUN1` |
| brand, name, category, gender | TEXT | category e.g. running/casual/boots/sandals/formal; gender men/women/unisex/kids |
| supplier_id | FK → suppliers.id | NULL if none |
| cost_price, retail_price | REAL | defaults for its variants |
| status | TEXT | `active` / `archived` |
| created_at, updated_at | TEXT | |

## variants  (one row per sellable SKU)
| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| product_id | FK → products.id | cascade delete |
| sku | TEXT UNIQUE | auto `STYLE-COL-SIZE[-WIDTH]` |
| size | TEXT | stored as text (`10.5`, `EU42`); sort with `CAST(size AS REAL)` |
| color | TEXT | |
| width | TEXT | default `M`; e.g. N, W, XW, 2E, 4E |
| barcode | TEXT UNIQUE | optional |
| location | TEXT | bin / shelf |
| qty_on_hand | INTEGER | changed only via stock_movements |
| reorder_point, reorder_qty | INTEGER | defaults 3 and 6 |
| cost_price, retail_price | REAL | NULL → use product's; effective value = `COALESCE(v.cost_price, p.cost_price)` |
| status | TEXT | `active` / `archived` |
| UNIQUE | (product_id, size, color, width) | |

## stock_movements  (append-only ledger)
| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| variant_id | FK → variants.id | |
| movement_type | TEXT | `initial`, `receipt`, `sale`, `return`, `adjustment`, `damage`, `count` |
| qty_change | INTEGER | signed: sales/damage negative, receipts/returns positive |
| qty_after | INTEGER | on-hand after this movement |
| unit_cost | REAL | cost at time of movement |
| unit_price | REAL | selling price (sales/returns) |
| reference | TEXT | PO number, receipt no., POS ticket |
| reason | TEXT | required in practice for adjustment/damage/count |
| created_at | TEXT | |

Useful identities:
- Units sold = `SUM(-qty_change) WHERE movement_type='sale'`
- Net revenue = `SUM(-qty_change * unit_price) WHERE movement_type IN ('sale','return')`
- COGS = same with `unit_cost`

## purchase_orders
| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| po_number | TEXT UNIQUE | `PO-YYYYMMDD-NNN` |
| supplier_id | FK → suppliers.id | |
| status | TEXT | `draft` → `ordered` → `partial` / `received`; or `cancelled` |
| expected_date | TEXT | defaults to today + supplier lead time |
| notes, created_at, updated_at | TEXT | |

## po_items
| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| po_id | FK → purchase_orders.id | cascade delete |
| variant_id | FK → variants.id | |
| qty_ordered, qty_received | INTEGER | outstanding = ordered − received |
| unit_cost | REAL | |
| UNIQUE | (po_id, variant_id) | |

"On order" for a variant = outstanding qty on POs with status `draft`, `ordered` or `partial`.

## Example custom queries

```sql
-- Stock matrix for one style (sizes × colors)
SELECT v.color, v.size, v.qty_on_hand FROM variants v JOIN products p ON p.id=v.product_id
WHERE p.style_code='SW-RUN1' ORDER BY v.color, CAST(v.size AS REAL);

-- Average selling price vs list price by brand (last 30 days)
SELECT p.brand, ROUND(AVG(m.unit_price),2) AS avg_sold, ROUND(AVG(COALESCE(v.retail_price,p.retail_price)),2) AS list
FROM stock_movements m JOIN variants v ON v.id=m.variant_id JOIN products p ON p.id=v.product_id
WHERE m.movement_type='sale' AND m.created_at >= datetime('now','-30 days') GROUP BY p.brand;

-- Return rate by product
SELECT p.name,
  SUM(CASE WHEN m.movement_type='return' THEN m.qty_change ELSE 0 END)*100.0 /
  NULLIF(SUM(CASE WHEN m.movement_type='sale' THEN -m.qty_change ELSE 0 END),0) AS return_pct
FROM stock_movements m JOIN variants v ON v.id=m.variant_id JOIN products p ON p.id=v.product_id
GROUP BY p.id ORDER BY return_pct DESC;
```
