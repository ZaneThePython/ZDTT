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

  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const href = this.getAttribute('href');
      if (href === '#' || href === '#top') return;
      
      e.preventDefault();
      const target = document.querySelector(href);
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    });
  });

  // Intersection Observer for fade-in animations
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, observerOptions);

  // Observe sections and cards for fade-in effect (exclude hero section)
  const animatedElements = document.querySelectorAll('.section:not(.hero), .card, .metric, figure, .install-steps li');
  animatedElements.forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
  });

});
