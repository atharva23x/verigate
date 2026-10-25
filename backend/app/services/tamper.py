"""Tamper detection (Error Level Analysis) + perceptual hashing (duplicates).

ELA: re-save the page as JPEG at a slightly lower quality and measure the
per-pixel error, RESTRICTED TO FLAT REGIONS (low local variance). This is the
key refinement for rendered documents: anti-aliased text edges produce large
re-compression error everywhere and would otherwise false-positive on every
page, while genuinely pasted/recompressed regions show error in otherwise-flat
areas. Solid clusters of hot flat blocks are reported as the normalized
bounding box the UI draws the red overlay from.

pHash: 64-bit DCT perceptual hash, used to catch the same document being reused
across applications (hamming distance threshold).

MOCK_MODE note: the pipeline may merge a seeded ground-truth tamper region for
demo scenario C (spec: MOCK_MODE returns predefined results for the demo).
Both paths degrade gracefully if numpy/scipy are unavailable.
"""

import io

import numpy as np
from PIL import Image

from .. import config

try:
    from scipy import ndimage  # type: ignore
    from scipy.ndimage import uniform_filter  # type: ignore
except Exception:  # pragma: no cover
    ndimage = None
    uniform_filter = None

BLOCK = 16
FLAT_VAR_MAX = 12.0    # local luminance variance below this = "flat" region
HOT_BLOCK_MEAN = 12.0  # amplified-error threshold for a hot flat block
SCORE_DIVISOR = 50.0


def ela_analysis(image: Image.Image, quality: int = 88, amplify: int = 18):
    """Returns (heatmap_rgb, score 0..1, bbox_norm [x,y,w,h] | None)."""
    try:
        rgb = image.convert("RGB")
        w, h = rgb.size

        buf = io.BytesIO()
        rgb.save(buf, "JPEG", quality=quality)
        buf.seek(0)
        recompressed = Image.open(buf).convert("RGB")

        orig = np.asarray(rgb, dtype=np.int16)
        recomp = np.asarray(recompressed, dtype=np.int16)
        diff = np.abs(orig - recomp).max(axis=2).astype(np.float32) * amplify
        diff = np.clip(diff, 0, 255)

        # Flat-region mask: text edges (high local variance) are excluded so
        # they cannot masquerade as tampering on ordinary rendered pages.
        lum = np.asarray(rgb.convert("L"), dtype=np.float32)
        if uniform_filter is not None:
            variance = uniform_filter(lum**2, 5) - uniform_filter(lum, 5) ** 2
            flat = variance < FLAT_VAR_MAX
        else:
            flat = np.ones_like(lum, dtype=bool)

        bh, bw = h // BLOCK, w // BLOCK
        if bh < 2 or bw < 2:
            return _heatmap(diff), 0.0, None
        cut = lambda a: a[: bh * BLOCK, : bw * BLOCK]  # noqa: E731
        block_diff = cut(diff).reshape(bh, BLOCK, bw, BLOCK).mean(axis=(1, 3))
        # A block is "flat" only if virtually ALL its pixels are flat - thin
        # rules/hairlines inside otherwise-white blocks must not qualify.
        block_flat = cut(flat).reshape(bh, BLOCK, bw, BLOCK).mean(axis=(1, 3)) > 0.97

        hot = block_flat & (block_diff > HOT_BLOCK_MEAN)

        # Solid clusters only: a genuine pasted region is a contiguous 2D
        # chunk, whereas hairline leakage forms 1-block-tall strips.
        if uniform_filter is not None and hot.any():
            solid = uniform_filter(hot.astype(np.float32), size=3) >= 0.55
        else:
            solid = hot
        region = _chunky_regions(solid if solid.any() else hot)

        if not region.any():
            return _heatmap(diff), 0.0, None

        score = float(
            np.clip(np.percentile(block_diff[region], 95) / SCORE_DIVISOR, 0.0, 1.0)
        )
        bbox = _region_bbox(region, w, h)
        return _heatmap(diff), round(score, 4), bbox
    except Exception:
        return Image.new("RGB", image.size, "black"), 0.0, None


def _chunky_regions(mask: np.ndarray) -> np.ndarray:
    """Keep only connected components that are at least 2x2 blocks - drops
    hairline/strip leakage while retaining genuine pasted regions."""
    if ndimage is None:
        return mask
    labeled, n = ndimage.label(mask)
    keep = np.zeros_like(mask, dtype=bool)
    for i in range(1, n + 1):
        ys, xs = np.nonzero(labeled == i)
        if (ys.max() - ys.min() + 1) >= 2 and (xs.max() - xs.min() + 1) >= 2:
            keep |= labeled == i
    return keep


def _region_bbox(region: np.ndarray, w: int, h: int):
    mask = region.astype(np.uint8)
    if ndimage is not None:
        labeled, n = ndimage.label(mask)
        if n > 1:  # keep only the largest connected hot region
            sizes = ndimage.sum(mask, labeled, range(1, n + 1))
            mask = (labeled == (int(np.argmax(sizes)) + 1)).astype(np.uint8)
    ys, xs = np.nonzero(mask)
    x0, x1 = xs.min() * BLOCK, (xs.max() + 1) * BLOCK
    y0, y1 = ys.min() * BLOCK, (ys.max() + 1) * BLOCK
    return [
        round(x0 / w, 4),
        round(y0 / h, 4),
        round((x1 - x0) / w, 4),
        round((y1 - y0) / h, 4),
    ]


def _heatmap(diff: np.ndarray) -> Image.Image:
    gray = diff.astype(np.uint8)
    base = Image.merge("RGB", (Image.fromarray(gray),) * 3)
    arr = np.asarray(base).copy()
    arr[:, :, 0] = np.clip(arr[:, :, 0].astype(np.int16) + (diff * 0.9), 0, 255)
    arr[:, :, 1] = (arr[:, :, 1] * 0.5).astype(np.uint8)
    arr[:, :, 2] = (arr[:, :, 2] * 0.5).astype(np.uint8)
    return Image.fromarray(arr)


# ---------------------------------------------------------------------- pHash
_DCT_CACHE: dict = {}


def _dct_matrix(n: int) -> np.ndarray:
    if n not in _DCT_CACHE:
        k = np.arange(n)
        _DCT_CACHE[n] = np.cos(np.pi * np.outer(k, (2 * k + 1) / (2 * n)))
    return _DCT_CACHE[n]


def phash(image: Image.Image, size: int = 32, hash_size: int = 8) -> str:
    """64-bit DCT perceptual hash as a 16-char hex string."""
    try:
        img = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
        arr = np.asarray(img, dtype=np.float64)
        dct = _dct_matrix(size) @ arr @ _dct_matrix(size).T
        low = dct[:hash_size, :hash_size].flatten()
        med = np.median(low[1:])  # skip DC
        bits = (low > med).astype(np.uint8)
        bits[0] = 0
        value = 0
        for b in bits:
            value = (value << 1) | int(b)
        return f"{value:016x}"
    except Exception:
        return ""


def hamming(hex_a: str, hex_b: str) -> int:
    if not hex_a or not hex_b or len(hex_a) != len(hex_b):
        return 64
    return bin(int(hex_a, 16) ^ int(hex_b, 16)).count("1")


def duplicate_threshold() -> int:
    return config.PHASH_DUPLICATE_MAX_DISTANCE
