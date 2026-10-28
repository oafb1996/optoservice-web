// Opto Service — asistente de chat (sin dependencias).
// Se carga solo cuando alguien abre el chat. Habla con el canal web de osops;
// el contrato está en docs/contrato-chat-web.md.
(function () {
  'use strict';
  if (window.OptoChat) return;

  var cfgEl = document.getElementById('chat-config');
  if (!cfgEl) return;
  var cfg;
  try { cfg = JSON.parse(cfgEl.textContent); } catch (e) { return; }
  var API = String(cfg.apiUrl || '').replace(/\/+$/, '');
  if (!API) return;

  var TIMEOUT = cfg.timeoutMs > 0 ? cfg.timeoutMs : 45000;
  var WA_OK = /^https:\/\/(wa\.me|api\.whatsapp\.com)\//;
  var WA_FALLBACK = WA_OK.test(cfg.whatsappUrl || '') ? cfg.whatsappUrl : '';
  var STORE = 'opto-chat-v1';
  var DEFAULT_MAX = 500;
  var MOBILE = window.matchMedia('(max-width: 879.98px)');
  var COARSE = window.matchMedia('(pointer: coarse)');

  // ---------- utilidades ----------
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function svg(markup) {
    var s = document.createElement('span');
    s.style.display = 'flex';
    s.innerHTML = markup; // solo íconos fijos de este archivo, nunca texto del servidor
    return s;
  }
  var ICON_CHAT = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.2A8 8 0 1 1 21 12z"/></svg>';
  var ICON_CLOSE = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  var ICON_SEND = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>';
  var ICON_WA = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M12 2a10 10 0 0 0-8.5 15.2L2 22l4.9-1.3A10 10 0 1 0 12 2zm0 18a8 8 0 0 1-4.1-1.1l-.3-.2-2.9.8.8-2.8-.2-.3A8 8 0 1 1 12 20zm4.5-5.9c-.2-.1-1.4-.7-1.7-.8-.2-.1-.4-.1-.5.1l-.7.9c-.1.2-.3.2-.5.1a6.5 6.5 0 0 1-3.2-2.8c-.1-.2 0-.4.1-.5l.4-.5c.1-.2.1-.3.2-.5 0-.1 0-.3-.1-.4-.1-.1-.5-1.3-.8-1.8-.2-.4-.4-.4-.5-.4h-.5c-.2 0-.4.1-.6.3-.2.2-.8.8-.8 2s.8 2.3.9 2.4c.1.2 1.7 2.7 4.2 3.7 1.5.6 2 .7 2.7.6.4-.1 1.4-.6 1.6-1.1.2-.5.2-1 .1-1.1-.1-.1-.2-.1-.5-.3z"/></svg>';

  // Texto del bot -> nodos DOM. *negrita*, saltos de línea y enlaces https. Nada de HTML.
  var URL_RE = /(https?:\/\/[^\s<>"]+)/g;
  function addLink(parent, raw) {
    var m = raw.match(/^(.*?)([.,;:!?)\]]*)$/);
    var url = m[1], tail = m[2];
    if (/^https:\/\/[^\s]+$/i.test(url)) {
      var a = el('a', '', url);
      a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer';
      parent.appendChild(a);
    } else {
      parent.appendChild(document.createTextNode(url)); // http:// u otros: texto plano
    }
    if (tail) parent.appendChild(document.createTextNode(tail));
  }
  function addBold(parent, s) {
    s.split(/\*([^*\n]+)\*/).forEach(function (part, i) {
      if (i % 2) parent.appendChild(el('strong', '', part));
      else if (part) parent.appendChild(document.createTextNode(part));
    });
  }
  function rich(parent, text) {
    String(text).split('\n').forEach(function (line, i) {
      if (i) parent.appendChild(document.createElement('br'));
      line.split(URL_RE).forEach(function (part, idx) {
        if (idx % 2) addLink(parent, part);
        else addBold(parent, part);
      });
    });
  }

  // ---------- estado ----------
  function fresh() { return { sid: '', token: '', exp: 0, msgs: [], remaining: null, max: DEFAULT_MAX, handed: false }; }
  function loadState() {
    try {
      var s = JSON.parse(sessionStorage.getItem(STORE) || 'null');
      if (s && typeof s === 'object' && Array.isArray(s.msgs)) return Object.assign(fresh(), s);
    } catch (e) { /* sin almacenamiento: el chat funciona igual, solo no sobrevive a recargas */ }
    return fresh();
  }
  var state = loadState();
  function save() {
    try {
      var copy = Object.assign({}, state, { msgs: state.msgs.slice(-60) });
      sessionStorage.setItem(STORE, JSON.stringify(copy));
    } catch (e) { /* ignorar */ }
  }

  var root, log, input, sendBtn, meta, notice;
  var built = false, isOpen = false, pending = false, starting = null, lastTrigger = null, cssReady = null;

  // ---------- red ----------
  function post(path, body, token) {
    var ctrl = typeof AbortController === 'function' ? new AbortController() : null;
    var timedOut = false;
    var timer = setTimeout(function () { timedOut = true; if (ctrl) ctrl.abort(); }, TIMEOUT);
    var headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
    if (token) headers.Authorization = 'Bearer ' + token;
    return fetch(API + path, {
      method: 'POST', headers: headers, body: JSON.stringify(body), signal: ctrl ? ctrl.signal : undefined,
      credentials: 'omit', mode: 'cors', cache: 'no-store'
    }).then(function (res) {
      clearTimeout(timer);
      var ra = parseInt(res.headers.get('Retry-After'), 10);
      return res.json().catch(function () { return null; }).then(function (data) {
        return { status: res.status, data: data, retryAfter: isFinite(ra) ? ra : null };
      });
    }, function () {
      clearTimeout(timer);
      throw { network: true, timeout: timedOut };
    });
  }
  function errCode(res) { return res.data && res.data.error && res.data.error.code; }
  function errText(res, fallback) { return (res.data && res.data.error && res.data.error.message) || fallback; }
  function waUrl(res) {
    var u = res && res.data && res.data.whatsapp_url;
    return WA_OK.test(u || '') ? u : WA_FALLBACK;
  }

  // ---------- Turnstile (verificación anti-bots de Cloudflare) ----------
  var tsScript = null;
  function loadTurnstile() {
    if (window.turnstile) return Promise.resolve();
    if (!tsScript) {
      tsScript = new Promise(function (ok, fail) {
        var s = document.createElement('script');
        s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
        s.async = true; s.onload = ok;
        s.onerror = function () { tsScript = null; fail(new Error('turnstile')); };
        document.head.appendChild(s);
      });
    }
    return tsScript;
  }
  function getTurnstileToken() {
    if (!cfg.turnstileSiteKey) return Promise.resolve('sin-turnstile'); // solo desarrollo
    return loadTurnstile().then(function () {
      return new Promise(function (ok, fail) {
        var box = el('div', 'oc-ts');
        log.appendChild(box);
        var id, done = false;
        var t = setTimeout(function () { end(fail, new Error('timeout')); }, 25000);
        function end(fn, v) {
          if (done) return;
          done = true; clearTimeout(t);
          try { window.turnstile.remove(id); } catch (e) { /* ignorar */ }
          box.remove();
          fn(v);
        }
        id = window.turnstile.render(box, {
          sitekey: cfg.turnstileSiteKey, appearance: 'interaction-only',
          callback: function (tok) { end(ok, tok); },
          'error-callback': function () { end(fail, new Error('turnstile')); },
          'timeout-callback': function () { end(fail, new Error('turnstile')); }
        });
      });
    });
  }

  // ---------- pintar ----------
  function scrollDown() { if (log) log.scrollTop = log.scrollHeight; }

  function paint(m) {
    var node;
    if (m.r === 'note') {
      node = el('div', 'oc-note' + (m.k === 'error' ? ' is-error' : m.k === 'ok' ? ' is-ok' : ''));
      rich(node, m.t);
    } else {
      node = el('div', 'oc-msg ' + (m.r === 'me' ? 'oc-me' : 'oc-bot'));
      rich(node, m.t);
    }
    if (m.wa && WA_OK.test(m.wa)) {
      var a = el('a', 'oc-wa');
      a.href = m.wa; a.target = '_blank'; a.rel = 'noopener noreferrer';
      a.appendChild(svg(ICON_WA));
      a.appendChild(document.createTextNode('Continuar por WhatsApp'));
      node.appendChild(a);
    }
    if (m.retry) {
      var wrap = el('div', 'oc-actions');
      var b = el('button', 'oc-retry', 'Reintentar');
      b.type = 'button';
      b.addEventListener('click', function () { b.disabled = true; startSession('new'); });
      wrap.appendChild(b);
      node.appendChild(wrap);
    }
    log.appendChild(node);
    return node;
  }
  function renderAll() {
    log.textContent = '';
    state.msgs.forEach(paint);
    scrollDown();
  }
  function add(role, text, extra) {
    var m = Object.assign({ r: role, t: text }, extra || {});
    state.msgs.push(m);
    save();
    if (log) { paint(m); scrollDown(); }
    return m;
  }
  function dropLast(role) {
    for (var i = state.msgs.length - 1; i >= 0; i--) {
      if (state.msgs[i].r === role) { state.msgs.splice(i, 1); break; }
    }
    save();
    if (log) renderAll();
  }

  var typing = null, status = null;
  function setBusy(on, label) {
    if (on && !typing) {
      typing = el('div', 'oc-typing');
      typing.setAttribute('role', 'status');
      typing.setAttribute('aria-label', label || 'El asistente está escribiendo');
      typing.appendChild(el('i')); typing.appendChild(el('i')); typing.appendChild(el('i'));
      log.appendChild(typing); scrollDown();
    } else if (!on && typing) { typing.remove(); typing = null; }
    if (!on && status) { status.remove(); status = null; }
    refresh();
  }
  function showStatus(text) {
    if (status) status.remove();
    status = el('div', 'oc-note', text);
    status.setAttribute('role', 'status');
    log.appendChild(status); scrollDown();
  }

  function locked() { return state.handed || state.remaining === 0; }
  function refresh() {
    if (!input) return;
    var off = locked();
    input.disabled = off;
    input.placeholder = state.handed ? 'Continúa la conversación en WhatsApp' : state.remaining === 0 ? 'Llegaste al máximo de mensajes' : 'Escribe tu mensaje…';
    input.maxLength = state.max || DEFAULT_MAX;
    sendBtn.disabled = off || pending || !!starting || !input.value.trim();
    var len = input.value.length, max = state.max || DEFAULT_MAX, txt = '';
    if (len >= max * 0.8) txt = len + '/' + max;
    else if (state.remaining != null && state.remaining > 0 && state.remaining <= 5) txt = 'Te quedan ' + state.remaining + ' mensajes';
    meta.firstChild.textContent = txt;
  }

  // ---------- sesión ----------
  function sessionValid() { return !!state.sid && Date.now() < state.exp; }

  function startSession(reason) {
    if (starting) return starting;
    var hadMessages = state.msgs.length > 0;
    if (reason === 'new') { state = fresh(); }
    else if (reason === 'renew') { state.sid = ''; state.token = ''; state.handed = false; state.remaining = null; }
    if (reason === 'new' && log) log.textContent = '';
    if (reason === 'renew' && hadMessages) add('note', 'La conversación anterior terminó. Empezamos una nueva.');
    save();
    refresh();
    showStatus('Conectando…');
    setBusy(true, 'Conectando');
    var attempt = function (n) {
      return getTurnstileToken().then(function (tok) {
        return post('/session', { turnstile_token: tok });
      }).then(function (res) {
        if (res.status === 403 && errCode(res) === 'turnstile_failed' && n < 2) return attempt(n + 1);
        return res;
      });
    };
    starting = attempt(1).then(function (res) {
      var d = res.data;
      if ((res.status === 200 || res.status === 201) && d && d.session_id && d.token) {
        state.sid = d.session_id; state.token = d.token;
        state.exp = Date.parse(d.expires_at) || (Date.now() + 25 * 60000);
        state.max = (d.limits && d.limits.max_message_chars) || DEFAULT_MAX;
        state.remaining = d.limits && d.limits.max_messages ? d.limits.max_messages : null;
        state.handed = false;
        if (d.greeting) state.msgs.push({ r: 'bot', t: d.greeting });
        save();
        return true;
      }
      var wa = waUrl(res);
      add('note', errText(res, 'No pudimos iniciar el chat en este momento.'), { k: 'error', retry: true, wa: wa });
      return false;
    }, function () {
      add('note', 'No pudimos conectar con el asistente. Revisa tu conexión e inténtalo de nuevo.', { k: 'error', retry: true, wa: WA_FALLBACK });
      return false;
    }).then(function (ok) {
      starting = null;
      setBusy(false);
      renderAll();
      refresh();
      if (ok && input && !MOBILE.matches) input.focus();
      return ok;
    });
    return starting;
  }

  // ---------- enviar ----------
  function send(text, resent) {
    text = String(text || '').trim();
    if (!text || pending || starting || locked()) return;
    if (text.length > (state.max || DEFAULT_MAX)) return;
    if (!sessionValid()) {
      startSession(state.sid ? 'renew' : 'new').then(function (ok) { if (ok) send(text, true); });
      return;
    }
    pending = true;
    input.value = ''; autoGrow();
    add('me', text);
    setBusy(true);
    post('/message', { session_id: state.sid, message: text }, state.token).then(function (res) {
      pending = false;
      setBusy(false);
      var d = res.data;
      if (res.status === 200 && d && d.reply && typeof d.reply.text === 'string') {
        var wa = d.handoff && WA_OK.test(d.handoff.whatsapp_url || '') ? d.handoff.whatsapp_url : null;
        if (d.expires_at) state.exp = Date.parse(d.expires_at) || state.exp;
        if (typeof d.remaining_messages === 'number') state.remaining = d.remaining_messages;
        if (d.handoff) state.handed = true;
        add('bot', d.reply.text, wa ? { wa: wa } : null);
        if (d.handoff && !wa && WA_FALLBACK) add('note', 'Si lo prefieres, continúa por WhatsApp.', { wa: WA_FALLBACK });
        if (d.lead_saved) add('note', 'Guardamos tus datos de contacto. El equipo te contactará.', { k: 'ok' });
        if (state.remaining === 0 && !state.handed) add('note', 'Llegaste al máximo de mensajes de esta conversación.', { wa: WA_FALLBACK });
        save(); refresh();
        return;
      }
      // Errores: se quita el mensaje del chat y se devuelve al cuadro para poder corregirlo o reenviarlo
      var code = errCode(res);
      if (res.status === 401) {
        dropLast('me');
        if (!resent) {
          startSession('renew').then(function (ok) { if (ok) send(text, true); else input.value = text; });
          return;
        }
        input.value = text;
        add('note', errText(res, 'La sesión terminó. Inténtalo de nuevo.'), { k: 'error' });
      } else if (res.status === 409 && code === 'handed_off') {
        state.handed = true;
        add('note', errText(res, 'Esta conversación continúa por WhatsApp.'), { k: 'error', wa: waUrl(res) });
      } else if (res.status === 409) {
        dropLast('me'); input.value = text;
        add('note', 'Un momento: sigo respondiendo tu mensaje anterior.', { k: 'error' });
      } else if (res.status === 429) {
        dropLast('me'); input.value = text;
        var wait = res.retryAfter;
        var when = wait ? (wait >= 120 ? ' Inténtalo en ' + Math.ceil(wait / 60) + ' minutos.' : ' Inténtalo de nuevo en ' + wait + ' segundos.') : '';
        add('note', errText(res, 'Estás enviando mensajes muy rápido.') + when, { k: 'error', wa: wait && wait >= 600 ? waUrl(res) : null });
      } else if (res.status === 400 || res.status === 413) {
        dropLast('me'); input.value = text;
        add('note', errText(res, 'No pudimos enviar ese mensaje.'), { k: 'error' });
      } else {
        dropLast('me'); input.value = text;
        add('note', errText(res, 'El asistente no está disponible en este momento.'), { k: 'error', wa: waUrl(res) });
      }
      refresh(); autoGrow();
    }, function (e) {
      pending = false;
      setBusy(false);
      dropLast('me'); input.value = text;
      add('note', e && e.timeout ? 'El asistente tardó demasiado en responder. Inténtalo de nuevo.' : 'No pudimos conectar. Revisa tu conexión e inténtalo de nuevo.', { k: 'error', wa: WA_FALLBACK });
      refresh(); autoGrow();
    });
  }

  // ---------- construir el panel ----------
  function autoGrow() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  }

  function build() {
    root = el('div', 'oc-root');
    root.setAttribute('role', 'dialog');
    root.setAttribute('aria-labelledby', 'oc-title');
    root.hidden = true;

    var head = el('div', 'oc-head');
    var av = el('div', 'oc-avatar'); av.appendChild(svg(ICON_CHAT));
    var titles = el('div', 'oc-titles');
    var title = el('div', 'oc-title', 'Asistente de Opto Service');
    title.id = 'oc-title'; title.tabIndex = -1;
    titles.appendChild(title);
    titles.appendChild(el('div', 'oc-sub', 'Asistente virtual con IA'));
    var close = el('button', 'oc-close'); close.type = 'button';
    close.setAttribute('aria-label', 'Cerrar el chat'); close.appendChild(svg(ICON_CLOSE));
    close.addEventListener('click', closePanel);
    head.appendChild(av); head.appendChild(titles); head.appendChild(close);

    notice = el('div', 'oc-notice');
    var nt = el('div');
    nt.appendChild(document.createTextNode('Asistente virtual con IA. No compartas datos médicos ni de pago. Guardamos la conversación para atenderte. '));
    if (cfg.privacyUrl) {
      var pa = el('a', '', 'Política de privacidad');
      pa.href = cfg.privacyUrl; pa.target = '_blank'; pa.rel = 'noopener';
      nt.appendChild(pa);
    }
    var again = el('button', 'oc-link', 'Nueva conversación'); again.type = 'button';
    again.addEventListener('click', function () { if (!pending) startSession('new'); });
    notice.appendChild(nt); notice.appendChild(again);

    log = el('div', 'oc-log');
    log.setAttribute('role', 'log');
    log.setAttribute('aria-live', 'polite');
    log.setAttribute('aria-label', 'Conversación con el asistente');

    var foot = el('div', 'oc-foot');
    var form = el('form', 'oc-form'); form.noValidate = true;
    input = el('textarea', 'oc-input'); input.rows = 1;
    input.setAttribute('aria-label', 'Escribe tu mensaje'); input.maxLength = state.max || DEFAULT_MAX;
    input.autocomplete = 'off';
    sendBtn = el('button', 'oc-send'); sendBtn.type = 'submit';
    sendBtn.setAttribute('aria-label', 'Enviar mensaje'); sendBtn.appendChild(svg(ICON_SEND));
    form.appendChild(input); form.appendChild(sendBtn);
    meta = el('div', 'oc-meta');
    meta.appendChild(el('span'));
    meta.firstChild.setAttribute('role', 'status');
    if (WA_FALLBACK) {
      var wl = el('a', '', '¿Prefieres WhatsApp?');
      wl.href = WA_FALLBACK; wl.target = '_blank'; wl.rel = 'noopener noreferrer';
      meta.appendChild(wl);
    }
    foot.appendChild(form); foot.appendChild(meta);

    root.appendChild(head); root.appendChild(notice); root.appendChild(log); root.appendChild(foot);
    document.body.appendChild(root);

    form.addEventListener('submit', function (e) { e.preventDefault(); send(input.value); });
    input.addEventListener('input', function () { autoGrow(); refresh(); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && !COARSE.matches) { e.preventDefault(); send(input.value); }
    });
    root.addEventListener('keydown', onKeydown);
    MOBILE.addEventListener('change', syncModal);
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', fitViewport);
      window.visualViewport.addEventListener('scroll', fitViewport);
    }
    built = true;
  }

  function visible(n) { return n.getClientRects().length > 0; }
  function focusables() {
    return Array.prototype.filter.call(root.querySelectorAll('a[href],button,textarea,input'), function (n) {
      return !n.disabled && !n.hidden && visible(n);
    });
  }
  function onKeydown(e) {
    if (e.key === 'Escape') { e.preventDefault(); closePanel(); return; }
    if (e.key !== 'Tab' || !MOBILE.matches) return;
    var f = focusables();
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === root)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  function syncModal() {
    if (!root) return;
    root.setAttribute('aria-modal', MOBILE.matches ? 'true' : 'false');
    document.documentElement.classList.toggle('oc-lock', isOpen && MOBILE.matches);
    fitViewport();
  }
  function fitViewport() {
    if (!root) return;
    var vv = window.visualViewport;
    if (isOpen && MOBILE.matches && vv) {
      root.style.setProperty('--oc-h', vv.height + 'px');
      root.style.setProperty('--oc-top', vv.offsetTop + 'px');
    } else {
      root.style.removeProperty('--oc-h');
      root.style.removeProperty('--oc-top');
    }
  }
  function loadCss() {
    if (cssReady) return cssReady;
    cssReady = new Promise(function (ok) {
      var l = document.createElement('link');
      l.rel = 'stylesheet'; l.href = 'assets/css/chat.css';
      l.onload = l.onerror = function () { ok(); };
      document.head.appendChild(l);
      setTimeout(ok, 3000);
    });
    return cssReady;
  }

  // ---------- abrir y cerrar ----------
  function open(trigger) {
    if (isOpen) return;
    lastTrigger = trigger || lastTrigger;
    loadCss().then(function () {
      if (isOpen) return;
      if (!built) build();
      isOpen = true;
      root.hidden = false;
      document.documentElement.classList.add('oc-open');
      void root.offsetWidth; // permite la animación de entrada
      root.classList.add('is-open');
      syncModal();
      renderAll();
      refresh();
      if (!sessionValid()) startSession(state.sid ? 'renew' : 'new');
      if (MOBILE.matches) document.getElementById('oc-title').focus();
      else input.focus();
    });
  }
  function closePanel() {
    if (!isOpen) return;
    isOpen = false;
    save();
    root.classList.remove('is-open');
    document.documentElement.classList.remove('oc-open', 'oc-lock');
    fitViewport();
    var done = function () { if (!isOpen) root.hidden = true; };
    setTimeout(done, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 230);
    var target = lastTrigger && visible(lastTrigger) ? lastTrigger
      : Array.prototype.filter.call(document.querySelectorAll('[data-chat-open]'), visible)[0];
    if (target) target.focus();
  }

  window.OptoChat = { open: open, close: closePanel };
})();
