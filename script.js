document.addEventListener('DOMContentLoaded', () => {
  const navToggle = document.querySelector('.nav__toggle');
  const navLinks = document.querySelector('.nav__links');
  const yearEl = document.getElementById('year');

  if (yearEl) {
    yearEl.textContent = new Date().getFullYear();
  }

  if (navToggle && navLinks) {
    const setExpanded = (isOpen) => {
      navLinks.classList.toggle('is-open', isOpen);
      navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    };

    navToggle.addEventListener('click', () => {
      const nextState = !navLinks.classList.contains('is-open');
      setExpanded(nextState);
    });

    navLinks.addEventListener('click', (event) => {
      if (event.target.closest('a')) {
        setExpanded(false);
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && navLinks.classList.contains('is-open')) {
        setExpanded(false);
        navToggle.focus();
      }
    });
  }

  document.querySelectorAll('[data-copy]').forEach((button) => {
    const defaultLabel = button.textContent;
    const setStatus = (label) => {
      button.textContent = label;
      setTimeout(() => {
        button.textContent = defaultLabel;
      }, 1800);
    };

    button.addEventListener('click', () => {
      const target = document.querySelector(button.dataset.copy);
      if (!target) {
        return;
      }
      const textToCopy = target.textContent.trim();
      const clipboard = navigator.clipboard;

      if (clipboard && typeof clipboard.writeText === 'function') {
        clipboard.writeText(textToCopy).then(() => {
          setStatus('Copied!');
        }).catch(() => {
          setStatus('Copy manually');
        });
        return;
      }

      try {
        const range = document.createRange();
        range.selectNodeContents(target);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        const successful = document.execCommand('copy');
        selection.removeAllRanges();
        setStatus(successful ? 'Copied!' : 'Copy manually');
      } catch (error) {
        setStatus('Copy manually');
      }
    });
  });
});
