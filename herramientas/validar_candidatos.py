"""Prueba una lista de URLs de feeds y dice cuáles responden con items recientes."""
import concurrent.futures as cf
import sys
import time

import feedparser
import httpx

UAS = {
    "bot": "NoticiasMundoBot/1.0 (+https://github.com/GustavoMix/cron-rss-noticias)",
    "nav": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36",
}


def probar(url):
    out = []
    for nombre, ua in UAS.items():
        try:
            r = httpx.get(url, headers={"User-Agent": ua, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"},
                          follow_redirects=True, timeout=20)
            if r.status_code >= 400:
                out.append(f"{nombre}:HTTP{r.status_code}")
                continue
            f = feedparser.parse(r.content)
            n = len(f.entries)
            if n == 0:
                out.append(f"{nombre}:0items")
                continue
            ult = 0
            for e in f.entries:
                t = e.get("published_parsed") or e.get("updated_parsed")
                if t:
                    ult = max(ult, time.mktime(t))
            edad = (time.time() - ult) / 3600 if ult else -1
            titulo = (f.feed.get("title") or "")[:50]
            return f"OK {nombre} items={n} edad_h={edad:.0f} final={r.url} titulo={titulo!r}"
        except Exception as exc:  # noqa: BLE001
            out.append(f"{nombre}:{type(exc).__name__}")
    return "FAIL " + " ".join(out)


urls = [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]
with cf.ThreadPoolExecutor(16) as ex:
    for url, res in zip(urls, ex.map(probar, urls)):
        print(f"{res}  <-  {url}", flush=True)
