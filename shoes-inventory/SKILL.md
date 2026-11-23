---
name: shoes-inventory
description: Manage a shoe store's inventory in a local SQLite database — add, update, archive or delete shoe styles and their size/color/width variants (SKUs); record sales, returns, receipts, damage, manual adjustments and cycle counts; raise low-stock reorder alerts and create, submit and receive purchase orders with suppliers; and report analytics such as stock valuation, best/worst sellers, sales trends, slow movers, size curves, turnover and shrinkage. Use this skill whenever the user talks about shoe or footwear stock, SKUs, sizes on hand, "how many pairs", restocking, reordering, suppliers, purchase orders, stock counts, inventory value, or sales performance for a shoe shop — even if they don't say "database" or "inventory".
---

# Shoes Inventory Agent

You manage a shoe inventory stored in SQLite through one bundled CLI:
`scripts/inventory.py`. It uses only the Python standard library, so it runs
with any Python 3.8+ and needs no installation.

Use the CLI for all reads and writes instead of hand-written SQL. It keeps
the on-hand quantity and the movement ledger consistent. Every stock change
goes through one function that writes the new quantity and an audit row in
the same transaction, so the history always explains the current count.
Raw `UPDATE`s would break that link.

## Setup

```bash
INV="python3 <skill-dir>/scripts/inventory.py"
$INV init                    # creates tables if missing, shows row counts
$INV seed                    # optional: demo data with 90 days of history
python3 <skill-dir>/scripts/selftest.py   # 40 checks on a temp DB; run after changing inventory.py
```

- **Database file**: `--db PATH`, else `$SHOES_INVENTORY_DB`, else
  `./shoes_inventory.db` in the current directory. Find out which database
  the user means at the start, and pass `--db` explicitly on every call so
  you never write to the wrong file.
- **Global flags go before the command group**: `$INV --db shop.db --table variant list --low`.
- Output is JSON by default, which is the best format for you to read.
  `--table` prints plain text, which helps when you want to show raw rows.
  Errors go to stderr as `{"error": ...}` with exit code 1, and nothing is
  written when a command fails.

## Data model (short version)

- **supplier**: name, lead time in days (used for reorder maths).
- **product**: a style, identified by `style_code` (e.g. `SW-RUN1`), with brand, name,
  category, gender, supplier, default cost and retail price.
- **variant**: one sellable SKU, meaning a product in one size, color and
  width. It holds `qty_on_hand`, `reorder_point`, `reorder_qty`, a bin
  location, and optional cost and price overrides. SKUs are generated
  automatically as `STYLE-COL-SIZE[-WIDTH]`, e.g. `SW-RUN1-BLA-10.5`.
- **stock_movements**: an append-only ledger with the types `initial`,
  `receipt`, `sale`, `return`, `adjustment`, `damage` and `count`.
- **purchase_orders / po_items**: go from `draft` to `ordered` to
  `partial`/`received`. A PO can also be `cancelled`.

The full schema is in `references/schema.md`. Read it before you write a
custom `query`.

Commands that take a variant accept a SKU, a barcode or a numeric id.
Commands that take a product accept a style code or an id.

## 1. Manage products and variants

```bash
# New style with a full size × color run (creates every SKU in one go)
$INV product add SW-RUN1 --brand Stridewell --name "Velocity Runner" \
    --category running --gender men --supplier "Stridewell Footwear Co" \
    --cost 48 --price 110 --sizes 8,8.5,9,9.5,10,10.5,11,12 --colors Black,Blue \
    [--widths M,W] [--initial-qty 6] [--reorder-point 3] [--reorder-qty 6] [--location A1]

$INV variant add SW-RUN1 --size 13 --color Black [--width W --barcode 0123 --initial-qty 4]
$INV product list [--brand X --category running --gender women --search text]
$INV product show SW-RUN1                      # product + all its variants
$INV variant list [--low | --out] [--size 9 --color Black --brand X --product SW-RUN1 --search text]
$INV variant show SW-RUN1-BLA-10

$INV product update SW-RUN1 --price 120 [--cost --name --category --supplier --status]
$INV variant update SW-RUN1-BLA-10 --reorder-point 5 --reorder-qty 8 --location B3 [--price --cost --barcode]

$INV product delete SW-RUN1        # archives (default): hidden, history kept, reversible
$INV variant delete SW-RUN1-BLA-13 # archives one SKU
# --hard deletes permanently. It is refused if the item has movements or POs, unless --force is added.
```

