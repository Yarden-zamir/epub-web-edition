# /// script
# requires-python = ">=3.15"
# dependencies = ["opencv-python-headless==4.14.0.94", "numpy==2.5.4"]
# ///
"""Crop a better original of a printed figure to the printed crop, for a [[release.change]] replacement.

Usage: uv run scripts/crop_to_print.py BOOK_IMAGE ORIGINAL OUT.jpg [MAX_SIDE]

SIFT keypoints and a RANSAC homography map the corners of the book image into the original (the same match as
pd-sources/tools/match.py). The script crops the original to the box of those corners, scales the long side to at
most MAX_SIDE px (default 2000; Kindle guidance for inline images) and writes a JPEG at quality 85.
It stops when fewer than 100 inliers support the homography: then the two are not the same image.
Limit: the crop is the axis-aligned box of the mapped corners, so a rotated print keeps a thin margin. Revisit if
a print turns out rotated against its original.
"""

import sys

import cv2
import numpy as np


def main() -> None:
    book_path, orig_path, out_path = sys.argv[1:4]
    max_side = int(sys.argv[4]) if len(sys.argv) > 4 else 2000
    book = cv2.imread(book_path, cv2.IMREAD_GRAYSCALE)
    orig = cv2.imread(orig_path, cv2.IMREAD_COLOR)
    if book is None or orig is None:
        raise SystemExit("cannot read an input image")
    sift = cv2.SIFT_create()
    kb, db = sift.detectAndCompute(book, None)
    ko, do = sift.detectAndCompute(cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY), None)
    good = [m for m, n in (p for p in cv2.BFMatcher().knnMatch(db, do, k=2) if len(p) == 2) if m.distance < 0.75 * n.distance]
    src = np.float32([kb[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([ko[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    h, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    inliers = int(mask.sum()) if mask is not None else 0
    if h is None or inliers < 100:
        raise SystemExit(f"only {inliers} inliers: not the same image")
    hb, wb = book.shape
    corners = cv2.perspectiveTransform(np.float32([[0, 0], [wb, 0], [wb, hb], [0, hb]]).reshape(-1, 1, 2), h).reshape(-1, 2)
    x0, y0 = np.floor(corners.min(axis=0)).astype(int).clip(0)
    x1, y1 = np.ceil(corners.max(axis=0)).astype(int)
    x1, y1 = min(x1, orig.shape[1]), min(y1, orig.shape[0])
    crop = orig[y0:y1, x0:x1]
    scale = min(1.0, max_side / max(crop.shape[:2]))
    if scale < 1:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    cv2.imwrite(out_path, crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"{inliers} inliers; crop x {x0}-{x1}, y {y0}-{y1} of {orig.shape[1]}x{orig.shape[0]}; "
          f"out {crop.shape[1]}x{crop.shape[0]} (book {wb}x{hb})")


if __name__ == "__main__":
    main()
