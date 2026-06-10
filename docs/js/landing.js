/* ─── Scroll progress bar + frosted nav ──────────────────────────────────── */
const progressBar = document.createElement('div');
progressBar.className = 'scroll-progress';
document.body.prepend(progressBar);

const navEl = document.getElementById('nav');

window.addEventListener('scroll', () => {
  const max    = document.documentElement.scrollHeight - window.innerHeight;
  const ratio  = max > 0 ? window.scrollY / max : 0;
  progressBar.style.transform = `scaleX(${ratio})`;
  navEl?.classList.toggle('nav--scrolled', window.scrollY > 40);
}, { passive: true });

/* ─── Libraries dropdown ─────────────────────────────────────────────────── */
const librariesDropdown = document.getElementById('nav-libraries');
const librariesTrigger  = librariesDropdown?.querySelector('.nav-dropdown-trigger');

librariesTrigger?.addEventListener('click', e => {
  e.stopPropagation();
  const isOpen = librariesDropdown.classList.toggle('open');
  librariesTrigger.setAttribute('aria-expanded', isOpen);
});

document.addEventListener('click', e => {
  if (!e.target.closest('#nav-libraries')) {
    librariesDropdown?.classList.remove('open');
    librariesTrigger?.setAttribute('aria-expanded', 'false');
  }
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    librariesDropdown?.classList.remove('open');
    librariesTrigger?.setAttribute('aria-expanded', 'false');
  }
});

/* ─── Theme toggle ───────────────────────────────────────────────────────── */
const themeToggle = document.getElementById('theme-toggle');

themeToggle?.addEventListener('click', () => {
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('pianove-theme', next);
});

/* ─── Enable theme transitions after page-enter animation settles ────────── */
setTimeout(() => document.body.classList.add('transitions-ready'), 450);

/* ─── Page exit transition ───────────────────────────────────────────────── */
document.querySelectorAll('a[href]').forEach(link => {
  const href = link.getAttribute('href');
  if (!href || href.startsWith('#') || href.startsWith('http') || href.startsWith('//') || href.startsWith('mailto')) return;
  link.addEventListener('click', e => {
    e.preventDefault();
    const target = href;
    document.documentElement.classList.add('page-leaving');
    setTimeout(() => { window.location.href = target; }, 260);
  });
});

/* ─── Nav scroll-spy + hamburger ─────────────────────────────────────────── */
const navLinks    = document.querySelectorAll('.nav-links a[data-section]');
const hamburger   = document.getElementById('nav-hamburger');
const navLinksCtr = document.querySelector('.nav-links');

hamburger?.addEventListener('click', () => navLinksCtr.classList.toggle('open'));
navLinksCtr?.querySelectorAll('a').forEach(a => {
  a.addEventListener('click', () => navLinksCtr.classList.remove('open'));
});

const sections = Array.from(document.querySelectorAll('section[id]'));
const spyObserver = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      navLinks.forEach(a => a.classList.toggle('active', a.dataset.section === e.target.id));
    }
  });
}, { rootMargin: '-40% 0px -55% 0px' });
sections.forEach(s => spyObserver.observe(s));

/* ─── Scroll-reveal ──────────────────────────────────────────────────────── */
const revealObserver = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('is-visible');
      revealObserver.unobserve(e.target);
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));
