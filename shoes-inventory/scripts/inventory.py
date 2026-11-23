#!/usr/bin/env python3
"""
Shoe inventory CLI backed by SQLite (Python standard library only).

Every command prints JSON to stdout (or a plain table with --table).
Errors print {"error": "..."} to stderr and exit with status 1.

Database location: --db PATH, else $SHOES_INVENTORY_DB, else ./shoes_inventory.db
Global flags go BEFORE the command group:
    python3 inventory.py --db shop.db --table variant list --low
"""
import argparse
import json
import math
import os
import random
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS suppliers (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    contact_email   TEXT,
    phone           TEXT,
    lead_time_days  INTEGER NOT NULL DEFAULT 14,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY,
    style_code    TEXT NOT NULL UNIQUE,
    brand         TEXT NOT NULL,
    name          TEXT NOT NULL,
    category      TEXT,
    gender        TEXT,
    supplier_id   INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    cost_price    REAL NOT NULL DEFAULT 0,
    retail_price  REAL NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS variants (
    id             INTEGER PRIMARY KEY,
    product_id     INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    sku            TEXT NOT NULL UNIQUE,
    size           TEXT NOT NULL,
    color          TEXT NOT NULL DEFAULT '',
    width          TEXT NOT NULL DEFAULT 'M',
    barcode        TEXT UNIQUE,
    location       TEXT,
    qty_on_hand    INTEGER NOT NULL DEFAULT 0,
    reorder_point  INTEGER NOT NULL DEFAULT 3,
    reorder_qty    INTEGER NOT NULL DEFAULT 6,
    cost_price     REAL,
    retail_price   REAL,
    status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (product_id, size, color, width)
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id             INTEGER PRIMARY KEY,
    variant_id     INTEGER NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    movement_type  TEXT NOT NULL CHECK (movement_type IN
                   ('initial','receipt','sale','return','adjustment','damage','count')),
    qty_change     INTEGER NOT NULL,
    qty_after      INTEGER NOT NULL,
    unit_cost      REAL,
    unit_price     REAL,
    reference      TEXT,
    reason         TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_mov_variant ON stock_movements(variant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_mov_type ON stock_movements(movement_type, created_at);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id             INTEGER PRIMARY KEY,
    po_number      TEXT NOT NULL UNIQUE,
    supplier_id    INTEGER NOT NULL REFERENCES suppliers(id),
    status         TEXT NOT NULL DEFAULT 'draft' CHECK (status IN
                   ('draft','ordered','partial','received','cancelled')),
    expected_date  TEXT,
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS po_items (
    id            INTEGER PRIMARY KEY,
    po_id         INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    variant_id    INTEGER NOT NULL REFERENCES variants(id),
    qty_ordered   INTEGER NOT NULL CHECK (qty_ordered > 0),
    qty_received  INTEGER NOT NULL DEFAULT 0,
    unit_cost     REAL NOT NULL DEFAULT 0,
    UNIQUE (po_id, variant_id)
);
"""

OPEN_PO = "('draft','ordered','partial')"

VARIANT_VIEW = f"""
SELECT v.id, v.sku, p.style_code, p.brand, p.name AS product, p.category, p.gender,
       v.size, v.color, v.width, v.location, v.barcode,
       v.qty_on_hand, v.reorder_point, v.reorder_qty,
       COALESCE(v.cost_price, p.cost_price)     AS cost_price,
       COALESCE(v.retail_price, p.retail_price) AS retail_price,
       v.status, s.name AS supplier, s.id AS supplier_id,
       COALESCE(s.lead_time_days, 14) AS lead_time_days,
       (SELECT COALESCE(SUM(pi.qty_ordered - pi.qty_received), 0)
          FROM po_items pi JOIN purchase_orders po ON po.id = pi.po_id
         WHERE pi.variant_id = v.id AND po.status IN {OPEN_PO}) AS on_order
FROM variants v
JOIN products p ON p.id = v.product_id
LEFT JOIN suppliers s ON s.id = p.supplier_id
"""


class InvError(Exception):
    pass


# --------------------------------------------------------------------------- helpers

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def connect(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def rows(cur):
    return [dict(r) for r in cur.fetchall()]


def one(cur):
    r = cur.fetchone()
    return dict(r) if r else None


def split_list(s):
    return [x.strip() for x in s.split(",") if x.strip()] if s else []


def since(days):
    return f"-{int(days)} days"


def resolve_supplier(con, ident):
    r = one(con.execute("SELECT * FROM suppliers WHERE name = ? COLLATE NOCASE", (ident,)))
    if not r and str(ident).isdigit():
        r = one(con.execute("SELECT * FROM suppliers WHERE id = ?", (int(ident),)))
    if not r:
        raise InvError(f"Supplier not found: {ident}")
    return r


def resolve_product(con, ident):
    r = one(con.execute("SELECT * FROM products WHERE style_code = ? COLLATE NOCASE", (ident,)))
    if not r and str(ident).isdigit():
        r = one(con.execute("SELECT * FROM products WHERE id = ?", (int(ident),)))
    if not r:
        raise InvError(f"Product not found (use style code or id): {ident}")
    return r


def resolve_variant(con, ident):
    r = one(con.execute(VARIANT_VIEW + " WHERE v.sku = ? COLLATE NOCASE", (ident,)))
    if not r:
        r = one(con.execute(VARIANT_VIEW + " WHERE v.barcode = ?", (ident,)))
    if not r and str(ident).isdigit():
        r = one(con.execute(VARIANT_VIEW + " WHERE v.id = ?", (int(ident),)))
    if not r:
        raise InvError(f"Variant not found (use SKU, barcode or id): {ident}")
    return r


def make_sku(con, style, color, size, width):
    def build(color_part):
        parts = [style.upper()]
        if color_part:
            parts.append(color_part)
        parts.append(str(size).replace(" ", "").upper())
        if width and width.upper() != "M":
            parts.append(width.upper())
        return "-".join(parts)

    clean = re.sub(r"[^A-Za-z0-9]", "", color or "").upper()
    sku = build(clean[:3])
    if con.execute("SELECT 1 FROM variants WHERE sku = ?", (sku,)).fetchone():
        sku = build(clean)
    return sku


def apply_movement(con, variant_id, mtype, delta, reference=None, reason=None,
                   unit_cost=None, unit_price=None, allow_negative=False, at=None):
    """The single place stock levels change. Writes the ledger row and the new on-hand qty."""
    r = con.execute("SELECT qty_on_hand, sku FROM variants WHERE id = ?", (variant_id,)).fetchone()
    if not r:
        raise InvError(f"Variant id {variant_id} not found")
    new_qty = r["qty_on_hand"] + delta
    if new_qty < 0 and not allow_negative:
        raise InvError(f"{r['sku']}: only {r['qty_on_hand']} on hand, cannot remove {-delta} "
                       f"(pass --allow-negative to override)")
    ts = at or now_utc()
    con.execute("UPDATE variants SET qty_on_hand = ?, updated_at = ? WHERE id = ?",
                (new_qty, ts, variant_id))
    cur = con.execute(
        "INSERT INTO stock_movements (variant_id, movement_type, qty_change, qty_after, unit_cost,"
        " unit_price, reference, reason, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (variant_id, mtype, delta, new_qty, unit_cost, unit_price, reference, reason, ts))
    return {"movement_id": cur.lastrowid, "sku": r["sku"], "type": mtype,
            "qty_change": delta, "qty_before": r["qty_on_hand"], "qty_after": new_qty}


def parse_items(specs):
    """'SKU:QTY' or 'SKU:QTY:UNIT_COST' -> list of tuples."""
    items = []
    for spec in specs or []:
        parts = spec.split(":")
        if len(parts) not in (2, 3):
            raise InvError(f"Bad item '{spec}', expected SKU:QTY or SKU:QTY:COST")
        try:
            qty = int(parts[1])
            cost = float(parts[2]) if len(parts) == 3 else None
        except ValueError:
            raise InvError(f"Bad number in item '{spec}'")
        if qty <= 0:
            raise InvError(f"Quantity must be positive in '{spec}'")
        items.append((parts[0], qty, cost))
    return items


def sales_velocity(con, variant_id, days):
    sold = con.execute(
        "SELECT COALESCE(SUM(-qty_change),0) FROM stock_movements WHERE variant_id = ? "
        "AND movement_type = 'sale' AND created_at >= datetime('now', ?)",
        (variant_id, since(days))).fetchone()[0]
    return sold, sold / days if days else 0


# --------------------------------------------------------------------------- init / seed / query

def cmd_init(con, a):
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    return {"database": os.path.abspath(a.db), "tables": counts}


def cmd_seed(con, a):
    if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] and not a.force:
        raise InvError("Database already has products; pass --force to add sample data anyway")
    rnd = random.Random(42)
    sups = [("Stridewell Footwear Co", "orders@stridewell.example", 10),
            ("Trailforge Supply", "po@trailforge.example", 21)]
    sup_ids = []
    for name, email, lead in sups:
        sup_ids.append(con.execute(
            "INSERT INTO suppliers (name, contact_email, lead_time_days) VALUES (?,?,?)",
            (name, email, lead)).lastrowid)
    catalog = [
        ("SW-RUN1", "Stridewell", "Velocity Runner", "running", "men", 0, 48, 110,
         ["8", "8.5", "9", "9.5", "10", "10.5", "11", "12"], ["Black", "Blue"]),
        ("SW-CAS2", "Stridewell", "Daily Canvas Low", "casual", "unisex", 0, 18, 45,
         ["6", "7", "8", "9", "10", "11"], ["White", "Navy"]),
        ("TF-BOOT3", "Trailforge", "Ridge Hiker Boot", "boots", "women", 1, 70, 165,
         ["6", "6.5", "7", "7.5", "8", "8.5", "9"], ["Brown"]),
        ("TF-SAN4", "Trailforge", "Creek Sport Sandal", "sandals", "unisex", 1, 15, 39,
         ["5", "6", "7", "8", "9", "10", "11", "12"], ["Grey", "Green"]),
    ]
    start = datetime.now(timezone.utc) - timedelta(days=90)
    fmt = "%Y-%m-%d %H:%M:%S"
    variant_ids = []
    for style, brand, name, cat, gender, si, cost, price, sizes, colors in catalog:
        pid = con.execute(
            "INSERT INTO products (style_code, brand, name, category, gender, supplier_id,"
            " cost_price, retail_price) VALUES (?,?,?,?,?,?,?,?)",
            (style, brand, name, cat, gender, sup_ids[si], cost, price)).lastrowid
        mid = len(sizes) / 2
        for c in colors:
            for idx, s in enumerate(sizes):
                sku = make_sku(con, style, c, s, "M")
                vid = con.execute(
                    "INSERT INTO variants (product_id, sku, size, color, reorder_point, reorder_qty,"
                    " location) VALUES (?,?,?,?,?,?,?)",
                    (pid, sku, s, c, 3, 6, f"A{si + 1}-{idx + 1:02d}")).lastrowid
                popularity = max(0.05, 0.35 - abs(idx - mid) * 0.07) * (1.4 if cat == "running" else 1)
                if cat == "boots":
                    popularity *= 0.5
                variant_ids.append((vid, popularity, cost, price))
                apply_movement(con, vid, "initial", rnd.randint(6, 16), reference="SEED",
                               unit_cost=cost, at=start.strftime(fmt))
    for day in range(1, 90):
        ts = (start + timedelta(days=day, hours=rnd.randint(9, 19))).strftime(fmt)
        for vid, pop, cost, price in variant_ids:
            if rnd.random() < pop * 0.35:
                q = con.execute("SELECT qty_on_hand FROM variants WHERE id=?", (vid,)).fetchone()[0]
                if q > 0:
                    apply_movement(con, vid, "sale", -1, reference=f"POS-{day:03d}",
                                   unit_cost=cost, unit_price=price, at=ts)
                    if rnd.random() < 0.04:
                        apply_movement(con, vid, "return", 1, reference=f"RET-{day:03d}",
                                       reason="wrong size", unit_cost=cost, unit_price=price, at=ts)
            if day == 45 and pop > 0.25:
                apply_movement(con, vid, "receipt", 6, reference="PO-SEED-1", unit_cost=cost, at=ts)
        if day == 60:
            vid, _, cost, _ = variant_ids[3]
            q = con.execute("SELECT qty_on_hand FROM variants WHERE id=?", (vid,)).fetchone()[0]
            if q > 0:
                apply_movement(con, vid, "damage", -1, reason="scuffed display pair",
                               unit_cost=cost, at=ts)
    return {"seeded": True, "suppliers": len(sups), "products": len(catalog),
            "variants": len(variant_ids)}


def cmd_query(con, a):
    sql = a.sql.strip().rstrip(";")
    if not re.match(r"^(select|with)\b", sql, re.I) or ";" in sql:
        raise InvError("Only a single read-only SELECT/WITH statement is allowed")
    ro = sqlite3.connect(f"file:{os.path.abspath(a.db)}?mode=ro", uri=True)
    ro.row_factory = sqlite3.Row
    try:
        return rows(ro.execute(sql))
    finally:
        ro.close()


# --------------------------------------------------------------------------- suppliers

def cmd_supplier_add(con, a):
    sid = con.execute(
        "INSERT INTO suppliers (name, contact_email, phone, lead_time_days, notes) VALUES (?,?,?,?,?)",
        (a.name, a.email, a.phone, a.lead_time, a.notes)).lastrowid
    return one(con.execute("SELECT * FROM suppliers WHERE id=?", (sid,)))


def cmd_supplier_list(con, a):
    return rows(con.execute(
        "SELECT s.*, (SELECT COUNT(*) FROM products p WHERE p.supplier_id = s.id) AS products"
        " FROM suppliers s ORDER BY s.name"))


def cmd_supplier_update(con, a):
    s = resolve_supplier(con, a.supplier)
    fields = {"name": a.name, "contact_email": a.email, "phone": a.phone,
              "lead_time_days": a.lead_time, "notes": a.notes}
    sets = {k: v for k, v in fields.items() if v is not None}
    if not sets:
        raise InvError("Nothing to update")
    con.execute(f"UPDATE suppliers SET {', '.join(k + '=?' for k in sets)} WHERE id=?",
                (*sets.values(), s["id"]))
    return one(con.execute("SELECT * FROM suppliers WHERE id=?", (s["id"],)))


def cmd_supplier_delete(con, a):
    s = resolve_supplier(con, a.supplier)
    pos = con.execute("SELECT COUNT(*) FROM purchase_orders WHERE supplier_id=?", (s["id"],)).fetchone()[0]
    if pos:
        raise InvError(f"Supplier has {pos} purchase order(s); keep it for history or cancel/remove them first")
    con.execute("DELETE FROM suppliers WHERE id=?", (s["id"],))
    return {"deleted_supplier": s["name"], "note": "Products from this supplier now have no supplier"}


# --------------------------------------------------------------------------- products

def create_variant(con, pid, style, size, color, width, rp, rq, initial, location,
                   barcode=None, cost=None, price=None):
    sku = make_sku(con, style, color, size, width)
    vid = con.execute(
        "INSERT INTO variants (product_id, sku, size, color, width, reorder_point, reorder_qty,"
        " location, barcode, cost_price, retail_price) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (pid, sku, size, color or "", width or "M", rp, rq, location, barcode, cost, price)).lastrowid
    if initial:
        unit_cost = cost if cost is not None else con.execute(
            "SELECT cost_price FROM products WHERE id=?", (pid,)).fetchone()[0]
        apply_movement(con, vid, "initial", initial, reference="initial stock", unit_cost=unit_cost)
    return sku


def cmd_product_add(con, a):
    sup = resolve_supplier(con, a.supplier)["id"] if a.supplier else None
    pid = con.execute(
        "INSERT INTO products (style_code, brand, name, category, gender, supplier_id, cost_price,"
        " retail_price) VALUES (?,?,?,?,?,?,?,?)",
        (a.style_code.upper(), a.brand, a.name, a.category, a.gender, sup, a.cost, a.price)).lastrowid
    skus = []
    sizes = split_list(a.sizes)
    for c in split_list(a.colors) or [""]:
        for s in sizes:
            for w in split_list(a.widths) or ["M"]:
                skus.append(create_variant(con, pid, a.style_code, s, c, w, a.reorder_point,
                                           a.reorder_qty, a.initial_qty, a.location))
    return {"product": one(con.execute("SELECT * FROM products WHERE id=?", (pid,))),
            "variants_created": len(skus), "skus": skus}


def cmd_product_list(con, a):
    where, params = [], []
    if not a.include_archived:
        where.append("p.status = 'active'")
    for col, val in (("p.brand", a.brand), ("p.category", a.category), ("p.gender", a.gender)):
        if val:
            where.append(f"{col} = ? COLLATE NOCASE")
            params.append(val)
    if a.search:
        where.append("(p.name LIKE ? OR p.style_code LIKE ? OR p.brand LIKE ?)")
        params += [f"%{a.search}%"] * 3
    sql = ("SELECT p.id, p.style_code, p.brand, p.name, p.category, p.gender, s.name AS supplier,"
           " p.cost_price, p.retail_price, p.status, COUNT(v.id) AS variants,"
           " COALESCE(SUM(v.qty_on_hand),0) AS units_on_hand"
           " FROM products p LEFT JOIN suppliers s ON s.id = p.supplier_id"
           " LEFT JOIN variants v ON v.product_id = p.id AND v.status = 'active'")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY p.id ORDER BY p.brand, p.name"
    return rows(con.execute(sql, params))


def cmd_product_show(con, a):
    p = resolve_product(con, a.product)
    vs = rows(con.execute(VARIANT_VIEW + " WHERE v.product_id = ? ORDER BY v.color, CAST(v.size AS REAL), v.width",
                          (p["id"],)))
    return {"product": p, "variants": vs}


def cmd_product_update(con, a):
    p = resolve_product(con, a.product)
    fields = {"brand": a.brand, "name": a.name, "category": a.category, "gender": a.gender,
              "cost_price": a.cost, "retail_price": a.price, "status": a.status}
    if a.supplier:
        fields["supplier_id"] = resolve_supplier(con, a.supplier)["id"]
    sets = {k: v for k, v in fields.items() if v is not None}
    if not sets:
        raise InvError("Nothing to update")
    sets["updated_at"] = now_utc()
    con.execute(f"UPDATE products SET {', '.join(k + '=?' for k in sets)} WHERE id=?",
                (*sets.values(), p["id"]))
    return one(con.execute("SELECT * FROM products WHERE id=?", (p["id"],)))


def cmd_product_delete(con, a):
    p = resolve_product(con, a.product)
    if not a.hard:
        con.execute("UPDATE products SET status='archived', updated_at=? WHERE id=?", (now_utc(), p["id"]))
        con.execute("UPDATE variants SET status='archived', updated_at=? WHERE product_id=?", (now_utc(), p["id"]))
        return {"archived_product": p["style_code"], "note": "History kept; restore with product update --status active"}
    moves = con.execute("SELECT COUNT(*) FROM stock_movements m JOIN variants v ON v.id=m.variant_id"
                        " WHERE v.product_id=?", (p["id"],)).fetchone()[0]
    po = con.execute("SELECT COUNT(*) FROM po_items pi JOIN variants v ON v.id=pi.variant_id"
                     " WHERE v.product_id=?", (p["id"],)).fetchone()[0]
    if po:
        raise InvError("Product appears on purchase orders; archive it instead of hard-deleting")
    if moves and not a.force:
        raise InvError(f"Product has {moves} stock movements; hard delete would erase history. "
                       "Archive instead, or add --force")
    con.execute("DELETE FROM products WHERE id=?", (p["id"],))
    return {"deleted_product": p["style_code"], "movements_deleted": moves}


# --------------------------------------------------------------------------- variants

def cmd_variant_add(con, a):
    p = resolve_product(con, a.product)
    sku = create_variant(con, p["id"], p["style_code"], a.size, a.color, a.width, a.reorder_point,
                         a.reorder_qty, a.initial_qty, a.location, a.barcode, a.cost, a.price)
    return resolve_variant(con, sku)


def cmd_variant_list(con, a):
    where, params = [], []
    if not a.include_archived:
        where.append("v.status = 'active'")
    for col, val in (("p.brand", a.brand), ("p.category", a.category), ("v.size", a.size),
                     ("v.color", a.color), ("p.style_code", a.product), ("p.gender", a.gender)):
        if val:
            where.append(f"{col} = ? COLLATE NOCASE")
            params.append(val)
    if a.search:
        where.append("(v.sku LIKE ? OR p.name LIKE ? OR p.brand LIKE ?)")
        params += [f"%{a.search}%"] * 3
    if a.out:
        where.append("v.qty_on_hand <= 0")
    elif a.low:
        where.append("v.qty_on_hand <= v.reorder_point")
    sql = VARIANT_VIEW + (" WHERE " + " AND ".join(where) if where else "")
    sql += " ORDER BY p.brand, p.name, v.color, CAST(v.size AS REAL)"
    return rows(con.execute(sql, params))


def cmd_variant_show(con, a):
    return resolve_variant(con, a.sku)


def cmd_variant_update(con, a):
    v = resolve_variant(con, a.sku)
    fields = {"size": a.size, "color": a.color, "width": a.width, "barcode": a.barcode,
              "location": a.location, "reorder_point": a.reorder_point, "reorder_qty": a.reorder_qty,
              "cost_price": a.cost, "retail_price": a.price, "status": a.status}
    sets = {k: v_ for k, v_ in fields.items() if v_ is not None}
    if not sets:
        raise InvError("Nothing to update (quantities change only through stock commands)")
    sets["updated_at"] = now_utc()
    con.execute(f"UPDATE variants SET {', '.join(k + '=?' for k in sets)} WHERE id=?",
                (*sets.values(), v["id"]))
    return resolve_variant(con, v["id"])


def cmd_variant_delete(con, a):
    v = resolve_variant(con, a.sku)
    if not a.hard:
        con.execute("UPDATE variants SET status='archived', updated_at=? WHERE id=?", (now_utc(), v["id"]))
        return {"archived_variant": v["sku"], "qty_on_hand": v["qty_on_hand"]}
    if con.execute("SELECT 1 FROM po_items WHERE variant_id=?", (v["id"],)).fetchone():
        raise InvError("Variant appears on purchase orders; archive it instead")
    moves = con.execute("SELECT COUNT(*) FROM stock_movements WHERE variant_id=?", (v["id"],)).fetchone()[0]
    if moves and not a.force:
        raise InvError(f"Variant has {moves} stock movements; archive instead, or add --force")
    con.execute("DELETE FROM variants WHERE id=?", (v["id"],))
    return {"deleted_variant": v["sku"], "movements_deleted": moves}


# --------------------------------------------------------------------------- stock movements

def cmd_stock_receive(con, a):
    v = resolve_variant(con, a.sku)
    return apply_movement(con, v["id"], "receipt", a.qty, a.ref, a.reason,
                          unit_cost=a.cost if a.cost is not None else v["cost_price"])


def cmd_stock_sell(con, a):
    v = resolve_variant(con, a.sku)
    return apply_movement(con, v["id"], "sale", -a.qty, a.ref, a.reason, unit_cost=v["cost_price"],
                          unit_price=a.price if a.price is not None else v["retail_price"],
                          allow_negative=a.allow_negative)


def cmd_stock_return(con, a):
    v = resolve_variant(con, a.sku)
    res = apply_movement(con, v["id"], "return", a.qty, a.ref, a.reason, unit_cost=v["cost_price"],
                         unit_price=a.price if a.price is not None else v["retail_price"])
    if a.damaged:
        res = {"return": res, "damage": apply_movement(con, v["id"], "damage", -a.qty, a.ref,
                                                         "returned damaged", unit_cost=v["cost_price"])}
    return res


def cmd_stock_adjust(con, a):
    if a.qty == 0:
        raise InvError("Adjustment quantity cannot be zero")
    v = resolve_variant(con, a.sku)
    return apply_movement(con, v["id"], "adjustment", a.qty, a.ref, a.reason,
                          unit_cost=v["cost_price"], allow_negative=a.allow_negative)


def cmd_stock_damage(con, a):
    v = resolve_variant(con, a.sku)
    return apply_movement(con, v["id"], "damage", -a.qty, a.ref, a.reason, unit_cost=v["cost_price"])


def cmd_stock_count(con, a):
    if a.counted < 0:
        raise InvError("Counted quantity cannot be negative")
    v = resolve_variant(con, a.sku)
    delta = a.counted - v["qty_on_hand"]
    if delta == 0:
        return {"sku": v["sku"], "qty_on_hand": v["qty_on_hand"], "variance": 0, "note": "Count matches"}
    res = apply_movement(con, v["id"], "count", delta, a.ref, a.reason or "cycle count",
                         unit_cost=v["cost_price"])
    res["variance_value_at_cost"] = round(delta * (v["cost_price"] or 0), 2)
    return res


def cmd_stock_history(con, a):
    where, params = ["m.created_at >= datetime('now', ?)"], [since(a.days)]
    if a.sku:
        where.append("v.id = ?")
        params.append(resolve_variant(con, a.sku)["id"])
    if a.product:
        where.append("v.product_id = ?")
        params.append(resolve_product(con, a.product)["id"])
    if a.type:
        where.append("m.movement_type = ?")
        params.append(a.type)
    params.append(a.limit)
    return rows(con.execute(
        "SELECT m.id, m.created_at, v.sku, m.movement_type, m.qty_change, m.qty_after, m.unit_cost,"
        " m.unit_price, m.reference, m.reason FROM stock_movements m JOIN variants v ON v.id = m.variant_id"
        f" WHERE {' AND '.join(where)} ORDER BY m.created_at DESC, m.id DESC LIMIT ?", params))


# --------------------------------------------------------------------------- reorder & purchasing

def reorder_candidates(con, days, cover_days, supplier=None, include_all=False):
    params = []
    sql = VARIANT_VIEW + " WHERE v.status='active' AND p.status='active'"
    if supplier:
        sql += " AND p.supplier_id = ?"
        params.append(resolve_supplier(con, supplier)["id"])
    out = []
    for v in rows(con.execute(sql, params)):
        sold, vel = sales_velocity(con, v["id"], days)
        available = v["qty_on_hand"] + v["on_order"]
        needs = available <= v["reorder_point"]
        if not needs and not include_all:
            continue
        target = max(v["reorder_point"] + v["reorder_qty"],
                     math.ceil(vel * (v["lead_time_days"] + cover_days)) + v["reorder_point"])
        v.update({
            "sold_last_n_days": sold,
            "daily_velocity": round(vel, 3),
            "days_of_cover": round(v["qty_on_hand"] / vel, 1) if vel else None,
            "available_incl_on_order": available,
            "needs_reorder": needs,
            "suggested_qty": max(target - available, 0) if needs else 0,
            "urgency": ("OUT_OF_STOCK" if v["qty_on_hand"] <= 0 else
                        "CRITICAL" if vel and v["qty_on_hand"] / vel < v["lead_time_days"] else
                        "LOW") if needs else "OK",
        })
        out.append(v)
    order = {"OUT_OF_STOCK": 0, "CRITICAL": 1, "LOW": 2, "OK": 3}
    out.sort(key=lambda x: (order[x["urgency"]], -x["daily_velocity"]))
    return out


def cmd_reorder_alerts(con, a):
    cols = ["sku", "brand", "product", "size", "color", "qty_on_hand", "on_order", "reorder_point",
            "daily_velocity", "days_of_cover", "lead_time_days", "urgency", "suggested_qty", "supplier"]
    return [{k: c[k] for k in cols} for c in reorder_candidates(con, a.days, a.cover_days, a.supplier)]


def next_po_number(con):
    prefix = "PO-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-"
    n = con.execute("SELECT COUNT(*) FROM purchase_orders WHERE po_number LIKE ?", (prefix + "%",)).fetchone()[0]
    return f"{prefix}{n + 1:03d}"


def create_po(con, supplier_id, items, notes=None, expected=None):
    if not items:
        raise InvError("A purchase order needs at least one item")
    if not expected:
        lead = con.execute("SELECT lead_time_days FROM suppliers WHERE id=?", (supplier_id,)).fetchone()[0]
        expected = (datetime.now(timezone.utc) + timedelta(days=lead)).strftime("%Y-%m-%d")
    po_number = next_po_number(con)
    po_id = con.execute("INSERT INTO purchase_orders (po_number, supplier_id, expected_date, notes)"
                        " VALUES (?,?,?,?)", (po_number, supplier_id, expected, notes)).lastrowid
    for vid, qty, cost in items:
        con.execute("INSERT INTO po_items (po_id, variant_id, qty_ordered, unit_cost) VALUES (?,?,?,?)"
                    " ON CONFLICT(po_id, variant_id) DO UPDATE SET qty_ordered = qty_ordered + excluded.qty_ordered",
                    (po_id, vid, qty, cost))
    return po_id


def po_detail(con, po_id):
    po = one(con.execute("SELECT po.*, s.name AS supplier FROM purchase_orders po JOIN suppliers s"
                         " ON s.id = po.supplier_id WHERE po.id = ?", (po_id,)))
    po["items"] = rows(con.execute(
        "SELECT v.sku, p.name AS product, v.size, v.color, pi.qty_ordered, pi.qty_received,"
        " pi.qty_ordered - pi.qty_received AS qty_outstanding, pi.unit_cost,"
        " ROUND(pi.qty_ordered * pi.unit_cost, 2) AS line_total"
        " FROM po_items pi JOIN variants v ON v.id = pi.variant_id JOIN products p ON p.id = v.product_id"
        " WHERE pi.po_id = ? ORDER BY v.sku", (po_id,)))
    po["total_units"] = sum(i["qty_ordered"] for i in po["items"])
    po["total_cost"] = round(sum(i["line_total"] for i in po["items"]), 2)
    return po


def resolve_po(con, ident):
    r = one(con.execute("SELECT * FROM purchase_orders WHERE po_number = ? COLLATE NOCASE", (ident,)))
    if not r and str(ident).isdigit():
        r = one(con.execute("SELECT * FROM purchase_orders WHERE id = ?", (int(ident),)))
    if not r:
        raise InvError(f"Purchase order not found: {ident}")
    return r


def cmd_po_create(con, a):
    if a.from_alerts:
        cands = [c for c in reorder_candidates(con, a.days, a.cover_days, a.supplier) if c["suggested_qty"] > 0]
        if not cands:
            return {"created": [], "note": "Nothing needs reordering"}
        by_sup, skipped = {}, []
        for c in cands:
            if not c["supplier_id"]:
                skipped.append(c["sku"])
                continue
            by_sup.setdefault(c["supplier_id"], []).append((c["id"], c["suggested_qty"], c["cost_price"]))
        created = [po_detail(con, create_po(con, sid, items, a.notes or "Auto-generated from reorder alerts"))
                   for sid, items in by_sup.items()]
        return {"created": created, "skipped_no_supplier": skipped}
    if not a.supplier or not a.item:
        raise InvError("Give --supplier and one or more --item SKU:QTY[:COST], or use --from-alerts")
    sup = resolve_supplier(con, a.supplier)
    items = []
    for sku, qty, cost in parse_items(a.item):
        v = resolve_variant(con, sku)
        items.append((v["id"], qty, cost if cost is not None else v["cost_price"]))
    return po_detail(con, create_po(con, sup["id"], items, a.notes, a.expected))


def cmd_po_list(con, a):
    sql = ("SELECT po.po_number, s.name AS supplier, po.status, po.expected_date, po.created_at,"
           " COALESCE(SUM(pi.qty_ordered),0) AS units, COALESCE(SUM(pi.qty_received),0) AS received,"
           " ROUND(COALESCE(SUM(pi.qty_ordered * pi.unit_cost),0),2) AS total_cost"
           " FROM purchase_orders po JOIN suppliers s ON s.id = po.supplier_id"
           " LEFT JOIN po_items pi ON pi.po_id = po.id")
    params = []
    if a.status:
        sql += " WHERE po.status = ?"
        params.append(a.status)
    elif not a.all:
        sql += f" WHERE po.status IN {OPEN_PO}"
    sql += " GROUP BY po.id ORDER BY po.created_at DESC"
    return rows(con.execute(sql, params))


def cmd_po_show(con, a):
    return po_detail(con, resolve_po(con, a.po)["id"])


def set_po_status(con, po_id, status):
    con.execute("UPDATE purchase_orders SET status=?, updated_at=? WHERE id=?", (status, now_utc(), po_id))


def cmd_po_submit(con, a):
    po = resolve_po(con, a.po)
    if po["status"] != "draft":
        raise InvError(f"Only draft POs can be submitted (this one is {po['status']})")
    set_po_status(con, po["id"], "ordered")
    return po_detail(con, po["id"])


def cmd_po_receive(con, a):
    po = resolve_po(con, a.po)
    if po["status"] not in ("ordered", "partial", "draft"):
        raise InvError(f"Cannot receive against a {po['status']} PO")
    lines = rows(con.execute("SELECT pi.*, v.sku FROM po_items pi JOIN variants v ON v.id=pi.variant_id"
                             " WHERE pi.po_id=?", (po["id"],)))
    by_sku = {l["sku"].upper(): l for l in lines}
    if a.item:
        wanted = []
        for sku, qty, _ in parse_items(a.item):
            line = by_sku.get(sku.upper()) or by_sku.get(resolve_variant(con, sku)["sku"].upper())
            if not line:
                raise InvError(f"{sku} is not on {po['po_number']}")
            wanted.append((line, qty))
    else:
        wanted = [(l, l["qty_ordered"] - l["qty_received"]) for l in lines if l["qty_ordered"] > l["qty_received"]]
    received = []
    for line, qty in wanted:
        outstanding = line["qty_ordered"] - line["qty_received"]
        if qty > outstanding and not a.allow_over:
            raise InvError(f"{line['sku']}: receiving {qty} but only {outstanding} outstanding "
                           "(pass --allow-over to accept extra)")
        con.execute("UPDATE po_items SET qty_received = qty_received + ? WHERE id=?", (qty, line["id"]))
        received.append(apply_movement(con, line["variant_id"], "receipt", qty, po["po_number"],
                                       "PO receipt", unit_cost=line["unit_cost"]))
    remaining = con.execute("SELECT COALESCE(SUM(MAX(qty_ordered - qty_received,0)),0) FROM po_items"
                            " WHERE po_id=?", (po["id"],)).fetchone()[0]
    set_po_status(con, po["id"], "received" if remaining == 0 else "partial")
    return {"po_number": po["po_number"], "status": "received" if remaining == 0 else "partial",
            "units_outstanding": remaining, "received": received}


def cmd_po_cancel(con, a):
    po = resolve_po(con, a.po)
    if po["status"] in ("received", "cancelled"):
        raise InvError(f"PO is already {po['status']}")
    set_po_status(con, po["id"], "cancelled")
    return {"cancelled": po["po_number"],
            "note": "Units already received stay in stock" if po["status"] == "partial" else None}


# --------------------------------------------------------------------------- analytics

def cmd_an_summary(con, a):
    inv = one(con.execute(
        "SELECT COUNT(DISTINCT p.id) AS active_products, COUNT(v.id) AS active_variants,"
        " COALESCE(SUM(v.qty_on_hand),0) AS units_on_hand,"
        " ROUND(COALESCE(SUM(v.qty_on_hand * COALESCE(v.cost_price, p.cost_price)),0),2) AS inventory_value_cost,"
        " ROUND(COALESCE(SUM(v.qty_on_hand * COALESCE(v.retail_price, p.retail_price)),0),2) AS inventory_value_retail,"
        " SUM(CASE WHEN v.qty_on_hand <= 0 THEN 1 ELSE 0 END) AS out_of_stock_variants,"
        " SUM(CASE WHEN v.qty_on_hand > 0 AND v.qty_on_hand <= v.reorder_point THEN 1 ELSE 0 END) AS low_stock_variants"
        " FROM variants v JOIN products p ON p.id = v.product_id"
        " WHERE v.status='active' AND p.status='active'"))
    sales = one(con.execute(
        "SELECT COALESCE(SUM(CASE WHEN movement_type='sale' THEN -qty_change END),0) AS units_sold,"
        " COALESCE(SUM(CASE WHEN movement_type='return' THEN qty_change END),0) AS units_returned,"
        " ROUND(COALESCE(SUM(CASE WHEN movement_type='sale' THEN -qty_change*unit_price"
        "   WHEN movement_type='return' THEN -qty_change*unit_price END),0),2) AS net_revenue,"
        " ROUND(COALESCE(SUM(CASE WHEN movement_type='sale' THEN -qty_change*unit_cost"
        "   WHEN movement_type='return' THEN -qty_change*unit_cost END),0),2) AS cogs,"
        " ROUND(COALESCE(SUM(CASE WHEN movement_type IN ('damage','adjustment','count') AND qty_change<0"
        "   THEN -qty_change*COALESCE(unit_cost,0) END),0),2) AS shrinkage_cost"
        " FROM stock_movements WHERE created_at >= datetime('now', ?)", (since(a.days),)))
    sales["gross_profit"] = round(sales["net_revenue"] - sales["cogs"], 2)
    sales["gross_margin_pct"] = round(100 * sales["gross_profit"] / sales["net_revenue"], 1) if sales["net_revenue"] else None
    sales["return_rate_pct"] = round(100 * sales["units_returned"] / sales["units_sold"], 1) if sales["units_sold"] else None
    open_po = one(con.execute(
        f"SELECT COUNT(DISTINCT po.id) AS open_pos, COALESCE(SUM(pi.qty_ordered-pi.qty_received),0) AS units_on_order"
        f" FROM purchase_orders po LEFT JOIN po_items pi ON pi.po_id=po.id WHERE po.status IN {OPEN_PO}"))
    return {"period_days": a.days, "inventory": inv, "sales": sales, "purchasing": open_po}


def cmd_an_valuation(con, a):
    col = {"brand": "p.brand", "category": "p.category", "gender": "p.gender",
           "supplier": "COALESCE(s.name,'(none)')", "product": "p.style_code || ' ' || p.name",
           "size": "v.size"}[a.by]
    return rows(con.execute(
        f"SELECT {col} AS {a.by}, COUNT(v.id) AS variants, SUM(v.qty_on_hand) AS units,"
        " ROUND(SUM(v.qty_on_hand * COALESCE(v.cost_price, p.cost_price)),2) AS value_cost,"
        " ROUND(SUM(v.qty_on_hand * COALESCE(v.retail_price, p.retail_price)),2) AS value_retail"
        " FROM variants v JOIN products p ON p.id=v.product_id LEFT JOIN suppliers s ON s.id=p.supplier_id"
        " WHERE v.status='active' AND p.status='active'"
        f" GROUP BY 1 ORDER BY value_cost DESC"))


SALES_AGG = (" SUM(CASE WHEN m.movement_type='sale' THEN -m.qty_change ELSE 0 END) AS units_sold,"
             " SUM(CASE WHEN m.movement_type='return' THEN m.qty_change ELSE 0 END) AS units_returned,"
             " ROUND(SUM(-m.qty_change * COALESCE(m.unit_price,0)),2) AS net_revenue,"
             " ROUND(SUM(-m.qty_change * (COALESCE(m.unit_price,0) - COALESCE(m.unit_cost,0))),2) AS gross_profit")


def cmd_an_top(con, a):
    group = {"sku": "v.id", "product": "p.id", "brand": "p.brand", "category": "p.category"}[a.by]
    label = {"sku": "v.sku AS sku, p.name AS product, v.size, v.color",
             "product": "p.style_code, p.brand, p.name AS product",
             "brand": "p.brand", "category": "p.category"}[a.by]
    direction = "ASC" if a.bottom else "DESC"
    return rows(con.execute(
        f"SELECT {label}, {SALES_AGG} FROM stock_movements m JOIN variants v ON v.id=m.variant_id"
        " JOIN products p ON p.id=v.product_id"
        " WHERE m.movement_type IN ('sale','return') AND m.created_at >= datetime('now', ?)"
        f" GROUP BY {group} ORDER BY {a.metric} {direction} LIMIT ?", (since(a.days), a.limit)))


def cmd_an_trend(con, a):
    fmt = {"day": "%Y-%m-%d", "week": "%Y-W%W", "month": "%Y-%m"}[a.period]
    return rows(con.execute(
        f"SELECT strftime('{fmt}', m.created_at) AS period, {SALES_AGG}"
        " FROM stock_movements m WHERE m.movement_type IN ('sale','return')"
        " AND m.created_at >= datetime('now', ?) GROUP BY 1 ORDER BY 1", (since(a.days),)))


def cmd_an_slow(con, a):
    out = []
    for v in rows(con.execute(VARIANT_VIEW + " WHERE v.status='active' AND v.qty_on_hand > 0")):
        sold, _ = sales_velocity(con, v["id"], a.days)
        if sold > a.max_sold:
            continue
        last = con.execute("SELECT MAX(created_at) FROM stock_movements WHERE variant_id=? AND movement_type='sale'",
                           (v["id"],)).fetchone()[0]
        out.append({"sku": v["sku"], "product": v["product"], "size": v["size"], "color": v["color"],
                    "qty_on_hand": v["qty_on_hand"], "sold_last_n_days": sold, "last_sale": last,
                    "value_at_cost": round(v["qty_on_hand"] * (v["cost_price"] or 0), 2)})
    out.sort(key=lambda x: -x["value_at_cost"])
    return out


def cmd_an_size_curve(con, a):
    where, params = ["v.status='active'"], [since(a.days)]
    if a.product:
        where.append("p.id = ?")
        params.append(resolve_product(con, a.product)["id"])
    if a.category:
        where.append("p.category = ? COLLATE NOCASE")
        params.append(a.category)
    if a.brand:
        where.append("p.brand = ? COLLATE NOCASE")
        params.append(a.brand)
    data = rows(con.execute(
        "SELECT v.size, SUM(v.qty_on_hand) AS on_hand,"
        " COALESCE(SUM((SELECT SUM(-m.qty_change) FROM stock_movements m WHERE m.variant_id=v.id"
        "   AND m.movement_type='sale' AND m.created_at >= datetime('now', ?))),0) AS units_sold"
        " FROM variants v JOIN products p ON p.id=v.product_id"
        f" WHERE {' AND '.join(where)} GROUP BY v.size ORDER BY CAST(v.size AS REAL), v.size", params))
    ts, tq = sum(d["units_sold"] for d in data) or 1, sum(d["on_hand"] for d in data) or 1
    for d in data:
        d["pct_of_sales"] = round(100 * d["units_sold"] / ts, 1)
        d["pct_of_stock"] = round(100 * d["on_hand"] / tq, 1)
        d["gap_pct"] = round(d["pct_of_sales"] - d["pct_of_stock"], 1)
    return data


def cmd_an_turnover(con, a):
    group = {"product": "p.id", "brand": "p.brand", "category": "p.category", "sku": "v.id"}[a.by]
    label = {"product": "p.style_code, p.name AS product", "brand": "p.brand",
             "category": "p.category", "sku": "v.sku, p.name AS product, v.size, v.color"}[a.by]
    data = rows(con.execute(
        f"SELECT {label}, SUM(v.qty_on_hand) AS on_hand,"
        " ROUND(SUM(v.qty_on_hand * COALESCE(v.cost_price, p.cost_price)),2) AS stock_value_cost,"
        " COALESCE(SUM((SELECT SUM(-m.qty_change) FROM stock_movements m WHERE m.variant_id=v.id"
        "   AND m.movement_type='sale' AND m.created_at >= datetime('now', ?))),0) AS units_sold,"
        " COALESCE(SUM((SELECT SUM(-m.qty_change * COALESCE(m.unit_cost,0)) FROM stock_movements m"
        "   WHERE m.variant_id=v.id AND m.movement_type='sale' AND m.created_at >= datetime('now', ?))),0) AS cogs"
        " FROM variants v JOIN products p ON p.id=v.product_id WHERE v.status='active'"
        f" GROUP BY {group}", (since(a.days), since(a.days))))
    for d in data:
        vel = d["units_sold"] / a.days
        d["cogs"] = round(d["cogs"], 2)
        d["days_of_supply"] = round(d["on_hand"] / vel, 1) if vel else None
        d["sell_through_pct"] = round(100 * d["units_sold"] / (d["units_sold"] + d["on_hand"]), 1) \
            if (d["units_sold"] + d["on_hand"]) else None
        d["annualized_turnover"] = round(d["cogs"] * 365 / a.days / d["stock_value_cost"], 2) \
            if d["stock_value_cost"] else None
    data.sort(key=lambda d: -(d["annualized_turnover"] or 0))
    return data


def cmd_an_shrinkage(con, a):
    return rows(con.execute(
        "SELECT m.movement_type, COALESCE(m.reason,'(no reason)') AS reason, COUNT(*) AS events,"
        " SUM(m.qty_change) AS net_units, ROUND(SUM(m.qty_change * COALESCE(m.unit_cost,0)),2) AS net_value_cost"
        " FROM stock_movements m WHERE m.movement_type IN ('adjustment','damage','count')"
        " AND m.created_at >= datetime('now', ?) GROUP BY 1, 2 ORDER BY net_value_cost", (since(a.days),)))


# --------------------------------------------------------------------------- output & CLI

def print_table(data):
    if isinstance(data, dict):
        flat = {k: v for k, v in data.items() if not isinstance(v, (list, dict))}
        for k, v in flat.items():
            print(f"{k}: {v}")
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                print(f"\n[{k}]")
                print_table(v)
        return
    if not data:
        print("(no rows)")
        return
    if not isinstance(data[0], dict):
        print("\n".join(map(str, data)))
        return
    cols = list(data[0].keys())
    cells = [[("" if r.get(c) is None else str(r.get(c))) for c in cols] for r in data]
    widths = [max(len(c), *(len(row[i]) for row in cells)) for i, c in enumerate(cols)]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    print("  ".join("-" * w for w in widths))
    for row in cells:
        print("  ".join(v.ljust(w) for v, w in zip(row, widths)))


def build_parser():
    p = argparse.ArgumentParser(description="Shoe inventory manager (SQLite)")
    p.add_argument("--db", default=os.environ.get("SHOES_INVENTORY_DB", "shoes_inventory.db"))
    p.add_argument("--table", action="store_true", help="print a plain-text table instead of JSON")
    g = p.add_subparsers(dest="group", required=True)

    def cmd(parent, name, func, help_=None):
        sp = parent.add_parser(name, help=help_)
        sp.set_defaults(func=func)
        return sp

    cmd(g, "init", cmd_init, "create tables (idempotent) and show row counts")
    s = cmd(g, "seed", cmd_seed, "load demo data with 90 days of history")
    s.add_argument("--force", action="store_true")
    s = cmd(g, "query", cmd_query, "run a read-only SELECT")
    s.add_argument("sql")

    # suppliers
    sup = g.add_parser("supplier").add_subparsers(dest="action", required=True)
    s = cmd(sup, "add", cmd_supplier_add)
    s.add_argument("name"); s.add_argument("--email"); s.add_argument("--phone")
    s.add_argument("--lead-time", type=int, default=14); s.add_argument("--notes")
    cmd(sup, "list", cmd_supplier_list)
    s = cmd(sup, "update", cmd_supplier_update)
    s.add_argument("supplier"); s.add_argument("--name"); s.add_argument("--email"); s.add_argument("--phone")
    s.add_argument("--lead-time", type=int); s.add_argument("--notes")
    s = cmd(sup, "delete", cmd_supplier_delete); s.add_argument("supplier")

    # products
    pr = g.add_parser("product").add_subparsers(dest="action", required=True)
    s = cmd(pr, "add", cmd_product_add)
    s.add_argument("style_code"); s.add_argument("--brand", required=True); s.add_argument("--name", required=True)
    s.add_argument("--category"); s.add_argument("--gender"); s.add_argument("--supplier")
    s.add_argument("--cost", type=float, default=0); s.add_argument("--price", type=float, default=0)
    s.add_argument("--sizes", help="comma list, e.g. 7,7.5,8"); s.add_argument("--colors", help="comma list")
    s.add_argument("--widths", help="comma list, default M"); s.add_argument("--initial-qty", type=int, default=0)
    s.add_argument("--reorder-point", type=int, default=3); s.add_argument("--reorder-qty", type=int, default=6)
    s.add_argument("--location")
    s = cmd(pr, "list", cmd_product_list)
    s.add_argument("--brand"); s.add_argument("--category"); s.add_argument("--gender"); s.add_argument("--search")
    s.add_argument("--include-archived", action="store_true")
    s = cmd(pr, "show", cmd_product_show); s.add_argument("product")
    s = cmd(pr, "update", cmd_product_update)
    s.add_argument("product"); s.add_argument("--brand"); s.add_argument("--name"); s.add_argument("--category")
    s.add_argument("--gender"); s.add_argument("--supplier"); s.add_argument("--cost", type=float)
    s.add_argument("--price", type=float); s.add_argument("--status", choices=["active", "archived"])
    s = cmd(pr, "delete", cmd_product_delete)
    s.add_argument("product"); s.add_argument("--hard", action="store_true"); s.add_argument("--force", action="store_true")

    # variants
    va = g.add_parser("variant").add_subparsers(dest="action", required=True)
    s = cmd(va, "add", cmd_variant_add)
    s.add_argument("product"); s.add_argument("--size", required=True); s.add_argument("--color", default="")
    s.add_argument("--width", default="M"); s.add_argument("--barcode"); s.add_argument("--location")
    s.add_argument("--initial-qty", type=int, default=0); s.add_argument("--reorder-point", type=int, default=3)
    s.add_argument("--reorder-qty", type=int, default=6); s.add_argument("--cost", type=float)
    s.add_argument("--price", type=float)
    s = cmd(va, "list", cmd_variant_list)
    for f in ("--brand", "--category", "--size", "--color", "--product", "--gender", "--search"):
        s.add_argument(f)
    s.add_argument("--low", action="store_true", help="at or below reorder point")
    s.add_argument("--out", action="store_true", help="out of stock")
    s.add_argument("--include-archived", action="store_true")
    s = cmd(va, "show", cmd_variant_show); s.add_argument("sku")
    s = cmd(va, "update", cmd_variant_update)
    s.add_argument("sku"); s.add_argument("--size"); s.add_argument("--color"); s.add_argument("--width")
    s.add_argument("--barcode"); s.add_argument("--location"); s.add_argument("--reorder-point", type=int)
    s.add_argument("--reorder-qty", type=int); s.add_argument("--cost", type=float); s.add_argument("--price", type=float)
    s.add_argument("--status", choices=["active", "archived"])
    s = cmd(va, "delete", cmd_variant_delete)
    s.add_argument("sku"); s.add_argument("--hard", action="store_true"); s.add_argument("--force", action="store_true")

    # stock
    st = g.add_parser("stock").add_subparsers(dest="action", required=True)

    def stock_cmd(name, func, qty_help="units (positive)", qty_type=None):
        sp = cmd(st, name, func)
        sp.add_argument("sku")
        sp.add_argument("qty", type=qty_type or (lambda x: _positive(x)), help=qty_help)
        sp.add_argument("--ref"); sp.add_argument("--reason")
        return sp

    s = stock_cmd("receive", cmd_stock_receive); s.add_argument("--cost", type=float)
    s = stock_cmd("sell", cmd_stock_sell); s.add_argument("--price", type=float)
    s.add_argument("--allow-negative", action="store_true")
    s = stock_cmd("return", cmd_stock_return); s.add_argument("--price", type=float)
    s.add_argument("--damaged", action="store_true", help="returned pair is unsellable")
    s = stock_cmd("adjust", cmd_stock_adjust, "signed change, e.g. -2 or 3", int)
    s.add_argument("--allow-negative", action="store_true")
    stock_cmd("damage", cmd_stock_damage)
    s = cmd(st, "count", cmd_stock_count, "set on-hand to a physical count")
    s.add_argument("sku"); s.add_argument("counted", type=int); s.add_argument("--ref"); s.add_argument("--reason")
    s = cmd(st, "history", cmd_stock_history)
    s.add_argument("--sku"); s.add_argument("--product")
    s.add_argument("--type", choices=["initial", "receipt", "sale", "return", "adjustment", "damage", "count"])
    s.add_argument("--days", type=int, default=30); s.add_argument("--limit", type=int, default=50)

    # reorder
    ro = g.add_parser("reorder").add_subparsers(dest="action", required=True)
    s = cmd(ro, "alerts", cmd_reorder_alerts)
    s.add_argument("--days", type=int, default=30, help="sales window for velocity")
    s.add_argument("--cover-days", type=int, default=30, help="days of stock to cover after arrival")
    s.add_argument("--supplier")

    # purchase orders
    po = g.add_parser("po").add_subparsers(dest="action", required=True)
    s = cmd(po, "create", cmd_po_create)
    s.add_argument("--supplier"); s.add_argument("--item", action="append", help="SKU:QTY[:COST], repeatable")
    s.add_argument("--from-alerts", action="store_true", help="draft one PO per supplier from reorder alerts")
    s.add_argument("--days", type=int, default=30); s.add_argument("--cover-days", type=int, default=30)
    s.add_argument("--expected", help="YYYY-MM-DD"); s.add_argument("--notes")
    s = cmd(po, "list", cmd_po_list)
    s.add_argument("--status", choices=["draft", "ordered", "partial", "received", "cancelled"])
    s.add_argument("--all", action="store_true")
    s = cmd(po, "show", cmd_po_show); s.add_argument("po")
    s = cmd(po, "submit", cmd_po_submit); s.add_argument("po")
    s = cmd(po, "receive", cmd_po_receive)
    s.add_argument("po"); s.add_argument("--item", action="append", help="SKU:QTY for partial receipt")
    s.add_argument("--allow-over", action="store_true")
    s = cmd(po, "cancel", cmd_po_cancel); s.add_argument("po")

    # analytics
    an = g.add_parser("analytics").add_subparsers(dest="action", required=True)
    s = cmd(an, "summary", cmd_an_summary); s.add_argument("--days", type=int, default=30)
    s = cmd(an, "valuation", cmd_an_valuation)
    s.add_argument("--by", choices=["brand", "category", "gender", "supplier", "product", "size"], default="brand")
    s = cmd(an, "top-sellers", cmd_an_top)
    s.add_argument("--days", type=int, default=30); s.add_argument("--limit", type=int, default=10)
    s.add_argument("--by", choices=["sku", "product", "brand", "category"], default="product")
    s.add_argument("--metric", choices=["units_sold", "net_revenue", "gross_profit"], default="units_sold")
    s.add_argument("--bottom", action="store_true", help="worst performers among items with sales")
    s = cmd(an, "sales-trend", cmd_an_trend)
    s.add_argument("--days", type=int, default=90); s.add_argument("--period", choices=["day", "week", "month"], default="week")
    s = cmd(an, "slow-movers", cmd_an_slow)
    s.add_argument("--days", type=int, default=60); s.add_argument("--max-sold", type=int, default=0)
    s = cmd(an, "size-curve", cmd_an_size_curve)
    s.add_argument("--product"); s.add_argument("--category"); s.add_argument("--brand")
    s.add_argument("--days", type=int, default=90)
    s = cmd(an, "turnover", cmd_an_turnover)
    s.add_argument("--by", choices=["product", "brand", "category", "sku"], default="product")
    s.add_argument("--days", type=int, default=90)
    s = cmd(an, "shrinkage", cmd_an_shrinkage); s.add_argument("--days", type=int, default=90)
    return p


def _positive(x):
    v = int(x)
    if v <= 0:
        raise argparse.ArgumentTypeError("quantity must be a positive integer")
    return v


def main(argv=None):
    args = build_parser().parse_args(argv)
    con = connect(args.db)
    try:
        result = args.func(con, args)
        con.commit()
    except (InvError, sqlite3.IntegrityError, sqlite3.OperationalError) as e:
        con.rollback()
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    finally:
        con.close()
    if args.table:
        print_table(result)
    else:
        print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
