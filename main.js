document.addEventListener('DOMContentLoaded', () => {
    // Flash message auto-dismiss
    const flashMessages = document.querySelectorAll('.flash-message');
    if (flashMessages.length > 0) {
        setTimeout(() => {
            flashMessages.forEach(msg => {
                msg.style.opacity = '0';
                msg.style.transform = 'translateY(-10px)';
                setTimeout(() => msg.remove(), 300);
            });
        }, 5000);
    }

    // Image upload preview
    const imageInput = document.getElementById('image');
    const imagePreviewContainer = document.getElementById('image-preview');
    
    if (imageInput && imagePreviewContainer) {
        imageInput.addEventListener('change', function() {
            const file = this.files[0];
            const imgElement = imagePreviewContainer.querySelector('img');
            
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    imgElement.src = e.target.result;
                    imagePreviewContainer.style.display = 'block';
                }
                reader.readAsDataURL(file);
            } else {
                imagePreviewContainer.style.display = 'none';
                imgElement.src = '';
            }
        });
    }
});
