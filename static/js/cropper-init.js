// Cropper.js initialization for product image editing
// Requires Cropper.js library (https://fengyuanchen.github.io/cropperjs/)
document.addEventListener('DOMContentLoaded', function() {
    var image = document.getElementById('product-image-edit');
    var preview = document.getElementById('crop-preview');
    var resetBtn = document.getElementById('crop-reset');
    var rotateBtn = document.getElementById('crop-rotate');
    var zoomInBtn = document.getElementById('crop-zoom-in');
    var zoomOutBtn = document.getElementById('crop-zoom-out');
    if (image) {
        var cropper = new Cropper(image, {
            aspectRatio: NaN, // Allow free aspect ratio, can be set dynamically
            viewMode: 2,
            autoCropArea: 0.85,
            movable: true,
            zoomable: true,
            rotatable: true,
            scalable: true,
            background: true,
            minCropBoxWidth: 50,
            minCropBoxHeight: 50,
            ready: function() {
                // Set default aspect ratio if needed
                cropper.setAspectRatio(220/160);
            },
            crop: function(event) {
                document.getElementById('crop-x').value = event.detail.x;
                document.getElementById('crop-y').value = event.detail.y;
                document.getElementById('crop-width').value = event.detail.width;
                document.getElementById('crop-height').value = event.detail.height;
                // Live preview
                if (preview) {
                    var canvas = cropper.getCroppedCanvas({ width: 220, height: 160 });
                    preview.src = canvas.toDataURL('image/png');
                }
            }
        });
        // Controls
        if (resetBtn) {
            resetBtn.addEventListener('click', function() {
                cropper.reset();
            });
        }
        if (rotateBtn) {
            rotateBtn.addEventListener('click', function() {
                cropper.rotate(90);
            });
        }
        if (zoomInBtn) {
            zoomInBtn.addEventListener('click', function() {
                cropper.zoom(0.2);
            });
        }
        if (zoomOutBtn) {
            zoomOutBtn.addEventListener('click', function() {
                cropper.zoom(-0.2);
            });
        }
    }
});
