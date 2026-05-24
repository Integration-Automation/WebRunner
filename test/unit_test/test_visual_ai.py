"""Unit tests for je_web_runner.utils.visual_ai."""
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from je_web_runner.utils.visual_ai.perceptual import (
    HashResult,
    SimilarityResult,
    VisualAIError,
    assert_visual_similar,
    average_hash,
    compare_images,
    difference_hash,
    hamming_distance,
    hash_similarity,
    perceptual_hash,
)


def _require_pillow():
    try:
        from PIL import Image  # noqa: F401
        return True
    except ImportError:
        return False


def _make_solid(rgb, size=32):
    from PIL import Image
    img = Image.new("RGB", (size, size), rgb)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_checker(square_size=4, total=32):
    from PIL import Image
    img = Image.new("RGB", (total, total), (0, 0, 0))
    px = img.load()
    for y in range(total):
        for x in range(total):
            if ((x // square_size) + (y // square_size)) % 2 == 0:
                px[x, y] = (255, 255, 255)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_gradient(total=32, flipped=False):
    from PIL import Image
    img = Image.new("RGB", (total, total), (0, 0, 0))
    px = img.load()
    for y in range(total):
        for x in range(total):
            v = int(255 * (x / max(1, total - 1)))
            if flipped:
                v = 255 - v
            px[x, y] = (v, v, v)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@unittest.skipUnless(_require_pillow(), "Pillow not installed")
class TestHashFunctions(unittest.TestCase):

    def test_average_hash_default_size(self):
        img = _make_solid((128, 128, 128))
        h = average_hash(img)
        self.assertEqual(h.kind, "aHash")
        self.assertEqual(len(h.bits), 64)

    def test_difference_hash_length(self):
        img = _make_gradient()
        h = difference_hash(img)
        self.assertEqual(h.kind, "dHash")
        self.assertEqual(len(h.bits), 64)

    def test_perceptual_hash_length(self):
        img = _make_gradient()
        h = perceptual_hash(img)
        self.assertEqual(h.kind, "pHash")
        # 8*8 - 1 (DC removed)
        self.assertEqual(len(h.bits), 63)

    def test_hex_round_trip_no_crash(self):
        img = _make_solid((50, 100, 200))
        h = average_hash(img)
        self.assertGreater(len(h.hex()), 0)

    def test_identical_images_perfect_similarity(self):
        img = _make_gradient()
        a = perceptual_hash(img)
        b = perceptual_hash(img)
        self.assertAlmostEqual(hash_similarity(a, b), 1.0)
        self.assertEqual(hamming_distance(a, b), 0)

    def test_different_kinds_raise(self):
        img = _make_solid((0, 0, 0))
        a = average_hash(img)
        d = difference_hash(img)
        with self.assertRaises(VisualAIError):
            hamming_distance(a, d)

    def test_different_lengths_raise(self):
        a = HashResult("aHash", "1010")
        b = HashResult("aHash", "101010")
        with self.assertRaises(VisualAIError):
            hamming_distance(a, b)


@unittest.skipUnless(_require_pillow(), "Pillow not installed")
class TestCompareImages(unittest.TestCase):

    def test_identical_images_pass(self):
        img = _make_gradient()
        result = compare_images(img, img, threshold=0.95)
        self.assertTrue(result.passed)
        self.assertAlmostEqual(result.composite, 1.0, places=2)

    def test_wildly_different_images_fail(self):
        # Use structurally different content (checker vs gradient). Pure-
        # colour images degenerate aHash/dHash because every bit is "all
        # below mean" on both sides — that's a corner case, not realistic.
        a = _make_checker(square_size=4)
        b = _make_gradient(flipped=False)
        result = compare_images(a, b, threshold=0.85)
        self.assertFalse(result.passed)

    def test_similar_charts_pass_above_threshold(self):
        # two gradients differing by a tiny perturbation
        from PIL import Image
        base = _make_gradient()
        perturbed_img = Image.open(BytesIO(base)).convert("RGB")
        px = perturbed_img.load()
        # Add subtle noise to a handful of pixels (much less than before)
        for i in range(8):
            x = (i * 7) % 32
            y = (i * 5) % 32
            px[x, y] = (min(255, px[x, y][0] + 10), 0, 0)
        buf = BytesIO()
        perturbed_img.save(buf, format="PNG")
        result = compare_images(base, buf.getvalue(), threshold=0.85)
        self.assertTrue(result.passed)

    def test_invalid_threshold_raises(self):
        img = _make_solid((0, 0, 0))
        with self.assertRaises(VisualAIError):
            compare_images(img, img, threshold=1.5)

    def test_weights_must_sum_to_one(self):
        img = _make_solid((0, 0, 0))
        with self.assertRaises(VisualAIError):
            compare_images(img, img, weights=(0.5, 0.5, 0.5, 0.5))

    def test_file_path_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path_a = Path(tmpdir) / "a.png"
            path_a.write_bytes(_make_gradient())
            result = compare_images(path_a, path_a)
            self.assertTrue(result.passed)


@unittest.skipUnless(_require_pillow(), "Pillow not installed")
class TestAssertVisualSimilar(unittest.TestCase):

    def test_pass(self):
        img = _make_gradient()
        result = assert_visual_similar(img, img, threshold=0.9)
        self.assertIsInstance(result, SimilarityResult)

    def test_fail_raises(self):
        a = _make_checker(square_size=4)
        b = _make_gradient()
        with self.assertRaises(VisualAIError):
            assert_visual_similar(a, b, threshold=0.85)


@unittest.skipUnless(_require_pillow(), "Pillow not installed")
class TestROIAndMask(unittest.TestCase):

    def _half_red_half_blue(self, size=64):
        from PIL import Image
        img = Image.new("RGB", (size, size), (0, 0, 255))
        px = img.load()
        for y in range(size):
            for x in range(size // 2):
                px[x, y] = (255, 0, 0)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _half_red_half_green(self, size=64):
        from PIL import Image
        img = Image.new("RGB", (size, size), (0, 255, 0))
        px = img.load()
        for y in range(size):
            for x in range(size // 2):
                px[x, y] = (255, 0, 0)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_crop_box_focuses_comparison(self):
        a = self._half_red_half_blue()
        b = self._half_red_half_green()
        # Whole image differs (blue right half vs green right half),
        # but the left half (red) is identical.
        no_crop = compare_images(a, b, threshold=0.99)
        cropped = compare_images(
            a, b, threshold=0.99, crop_box=(0, 0, 32, 64),
        )
        self.assertGreater(cropped.composite, no_crop.composite)
        self.assertAlmostEqual(cropped.composite, 1.0, places=2)

    def test_mask_boxes_hides_dynamic_region(self):
        a = self._half_red_half_blue()
        b = self._half_red_half_green()
        # Mask out the right half so only the identical red side counts.
        result = compare_images(
            a, b, threshold=0.99, mask_boxes=[(32, 0, 64, 64)],
        )
        self.assertTrue(result.passed)

    def test_invalid_box_shape_raises(self):
        a = self._half_red_half_blue()
        with self.assertRaises(VisualAIError):
            compare_images(a, a, crop_box=(0, 0, 10))  # type: ignore[arg-type]

    def test_inverted_box_raises(self):
        a = self._half_red_half_blue()
        with self.assertRaises(VisualAIError):
            compare_images(a, a, crop_box=(10, 10, 5, 20))

    def test_negative_origin_raises(self):
        a = self._half_red_half_blue()
        with self.assertRaises(VisualAIError):
            compare_images(a, a, crop_box=(-1, 0, 10, 10))

    def test_box_exceeding_image_raises(self):
        a = self._half_red_half_blue(size=32)
        with self.assertRaises(VisualAIError):
            compare_images(a, a, crop_box=(0, 0, 100, 100))

    def test_assert_with_mask_passes(self):
        a = self._half_red_half_blue()
        b = self._half_red_half_green()
        result = assert_visual_similar(
            a, b, threshold=0.95, mask_boxes=[(32, 0, 64, 64)],
        )
        self.assertTrue(result.passed)

    def test_hash_accepts_crop(self):
        from je_web_runner.utils.visual_ai.perceptual import perceptual_hash
        a = self._half_red_half_blue()
        # Just make sure passing a crop_box doesn't error
        h = perceptual_hash(a, crop_box=(0, 0, 32, 32))
        self.assertEqual(h.kind, "pHash")


class TestInputErrors(unittest.TestCase):

    @unittest.skipUnless(_require_pillow(), "Pillow not installed")
    def test_missing_file(self):
        with self.assertRaises(VisualAIError):
            average_hash("/no/such/file.png")

    @unittest.skipUnless(_require_pillow(), "Pillow not installed")
    def test_unsupported_type(self):
        with self.assertRaises(VisualAIError):
            average_hash(42)  # type: ignore[arg-type]

    @unittest.skipUnless(_require_pillow(), "Pillow not installed")
    def test_bad_bytes(self):
        with self.assertRaises(VisualAIError):
            average_hash(b"not an image")


if __name__ == "__main__":
    unittest.main()
