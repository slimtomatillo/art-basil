// Modal Manager - Handles image modal and other modal functionality

class ModalManager {
    constructor() {
        this.init();
    }

    init() {
        // Initialize image modal functionality
        this.initImageModal();
    }

    initImageModal() {
        // Get modal elements
        const modal = document.getElementById('imageModal');
        const modalImg = document.getElementById('modalImage');

        if (!modal || !modalImg) return;

        // Close modal when clicking on it
        modal.addEventListener('click', () => {
            this.closeImageModal();
        });

        // Close modal when pressing Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.style.display === 'block') {
                this.closeImageModal();
            }
        });
    }

    openImageModal(imageSrc) {
        const modal = document.getElementById('imageModal');
        const modalImg = document.getElementById('modalImage');
        
        if (modal && modalImg) {
            modal.style.display = 'block';
            modalImg.src = imageSrc;
        }
    }

    closeImageModal() {
        const modal = document.getElementById('imageModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    // Generic method to open any modal by ID
    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'block';
        }
    }

    // Generic method to close any modal by ID
    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    }

    // Method to close modal when clicking outside
    setupOutsideClickClose(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal(modalId);
                }
            });
        }
    }

    // Method to close modal with Escape key
    setupEscapeKeyClose(modalId) {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const modal = document.getElementById(modalId);
                if (modal && modal.style.display === 'block') {
                    this.closeModal(modalId);
                }
            }
        });
    }
}

// Initialize modal manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.modalManager = new ModalManager();
});
