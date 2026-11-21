"""A tiny grocery list helper. Your skills practise on this file."""


def add_item(items, name, price, quantity=1):
    """Add an item to the list."""
    items.append({"name": name, "price": price, "quantity": quantity})
    return items


def total_cost(items):
    """Total cost of everything on the list."""
    return round(sum(i["price"] * i["quantity"] for i in items), 2)


def cheapest(items):
    """The cheapest item (by unit price), or None if the list is empty."""
    return min(items, key=lambda i: i["price"]) if items else None


def apply_coupon(total, percent):
    """Take a percentage off the total."""
    return round(total * (1 - percent / 100), 2)


def format_receipt(items):
    """A printable receipt."""
    lines = [f"{i['quantity']} x {i['name']}  {i['price'] * i['quantity']:.2f}" for i in items]
    lines.append(f"TOTAL  {total_cost(items):.2f}")
    return "\n".join(lines)
