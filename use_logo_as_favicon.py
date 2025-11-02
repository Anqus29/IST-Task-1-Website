"""
Simple script to copy logo.png as favicon.png
No external libraries needed - just uses built-in Python!
"""
import os
import shutil

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Paths
logo_path = os.path.join(script_dir, 'static', 'img', 'logo.png')
favicon_path = os.path.join(script_dir, 'static', 'favicon.png')

try:
    # Simply copy logo.png to favicon.png
    shutil.copy2(logo_path, favicon_path)
    
    print(f"✓ Favicon created successfully!")
    print(f"  Copied: {logo_path}")
    print(f"  To: {favicon_path}")
    print("\nNow update your templates to use:")
    print('  <link rel="icon" href="{{ url_for(\'static\', filename=\'favicon.png\') }}" type="image/png">')
    
except FileNotFoundError:
    print(f"✗ Error: Could not find logo.png at {logo_path}")
    print("  Please make sure logo.png exists in the static/img folder")
except Exception as e:
    print(f"✗ Error: {e}")
