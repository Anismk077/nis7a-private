document.querySelectorAll('.faq-item').forEach((item) => {
  const button = item.querySelector('.faq-question');

  button?.addEventListener('click', () => {
    const isOpen = item.classList.contains('open');

    document.querySelectorAll('.faq-item.open').forEach((openItem) => {
      openItem.classList.remove('open');
    });

    if (!isOpen) {
      item.classList.add('open');
    }
  });
});

const navigateWithTransition = (targetUrl) => {
  document.body.classList.add('is-transitioning');
  setTimeout(() => {
    window.location.href = targetUrl;
  }, 220);
};

const links = document.querySelectorAll('a[href]');
links.forEach((link) => {
  link.addEventListener('click', (event) => {
    const href = link.getAttribute('href') || '';

    if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) {
      return;
    }

    const isExternal = /^https?:\/\//i.test(href);
    if (isExternal && !href.startsWith(window.location.origin)) {
      return;
    }

    event.preventDefault();
    navigateWithTransition(href);
  });
});

const root = document.documentElement;
const savedTheme = localStorage.getItem('nis7a-theme') || 'default';
const availableThemes = ['default', 'christmas', 'midnight', 'aurora', 'sunset', 'neon'];

const applyTheme = (theme) => {
  const safeTheme = availableThemes.includes(theme) ? theme : 'default';
  root.setAttribute('data-theme', safeTheme);
  localStorage.setItem('nis7a-theme', safeTheme);

  document.querySelectorAll('.theme-option').forEach((button) => {
    button.classList.toggle('active', button.getAttribute('data-theme') === safeTheme);
  });
};

applyTheme(savedTheme);

document.querySelectorAll('.theme-option').forEach((button) => {
  button.addEventListener('click', () => {
    applyTheme(button.getAttribute('data-theme') || 'default');
  });
});

window.addEventListener('storage', (event) => {
  if (event.key === 'nis7a-theme') {
    applyTheme(event.newValue || 'default');
  }
});
