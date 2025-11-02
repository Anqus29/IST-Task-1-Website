"""
Simple script to create a favicon.ico from logo.png
Requires Pillow: pip install Pillow
"""
from PIL import Image
import os

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Input and output paths
logo_path = os.path.join(script_dir, 'static', 'img', 'logo.png')
favicon_path = os.path.join(script_dir, 'static', 'favicon.ico')

try:
    # Open the logo
    img = Image.open(logo_path)
    
    # Convert to RGBA if needed
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Create favicon in multiple sizes (16x16, 32x32, 48x48)
    icon_sizes = [(16, 16), (32, 32), (48, 48)]
    
    # Resize and save
    img.save(favicon_path, format='ICO', sizes=icon_sizes)
    
    print(f"✓ Favicon created successfully at: {favicon_path}")
    print(f"  Sizes: 16x16, 32x32, 48x48")
    
except FileNotFoundError:
    print(f"✗ Error: Could not find logo.png at {logo_path}")
    print("  Please make sure logo.png exists in the static/img folder")
except Exception as e:
    print(f"✗ Error creating favicon: {e}")
    print("\nMake sure you have Pillow installed:")
    print("  pip install Pillow")
