import unittest

from je_web_runner.utils.factories.factory import (
    Factory,
    FactoryError,
    order_factory,
    product_factory,
    user_factory,
)


class TestFactory(unittest.TestCase):

    def test_callable_defaults_evaluated_per_build(self):
        counter = {"value": 0}

        def next_id():
            counter["value"] += 1
            return counter["value"]

        factory = Factory({"id": next_id, "kind": "static"})
        first = factory.build()
        second = factory.build()
        self.assertEqual(first["id"], 1)
        self.assertEqual(second["id"], 2)
        self.assertEqual(first["kind"], "static")

    def test_overrides_replace_defaults(self):
        factory = Factory({"name": "alice"})
        self.assertEqual(factory.build(name="bob"), {"name": "bob"})

    def test_build_batch_returns_list(self):
        factory = Factory({"name": lambda: "x"})
        batch = factory.build_batch(3)
        self.assertEqual(len(batch), 3)

    def test_extend_merges_defaults(self):
        base = Factory({"name": "alice"})
        extended = base.extend(role="admin")
        self.assertEqual(extended.build(), {"name": "alice", "role": "admin"})
        # Original is untouched.
        self.assertEqual(base.build(), {"name": "alice"})

    def test_invalid_defaults_raise(self):
        with self.assertRaises(FactoryError):
            Factory("not a dict")  # type: ignore[arg-type]


class TestPrebuiltFactories(unittest.TestCase):

    def test_user_factory_increments_id(self):
        factory = user_factory()
        first = factory.build()
        second = factory.build()
        self.assertEqual(first["id"], 1)
        self.assertEqual(second["id"], 2)
        self.assertIn("@", first["email"])

    def test_order_factory_default_currency(self):
        factory = order_factory()
        self.assertEqual(factory.build()["currency"], "USD")

    def test_product_factory_in_stock_default(self):
        factory = product_factory()
        self.assertTrue(factory.build()["in_stock"])


if __name__ == "__main__":
    unittest.main()
