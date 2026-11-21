import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from grocery import add_item, apply_coupon, cheapest, format_receipt, total_cost


class T(unittest.TestCase):
    def test_total(self):
        items = add_item(add_item([], "milk", 1.5, 2), "bread", 2.0)
        self.assertEqual(total_cost(items), 5.0)

    def test_cheapest(self):
        items = add_item(add_item([], "milk", 1.5), "bread", 2.0)
        self.assertEqual(cheapest(items)["name"], "milk")
        self.assertIsNone(cheapest([]))

    def test_coupon(self):
        self.assertEqual(apply_coupon(100, 10), 90.0)

    def test_receipt(self):
        self.assertIn("TOTAL  3.00", format_receipt(add_item([], "milk", 1.5, 2)))


if __name__ == "__main__":
    unittest.main()
