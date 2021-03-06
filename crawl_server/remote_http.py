from urllib.parse import unquote, urljoin
import warnings
import os
from html.parser import HTMLParser
from itertools import repeat
from crawl_server.crawler import RemoteDirectory, File
import requests
from requests.exceptions import RequestException
from multiprocessing.pool import ThreadPool
import config
from dateutil.parser import parse as parse_date


class Anchor:
    def __init__(self):
        self.text = None
        self.href = None


class HTMLAnchorParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.anchors = []
        self.current_anchor = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for attr in attrs:
                if attr[0] == "href":
                    self.current_anchor = Anchor()
                    self.current_anchor.href = attr[1]
                    break

    def handle_data(self, data):
        if self.current_anchor:
            self.current_anchor.text = data

    def handle_endtag(self, tag):
        if tag == "a":
            if self.current_anchor:
                self.anchors.append(self.current_anchor)
                self.current_anchor = None

    def error(self, message):
        pass

    def feed(self, data):
        self.anchors.clear()
        super().feed(data)


class HttpDirectory(RemoteDirectory):

    SCHEMES = ("http", "https",)
    HEADERS = config.HEADERS
    BLACK_LIST = (
        "?C=N&O=D",
        "?C=M&O=A",
        "?C=S&O=A",
        "?C=D&O=A",
        "?C=N;O=D",
        "?C=M;O=A",
        "?C=S;O=A",
        "?C=D;O=A"
    )
    MAX_RETRIES = 3

    def __init__(self, url):
        super().__init__(url)
        self.session = requests.Session()
        self.session.headers = HttpDirectory.HEADERS
        self.session.verify = False
        self.session.max_redirects = 1

    def list_dir(self, path):

        path_url = self.base_url + path.strip("/") + "/"
        body = self._stream_body(path_url)
        if not body:
            return None
        anchors = self._parse_links(body)

        urls_to_request = []

        for anchor in anchors:
            if self._should_ignore(self.base_url, anchor):
                continue

            if self._isdir(anchor):
                yield File(
                    name=anchor.href,
                    mtime=None,
                    size=None,
                    path=path,
                    is_dir=True
                )
            else:
                pass
                urls_to_request.append(path_url + anchor.href)

        for file in self.request_files(urls_to_request):
            yield file

    def request_files(self, urls_to_request: list) -> list:

        if len(urls_to_request) > 3000000:
            # Many urls, use multi-threaded solution
            pool = ThreadPool(processes=10)
            files = pool.starmap(HttpDirectory._request_file, zip(repeat(self), urls_to_request))
            pool.close()
            return (f for f in files if f)
        else:
            # Too few urls to create thread pool
            for url in urls_to_request:
                file = self._request_file(url)
                if file:
                    yield file

    def _request_file(self, url):

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            retries = HttpDirectory.MAX_RETRIES
            while retries > 0:
                try:
                    r = self.session.head(url, allow_redirects=False, timeout=40)

                    stripped_url = url[len(self.base_url) - 1:]

                    path, name = os.path.split(stripped_url)
                    date = r.headers["Last-Modified"] if "Last-Modified" in r.headers else "1970-01-01"
                    return File(
                        path=unquote(path).strip("/"),
                        name=unquote(name),
                        size=int(r.headers["Content-Length"]) if "Content-Length" in r.headers else -1,
                        mtime=int(parse_date(date).timestamp()),
                        is_dir=False
                    )
                except RequestException:
                    self.session.close()
                    retries -= 1

            return None

    def _stream_body(self, url: str):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            retries = HttpDirectory.MAX_RETRIES
            while retries > 0:
                try:
                    r = self.session.get(url, stream=True, timeout=40)
                    for chunk in r.iter_content(chunk_size=4096):
                        yield chunk.decode(r.encoding if r.encoding else "utf-8", errors="ignore")
                    r.close()
                    del r
                    break
                except RequestException:
                    self.session.close()
                    retries -= 1

            return None

    @staticmethod
    def _parse_links(body):

        parser = HTMLAnchorParser()

        for chunk in body:
            parser.feed(chunk)
            for anchor in parser.anchors:
                yield anchor

    @staticmethod
    def _isdir(link: Anchor):
        return link.href.endswith("/")

    @staticmethod
    def _should_ignore(base_url, link: Anchor):
        if link.text == "../" or link.href.endswith(HttpDirectory.BLACK_LIST):
            return True

        # Ignore external links
        full_url = os.path.join(base_url, link.href)
        if not full_url.startswith(base_url):
            return True

    def close(self):
        self.session.close()


