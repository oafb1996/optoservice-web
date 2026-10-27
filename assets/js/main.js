// Opto Service — interacción del sitio (sin dependencias)
(function () {
  'use strict';

  var MOBILE = window.matchMedia('(max-width: 879.98px)');
  var nav = document.querySelector('[data-nav]');
  var burger = document.querySelector('[data-menu-toggle]');

  // Navegación: fondo de vidrio al hacer scroll
  function onScroll() {
    nav.classList.toggle('is-scrolled', window.scrollY > 24);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // Menú móvil
  function setMenu(open) {
    nav.classList.toggle('menu-open', open);
    burger.setAttribute('aria-expanded', String(open));
  }
  burger.addEventListener('click', function () {
    setMenu(!nav.classList.contains('menu-open'));
  });
  document.querySelectorAll('[data-menu-close]').forEach(function (a) {
    a.addEventListener('click', function () { setMenu(false); });
  });
  MOBILE.addEventListener('change', function () { setMenu(false); });

  // Preguntas frecuentes: un panel abierto a la vez
  var faqButtons = Array.prototype.slice.call(document.querySelectorAll('[data-faq-toggle]'));
  function setFaq(btn, open) {
    var panel = document.getElementById(btn.getAttribute('aria-controls'));
    btn.setAttribute('aria-expanded', String(open));
    btn.querySelector('[data-faq-icon]').style.transform = open ? 'rotate(45deg)' : 'none';
    panel.style.maxHeight = open ? '460px' : '0px';
  }
  faqButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var open = btn.getAttribute('aria-expanded') !== 'true';
      faqButtons.forEach(function (b) { setFaq(b, b === btn && open); });
    });
  });

  // Formulario de afiliación: abre el correo con la solicitud lista
  var form = document.querySelector('[data-afil-form]');
  var success = document.querySelector('[data-afil-success]');
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var fd = new FormData(form);
    var g = function (k) { return (fd.get(k) || '').toString().trim(); };
    var to = 'afiliaciones@optoservice.com';
    var subject = 'Solicitud de afiliación – ' + (g('empresa') || 'Empresa');
    var body = [
      'Nueva solicitud de afiliación desde el sitio web:',
      '',
      'Empresa: ' + g('empresa'),
      'Persona de contacto: ' + g('contacto'),
      'Correo: ' + g('correo'),
      'Teléfono: ' + g('telefono'),
      '',
      'Mensaje:',
      g('mensaje') || '(sin mensaje)'
    ].join('\n');
    window.location.href = 'mailto:' + to + '?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
    form.style.display = 'none';
    success.hidden = false;
  });

  // Aparición suave al hacer scroll
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) {
        e.target.style.opacity = '1';
        e.target.style.transform = 'none';
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
  document.querySelectorAll('[data-reveal]').forEach(function (el, i) {
    el.style.opacity = '0';
    el.style.transform = 'translateY(28px) scale(.99)';
    el.style.transition = 'opacity .75s cubic-bezier(.22,.61,.36,1), transform .75s cubic-bezier(.22,.61,.36,1)';
    el.style.transitionDelay = ((i % 5) * 0.07) + 's';
    io.observe(el);
  });
})();
