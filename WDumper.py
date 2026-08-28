import os
import re
import io
import time
import signal
import shutil
import pathlib
import argparse
import threading
import http.server
import socketserver
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Comment, NavigableString
import pyfiglet
import colorama
from colorama import Fore, Style

colorama.init()

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

try:
    import rcssmin
    HAVE_RCSSMIN = True
except ImportError:
    HAVE_RCSSMIN = False

try:
    import rjsmin
    HAVE_RJSMIN = True
except ImportError:
    HAVE_RJSMIN = False

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

ASSET_TAGS = ("link", "script", "img")
SKIP_MINIFY_TAGS = ("pre", "script", "style", "textarea")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")

_print_lock = threading.Lock()
_warned = set()


def banner():
    if os.name == "nt":
        os.system("title WEB DUMP - 2.0 & mode con cols=150 lines=26")
    print(Fore.RED + pyfiglet.figlet_format("WEB DUMP", font="slant") + Style.RESET_ALL)
    print("                                                     By: Kamerzystanasyt\n")
    try:
        input("Press Enter to continue...")
    except EOFError:
        pass


def signal_handler(sig, frame):
    print("\nInterrupted by user. Exiting...")
    os._exit(0)


signal.signal(signal.SIGINT, signal_handler)


def log(msg, quiet=False):
    if quiet:
        return
    with _print_lock:
        print(msg)


def warn_once(key, msg):
    if key not in _warned:
        _warned.add(key)
        print(Fore.YELLOW + f"Warning: {msg}" + Style.RESET_ALL)


def page_local_path(url):
    """Map a page URL to a local file path, mirroring its URL path."""
    parsed = urlparse(url)
    path = parsed.path
    if not path or path.endswith("/"):
        return (path.strip("/"), "index.html")
    dir_part, name = os.path.split(path.strip("/"))
    if "." not in name:
        name += ".html"
    return (dir_part, name)


def normalize_url(url):
    parsed = urlparse(url)
    return parsed._replace(path=parsed.path or "/", fragment="").geturl()


def is_same_site(url, netloc):
    parsed = urlparse(url)
    if parsed.scheme not in ("", "http", "https"):
        return False
    return parsed.netloc == "" or parsed.netloc == netloc


def minify_html_soup(soup):
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    for text_node in soup.find_all(string=True):
        if type(text_node) is not NavigableString:
            continue
        if text_node.find_parent(SKIP_MINIFY_TAGS):
            continue
        if not text_node.strip():
            text_node.extract()
        else:
            text_node.replace_with(re.sub(r"\s+", " ", text_node).strip())


def minify_bytes(filename, content):
    if filename.endswith(".css") and HAVE_RCSSMIN:
        return rcssmin.cssmin(content.decode("utf-8", "ignore")).encode("utf-8")
    if filename.endswith(".js") and HAVE_RJSMIN:
        return rjsmin.jsmin(content.decode("utf-8", "ignore")).encode("utf-8")
    if filename.endswith(".css") and not HAVE_RCSSMIN:
        warn_once("rcssmin", "rcssmin not installed, skipping CSS minification (pip install -r requirements.txt)")
    if filename.endswith(".js") and not HAVE_RJSMIN:
        warn_once("rjsmin", "rjsmin not installed, skipping JS minification (pip install -r requirements.txt)")
    return content


def optimize_image(filename, content):
    if not filename.lower().endswith(IMAGE_EXTS):
        return content
    if not HAVE_PIL:
        warn_once("pillow", "Pillow not installed, skipping image optimization (pip install -r requirements.txt)")
        return content
    try:
        img = Image.open(io.BytesIO(content))
        fmt = img.format
        out = io.BytesIO()
        save_kwargs = {"optimize": True}
        if fmt == "JPEG":
            save_kwargs["quality"] = 85
        img.save(out, format=fmt, **save_kwargs)
        optimized = out.getvalue()
        return optimized if len(optimized) < len(content) else content
    except Exception:
        return content


