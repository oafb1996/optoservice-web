#!/usr/bin/env python3
"""Simulador del canal web del asistente (contrato en docs/contrato-chat-web.md).

NO es osops: solo imita sus respuestas para desarrollar y probar el widget del
sitio sin depender del backend real. Sirve también para comprobar el contrato
cuando osops lo implemente (mismas rutas, códigos y cabeceras).

Uso:
    python3 scripts/chat-mock.py [--port 8771] [--origin http://localhost:8770 ...]
                                 [--ttl 1800] [--delay 0.8]

Frases que activan escenarios (escribirlas en el chat):
    persona     -> traspaso a WhatsApp (handoff)
    /503        -> 503 bot_unavailable
    /500        -> 500 internal_error
    /429        -> 429 rate_limited con Retry-After: 7
    /expirar    -> la sesión caduca: el siguiente mensaje recibe 401 session_expired
    /contacto   -> respuesta con lead_saved = true
    /xss        -> respuesta con HTML, enlaces peligrosos y formato (prueba del render)
    /lento      -> la respuesta tarda 6 s (prueba del tiempo de espera)
    /largo      -> respuesta larga con varias líneas
    /ultimos    -> deja 2 mensajes restantes en la sesión
    horario     -> respuesta con negrita y un enlace
Con el token de Turnstile "FAIL" /session responde 403 turnstile_failed.
"""
import argparse
import base64
import hashlib
import hmac
import json
import secrets
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ARGS = None
SECRET = secrets.token_bytes(32)
SESSIONS = {}  # session_id -> dict
LOCK = threading.Lock()
MAX_CHARS = 500
MAX_MESSAGES = 30
WA_BOT = '50500000000'  # número ficticio del bot


def iso(ts):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(ts))


