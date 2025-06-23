// Mobile menu toggle logic
const mobileMenuToggle = document.getElementById('mobileMenuToggle');
const mobileMenuOverlay = document.getElementById('mobileMenuOverlay');
const closeMobileToolbar = document.getElementById('closeMobileToolbar');

if (mobileMenuToggle && mobileMenuOverlay) {
  mobileMenuToggle.addEventListener('click', () => {
    mobileMenuOverlay.classList.toggle('active');
    document.body.classList.toggle('modal-open', mobileMenuOverlay.classList.contains('active'));
  });
  // Optional: close menu when clicking outside or on a menu item
  mobileMenuOverlay.addEventListener('click', (e) => {
    if (e.target === mobileMenuOverlay) {
      mobileMenuOverlay.classList.remove('active');
      document.body.classList.remove('modal-open');
    }
  });
}

if (closeMobileToolbar && mobileMenuOverlay) {
  closeMobileToolbar.addEventListener('click', () => {
    mobileMenuOverlay.classList.remove('active');
    document.body.classList.remove('modal-open');
  });
}