class Dumper:
    def __init__(self, args):
        self.args = args
        self.netloc = urlparse(args.url).netloc
        self.output_dir = pathlib.Path(args.output or self.netloc).resolve()
        self.session = requests.Session()
        self.visited = set()
        self.stats = {"pages": 0, "assets": 0, "failed": 0}

    def prepare_output_dir(self):
        if self.output_dir.exists():
            log(f"Output folder '{self.output_dir}' already exists. Deleting...", self.args.quiet)
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, url):
        return self.session.get(url, timeout=self.args.timeout)

    def download_asset(self, link, filepath):
        if self.args.delay:
            time.sleep(self.args.delay)
        try:
            resp = self.session.get(link, timeout=self.args.timeout)
            resp.raise_for_status()
            content = resp.content
            if self.args.minify:
                content = minify_bytes(filepath.name, content)
                content = optimize_image(filepath.name, content)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(content)
            with _print_lock:
                self.stats["assets"] += 1
            log(f"  asset ok: {filepath.name}", self.args.quiet)
        except requests.exceptions.RequestException as e:
            with _print_lock:
                self.stats["failed"] += 1
            log(f"  asset FAILED: {link} ({e})", self.args.quiet)

    def collect_assets(self, soup, page_url):
        jobs = []
        for tag in soup.find_all(ASSET_TAGS):
            src = tag.get("href") or tag.get("src")
            if not src:
                continue
            abs_link = urljoin(page_url, src)
            if urlparse(abs_link).netloc != self.netloc:
                continue
            rel_path = urlparse(abs_link).path.lstrip("/") or "index.html"
            local_path = self.output_dir / rel_path
            jobs.append((tag, abs_link, local_path))

            if self.args.castify:
                local_href = "/" + rel_path
                if tag.get("href"):
                    tag["href"] = local_href
                if tag.get("src"):
                    tag["src"] = local_href
        return jobs

    def process_page(self, url, depth):
        url = normalize_url(url)
        if url in self.visited or len(self.visited) >= self.args.max_pages:
            return []
        self.visited.add(url)

        try:
            resp = self.fetch(url)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            log(f"Error accessing {url}: {e}", self.args.quiet)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        self.stats["pages"] += 1
        log(f"Page {self.stats['pages']}: {url}", self.args.quiet)

        jobs = self.collect_assets(soup, url)

        if self.args.nosocal:
            for a in soup.find_all("a"):
                href = a.get("href")
                if href and not is_same_site(urljoin(url, href), self.netloc):
                    a.decompose()

        next_links = []
        if self.args.recursive and depth < self.args.depth:
            seen = set()
            for a in soup.find_all("a", href=True):
                target = normalize_url(urljoin(url, a["href"]).split("#")[0])
                if is_same_site(target, self.netloc) and target not in self.visited and target not in seen:
                    seen.add(target)
                    next_links.append(target)

        if self.args.minify:
            minify_html_soup(soup)

        html_out = soup.prettify() if self.args.beautify else str(soup)
        dir_part, filename = page_local_path(url)
        page_dir = self.output_dir / dir_part if dir_part else self.output_dir
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / filename).write_text(html_out, encoding="utf-8")

        if jobs:
            with ThreadPoolExecutor(max_workers=self.args.threads) as pool:
                futures = [pool.submit(self.download_asset, link, path) for _, link, path in jobs]
                for f in as_completed(futures):
                    f.result()

        if self.args.antifont:
            for root, _, files in os.walk(self.output_dir):
                for f in files:
                    if f.endswith((".woff", ".woff2", ".ttf", ".otf")):
                        os.remove(os.path.join(root, f))

        return next_links

    def run(self):
        self.prepare_output_dir()
        queue = [(self.args.url, 0)]
        while queue:
            url, depth = queue.pop(0)
            next_links = self.process_page(url, depth)
            for link in next_links:
                if len(self.visited) + len(queue) < self.args.max_pages:
                    queue.append((link, depth + 1))

        log(
            f"\nDone. {self.stats['pages']} page(s), {self.stats['assets']} asset(s), "
            f"{self.stats['failed']} failed -> {self.output_dir}",
            self.args.quiet,
        )


def serve(folder, port):
    os.chdir(folder)
    with socketserver.TCPServer(("", port), http.server.SimpleHTTPRequestHandler) as httpd:
        print(f"Serving at port {port}")
        print(f"Open http://localhost:{port} in your browser to view the website.")
        httpd.serve_forever()


def build_parser():
    parser = argparse.ArgumentParser(description="Download a website for offline browsing")
    parser.add_argument("url", help="The URL of the website to scrape")
    parser.add_argument("-o", "--output", help="Output directory (default: domain name)")
    parser.add_argument("--serve", "--autohost", dest="serve", action="store_true",
                         help="Start a local server after downloading")
    parser.add_argument("--port", type=int, default=8000, help="Port for --serve (default: 8000)")
    parser.add_argument("--beautify", "--bf", dest="beautify", action="store_true",
                         help="Pretty-print saved HTML")
    parser.add_argument("--minify", action="store_true",
                         help="Minify saved HTML/CSS/JS and re-compress images (requires rcssmin/rjsmin/Pillow)")
    parser.add_argument("--castify", action="store_true", help="Rewrite asset links to local paths")
    parser.add_argument("--antifont", action="store_true", help="Remove downloaded font files")
    parser.add_argument("--nosocal", action="store_true", help="Remove links to other domains")
    parser.add_argument("--recursive", action="store_true", help="Follow same-domain page links")
    parser.add_argument("--depth", type=int, default=1, help="Max recursion depth with --recursive (default: 1)")
    parser.add_argument("--max-pages", type=int, default=50, dest="max_pages",
                         help="Safety cap on total pages crawled (default: 50)")
    parser.add_argument("--threads", type=int, default=20, help="Concurrent asset downloads (default: 20)")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay in seconds before each request")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()

    if not args.quiet:
        banner()

    dumper = Dumper(args)
    dumper.run()

    if args.serve:
        serve(dumper.output_dir, args.port)
