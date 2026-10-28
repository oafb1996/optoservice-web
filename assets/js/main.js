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

  // Formulario de afiliación: se envía por correo con Web3Forms (https://web3forms.com).
  // La clave pública (data-access-key en el <form>) hace que llegue a afiliaciones@optoservicenic.com.
  var form = document.querySelector('[data-afil-form]');
  var success = document.querySelector('[data-afil-success]');
  var errorBox = form.querySelector('[data-afil-error]');
  var sendBtn = form.querySelector('button[type="submit"]');
  var sendLabel = sendBtn.textContent;

  function showError(msg) {
    errorBox.querySelector('[data-afil-error-text]').textContent = msg;
    errorBox.hidden = false;
  }
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    errorBox.hidden = true;
    var key = form.getAttribute('data-access-key');
    if (!key) { showError('El envío del formulario no está disponible por ahora. Puedes'); return; }

    var fd = new FormData(form);
    var g = function (k) { return (fd.get(k) || '').toString().trim(); };
    var payload = {
      access_key: key,
      subject: 'Solicitud de afiliación – ' + (g('empresa') || 'Empresa'),
      from_name: 'Sitio web Opto Service',
      botcheck: fd.get('botcheck') ? true : '',
      email: g('correo'),
      'Empresa': g('empresa'),
      'Persona de contacto': g('contacto'),
      'Teléfono': g('telefono') || '(no indicado)',
      'Mensaje': g('mensaje') || '(sin mensaje)'
    };

    sendBtn.disabled = true;
    sendBtn.textContent = 'Enviando…';
    var ctrl = typeof AbortController === 'function' ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, 15000) : null;

    fetch('https://api.web3forms.com/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(payload),
      signal: ctrl ? ctrl.signal : undefined
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok || !data.success) throw new Error('rechazado');
      });
    }).then(function () {
      form.reset();
      form.style.display = 'none';
      success.hidden = false;
      success.focus();
    }).catch(function () {
      showError('No pudimos enviar tu solicitud. Revisa tu conexión e inténtalo de nuevo. También puedes');
    }).then(function () {
      if (timer) clearTimeout(timer);
      sendBtn.disabled = false;
      sendBtn.textContent = sendLabel;
    });
  });

  // Año del pie de página
  document.querySelectorAll('[data-year]').forEach(function (el) {
    el.textContent = new Date().getFullYear();
  });

  // Promociones: ocultar las vencidas aunque el sitio no se haya regenerado
  var promos = document.querySelector('[data-promos]');
  if (promos) {
    var d = new Date();
    var hoy = d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
    promos.querySelectorAll('[data-vence]').forEach(function (card) {
      if (card.getAttribute('data-vence') < hoy) card.remove();
    });
    if (!promos.querySelector('.promo-card')) {
      promos.hidden = true;
      document.querySelectorAll('[data-promo-link]').forEach(function (a) { a.hidden = true; });
    }
  }

  var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Carruseles de fotos: cambian solos mientras están a la vista
  function loadSlide(img) {
    if (img.dataset.srcset) { img.srcset = img.dataset.srcset; delete img.dataset.srcset; }
    if (img.dataset.src) { img.src = img.dataset.src; delete img.dataset.src; }
  }
  document.querySelectorAll('[data-carousel]').forEach(function (box) {
    var slides = box.querySelectorAll('.slide');
    if (slides.length < 2) return;
    var current = 0, timer = null, visible = false;
    var interval = parseInt(box.getAttribute('data-interval'), 10) || 5000;

    var dots = document.createElement('div');
    dots.className = 'carousel-dots';
    slides.forEach(function (_, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('aria-label', 'Foto ' + (i + 1) + ' de ' + slides.length);
      if (i === 0) b.setAttribute('aria-current', 'true');
      b.addEventListener('click', function () { show(i); restart(); });
      dots.appendChild(b);
    });
    box.appendChild(dots);

    function show(i) {
      loadSlide(slides[i]);
      slides[current].classList.remove('is-active');
      dots.children[current].removeAttribute('aria-current');
      current = i;
      slides[current].classList.add('is-active');
      dots.children[current].setAttribute('aria-current', 'true');
      loadSlide(slides[(current + 1) % slides.length]); // precarga la siguiente
    }
    function restart() {
      clearInterval(timer);
      timer = null;
      if (visible && !REDUCED && !document.hidden) {
        timer = setInterval(function () { show((current + 1) % slides.length); }, interval);
      }
    }

    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        if (visible) loadSlide(slides[1]);
        restart();
      }).observe(box);
    } else {
      visible = true;
      loadSlide(slides[1]);
      restart();
    }
    document.addEventListener('visibilitychange', restart);

    // Deslizar con el dedo
    var x0 = null;
    box.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
    box.addEventListener('touchend', function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0;
      x0 = null;
      if (Math.abs(dx) > 40) {
        show((current + (dx < 0 ? 1 : slides.length - 1)) % slides.length);
        restart();
      }
    });
  });

  // Asistente de chat: el código del panel se descarga solo cuando alguien lo abre
  var chatOpeners = document.querySelectorAll('[data-chat-open]');
  if (chatOpeners.length) {
    var chatLoading = null;
    var loadChat = function () {
      if (window.OptoChat) return Promise.resolve();
      if (!chatLoading) {
        chatLoading = new Promise(function (ok, fail) {
          var s = document.createElement('script');
          s.src = 'assets/js/chat.js';
          s.onload = function () { window.OptoChat ? ok() : fail(); };
          s.onerror = function () { chatLoading = null; fail(); };
          document.head.appendChild(s);
        });
      }
      return chatLoading;
    };
    chatOpeners.forEach(function (btn) {
      var warm = function () { loadChat().catch(function () {}); };
      btn.addEventListener('pointerenter', warm, { once: true });
      btn.addEventListener('touchstart', warm, { once: true, passive: true });
      btn.addEventListener('click', function () {
        loadChat().then(function () { window.OptoChat.open(btn); }, function () {
          var wa = btn.getAttribute('data-chat-fallback');
          if (wa) window.open(wa, '_blank', 'noopener');
        });
      });
    });
  }

  // Aparición suave al hacer scroll
  if (REDUCED || !('IntersectionObserver' in window)) return;
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