def sign(session_id, exp):
    msg = f'{session_id}.{int(exp)}'.encode()
    sig = hmac.new(SECRET, msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(msg).decode().rstrip('=') + '.' + base64.urlsafe_b64encode(sig).decode().rstrip('=')


def verify(token):
    try:
        body, sig = token.split('.')
        pad = lambda s: s + '=' * (-len(s) % 4)
        msg = base64.urlsafe_b64decode(pad(body))
        good = hmac.new(SECRET, msg, hashlib.sha256).digest()
        if not hmac.compare_digest(good, base64.urlsafe_b64decode(pad(sig))):
            return None
        session_id, exp = msg.decode().rsplit('.', 1)
        return session_id, int(exp)
    except Exception:
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = 'chat-mock'
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *a):
        sys.stderr.write('[mock] ' + fmt % a + '\n')

    # --- utilidades -------------------------------------------------------
    def origin_ok(self):
        o = self.headers.get('Origin')
        return o if o in ARGS.origin else None

    def cors(self):
        o = self.origin_ok()
        if o:
            self.send_header('Access-Control-Allow-Origin', o)
            self.send_header('Access-Control-Expose-Headers', 'Retry-After')
        self.send_header('Vary', 'Origin')

    def reply(self, status, payload=None, extra=None):
        body = b'' if payload is None else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.cors()
        if payload is not None:
            self.send_header('Content-Type', 'application/json; charset=utf-8')
        for k, v in (extra or {}).items():
            self.send_header(k, str(v))
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def error(self, status, code, message, wa=False, extra=None):
        payload = {'error': {'code': code, 'message': message}}
        if wa:
            payload['whatsapp_url'] = f'https://wa.me/{WA_BOT}?text=' + urllib.parse.quote('Hola, vengo del chat web de Opto Service')
        self.reply(status, payload, extra)

    def read_json(self):
        try:
            n = int(self.headers.get('Content-Length') or 0)
            data = json.loads(self.rfile.read(n) or b'{}')
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    # --- rutas ------------------------------------------------------------
    def do_OPTIONS(self):
        o = self.origin_ok()
        self.send_response(204)
        if o:
            self.send_header('Access-Control-Allow-Origin', o)
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.send_header('Access-Control-Max-Age', '600')
        self.send_header('Vary', 'Origin')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        if self.path == '/health':
            return self.reply(200, {'ok': True})
        self.error(404, 'not_found', 'No existe.')

    def do_POST(self):
        if self.headers.get('Origin') and not self.origin_ok():
            return self.error(403, 'origin_not_allowed', 'Origen no permitido.')
        path = urllib.parse.urlparse(self.path).path
        if path == '/api/web-chat/session':
            return self.session()
        if path == '/api/web-chat/message':
            return self.message()
        self.error(404, 'not_found', 'No existe.')

    def session(self):
        data = self.read_json()
        if data is None:
            return self.error(400, 'invalid_request', 'Solicitud no válida.')
        if data.get('turnstile_token') in (None, 'FAIL'):
            return self.error(403, 'turnstile_failed', 'No pudimos verificar que eres una persona. Inténtalo de nuevo.')
        sid = 'ws_' + secrets.token_hex(6)
        exp = time.time() + ARGS.ttl
        with LOCK:
            SESSIONS[sid] = {'count': 0, 'busy': False, 'handed_off': False, 'exp': exp, 'created': time.time()}
        self.reply(201, {
            'session_id': sid, 'token': sign(sid, exp), 'expires_at': iso(exp),
            'greeting': '¡Hola! 😊 Soy el asistente virtual de Opto Service. ¿Con cuál sucursal te quieres comunicar: *Masaya* o *Diriomo*?',
            'limits': {'max_message_chars': MAX_CHARS, 'max_messages': MAX_MESSAGES},
        })

    def message(self):
        auth = self.headers.get('Authorization', '')
        parsed = verify(auth[7:]) if auth.startswith('Bearer ') else None
        data = self.read_json()
        if data is None:
            return self.error(400, 'invalid_request', 'Solicitud no válida.')
        sid = data.get('session_id')
        if not parsed or parsed[0] != sid or sid not in SESSIONS:
            return self.error(401, 'invalid_token', 'La sesión no es válida.')
        s = SESSIONS[sid]
        if time.time() > s['exp'] or s.get('force_expired'):
            return self.error(401, 'session_expired', 'La sesión terminó. Empecemos una nueva conversación.')
        text = data.get('message')
        if not isinstance(text, str) or not text.strip():
            return self.error(400, 'invalid_request', 'Escribe un mensaje.')
        if len(text) > MAX_CHARS:
            return self.error(413, 'message_too_long', f'El mensaje es demasiado largo (máximo {MAX_CHARS} caracteres).')
        if s['handed_off']:
            return self.error(409, 'handed_off', 'Esta conversación continúa por WhatsApp.', wa=True)
        low = text.lower()
        if '/429' in low:
            return self.error(429, 'rate_limited', 'Estás enviando mensajes muy rápido.', extra={'Retry-After': 7})
        if s['count'] >= MAX_MESSAGES:
            return self.error(429, 'rate_limited', 'Llegaste al máximo de mensajes de esta conversación.', wa=True, extra={'Retry-After': 3600})
        with LOCK:
            if s['busy']:
                return self.error(409, 'busy', 'Estoy respondiendo tu mensaje anterior.')
            s['busy'] = True
        try:
            time.sleep(6 if '/lento' in low else ARGS.delay)
            if '/503' in low:
                return self.error(503, 'bot_unavailable', 'El asistente no está disponible en este momento.', wa=True)
            if '/500' in low:
                return self.error(500, 'internal_error', 'Algo salió mal de nuestro lado.')
            s['count'] += 1
            if '/ultimos' in low:
                s['count'] = MAX_MESSAGES - 2
            if '/expirar' in low:
                s['force_expired'] = True
            handoff, lead = None, False
            text_out = None
            if 'persona' in low:
                s['handed_off'] = True
                text_out = 'Te paso con una persona del equipo para ayudarte mejor 🙌 Continúa por WhatsApp y te atienden en cuanto puedan.'
                handoff = {'reason': 'pidió_persona', 'whatsapp_url': f'https://wa.me/{WA_BOT}?text=' + urllib.parse.quote(f'Hola, vengo del chat web (ref {sid[-5:].upper()})')}
            elif '/contacto' in low:
                lead = True
                text_out = 'Listo, guardé tus datos 😊 Una persona del equipo te llamará pronto.'
            elif '/xss' in low:
                text_out = '<img src=x onerror=alert(1)> <script>alert(2)</script> *negrita* https://optoservicenic.com/ y http://inseguro.test y javascript:alert(3) [clic](https://x.test) https://optoservicenic.com/#faq.'
            elif '/largo' in low:
                text_out = '\n'.join(f'Línea {i}: esta es una respuesta larga para probar el desplazamiento del chat 📜' for i in range(1, 16))
            elif 'horario' in low:
                text_out = 'En *Masaya* atendemos de lunes a viernes de 8:30 am a 5:00 pm 🕐\nMás información: https://optoservicenic.com/#sucursales\n¿Algo más en lo que te ayude? 😊'
            else:
                text_out = f'Recibí: "{text.strip()[:80]}" 😊 (respuesta de prueba del simulador)'
            remaining = MAX_MESSAGES - s['count']
            s['exp'] = min(time.time() + ARGS.ttl, s['created'] + 7200) if not s.get('force_expired') else s['exp']
            self.reply(200, {'reply': {'text': text_out, 'format': 'whatsapp'}, 'handoff': handoff,
                             'lead_saved': lead, 'remaining_messages': remaining, 'expires_at': iso(s['exp'])})
        finally:
            s['busy'] = False


def main():
    global ARGS
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--port', type=int, default=8771)
    p.add_argument('--origin', action='append', default=None, help='origen permitido (repetible)')
    p.add_argument('--ttl', type=float, default=1800, help='vida de la sesión en segundos')
    p.add_argument('--delay', type=float, default=0.8, help='latencia simulada por respuesta')
    ARGS = p.parse_args()
    ARGS.origin = ARGS.origin or ['http://localhost:8770', 'http://127.0.0.1:8770', 'http://localhost:8000']
    srv = ThreadingHTTPServer(('127.0.0.1', ARGS.port), Handler)
    print(f'Simulador del chat en http://127.0.0.1:{ARGS.port}  (orígenes: {", ".join(ARGS.origin)})')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
