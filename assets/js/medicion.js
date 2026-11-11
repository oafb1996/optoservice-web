// Opto Service — medición de clics (Google Analytics 4)
// Solo se carga si scripts/build.py activó GA4 (hay ID en content/analitica.json y la
// política de privacidad está publicada). Nunca se envían nombres, mensajes, el servicio
// elegido ni ningún dato de salud: solo qué botón se tocó, dónde y la sucursal si se sabe.
//
// Eventos:
//   clic_whatsapp   enlace a WhatsApp (ubicacion, sucursal)   ← intención, no consulta confirmada
//   abrir_agendar   abre la hoja "Agendar cita" (ubicacion)
//   clic_telefono   enlace tel: (ubicacion)
//   como_llegar     botón "Cómo llegar" (sucursal)
//   clic_resena     botón de reseña en Google (sucursal)
//   generate_lead   formulario de empresas enviado con éxito (metodo: empresa)
(function () {
  'use strict';
  if (typeof window.gtag !== 'function') return;

  function send(name, params) {
    window.gtag('event', name, params || {});
  }

  // Dónde está el botón: sección de la página, o el elemento fijo que lo contiene
  function ubicacion(el) {
    if (el.closest('[data-sheet]')) return 'agendar_cita';
    if (el.closest('.fab-wa')) return 'boton_flotante';
    if (el.closest('.mobile-bar')) return 'barra_movil';
    if (el.closest('.site-header')) return 'cabecera';
    if (el.closest('.site-footer')) return 'pie';
    var sec = el.closest('section[id], article[id]');
    if (!sec) return 'pagina';
    return sec.id === 'top' ? 'portada' : sec.id;
  }

  function sucursalElegida() {
    var r = document.querySelector('[data-sheet] input[name="sucursal"]:checked');
    return r ? r.value.toLowerCase() : undefined;
  }

  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    var href = a.getAttribute('href');
    var donde = ubicacion(a);
    var art = a.closest('article[id]');
    var sucursal = art && (art.id === 'masaya' || art.id === 'diriomo') ? art.id : undefined;

    if (a.hasAttribute('data-direcciones')) {
      send('como_llegar', { sucursal: a.getAttribute('data-direcciones') });
    } else if (a.hasAttribute('data-resena')) {
      send('clic_resena', { sucursal: a.getAttribute('data-resena') });
    } else if (/^https:\/\/wa\.me\//.test(href)) {
      // main.js ya canceló el clic si abrió la hoja "Agendar cita" en vez de WhatsApp
      if (e.defaultPrevented) {
        send('abrir_agendar', { ubicacion: donde });
      } else {
        send('clic_whatsapp', { ubicacion: donde, sucursal: donde === 'agendar_cita' ? sucursalElegida() : sucursal });
      }
    } else if (/^tel:/.test(href)) {
      send('clic_telefono', { ubicacion: donde });
    }
  });

  // main.js avisa cuando el formulario de empresas se envió bien
  document.addEventListener('opto:afiliacion-enviada', function () {
    send('generate_lead', { metodo: 'empresa' });
  });
})();
