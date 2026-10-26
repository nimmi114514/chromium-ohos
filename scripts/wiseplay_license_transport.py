#!/usr/bin/env python3
"""Opaque transport for published vendor examples. No payloads are logged."""
import struct
import argparse
import sys
import urllib.error
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument("--size", type=int, required=True)
parser.add_argument("--provider", choices=("ezdrm", "official-dta"), default="ezdrm")
args = parser.parse_args()
if not 0 <= args.size <= 1024 * 1024:
    raise SystemExit("Invalid public-sample request length")
body = sys.stdin.buffer.read(args.size)
if len(body) > 1024 * 1024:
    raise SystemExit("Oversized public-sample request")
endpoints = {
    "ezdrm": "https://wiseplay.ezdrm.com/",
    # Exact URL published by OpenHarmony MediaCollections/DTA.exolist.json.
    "official-dta": "http://license.dev.trustdta.com:8080/drmproxy/v3/getLicense",
}
request = urllib.request.Request(
    endpoints[args.provider], data=body,
    # Matches HMS-Core's WisePlay HttpMediaDrmCallback reference client.
    headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        status, payload = response.status, response.read(1024 * 1024)
except urllib.error.HTTPError as response:
    status, payload = response.code, response.read(1024 * 1024)
except Exception as error:
    print(type(error).__name__ + ": " + str(error), file=sys.stderr)
    status, payload = 502, b"Public sample transport failed"
sys.stdout.buffer.write(struct.pack(">I", status) + payload)
