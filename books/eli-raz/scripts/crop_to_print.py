# /// script
# requires-python = ">=3.15"
# dependencies = ["opencv-python-headless==4.14.0.94", "numpy==2.5.4"]
# ///
"""Crop a better original of a printed figure to the printed crop, for a [[release.change]] replacement.

Usage: uv run scripts/crop_to_print.py BOOK_IMAGE ORIGINAL OUT.jpg [MAX_SIDE] [QUALITY]

SIFT keypoints and a RANSAC homography (the same match as pd-sources/tools/match.py) map the book image into the
original. The script warps the original into the frame of the book image, so the result has the printed crop and
orientation (a plate printed sideways on its page comes out upright). The output keeps the original's resolution,
with the long side at most MAX_SIDE px (default 2000), and is a JPEG at QUALITY (default 85).
Matching runs on copies scaled to at most 3000 px (the matcher has a keypoint limit); the warp uses the full original.
It stops when fewer than 100 inliers support the homography: then the two are not the same image.
"""

import sys

import cv2
import numpy as np

MATCH_SIDE = 3000


def scaled(img: np.ndarray) -> tuple[np.ndarray, float]:
    s = min(1.0, MATCH_SIDE / max(img.shape[:2]))
    return (cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img), s


def main() -> None:
    book_path, orig_path, out_path = sys.argv[1:4]
    max_side = int(sys.argv[4]) if len(sys.argv) > 4 else 2000
    quality = int(sys.argv[5]) if len(sys.argv) > 5 else 85
    book = cv2.imread(book_path, cv2.IMREAD_GRAYSCALE)
    orig = cv2.imread(orig_path, cv2.IMREAD_COLOR)
    if book is None or orig is None:
        raise SystemExit("cannot read an input image")
    small, s = scaled(cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY))
    sift = cv2.SIFT_create()
    kb, db = sift.detectAndCompute(book, None)
    ko, do = sift.detectAndCompute(small, None)
    good = [m for m, n in (p for p in cv2.BFMatcher().knnMatch(db, do, k=2) if len(p) == 2) if m.distance < 0.75 * n.distance]
    src = np.float32([kb[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([ko[m.trainIdx].pt for m in good]).reshape(-1, 1, 2) / s  # Back to full-size coordinates.
    h, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0 / s)
    inliers = int(mask.sum()) if mask is not None else 0
    if h is None or inliers < 100:
        raise SystemExit(f"only {inliers} inliers: not the same image")
    hb, wb = book.shape
    corners = cv2.perspectiveTransform(np.float32([[0, 0], [wb, 0], [wb, hb], [0, hb]]).reshape(-1, 1, 2), h).reshape(-1, 2)
    # The original's own resolution over the printed frame, then the size cap.
    native = (np.linalg.norm(corners[1] - corners[0]) + np.linalg.norm(corners[2] - corners[3])) / 2 / wb
    k = min(native, max_side / max(wb, hb))
    w_out, h_out = round(wb * k), round(hb * k)
    to_book = np.array([[1 / k, 0, 0], [0, 1 / k, 0], [0, 0, 1]])  # Output pixel -> book pixel.
    out = cv2.warpPerspective(orig, h @ to_book, (w_out, h_out), flags=cv2.INTER_AREA | cv2.WARP_INVERSE_MAP,
                              borderMode=cv2.BORDER_REPLICATE)
    cv2.imwrite(out_path, out, [cv2.IMWRITE_JPEG_QUALITY, quality])
    print(f"{inliers} inliers; original {orig.shape[1]}x{orig.shape[0]}, {native:.2f}x the print; "
          f"out {w_out}x{h_out} (book {wb}x{hb})")


if __name__ == "__main__":
    main()
