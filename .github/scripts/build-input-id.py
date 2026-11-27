#!/usr/bin/env python3
"""Use the actual release pin, not unrelated changes in the package mirror."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.request import urlopen


def mirror_pin(manifest):
    packages = json.loads(manifest.read_text())
    mirror = packages['mirror']
    slug = re.fullmatch(r'https://github\.com/([\w.-]+/[\w.-]+?)\.git', mirror['repo']).group(1)
    ref = os.environ.get('PKG_MIRROR_REF') or mirror['ref']
    path = next(pkg['mirror_path'] for pkg in packages['packages'] if pkg['name'] == 'honk' and pkg['mirror_only'])
    with urlopen(f'https://raw.githubusercontent.com/{slug}/{ref}/{path}/honk-source.json', timeout=30) as response:
        return response.read()


def build_id(upstream, pin=None):
    if not re.fullmatch(r'[0-9a-f]{40}', upstream):
        raise ValueError('Missing upstream commit')
    if pin is None:
        return upstream
    if not re.fullmatch(r'[0-9a-f]{40}', json.loads(pin).get('wrapper_commit', '')):
        raise ValueError('Missing Honk release pin')
    return upstream + '-' + hashlib.sha256(pin).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('upstream')
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--manifest', type=Path)
    inputs.add_argument('--pin', type=Path)
    args = parser.parse_args()
    pin = None
    if args.manifest:
        pin = mirror_pin(args.manifest)
    elif args.pin:
        pin = args.pin.read_bytes()
    print(build_id(args.upstream, pin))
