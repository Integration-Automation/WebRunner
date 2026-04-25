import unittest

from je_web_runner.utils.sharding.shard import (
    ShardingError,
    parse_shard_spec,
    partition,
    partition_with_spec,
)


class TestParseSpec(unittest.TestCase):

    def test_valid_spec(self):
        self.assertEqual(parse_shard_spec("1/4"), (1, 4))
        self.assertEqual(parse_shard_spec("4/4"), (4, 4))

    def test_missing_slash_raises(self):
        with self.assertRaises(ShardingError):
            parse_shard_spec("1of4")

    def test_non_integer_raises(self):
        with self.assertRaises(ShardingError):
            parse_shard_spec("a/4")

    def test_zero_total_raises(self):
        with self.assertRaises(ShardingError):
            parse_shard_spec("1/0")

    def test_index_out_of_range(self):
        with self.assertRaises(ShardingError):
            parse_shard_spec("5/4")
        with self.assertRaises(ShardingError):
            parse_shard_spec("0/4")


class TestPartition(unittest.TestCase):

    def test_partitions_cover_full_set_and_disjoint(self):
        files = [f"tests/{name}.json" for name in (
            "login", "checkout", "search", "profile", "settings",
            "list_orders", "logout", "signup", "billing", "support",
        )]
        seen: set = set()
        for index in range(1, 5):
            picked = partition(files, index, 4)
            self.assertTrue(set(picked).isdisjoint(seen))
            seen.update(picked)
        self.assertEqual(seen, set(files))

    def test_partition_is_deterministic(self):
        files = ["a.json", "b.json", "c.json", "d.json"]
        first = partition(files, 1, 3)
        second = partition(files, 1, 3)
        self.assertEqual(first, second)

    def test_partition_with_spec_round_trip(self):
        files = [f"x{i}.json" for i in range(20)]
        parts = [partition_with_spec(files, f"{i}/4") for i in range(1, 5)]
        merged = sum(parts, [])
        self.assertEqual(set(merged), set(files))


if __name__ == "__main__":
    unittest.main()
