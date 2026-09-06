"""Serve the app on the local network so a phone on the same wifi can open it.

    python tools/serve.py            # port 8000
    python tools/serve.py 8080

Serves iron-ledger.html at "/", the same shape GitHub Pages gets, so what you
see here is what you get there.

One caveat worth knowing before you judge the result: service workers need a
secure context, and http://192.168.x.x is not one. Over wifi the app runs and
localStorage works, and iOS will still add it to the home screen, but the
offline cache does not activate. Offline is only real on the Pages URL, which
is https. Nothing to fix here — it is a browser rule.
"""
import http.server, socket, socketserver, functools, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000


class H(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = path.split("?", 1)[0].split("#", 1)[0]
        if p in ("/", "/index.html"):
            return os.path.join(ROOT, "iron-ledger.html")
        return super().translate_path(path)

    def end_headers(self):
        # never let a phone cache the page while you are iterating on it
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))          # no packet is sent; picks the route
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class S(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


with S(("0.0.0.0", PORT), functools.partial(H, directory=ROOT)) as httpd:
    print("The Iron Ledger")
    print("  this machine : http://localhost:%d/" % PORT)
    print("  your phone   : http://%s:%d/" % (lan_ip(), PORT))
    print("\nSame wifi, no VPN. Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
