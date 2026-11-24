# Cover photo provenance check (2026-11-24)

Printed credit (title page, PDF page 5): "צילום תמונת הכריכה: פטריית סחף שטפונית על נחל קדם, משה ברנשטיין."

Files: "נחל קדם 1.jpg" and "נחל קדם 2.jpg", received from Yarden in chat (from Eli's Drive share). Stored read-only with SHA256SUMS on the build machine, outside the repo (not in git).

| Check | Result |
|---|---|
| The two files | Byte-identical (sha256 ee592343…), 2000 x 1333 px, sRGB ICC profile, no EXIF (no camera, date or author fields) |
| Same photograph as the cover | Yes. SIFT + RANSAC homography against the PDF cover image (xref 1379, 1798 x 1651 px JPEG): 1,422 of 1,442 matches are inliers |
| Framing | The cover is a crop of the right part of the scene (Kedem x 425 to 2100), and it extends about 294 px above and 100 px right of the Kedem frame: 24% of the cover lies outside these files. The print used a larger frame of the same photograph |
| Resolution | In the overlap, the cover image has 1.07 x the pixels of these files, so they are not a higher-quality source for the cover |
| Provenance | A signature "Moshe Berenstein" sits in the lower left of the files (outside the printed crop). It matches the printed credit |

Conclusion: the credit is supported by the photographer's own signature on the same photograph. These files do not replace the cover image. The full-resolution original (with the sky above) would come from the photographer.
