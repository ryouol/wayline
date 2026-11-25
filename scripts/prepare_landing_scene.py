"""Make a small public presentation asset from the verified TUM reconstruction.

The source stays unchanged. Only this pinned, attributed benchmark artifact is
accepted, so this command cannot accidentally publish a private user capture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

SOURCE_SHA256 = "3556540de61cb0a99f8d1d54b128715739ecd3cc06593fb22fa515aae0e992b3"


def prepare(source: Path, destination: Path) -> None:
    original = source.read_bytes()
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA256:
        raise ValueError("Expected the verified public TUM benchmark reconstruction.")
    json_length = struct.unpack_from("<I", original, 12)[0]
    document = json.loads(original[20 : 20 + json_length])
    binary_start = 28 + json_length
    accessors = document["accessors"]
    views = document["bufferViews"]
    source_count = accessors[0]["count"]
    stride = (source_count + 74_999) // 75_000
    indices = range(0, source_count, stride)
    positions = bytearray()
    colors = bytearray()
    minimum = [float("inf")] * 3
    maximum = [float("-inf")] * 3
    for index in indices:
        offset = binary_start + views[0]["byteOffset"] + index * 12
        position = original[offset : offset + 12]
        positions.extend(position)
        for axis, value in enumerate(struct.unpack("<3f", position)):
            minimum[axis] = min(minimum[axis], value)
            maximum[axis] = max(maximum[axis], value)
        offset = binary_start + views[1]["byteOffset"] + index * 4
        colors.extend(original[offset : offset + 4])

    count = len(indices)
    accessors[0].update(count=count, min=minimum, max=maximum)
    accessors[1]["count"] = count
    views[0]["byteLength"] = len(positions)
    views[1].update(byteOffset=len(positions), byteLength=len(colors))
    binary = positions + colors
    document["buffers"][0]["byteLength"] = len(binary)
    trace = document["extras"]["wayline"]
    trace["pointCount"] = count
    for frame in trace["frames"]:
        frame["pointEnd"] = (frame["pointEnd"] + stride - 1) // stride
    document["extras"]["presentation"] = {
        "source": "TUM RGB-D Benchmark, freiburg3_long_office_household, first 10 seconds",
        "attribution": "J. Sturm, N. Engelhard, F. Endres, W. Burgard, D. Cremers, IROS 2012",
        "sourceLicense": "CC-BY-4.0",
        "sourceLicenseUrl": "https://cvg.cit.tum.de/data/datasets/rgbd-dataset#license",
        "sourceArtifactSha256": SOURCE_SHA256,
        "modification": "Reconstructed point cloud, uniformly reduced to 75,000 points for presentation.",
    }
    encoded = json.dumps(document, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 4)
    result = (
        struct.pack("<5I", 0x46546C67, 2, 28 + len(encoded) + len(binary), len(encoded), 0x4E4F534A)
        + encoded
        + struct.pack("<2I", len(binary), 0x004E4942)
        + binary
    )
    if len(result) > 1_500_000:
        raise ValueError("Landing asset exceeds its 1.5 MB transfer budget.")
    destination.write_bytes(result)
    print(f"{count:,} points, {len(trace['frames'])} source frames, {len(result):,} bytes")
    print(f"SHA-256: {hashlib.sha256(result).hexdigest()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    prepare(arguments.source, arguments.destination)
