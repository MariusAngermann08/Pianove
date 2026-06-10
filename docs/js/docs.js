/* ─── Frosted nav on scroll ──────────────────────────────────────────────── */
const docsNav = document.getElementById('nav');
window.addEventListener('scroll', () => {
  docsNav?.classList.toggle('nav--scrolled', window.scrollY > 40);
}, { passive: true });

/* ─── Syntax highlighting init ───────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  if (typeof hljs !== 'undefined') {
    hljs.highlightAll();
  }
});

/* ─── Re-highlight on theme change (token CSS handles colors automatically) ─ */
// Token colors are handled entirely via CSS [data-theme="dark"] .hljs-* rules.
// No JS needed for theme switching of highlighted code.

/* ─── Sidebar active-section tracking ───────────────────────────────────── */
const sidebarLinks = document.querySelectorAll('.docs-sidebar a[href]');

function markActive(href) {
  sidebarLinks.forEach(a => {
    const linkHref = a.getAttribute('href');
    // Match exact filename or anchor
    const isCurrent =
      linkHref === href ||
      linkHref === '#' + href.replace(/^#/, '') ||
      (href.includes('#') ? linkHref === href.split('#')[1] : false);
    a.classList.toggle('active', isCurrent);
  });
}

// If the page has doc-section elements, use IntersectionObserver
const docSections = document.querySelectorAll('.doc-section[id]');
if (docSections.length > 0) {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        sidebarLinks.forEach(a => {
          a.classList.toggle('active', a.getAttribute('href') === '#' + e.target.id);
        });
      }
    });
  }, { rootMargin: '-10% 0px -80% 0px', threshold: 0 });
  docSections.forEach(s => observer.observe(s));
} else {
  // Single-topic page: mark the link that matches this filename
  const filename = location.pathname.split('/').pop() || 'index.html';
  sidebarLinks.forEach(a => {
    a.classList.toggle('active', a.getAttribute('href') === filename);
  });
}

/* ─── Smooth sidebar click ───────────────────────────────────────────────── */
sidebarLinks.forEach(a => {
  if (!a.getAttribute('href').startsWith('#')) return;
  a.addEventListener('click', e => {
    const target = document.querySelector(a.getAttribute('href'));
    if (!target) return;
    e.preventDefault();
    const navH = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--nav-h')) || 52;
    window.scrollTo({ top: target.getBoundingClientRect().top + scrollY - navH - 16, behavior: 'smooth' });
  });
});
