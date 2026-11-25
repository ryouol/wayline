# Viewer parser comparison — October 7, 2026

Packed Float32 coordinates and normalized byte colors now use typed-array reads
after the existing accessor bounds/layout checks. Coordinates are copied into an
owned array, preserving the sample orientation transform without modifying the
downloaded artifact. Interleaved, unaligned, other component types, and non-native
byte order retain the existing DataView path. Color, coordinate, and trace
validation still run before graphics are published.

## Evidence

Baseline: `a7ad874b82ef40f3c02a47df41cba87365887b86`. Both versions parsed the same
bytes. [Raw measurements](viewer-parser-2026-10-07.json) include source/artifact
hashes and every sample. Node v20.11.0 CPU-only runs used three warmups and twelve
paired iterations, alternating order, without concurrent test execution.

| Scene | Points | Before median | After median |
| --- | ---: | ---: | ---: |
| Existing private audit fixture, 12.36 MB | 749,979 | 133.93 ms | 29.52 ms |
| Packaged landing scene, 1.41 MB | 75,000 | 13.90 ms | 3.60 ms |

Coordinates and colors were byte-identical; camera traces were identical and
input buffers were unchanged. In a local browser with the full scene prefetched,
four paired loads in alternating order measured a median **130.55 → 49.25 ms**
for the existing combined parse/normalization/graphics-upload/draw stage. Bounds
and camera traces matched; whole-scene and source-frame views were visually
compared. No browser console errors were observed.

These are local comparisons on one machine and two scenes, not mobile or field
percentiles, reconstruction speedups, network measurements, or confirmation of
physical GPU presentation. Parsing remains on the main thread. No point counts,
colors, file formats, delivery accounting, or reconstruction settings changed.

## Reproduce

From the repository root, compare against the packaged public scene:

```sh
git show a7ad874b82ef40f3c02a47df41cba87365887b86:lingbot_map/workspace/static/viewer.js > /tmp/wayline-viewer-before.js
node scripts/benchmark_viewer.cjs /tmp/wayline-viewer-before.js lingbot_map/workspace/static/viewer.js lingbot_map/workspace/static/landing-scene.glb /tmp/wayline-viewer-comparison.json
node tests/viewer-trace.test.js
```

The benchmark asserts exact coordinates/colors/trace parity before measuring.
The regression suite covers packed, interleaved and unaligned positions, RGB and
RGBA byte/float colors, input immutability, truncated buffers, count limits,
non-finite coordinates and invalid colors. Timing thresholds are not CI gates.
