# ingest

Owner: W5.

Input decoding and quality.

`decode_images(data, load_limits(config_directory))` accepts PNG/JPEG/WebP/TIFF/BMP
bytes and returns `DecodedPage` objects with grayscale original/processed arrays
and a clavis-ir-0.1.1 `PageInput`. File signatures must agree with the decoder.
TIFF pages may have different dimensions. Animated non-TIFF inputs are rejected.

All pages are preflighted against encoded bytes, per-page/total pixel counts,
page count and decoded-pixel/encoded-byte ratio. `configs/ingest/limits.yaml`
contains provisional operational memory limits, not recognition thresholds.
The repository default config path is for development; installed callers pass
their bundled config directory. No new runtime dependency is needed.

Original pixels are uint8 luminance in the stored raster orientation (row-major
bytes are hashed); alpha is composited on white, palettes are resolved, uint16
grayscale maps its full numeric range to uint8. Floating samples are rejected.
EXIF orientations 1–8, including reflections, produce an explicit pixel-centre
homography. Pillow's TIFF automatic orientation is inverted before this step,
so orientation is applied exactly once. Byte digest preserves source identity.

This is T5.1's raster boundary, not complete S0: PDF/two-pass rasterization,
photographed page quadrilateral detection, illumination normalization and
QualityReport are pending. No quality score or successful perspective correction
is invented when those stages have not run.
