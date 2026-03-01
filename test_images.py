#!/usr/bin/env python
"""Test that preview images load correctly."""
import os
from pathlib import Path

# Find the ktfigure module location
import ktfigure

module_path = Path(ktfigure.__file__).parent
images_dir = module_path / "images"

print(f"Module location: {module_path}")
print(f"Images directory: {images_dir}")
print(f"Images directory exists: {images_dir.exists()}")

if images_dir.exists():
    print("\nImages found:")
    for img in sorted(images_dir.glob("*.png")):
        print(f"  - {img.name}")
else:
    print("\nWARNING: Images directory not found!")

# Test loading preview images
print("\nTesting PIL image loading:")
try:
    from PIL import Image

    for style in ["whitegrid", "darkgrid", "white", "dark", "ticks"]:
        img_path = images_dir / f"style_preview_{style}.png"
        if img_path.exists():
            img = Image.open(img_path)
            print(f"  ✓ {style}: {img.size}")
        else:
            print(f"  ✗ {style}: NOT FOUND")
except Exception as e:
    print(f"  Error: {e}")
