import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.memory_leak import (
    MemoryLeakError,
    detect_growth,
    sample_used_heap,
)


class TestSampleUsedHeap(unittest.TestCase):

    def test_reads_from_execute_script(self):
        driver = MagicMock()
        driver.execute_script.return_value = 12345
        self.assertEqual(sample_used_heap(driver), 12345)

    def test_unsupported_driver_raises(self):
        with self.assertRaises(MemoryLeakError):
            sample_used_heap(object())

    def test_negative_value_raises(self):
        driver = MagicMock()
        driver.execute_script.return_value = -1
        with self.assertRaises(MemoryLeakError):
            sample_used_heap(driver)


class TestDetectGrowth(unittest.TestCase):

    def test_flat_heap_zero_slope(self):
        sizes = iter([1000, 1000, 1000, 1000, 1000])
        action = MagicMock()
        result = detect_growth(
            driver=object(),
            action=action,
            iterations=5,
            warmup=0,
            sampler=lambda _d: next(sizes),
        )
        self.assertEqual(result["slope_bytes_per_iter"], 0.0)

    def test_growing_heap_positive_slope(self):
        sizes = iter([1000, 1100, 1200, 1300, 1400])
        action = MagicMock()
        result = detect_growth(
            driver=object(),
            action=action,
            iterations=5,
            warmup=0,
            sampler=lambda _d: next(sizes),
        )
        self.assertEqual(result["slope_bytes_per_iter"], 100.0)
        self.assertEqual(result["delta_bytes"], 400)

    def test_budget_exceeded_raises(self):
        sizes = iter([1000, 5000, 9000, 13000, 17000])
        with self.assertRaises(MemoryLeakError):
            detect_growth(
                driver=object(),
                action=MagicMock(),
                iterations=5,
                warmup=0,
                sampler=lambda _d: next(sizes),
                growth_bytes_per_iter_budget=1000,
            )

    def test_too_few_iterations_raises(self):
        with self.assertRaises(MemoryLeakError):
            detect_growth(
                driver=object(),
                action=MagicMock(),
                iterations=1,
                sampler=lambda _d: 0,
            )


if __name__ == "__main__":
    unittest.main()
