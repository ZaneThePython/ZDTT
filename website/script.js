document.addEventListener('DOMContentLoaded', () => {
  const navToggle = document.querySelector('.nav__toggle');
  const navLinks = document.querySelector('.nav__links');
  const yearEl = document.getElementById('year');

  if (yearEl) {
    yearEl.textContent = new Date().getFullYear();
  }

  if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
      navLinks.classList.toggle('is-open');
    });
  }

  document.querySelectorAll('[data-copy]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = document.querySelector(button.dataset.copy);
      if (!target) {
        return;
      }
      navigator.clipboard?.writeText(target.textContent.trim()).then(() => {
        button.textContent = 'Copied!';
        setTimeout(() => {
          button.textContent = 'Copy Install Command';
        }, 1800);
      }).catch(() => {
        button.textContent = 'Unable to copy';
        setTimeout(() => {
          button.textContent = 'Copy Install Command';
        }, 1800);
      });
    });
  });
});
