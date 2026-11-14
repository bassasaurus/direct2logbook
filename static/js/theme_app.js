(function () {
  'use strict';

  const hero = document.querySelector('.index-app-hero');
  if (hero && window.matchMedia('(min-width: 1025px) and (prefers-reduced-motion: no-preference)').matches) {
    window.addEventListener('scroll', () => {
      hero.style.backgroundPosition = 'center ' + (-window.scrollY / 4) + 'px';
    }, {passive: true});
  }

  const messages = document.querySelectorAll('[data-animate]');
  const observer = new IntersectionObserver(entries => {
    entries.forEach(({target, isIntersecting}) => {
      if (!isIntersecting) return;
      observer.unobserve(target);
      target.style.animationDelay = Number(target.dataset.animateDelay || 0) + 's';
      target.style.animationDuration = Number(target.dataset.animateDuration || 1) + 's';
      target.classList.add('animated', target.dataset.animate);
    });
  });
  messages.forEach(message => observer.observe(message));
}());
