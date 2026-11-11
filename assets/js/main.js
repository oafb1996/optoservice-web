// Opto Service — interacción del sitio (sin dependencias)
(function () {
  'use strict';

  var WHATSAPP = '50584024868';
  var MOBILE = window.matchMedia('(max-width: 899.98px)');
  var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var HOVER = window.matchMedia('(hover: hover) and (pointer: fine)');

  // Menú móvil
  var burger = document.querySelector('[data-menu-toggle]');
  var menu = document.getElementById('nav-menu');
  function setMenu(open) {
    menu.hidden = !open;
    burger.setAttribute('aria-expanded', String(open));
    burger.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');
  }
  burger.addEventListener('click', function () { setMenu(menu.hidden); });
  menu.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', function () { setMenu(false); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !menu.hidden) { setMenu(false); burger.focus(); }
  });
  MOBILE.addEventListener('change', function () { setMenu(false); });

  // Preguntas frecuentes: una abierta a la vez (para navegadores sin <details name>)
  var faqs = Array.prototype.slice.call(document.querySelectorAll('details[name="faq"]'));
  faqs.forEach(function (d) {
    d.addEventListener('toggle', function () {
      if (d.open) faqs.forEach(function (o) { if (o !== d && o.open) o.open = false; });
    });
  });

  // ===== Agendar cita: 3 pasos que arman el mensaje de WhatsApp =====
  // Sin JavaScript (o sin <dialog>), los botones "Agendar" abren WhatsApp directamente.
  var sheet = document.querySelector('[data-sheet]');
  if (sheet && typeof sheet.showModal === 'function') {
    var sForm = sheet.querySelector('[data-sheet-form]');
    var steps = sheet.querySelectorAll('[data-step]');
    var bars = sheet.querySelectorAll('.sheet-bars span');
    var stepLabel = sheet.querySelector('[data-sheet-step]');
    var title = sheet.querySelector('[data-sheet-title]');
    var nextBtn = sheet.querySelector('[data-sheet-next]');
    var backBtn = sheet.querySelector('[data-sheet-back]');
    var sendLink = sheet.querySelector('[data-sheet-send]');
    var sendNote = sheet.querySelector('[data-sheet-note]');
    var TITLES = ['¿Qué necesitas?', '¿En cuál sucursal?', '¿Cuándo te viene bien?'];
    var REQUIRED = ['servicio', 'sucursal'];
    var step = 1;
    var opener = null;

    var value = function (name) {
      var el = sForm.querySelector('input[name="' + name + '"]:checked');
      return el ? el.value : null;
    };
    var message = function () {
      var svc = value('servicio'), br = value('sucursal'), when = value('cuando');
      var name = (sForm.elements.nombre.value || '').replace(/\s+/g, ' ').trim().slice(0, 60);
      var msg = '¡Hola Opto Service! ' + (svc && svc !== 'no-seguro'
        ? 'Quisiera agendar una cita para: ' + svc
        : 'Quisiera agendar una cita, pero no estoy seguro de qué servicio necesito');
      if (br) msg += ', en la sucursal de ' + br;
      msg += '.';
      if (when) msg += ' ' + when;
      if (name) msg += ' Mi nombre es ' + name + '.';
      return msg;
    };
    var canNext = function () {
      return step > REQUIRED.length || value(REQUIRED[step - 1]) !== null;
    };
    var render = function (focusTitle) {
      steps.forEach(function (el) { el.hidden = +el.getAttribute('data-step') !== step; });
      bars.forEach(function (b, i) { b.classList.toggle('is-done', i < step); });
      stepLabel.textContent = 'Paso ' + step + ' de 3';
      title.textContent = TITLES[step - 1];
      nextBtn.hidden = step === 3;
      nextBtn.setAttribute('aria-disabled', String(!canNext()));
      backBtn.hidden = step === 1;
      sendLink.hidden = sendNote.hidden = step !== 3;
      sendLink.href = 'https://wa.me/' + WHATSAPP + '?text=' + encodeURIComponent(message());
      if (focusTitle) title.focus();
    };

    var open = function (from) {
      opener = from || null;
      sForm.reset();
      step = 1;
      // Un enlace puede dejar elegido el servicio (por ejemplo, el recuadro de una foto)
      var pre = from && from.getAttribute('data-servicio');
      if (pre) {
        sForm.querySelectorAll('input[name="servicio"]').forEach(function (r) { r.checked = r.value === pre; });
      }
      setMenu(false);
      if (window.OptoChat && typeof window.OptoChat.close === 'function') window.OptoChat.close();
      render(false);
      sheet.showModal();
      title.focus();
    };
    var close = function () { if (sheet.open) sheet.close(); };

    document.querySelectorAll('[data-agendar]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button > 0) return; // abrir en otra pestaña: WhatsApp directo
        e.preventDefault();
        open(a);
      });
    });
    sForm.addEventListener('change', function () { render(false); });
    sForm.addEventListener('input', function () { render(false); });
    sForm.addEventListener('submit', function (e) {
      e.preventDefault();
      if (step < 3) nextBtn.click(); else sendLink.click();
    });
    nextBtn.addEventListener('click', function () {
      if (!canNext()) {
        var first = steps[step - 1].querySelector('input');
        if (first) first.focus();
        return;
      }
      step += 1;
      render(true);
    });
    backBtn.addEventListener('click', function () { step = Math.max(1, step - 1); render(true); });
    sheet.querySelector('[data-sheet-close]').addEventListener('click', close);
    sendLink.addEventListener('click', function () { setTimeout(close, 300); });
    // Tocar fuera de la hoja la cierra
    sheet.addEventListener('click', function (e) { if (e.target === sheet) close(); });
    sheet.addEventListener('close', function () {
      if (opener && document.contains(opener) && opener.offsetParent !== null) opener.focus();
      opener = null;
    });
  }

  // ===== Formulario de afiliación =====
  // Se envía por correo con Web3Forms (https://web3forms.com). La clave pública está en
  // data-access-key del <form>; el correo de destino lo define la clave.
  var form = document.querySelector('[data-afil-form]');
  if (form) { // solo en el inicio
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
        form.hidden = true;
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
  }

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

  // ===== Carruseles de fotos: cambian solos mientras están a la vista =====
  // Se detienen al pasar el mouse o al usar el teclado sobre ellos, y tienen un botón para pausarlos
  // (pautas de accesibilidad: lo que se mueve solo más de 5 segundos se debe poder pausar).
  var ICON_PAUSE = '<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true"><rect x="2.5" y="2" width="3" height="10"/><rect x="8.5" y="2" width="3" height="10"/></svg>';
  var ICON_PLAY = '<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true"><path d="M3.5 2v10l8-5z"/></svg>';
  function loadSlide(slide) {
    slide.querySelectorAll('[data-srcset], [data-src]').forEach(function (el) {
      if (el.dataset.srcset) { el.srcset = el.dataset.srcset; delete el.dataset.srcset; }
      if (el.dataset.src) { el.src = el.dataset.src; delete el.dataset.src; }
    });
  }
  document.querySelectorAll('[data-carousel]').forEach(function (box) {
    var slides = box.querySelectorAll('.slide');
    if (slides.length < 2) return;
    var current = 0, timer = null, visible = false;
    var paused = false, hovering = false, focused = false;
    var interval = parseInt(box.getAttribute('data-interval'), 10) || 5000;
    var outside = box.getAttribute('data-dots') === 'outside';

    // Controles: pausa + una línea por foto (debajo de la portada, sobre la foto en las demás)
    var bar = document.createElement('div');
    bar.className = 'carousel-dots ' + (outside ? 'is-outside' : 'is-inside');
    bar.setAttribute('role', 'group');
    bar.setAttribute('aria-label', 'Fotos');
    var toggle = null;
    if (!REDUCED) {
      toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'carousel-toggle';
      toggle.addEventListener('click', function () {
        paused = !paused;
        if (!paused) { hovering = false; focused = false; } // "Reanudar" reanuda de inmediato
        paint();
        restart();
      });
      bar.appendChild(toggle);
    }
    var dots = [];
    slides.forEach(function (_, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'carousel-dot';
      b.setAttribute('aria-label', 'Foto ' + (i + 1) + ' de ' + slides.length);
      if (i === 0) b.setAttribute('aria-current', 'true');
      b.addEventListener('click', function () { show(i); restart(); });
      dots.push(b);
      bar.appendChild(b);
    });
    // Flechas del teclado sobre los indicadores
    bar.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      e.preventDefault();
      var i = (current + (e.key === 'ArrowRight' ? 1 : slides.length - 1)) % slides.length;
      show(i);
      dots[i].focus();
    });
    if (outside) box.parentNode.insertBefore(bar, box.nextSibling); else box.appendChild(bar);

    function paint() {
      if (!toggle) return;
      toggle.innerHTML = paused ? ICON_PLAY : ICON_PAUSE;
      toggle.setAttribute('aria-label', paused ? 'Reanudar las fotos' : 'Pausar las fotos');
      toggle.setAttribute('aria-pressed', String(paused));
    }
    function show(i) {
      loadSlide(slides[i]);
      slides[current].classList.remove('is-active');
      dots[current].removeAttribute('aria-current');
      current = i;
      slides[current].classList.add('is-active');
      dots[current].setAttribute('aria-current', 'true');
      loadSlide(slides[(current + 1) % slides.length]); // precarga la siguiente
    }
    function restart() {
      clearInterval(timer);
      timer = null;
      if (visible && !REDUCED && !document.hidden && !paused && !hovering && !focused) {
        timer = setInterval(function () { show((current + 1) % slides.length); }, interval);
      }
    }
    paint();

    // Se detiene mientras el mouse o el foco del teclado están sobre la foto o sus controles
    [box, bar].forEach(function (el) {
      if (HOVER.matches) { // solo con mouse: en pantallas táctiles no hay "mouse fuera"
        el.addEventListener('mouseenter', function () { hovering = true; restart(); });
        el.addEventListener('mouseleave', function () { hovering = false; restart(); });
      }
      el.addEventListener('focusin', function (e) { // solo foco de teclado, no clics
        var kb = true;
        try { kb = e.target.matches(':focus-visible'); } catch (err) { /* navegador antiguo */ }
        if (kb) { focused = true; restart(); }
      });
      el.addEventListener('focusout', function (e) {
        if (!box.contains(e.relatedTarget) && !bar.contains(e.relatedTarget)) { focused = false; restart(); }
      });
    });

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

  // ===== Asistente de chat: el código del panel se descarga solo cuando alguien lo abre =====
  var chatOpeners = document.querySelectorAll('[data-chat-open]');
  if (chatOpeners.length) {
    var chatLoading = null;
    var loadChat = function () {
      if (window.OptoChat) return Promise.resolve();
      if (!chatLoading) {
        chatLoading = new Promise(function (ok, fail) {
          var s = document.createElement('script');
          s.src = '/assets/js/chat.js';
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
})();
