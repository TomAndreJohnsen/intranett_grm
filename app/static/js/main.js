/**
 * Logout function - calls /auth/logout and redirects to login
 */
async function logoutUser() {
    try {
        // Call the unified app logout endpoint
        const response = await fetch('/auth/logout', {
            method: 'POST',
            credentials: 'include', // Include session cookies
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            console.log('Logout successful');
            // The response might contain a redirect URL to Microsoft logout
            const data = await response.json();
            if (data.logout_url) {
                window.location.href = data.logout_url;
                return;
            }
        } else {
            console.warn('Logout request failed, but continuing...');
        }
    } catch (error) {
        console.error('Logout error:', error);
    }

    // Fallback: redirect to home page
    window.location.href = '/';
}

document.addEventListener('DOMContentLoaded', function() {

    // User dropdown functionality
    const userMenuBtn = document.querySelector('.user-menu-btn');
    const dropdownContent = document.querySelector('.dropdown-content');

    if (userMenuBtn) {
        userMenuBtn.addEventListener('click', function(e) {
            e.preventDefault();
            dropdownContent.style.display = dropdownContent.style.display === 'block' ? 'none' : 'block';
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!userMenuBtn.contains(e.target) && !dropdownContent.contains(e.target)) {
                dropdownContent.style.display = 'none';
            }
        });
    }

    // Auto-resize textarea
    const textareas = document.querySelectorAll('.post-textarea');
    textareas.forEach(textarea => {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    });

    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;

            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    isValid = false;
                    field.style.borderColor = 'var(--primary-red)';
                } else {
                    field.style.borderColor = 'var(--border-color)';
                }
            });

            if (!isValid) {
                e.preventDefault();
                alert('Vennligst fyll ut alle påkrevde felt');
            }
        });
    });

    // Flash message auto-hide
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.remove();
            }, 300);
        }, 5000);
    });

    // Mobile navigation toggle
    const navToggle = document.querySelector('.nav-toggle');
    const navMenu = document.querySelector('.nav-menu');

    if (navToggle) {
        navToggle.addEventListener('click', function() {
            navMenu.classList.toggle('nav-menu-open');
        });
    }

    // Post actions
    document.querySelectorAll('.post-action').forEach(action => {
        action.addEventListener('click', function() {
            const actionType = this.querySelector('span').textContent;

            // Add visual feedback
            this.style.color = 'var(--primary-green)';
            setTimeout(() => {
                this.style.color = '';
            }, 200);

            // Here you can add functionality for likes, comments, shares
            console.log('Action clicked:', actionType);
        });
    });

    // Smooth scrolling for internal links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
});