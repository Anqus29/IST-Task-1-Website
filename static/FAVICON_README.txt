To add a favicon - MULTIPLE METHODS:

METHOD 1: AUTOMATIC (using Python script)
1. Install Pillow: pip install Pillow
2. Run: python create_favicon.py
3. This will create favicon.ico from the logo.png in static/img/

METHOD 2: ONLINE CONVERTER (Easiest - No installation needed!)
1. Go to https://favicon.io/favicon-converter/
2. Upload your static/img/logo.png
3. Click "Download" to get the favicon package
4. Extract and copy the favicon.ico file to the static/ folder

METHOD 3: ALTERNATIVE ONLINE TOOLS
- https://www.favicon-generator.org/ - Upload logo.png and download
- https://realfavicongenerator.net/ - More advanced options
- https://convertio.co/png-ico/ - Simple PNG to ICO converter

METHOD 4: USE PNG DIRECTLY (Modern browsers support this!)
Instead of .ico, you can use the logo.png directly:
1. Just use logo.png as-is (already in static/img/)
2. Update templates to use:
   <link rel="icon" href="{{ url_for('static', filename='img/logo.png') }}" type="image/png">

METHOD 5: WINDOWS PAINT (if you have it)
1. Open logo.png in Paint
2. Resize to 32x32 or 64x64 pixels
3. Save as .ico format (if available) or save as PNG and use Method 2

CURRENT SETUP:
The templates are configured to use:
<link rel="icon" href="{{ url_for('static', filename='favicon.ico') }}" type="image/x-icon">

You can also change this to use logo.png directly - all modern browsers support PNG favicons!

GOOD NEWS: A fallback route is built-in.
Even if favicon.ico is missing, the app will automatically serve:
 1) static/favicon.png (if present), or
 2) static/img/logo.png
at the /favicon.ico URL, so you should always see a favicon without extra work.
