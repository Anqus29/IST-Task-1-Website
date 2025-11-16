// Cropper.js initialization for product image editing
// Requires Cropper.js library (https://fengyuanchen.github.io/cropperjs/)
document.addEventListener('DOMContentLoaded', function() {
    var image = document.getElementById('product-image-edit');
    if (image) {
        var cropper = new Cropper(image, {
            aspectRatio: 220 / 160,
            viewMode: 1,
            autoCropArea: 1,
            movable: true,
            zoomable: true,
            rotatable: true,
            scalable: true,
            crop: function(event) {
                // You can update hidden fields with crop data here
                document.getElementById('crop-x').value = event.detail.x;
                document.getElementById('crop-y').value = event.detail.y;
                document.getElementById('crop-width').value = event.detail.width;
                document.getElementById('crop-height').value = event.detail.height;
            }
        });
    }
});
