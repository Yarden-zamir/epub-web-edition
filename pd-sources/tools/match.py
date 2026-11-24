# /// script
# requires-python = ">=3.15"
# dependencies = ["opencv-python-headless==4.14.0.94", "numpy==2.5.4"]
# ///
"""SIFT + RANSAC homography match of a book image against candidate images.

Usage: uv run -I match.py <book image> <candidate> [<candidate> ...]
Prints inliers, matches after the ratio test, and the share of the candidate that the book image covers.
Both images are scaled so the long side is at most MATCH_MAX_SIDE px (default 1600); this keeps the run fast and the counts comparable.
"""
import os
import sys

import cv2
import numpy as np

MAX_SIDE = int(os.environ.get("MATCH_MAX_SIDE", "1600"))  # raise it when the book image is a small detail of a large sheet


def load(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise SystemExit(f"cannot read {path}")
    scale = MAX_SIDE / max(img.shape)
    return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else img


def match(book: np.ndarray, cand: np.ndarray, sift) -> tuple[int, int, float]:
    kb, db = sift.detectAndCompute(book, None)
    kc, dc = sift.detectAndCompute(cand, None)
    if db is None or dc is None or len(kb) < 4 or len(kc) < 4:
        return 0, 0, 0.0
    pairs = cv2.BFMatcher().knnMatch(db, dc, k=2)
    good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 4:
        return 0, len(good), 0.0
    src = np.float32([kb[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kc[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    h, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if h is None:
        return 0, len(good), 0.0
    hb, wb = book.shape
    corners = cv2.perspectiveTransform(np.float32([[0, 0], [wb, 0], [wb, hb], [0, hb]]).reshape(-1, 1, 2), h)
    coverage = abs(cv2.contourArea(corners)) / (cand.shape[0] * cand.shape[1])
    return int(mask.sum()), len(good), coverage


def main() -> None:
    sift = cv2.SIFT_create()
    book = load(sys.argv[1])
    for path in sys.argv[2:]:
        inliers, good, coverage = match(book, load(path), sift)
        print(f"{inliers:5d} inliers {good:5d} good  coverage {coverage:6.1%}  {path}")


if __name__ == "__main__":
    main()
