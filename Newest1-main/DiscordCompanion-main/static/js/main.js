// Main JavaScript for Deadside Bot Dashboard

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Add SFTP credentials toggle based on access method selection
    const accessMethodSelect = document.getElementById('accessMethod');
    const sftpCredentials = document.getElementById('sftpCredentials');
    
    if (accessMethodSelect && sftpCredentials) {
        // Show/hide SFTP credentials based on selected access method
        function toggleSftpCredentials() {
            if (accessMethodSelect.value === 'sftp') {
                sftpCredentials.style.display = 'block';
            } else {
                sftpCredentials.style.display = 'none';
            }
        }
        
        // Initial state
        toggleSftpCredentials();
        
        // Listen for changes
        accessMethodSelect.addEventListener('change', toggleSftpCredentials);
    }
    
    // Enable custom form validation
    const forms = document.querySelectorAll('.needs-validation');
    
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            form.classList.add('was-validated');
        }, false);
    });
    
    // Add confirmation for dangerous actions
    const dangerousActions = document.querySelectorAll('.btn-danger');
    
    dangerousActions.forEach(button => {
        button.addEventListener('click', function(event) {
            if (!confirm('Are you sure you want to perform this action?')) {
                event.preventDefault();
            }
        });
    });
    
    // Add smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            
            if (href !== '#' && href !== '') {
                const target = document.querySelector(href);
                
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({
                        behavior: 'smooth'
                    });
                }
            }
        });
    });
});