**About deletes**: when the user says "delete", archive by default. Shoe
styles get discontinued, but their sales history still matters for
analytics and for answering "what did we sell last year". Use `--hard` only
when the user clearly wants the record gone (e.g. "it was a typo, remove it
completely"). Confirm with them before you add `--force`, because it
destroys movement history.

Quantities cannot be edited with `update`. Change stock only through the
stock commands below.

## 2. Stock movements and adjustments

| Situation | Command |
|---|---|
| Goods arrived without a PO | `stock receive SKU QTY [--cost 47.5 --ref INV-889]` |
| Sale | `stock sell SKU QTY [--price 99 --ref POS-1234]` |
| Customer return (resellable) | `stock return SKU QTY [--ref ...]` |
| Return that is unsellable | `stock return SKU QTY --damaged` (logs return + damage write-off) |
| Damaged / defective / display wear | `stock damage SKU QTY --reason "sole separation"` |
| Correction with a known delta | `stock adjust SKU -2 --reason "found in wrong bin"` (signed) |
| Physical count | `stock count SKU COUNTED [--reason "Nov cycle count"]` (sets absolute qty, records variance) |
| Audit trail | `stock history [--sku X --product STYLE --type sale --days 30 --limit 50]` |

Guidance:
- Always pass a `--reason` for `adjust`, `damage` and `count`. The
  shrinkage report groups by reason, and an adjustment without a reason
  can't be audited later. If the user doesn't give one, ask or write a
  clear summary of what they said.
- If the user tells you how many pairs they *have*, use `count`. If they
  tell you how many to *add or remove*, use `adjust`. Mixing these up is the
  most common way inventories drift.
- Sales that would push stock below zero are refused. That usually means a
  missed receipt or a wrong SKU, so check with the user before you retry
  with `--allow-negative`.
- When the user gives a batch of sales or counts (e.g. a pasted list), run
  one command per line, then report a compact summary of what changed.
  Don't paste every JSON result.

## 3. Reorder alerts and purchasing

```bash
$INV reorder alerts [--days 30 --cover-days 30 --supplier X]
```
A variant is flagged when `qty_on_hand + on_order <= reorder_point`. Each
alert includes the sales velocity over `--days`, the days of cover left,
the supplier lead time and an urgency level:
- `OUT_OF_STOCK`: no pairs on hand.
- `CRITICAL`: stock will run out before a new order could arrive (days of cover < lead time).
- `LOW`: at or below the reorder point.

`suggested_qty` brings stock up to whichever is larger:
`reorder_point + reorder_qty`, or the expected demand over
lead time + cover days plus the reorder point.

```bash
$INV po create --from-alerts [--supplier X]              # one draft PO per supplier from current alerts
$INV po create --supplier "Trailforge Supply" --item TF-BOOT3-BRO-7:6 --item TF-BOOT3-BRO-8:4:68.5
$INV po list [--status draft | --all]
$INV po show PO-20261121-001
$INV po submit PO-20261121-001                           # draft → ordered
$INV po receive PO-20261121-001                          # receive everything outstanding
$INV po receive PO-20261121-001 --item TF-BOOT3-BRO-7:4  # partial delivery → status partial
$INV po cancel PO-20261121-001
```

Guidance:
- Draft POs count as "on order", so running `--from-alerts` again won't
  create duplicates. Cancel a draft you don't want.
- Show the user the draft (SKUs, quantities, total cost) before you
  `submit` it. Submitting stands for placing a real order with a supplier.
- Receiving a PO creates `receipt` movements at the PO's unit cost.
  Over-receiving is refused unless you pass `--allow-over`.
- Size runs matter in footwear. If the alerts show only one size of a style
  is low, mention neighbouring sizes that are close to their reorder point
  too, since the user may want to fill the whole run in one order.

## 4. Analytics

| Question | Command |
|---|---|
| Overall health: stock value, sales, margin, returns, shrinkage, open POs | `analytics summary [--days 30]` |
| Where is money tied up? | `analytics valuation --by brand\|category\|gender\|supplier\|product\|size` |
| Best sellers / worst sellers | `analytics top-sellers [--by sku\|product\|brand\|category --metric units_sold\|net_revenue\|gross_profit --days 30 --limit 10 --bottom]` |
| Sales over time | `analytics sales-trend [--period day\|week\|month --days 90]` |
| Dead / slow stock | `analytics slow-movers [--days 60 --max-sold 0]` |
| Are we stocking the right sizes? | `analytics size-curve [--product X \| --category running \| --brand X] [--days 90]` |
| Turnover, days of supply, sell-through | `analytics turnover [--by product\|brand\|category\|sku --days 90]` |
| Losses from damage, counts, adjustments | `analytics shrinkage [--days 90]` |
| Anything else | `query "SELECT ..."` (read-only, single statement; see `references/schema.md`) |

How to present analytics:
- Lead with the answer and what it means, then show the numbers in a
  compact markdown table. Don't dump raw JSON. A shop owner wants to hear
  "Running shoes turn 4× a year but boots only 1.5×, and you have $3.7k
  tied up in boots", not every field.
- Point out what to do next. In `size-curve`, a positive `gap_pct` means
  that size sells faster than it is stocked (buy more), and a negative one
  means it is overstocked. Slow movers are candidates for markdowns.
  `CRITICAL` alerts should go on a PO today.
- Money values use the stored cost and retail prices. Revenue comes from the
  `unit_price` recorded on each sale, so it reflects discounts if prices
  were passed with `--price`.
- If the user asks for a chart or dashboard, build it from the JSON output.

## Typical workflows

**"What do I need to reorder?"** Run `reorder alerts` and summarise by
urgency and supplier. Offer to draft POs with `po create --from-alerts`,
show the drafts, and submit only after the user confirms.

**"Delivery from Trailforge arrived, 4 short on the size 7 boots."** Run
`po list` to find the open PO, then `po receive` with explicit `--item`
quantities for what actually arrived. Report that the PO is `partial` and
how many units are still outstanding.

**"Did a stock take, here are the counts."** Run `stock count` for each
line, then report the total variance in units and at cost, plus the SKUs
with the biggest discrepancies.

**"How's the business doing this month?"** Run `analytics summary --days 30`,
then top sellers, then reorder alerts. Give a short narrative with 2–3
recommendations.
