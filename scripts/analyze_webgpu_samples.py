#!/usr/bin/env python3
"""Check compositor screenshots of the owned public WebGPU sample window."""
import json
from pathlib import Path
import re
import sys
from PIL import Image, ImageChops

label = sys.argv[1]
if not re.fullmatch(r"native\d+-[a-z0-9-]+", label):
    raise SystemExit("Invalid label")
root = Path(__file__).resolve().parents[1] / "reports"
output = root / (label + ".json")
report = json.loads(output.read_text())
for case in report["cases"]:
    if len(case.get("frames", [])) != 2:
        continue
    crops = []
    for frame in case["frames"]:
        image = Image.open(root / frame).convert("RGB")
        rect, viewport = case["page"]["rect"], case["page"]["viewport"]
        sx, sy = image.width / viewport["width"], image.height / viewport["height"]
        bounds = (max(0, round(rect["x"] * sx)),
                  max(0, round(rect["y"] * sy)),
                  min(image.width, round((rect["x"] + rect["width"]) * sx)),
                  min(image.height, round((rect["y"] + rect["height"]) * sy)))
        crops.append(image.crop(bounds).resize((256, 256)))
    pixels = list(crops[0].getdata())
    nonblack = sum(max(pixel) > 16 for pixel in pixels)
    unique = len(set(pixels))
    changed = sum(max(pixel) > 5 for pixel in
                  ImageChops.difference(*crops).getdata())
    case["compositorPixels"] = {
        "nonblackPixelsOf65536": nonblack, "uniqueColors": unique,
        "changedPixelsBetweenFrames": changed}
    animated = case["sample"] != "helloTriangle"
    case["passed"] = bool(
        case["page"]["visibility"] == "visible" and
        not case["rendererCrashed"] and not case["scriptErrors"] and
        nonblack > 100 and unique > 8 and (not animated or changed > 25))
    case["needsCompositorPixelVerification"] = False
report["passed"] = (len(report["cases"]) == 3 and
                    all(case["passed"] for case in report["cases"]))
output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
