#!/usr/bin/env python3
"""
Self-test for the shoes inventory tool.

Runs every feature against a temporary database (your real databases are not
touched) and prints PASS/FAIL for each check.

    python3 .claude/skills/shoes-inventory/scripts/selftest.py
"""
import contextlib
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inventory  # noqa: E402

DB = os.path.join(tempfile.mkdtemp(), "selftest.db")
results = []


def run(*args):
    """Run one CLI command; return (ok, parsed_output_or_error)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = inventory.main(["--db", DB, *args])
    text = out.getvalue() if code == 0 else err.getvalue()
    try:
        return code == 0, json.loads(text)
    except json.JSONDecodeError:
        return code == 0, text


def check(section, name, condition, detail=""):
    results.append(bool(condition))
    mark = "\033[32mPASS\033[0m" if condition else "\033[31mFAIL\033[0m"
    print(f"  {mark}  {name}" + (f"  ({detail})" if detail and not condition else ""))


def section(title):
    print(f"\n\033[1m{title}\033[0m")


# ---------------------------------------------------------------- setup
section("1. Database setup")
ok, r = run("init")
check("setup", "creates all 6 tables", ok and len(r["tables"]) == 6, r)
ok, r = run("supplier", "add", "Test Supplier", "--lead-time", "7")
check("setup", "adds a supplier", ok and r["lead_time_days"] == 7, r)

# ---------------------------------------------------------------- products
section("2. Products & variants (add / update / delete)")
ok, r = run("product", "add", "T-RUN", "--brand", "TestBrand", "--name", "Test Runner",
            "--category", "running", "--supplier", "Test Supplier", "--cost", "40", "--price", "100",
            "--sizes", "8,9,10", "--colors", "Black,White", "--initial-qty", "5")
check("products", "adds a style with a 3 size x 2 color run (6 SKUs)", ok and r["variants_created"] == 6, r)
check("products", "auto-generates SKUs like T-RUN-BLA-9", ok and "T-RUN-BLA-9" in r["skus"], r)
ok, r = run("product", "add", "T-RUN", "--brand", "X", "--name", "Dup")
check("products", "rejects a duplicate style code", not ok)
ok, r = run("variant", "add", "T-RUN", "--size", "11", "--color", "Black", "--initial-qty", "2")
check("products", "adds a single extra size", ok and r["sku"] == "T-RUN-BLA-11" and r["qty_on_hand"] == 2, r)
ok, r = run("product", "update", "T-RUN", "--price", "110")
check("products", "updates product price", ok and r["retail_price"] == 110, r)
ok, r = run("variant", "update", "T-RUN-BLA-9", "--reorder-point", "4", "--location", "B1")
check("products", "updates variant reorder point & location", ok and r["reorder_point"] == 4 and r["location"] == "B1", r)
ok, r = run("variant", "list", "--size", "9")
check("products", "filters variants by size", ok and len(r) == 2, r)
ok, r = run("variant", "delete", "T-RUN-WHI-10")
check("products", "delete archives by default (keeps history)", ok and "archived_variant" in r, r)
ok, r = run("variant", "delete", "T-RUN-WHI-10", "--hard")
check("products", "refuses hard delete of a SKU with history", not ok)

# ---------------------------------------------------------------- stock
section("3. Stock movements & adjustments")
ok, r = run("stock", "sell", "T-RUN-BLA-9", "2")
check("stock", "sale reduces stock 5 -> 3", ok and r["qty_before"] == 5 and r["qty_after"] == 3, r)
ok, r = run("stock", "sell", "T-RUN-BLA-9", "10")
check("stock", "blocks overselling (3 on hand, selling 10)", not ok and "only 3 on hand" in str(r), r)
ok, r = run("stock", "return", "T-RUN-BLA-9", "1", "--reason", "too small")
check("stock", "return adds stock 3 -> 4", ok and r["qty_after"] == 4, r)
ok, r = run("stock", "return", "T-RUN-BLA-9", "1", "--damaged")
check("stock", "damaged return nets to zero change", ok and r["damage"]["qty_after"] == 4, r)
ok, r = run("stock", "receive", "T-RUN-BLA-9", "6", "--ref", "INV-1")
check("stock", "receipt adds stock 4 -> 10", ok and r["qty_after"] == 10, r)
ok, r = run("stock", "damage", "T-RUN-BLA-9", "1", "--reason", "scuffed")
check("stock", "damage write-off 10 -> 9", ok and r["qty_after"] == 9, r)
ok, r = run("stock", "adjust", "T-RUN-BLA-9", "-2", "--reason", "missing")
check("stock", "signed adjustment -2 -> 7", ok and r["qty_after"] == 7, r)
ok, r = run("stock", "count", "T-RUN-BLA-9", "8", "--reason", "stock take")
check("stock", "physical count sets 7 -> 8 and values variance (+$40)",
      ok and r["qty_after"] == 8 and r["variance_value_at_cost"] == 40, r)
ok, r = run("stock", "history", "--sku", "T-RUN-BLA-9")
# initial, sale, return, damaged return (return + write-off = 2), receipt, damage, adjust, count
check("stock", "history logs every movement (9 entries)", ok and len(r) == 9, f"{len(r)} entries")
ok, r = run("query", "SELECT v.qty_on_hand = SUM(m.qty_change) AS matches FROM variants v "
            "JOIN stock_movements m ON m.variant_id = v.id WHERE v.sku = 'T-RUN-BLA-9'")
check("stock", "on-hand qty equals the sum of the movement log", ok and r[0]["matches"] == 1, r)

# ---------------------------------------------------------------- reorder
section("4. Reorder alerts & purchasing")
run("stock", "sell", "T-RUN-WHI-8", "5")          # sell out
run("stock", "sell", "T-RUN-WHI-9", "3")          # 2 left, below reorder point 3
ok, r = run("reorder", "alerts")
skus = {a["sku"]: a for a in r} if ok else {}
check("reorder", "flags the sold-out SKU as OUT_OF_STOCK",
      skus.get("T-RUN-WHI-8", {}).get("urgency") == "OUT_OF_STOCK", r)
check("reorder", "flags the low SKU (2 left)", "T-RUN-WHI-9" in skus, list(skus))
check("reorder", "does not flag healthy SKUs", "T-RUN-BLA-9" not in skus, list(skus))
ok, r = run("po", "create", "--from-alerts")
po = r["created"][0]["po_number"] if ok and r["created"] else None
check("reorder", "drafts a purchase order from alerts", ok and po, r)
ok, r = run("reorder", "alerts")
check("reorder", "no duplicate alerts once items are on order", ok and len(r) == 0, r)
ok, r = run("po", "submit", po)
check("reorder", "submits PO (draft -> ordered)", ok and r["status"] == "ordered", r)
ok, r = run("po", "receive", po, "--item", "T-RUN-WHI-8:3")
check("reorder", "partial delivery sets status 'partial'", ok and r["status"] == "partial", r)
ok, r = run("po", "receive", po, "--item", "T-RUN-WHI-8:999")
check("reorder", "blocks receiving more than was ordered", not ok)
ok, r = run("po", "receive", po)
check("reorder", "receiving the rest sets status 'received'", ok and r["status"] == "received", r)
ok, r = run("variant", "show", "T-RUN-WHI-8")
check("reorder", "received stock lands on the shelf", ok and r["qty_on_hand"] > 0, r)

# ---------------------------------------------------------------- analytics
section("5. Analytics")
ok, r = run("analytics", "summary")
check("analytics", "summary reports units sold & margin",
      ok and r["sales"]["units_sold"] == 10 and r["sales"]["gross_margin_pct"] is not None, r)
for name, args in [("valuation", ["--by", "brand"]), ("top-sellers", []), ("sales-trend", []),
                   ("slow-movers", []), ("size-curve", ["--product", "T-RUN"]),
                   ("turnover", []), ("shrinkage", [])]:
    ok, r = run("analytics", name, *args)
    check("analytics", f"{name} runs and returns data", ok and len(r) > 0, r)
ok, r = run("query", "DELETE FROM variants")
check("analytics", "custom query refuses to modify data", not ok)

# ---------------------------------------------------------------- result
passed, total = sum(results), len(results)
colour = "\033[32m" if passed == total else "\033[31m"
print(f"\n{colour}\033[1m{passed}/{total} checks passed\033[0m")
print(f"(temporary test database: {DB})")
sys.exit(0 if passed == total else 1)
