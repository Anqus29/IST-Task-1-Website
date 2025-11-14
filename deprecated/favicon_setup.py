"""
Favicon setup utility (merged):
- Generate static/favicon.ico from static/img/logo.png (requires Pillow if available)
- Copy static/img/logo.png to static/favicon.png (no external deps)

Usage:
  py favicon_setup.py          # do both (PNG + ICO)
  py favicon_setup.py --all    # same as default
  py favicon_setup.py --png    # only copy logo.png -> static/favicon.png
  py favicon_setup.py --ico    # only generate static/favicon.ico (Pillow required)

Notes:
- Your Flask app serves /favicon.ico from the best available asset in priority:
  1) static/img/logo.png (PNG via server route)
  2) static/favicon.png (PNG)
  3) static/favicon.ico (ICO)
- This script helps ensure those assets exist.
"""
import os
import sys
import shutil
import argparse
from typing import Iterable, Tuple

# Resolve project root as the directory containing this file
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(ROOT_DIR, 'static', 'img')
STATIC_DIR = os.path.join(ROOT_DIR, 'static')

LOGO_PNG = os.path.join(IMG_DIR, 'logo.png')
FAVICON_PNG = os.path.join(STATIC_DIR, 'favicon.png')
FAVICON_ICO = os.path.join(STATIC_DIR, 'favicon.ico')


def _print_ok(msg: str):
    print(f"\u2713 {msg}")


def _print_err(msg: str):
    print(f"\u2717 {msg}")


def ensure_dirs(*paths: str) -> None:
    for p in paths:
        os.makedirs(p, exist_ok=True)


def copy_png(logo_path: str = LOGO_PNG, out_png: str = FAVICON_PNG) -> bool:
    """Copy logo.png to favicon.png. Returns True on success."""
    try:
        if not os.path.exists(logo_path):
            _print_err(f"Could not find logo.png at {logo_path}")
            return False
        ensure_dirs(os.path.dirname(out_png))
        shutil.copy2(logo_path, out_png)
        _print_ok(f"Favicon PNG created: {out_png}")
        return True
    except Exception as e:
        _print_err(f"Error copying PNG: {e}")
        return False


def generate_ico(logo_path: str = LOGO_PNG, out_ico: str = FAVICON_ICO,
                 sizes: Iterable[Tuple[int, int]] = ((16,16), (32,32), (48,48))) -> bool:
    """Generate favicon.ico from logo.png using Pillow. Returns True on success.
    If Pillow is not installed, prints guidance and returns False.
    """
    try:
        from PIL import Image  # type: ignore
    except Exception:
        _print_err("Pillow not installed. To enable ICO generation, run: pip install Pillow")
        return False

    try:
        if not os.path.exists(logo_path):
            _print_err(f"Could not find logo.png at {logo_path}")
            return False
        ensure_dirs(os.path.dirname(out_ico))
        img = Image.open(logo_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        img.save(out_ico, format='ICO', sizes=list(sizes))
        _print_ok(f"Favicon ICO created: {out_ico} (sizes: {', '.join(f'{w}x{h}' for w,h in sizes)})")
        return True
    except Exception as e:
        _print_err(f"Error creating ICO: {e}")
        return False


def run_cli(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create favicon assets from logo.png")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--png', action='store_true', help='Only create static/favicon.png from static/img/logo.png')
    group.add_argument('--ico', action='store_true', help='Only create static/favicon.ico (requires Pillow)')
    group.add_argument('--all', action='store_true', help='Create both favicon.png and favicon.ico (default)')

    args = parser.parse_args(argv)

    do_png = args.png or args.all or (not args.png and not args.ico and not args.all)
    do_ico = args.ico or args.all or (not args.png and not args.ico and not args.all)

    ok = True
    if do_png:
        ok = copy_png(LOGO_PNG, FAVICON_PNG) and ok
    if do_ico:
        ok = generate_ico(LOGO_PNG, FAVICON_ICO) and ok

    if ok:
        print("\nDone. Your Flask app will serve /favicon.ico using the best available asset.")
        return 0
    else:
        print("\nCompleted with some errors.")
        return 1


if __name__ == '__main__':
    sys.exit(run_cli())
