"""Loopback-only personal transit reference UI. Run: python -m experiments.local_app."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading

from experiments.local_planner import LocalPlanner, UserError
from sg_transit.routing import SearchBudgetExceeded

WEB = Path(__file__).with_name('web')
NETWORK_IMAGE = WEB.parents[1] / 'results/blk18_cde_reference/routes.png'
ASSETS = {
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
    '/app.css': ('app.css', 'text/css; charset=utf-8'),
    '/lucide.js': ('vendor/lucide.min.js', 'text/javascript; charset=utf-8'),
    '/favicon.svg': ('favicon.svg', 'image/svg+xml'),
}


def make_server(port=8765, planner=None):
    planner = planner or LocalPlanner()
    token, lock = secrets.token_urlsafe(32), threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code, data, content_type='application/json; charset=utf-8'):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(data)

        def valid_host(self):
            port = self.server.server_port
            return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {'error': '仅限本机访问。'})
            if self.path == '/api/config':
                if not lock.acquire(blocking=False):
                    return self.send(409, {'error': '正在处理上一个查询。'})
                try:
                    self.send(200, {**planner.config(), 'csrf': token})
                except Exception:
                    self.send(500, {'error': '本地案例加载失败，请检查静态数据与来源哈希。'})
                finally:
                    lock.release()
            elif self.path in ASSETS:
                filename, mime = ASSETS[self.path]
                self.send(200, (WEB / filename).read_bytes(), mime)
            elif self.path == '/network.png' and NETWORK_IMAGE.is_file():
                self.send(200, NETWORK_IMAGE.read_bytes(), 'image/png')
            else:
                self.send(404, {'error': 'Not found'})

        def do_POST(self):
            origin = self.headers.get('Origin')
            expected = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            if not self.valid_host() or origin not in expected or not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), token):
                return self.send(403, {'error': '请求来源校验失败，请刷新本地页面。'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, {'error': 'Expected JSON'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                return self.send(400, {'error': 'Invalid length'})
            if not 0 < size <= 4096:
                return self.send(413, {'error': 'Request too large'})
            try:
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError()
            except (ValueError, UnicodeDecodeError):
                return self.send(400, {'error': 'Invalid JSON'})
            actions = {'/api/plan': planner.plan, '/api/detail': planner.detail, '/api/onward': planner.onward}
            if self.path not in actions:
                return self.send(404, {'error': 'Not found'})
            if not lock.acquire(blocking=False):
                return self.send(409, {'error': '正在处理上一个查询，请稍后再试。'})
            try:
                self.send(200, actions[self.path](body))
            except UserError as exc:
                self.send(exc.status, {'error': str(exc)})
            except SearchBudgetExceeded:
                self.send(422, {'error': '搜索达到预算上限，本次未给出完整结果；这不表示没有路线。'})
            except Exception:
                # Provider exceptions can include authentication details; never echo them.
                self.send(500, {'error': '本次计算失败，未返回路线。请重新查询或使用离线模式。'})
            finally:
                lock.release()

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.port)
    print(f'Local transit reference: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
