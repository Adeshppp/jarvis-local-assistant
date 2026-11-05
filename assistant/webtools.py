"""Public web retrieval and an isolated, visible browser. No cloud inference."""
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import os
from pathlib import Path
import socket
from urllib.parse import urljoin, urlparse, quote_plus
import httpx
from .config import STATE
from .storage import BoundaryError

def public_url(value):
    parsed=urlparse(value)
    if parsed.scheme not in ("https","http") or not parsed.hostname or parsed.username or parsed.password:
        raise BoundaryError("Use a public HTTP(S) URL without embedded credentials")
    if parsed.port not in (None,80,443):raise BoundaryError("Browser tools support public HTTP/HTTPS ports")
    try:addresses=socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=="https" else 80),type=socket.SOCK_STREAM)
    except OSError as e:raise ConnectionError("Internet/DNS is unavailable for this website") from e
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise BoundaryError("Local services and private network addresses are not internet search targets")
    return value

def read_page(url,limit=9000):
    from bs4 import BeautifulSoup
    public_url(url)
    with httpx.Client(timeout=20,follow_redirects=False,trust_env=False,headers={"User-Agent":"Mozilla/5.0 (compatible; JarvisLocal/0.2; user-requested retrieval)"}) as client:
        for _ in range(6):
            public_url(url)
            with client.stream("GET",url) as response:
                if response.is_redirect:
                    url=urljoin(url,response.headers["location"]);continue
                response.raise_for_status()
                content_type=response.headers.get("content-type","")
                if not any(x in content_type for x in ("html","text","json","xml")):
                    raise ValueError("This URL is a download or non-text resource; open it in the browser")
                chunks=[];size=0
                for chunk in response.iter_bytes():
                    size+=len(chunk)
                    if size>2_000_000:break
                    chunks.append(chunk)
                soup=BeautifulSoup(b"".join(chunks),"html.parser")
                for tag in soup(["script","style","noscript","svg"]):tag.decompose()
                text=soup.get_text(" ",strip=True)
                links=[]
                for anchor in soup.find_all("a",href=True):
                    href=urljoin(url,anchor["href"])
                    if href.startswith(("https://","http://")):
                        links.append({"text":anchor.get_text(" ",strip=True)[:120],"url":href})
                    if len(links)>=30:break
                return {"url":url,"title":soup.title.get_text() if soup.title else "","untrusted_data":text[:limit],"truncated":len(text)>limit,"links":links}
    raise ValueError("Too many website redirects")

def search_web(query,limit=5):
    # A fixed provider avoids sending queries to an unspecified metasearch backend.
    from ddgs import DDGS
    try:
        rows=DDGS(timeout=15).text(query,backend="duckduckgo",max_results=limit)
        result=[{"title":r.get("title",""),"url":r.get("href",r.get("url","")),"snippet":r.get("body","")} for r in rows]
        if result:return {"query":query,"provider":"DuckDuckGo","untrusted_results":result}
    except Exception as first:
        error=type(first).__name__
    else:error="NoResults"
    # The provider may throttle its API. Its normal HTML page is an independent
    # fallback, with links validated again before any subsequent navigation.
    from bs4 import BeautifulSoup
    try:
        with httpx.Client(timeout=15,trust_env=False) as client:
            response=client.get("https://html.duckduckgo.com/html/",params={"q":query});response.raise_for_status()
        soup=BeautifulSoup(response.text,"html.parser");results=[]
        for card in soup.select(".result"):
            link=card.select_one(".result__a");snippet=card.select_one(".result__snippet")
            if not link:continue
            from urllib.parse import parse_qs,unquote
            href=urljoin("https://duckduckgo.com",link.get("href",""))
            href=parse_qs(urlparse(href).query).get("uddg",[href])[0]
            results.append({"title":link.get_text(" ",strip=True),"url":href,"snippet":snippet.get_text(" ",strip=True) if snippet else ""})
            if len(results)>=limit:break
        if results:return {"query":query,"provider":"DuckDuckGo HTML","untrusted_results":results}
    except Exception:pass
    return {"query":query,"error":"Search provider unavailable or blocked ("+error+"). No results were fabricated.","search_url":"https://duckduckgo.com/?q="+quote_plus(query)}

class Browser:
    def __init__(self,state=None,headless=False,binaries=None):
        self.state=Path(state or STATE);self.headless=headless
        self.binaries=Path(binaries) if binaries else self.state/'browser-binaries'
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix="jarvis-browser")
        self.playwright=None;self.context=None;self.page=None

    def call(self,action,**arguments):
        return self.executor.submit(self._call,action,arguments).result(timeout=45)

    def _start(self):
        if self.context and self.page and not self.page.is_closed():return
        if self.playwright:
            try:self.playwright.stop()
            except Exception:pass
            self.playwright=self.context=self.page=None
        from playwright.sync_api import sync_playwright
        os.environ["PLAYWRIGHT_BROWSERS_PATH"]=str(self.binaries)
        self.playwright=sync_playwright().start()
        self.context=self.playwright.chromium.launch_persistent_context(str(self.state/"browser-profile"),headless=self.headless,
            chromium_sandbox=True,accept_downloads=False,permissions=[],viewport={"width":1280,"height":850},timeout=20000)
        self.context.set_default_timeout(10000)
        def route(request):
            try:
                if request.request.url.startswith("data:"):request.continue_();return
                public_url(request.request.url);request.continue_()
            except Exception:request.abort()
        self.context.route("**/*",route)
        self.page=self.context.pages[0] if self.context.pages else self.context.new_page()

    def _call(self,action,a):
        if action=="close":
            if self.context:self.context.close();self.playwright.stop()
            self.context=self.playwright=self.page=None
            return {"closed":True}
        self._start()
        if action=="navigate":
            public_url(a["url"])
            self.page.goto(a["url"],wait_until="domcontentloaded",timeout=25000)
            self.page.bring_to_front()
        elif action=="back":self.page.go_back(wait_until="domcontentloaded",timeout=20000)
        elif action in ("click","fill"):
            public_url(self.page.url)
            if a.get("expected_url") and self.page.url!=a["expected_url"]:raise BoundaryError("Browser page changed; request a new preview")
            selector=a["selector"]
            locator=self.page.locator(selector)
            if locator.count()!=1:raise ValueError("Choose a selector matching exactly one visible element")
            if locator.get_attribute("type") in ("file","password"):
                raise BoundaryError("Complete file-upload and password fields yourself in the browser")
            if action=="click":locator.click(timeout=10000)
            else:locator.fill(a["text"],timeout=10000)
        elif action not in ("read","tabs"):raise ValueError("Unknown browser action")
        if action=="tabs":return {"tabs":[{"url":p.url,"title":p.title()} for p in self.context.pages]}
        self.page.wait_for_load_state("domcontentloaded",timeout=10000)
        text=self.page.locator("body").inner_text(timeout=10000)
        links=self.page.locator("a[href]").evaluate_all("items => items.slice(0,40).map(e=>({text:e.innerText.slice(0,100),url:e.href}))")
        controls=self.page.locator("button,input,textarea,select").evaluate_all("items => items.slice(0,30).map(e=>({tag:e.tagName.toLowerCase(),type:e.type,id:e.id,name:e.name,text:(e.innerText||e.getAttribute('aria-label')||'').slice(0,100)}))")
        return {"url":self.page.url,"title":self.page.title(),"untrusted_data":text[:9000],"links":links,"controls":controls}

    def shutdown(self):
        try:self.call("close")
        finally:self.executor.shutdown(wait=False,cancel_futures=True)
