# demo.db — readable copy

`demo.db` (in the repo root) is a SQLite database, a binary file GitHub can't preview.
This folder has the same data in formats GitHub can display:

| File | What's in it |
|---|---|
| [suppliers.csv](suppliers.csv) | Shoe suppliers |
| [products.csv](products.csv) | Shoe styles |
| [variants.csv](variants.csv) | Size / color / width SKUs and stock on hand |
| [stock_movements.csv](stock_movements.csv) | Sales, returns, receipts, adjustments |
| [purchase_orders.csv](purchase_orders.csv) | Purchase orders |
| [po_items.csv](po_items.csv) | Line items on each purchase order |
| [demo.sql](demo.sql) | Full SQL dump — rebuild with `sqlite3 demo.db < demo.sql` |

To open `demo.db` itself, download it and use [DB Browser for SQLite](https://sqlitebrowser.org/) or `sqlite3 demo.db`.
