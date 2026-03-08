"""
╔══════════════════════════════════════════════════════════════════╗
║         SUPPORTRD AUTO CONTENT ENGINE v2                        ║
║         Scrapes trends from Western + Chinese platforms         ║
║         Writes SEO posts in English + Chinese                   ║
╚══════════════════════════════════════════════════════════════════╝

CHINESE PLATFORMS USED AS TREND RADAR:
- Weibo      — Chinese Twitter, public search
- Xiaohongshu (RED) — Chinese Instagram/beauty platform  
- Douyin     — Chinese TikTok, public trending
- Baidu      — Chinese Google, search trends

No accounts needed — scrapes public trending data only.
"""

import os, json, time, re, random, datetime
import requests, urllib.request, urllib.parse

ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
SHOPIFY_STORE       = os.environ.get("SHOPIFY_STORE", "supportrd.myshopify.com")
SHOPIFY_ADMIN_TOKEN = os.environ.get("SHOPIFY_ADMIN_TOKEN", "")
PINTEREST_TOKEN     = os.environ.get("PINTEREST_TOKEN", "")
REDDIT_CLIENT_ID    = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_SECRET       = os.environ.get("REDDIT_SECRET", "")
REDDIT_USERNAME     = os.environ.get("REDDIT_USERNAME", "")
REDDIT_PASSWORD     = os.environ.get("REDDIT_PASSWORD", "")
STORE_URL           = "https://supportrd.com"

SEED_TOPICS = [
    "how to fix damaged hair",
    "hair growth tips for black hair",
    "Dominican hair care routine",
    "how to stop hair breakage",
    "hair loss treatment at home",
    "curly hair moisture routine",
    "how to grow hair faster",
    "deep conditioning routine",
    "frizzy hair solutions",
    "best oils for hair growth",
    "how to repair bleached hair",
    "relaxed hair care tips",
    "postpartum hair loss solutions",
    "protein treatment for hair",
    "natural ingredients for hair growth",
    "how to moisturize dry natural hair",
    "why is my hair falling out",
    "hair porosity explained",
    "how to detangle matted hair",
    "Caribbean hair care secrets",
    "rosemary oil for hair growth",
    "aloe vera benefits for hair",
    "how to strengthen weak hair",
    "overnight hair mask recipes",
    "why hair stops growing",
    "heat damage repair for hair",
    "best shampoo for hair loss",
    "onion juice for hair regrowth",
    "how to get thicker hair naturally",
    "split ends treatment at home",
    "hair care routine for mixed hair",
    "how to reduce hair shedding",
    "biotin for hair growth does it work",
    "co-washing natural hair guide",
    "how to revive dull lifeless hair",
    "hair growth stages explained",
    "why does my hair break off",
    "Dominican blowout at home",
    "ayurvedic hair care routine",
    "how to seal moisture in natural hair",
]

REDDIT_COMMUNITIES = ["Hair","Haircare","BlackHair","curlyhair","FancyFollicles","NaturalHair"]
PINTEREST_BOARDS   = ["Hair Care Tips","Hair Growth","Damaged Hair Repair"]

CHINESE_HAIR_KW = [
    "头发","护发","发质","掉发","脱发","生发","头皮","秀发",
    "发型","护理","洗发","毛躁","烫发","染发","修复","滋养",
    "柔顺","光泽","增发","发根","发丝","头油","干枯"
]

CHINESE_TREND_MAP = {
    "头发掉落": "hair loss prevention",
    "头发干枯": "dry damaged hair repair",
    "头发生长": "hair growth tips",
    "头皮护理": "scalp care routine",
    "头发毛躁": "frizzy hair solutions",
    "头发修复": "hair repair treatment",
    "防脱发":   "anti hair loss treatment",
    "头发增长": "how to grow hair faster",
    "护发素":   "deep conditioning routine",
    "头发光泽": "shiny hair tips",
    "掉发":     "hair loss treatment",
    "脱发":     "hair loss solutions",
    "生发":     "hair regrowth tips",
    "护发":     "hair care routine",
    "头皮":     "scalp health tips",
}


def translate_chinese_topic(chinese_text):
    if not ANTHROPIC_API_KEY or not chinese_text:
        return None
    try:
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 60,
            "messages": [{"role": "user", "content": f"Translate this Chinese hair care topic into a short English blog post topic (under 10 words, actionable): {chinese_text}\nRespond with ONLY the English topic, nothing else."}]
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["content"][0]["text"].strip()
    except:
        return None


def _extract_chinese_trend(html, source):
    patterns = [
        r'"title"\s*:\s*"([^"]{5,80})"',
        r'"desc"\s*:\s*"([^"]{5,80})"',
        r'<p[^>]*>(.*?)</p>',
        r'<h3[^>]*>(.*?)</h3>',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, html, re.DOTALL)
        for m in matches:
            clean = re.sub(r'<[^>]+>', '', m).strip()
            if any(kw in clean for kw in CHINESE_HAIR_KW) and 5 < len(clean) < 100:
                for cn, en in CHINESE_TREND_MAP.items():
                    if cn in clean:
                        print(f"{source} trend: {cn} -> {en}")
                        return en
                translated = translate_chinese_topic(clean[:80])
                if translated and len(translated) > 5:
                    print(f"{source} trend (translated): {translated}")
                    return translated
    return None


def scrape_weibo_trends():
    queries = ["护发", "头发护理", "掉发", "生发", "头发修复"]
    query = random.choice(queries)
    try:
        url = f"https://s.weibo.com/weibo?q={urllib.parse.quote(query)}&rd=realtime"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        return _extract_chinese_trend(html, "Weibo")
    except Exception as e:
        print(f"Weibo scrape failed: {e}")
    return None


def scrape_xiaohongshu_trends():
    queries = ["护发攻略", "头发护理", "头皮护理", "防脱发"]
    query = random.choice(queries)
    try:
        url = f"https://www.xiaohongshu.com/search_result?keyword={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.xiaohongshu.com/"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        return _extract_chinese_trend(html, "Xiaohongshu")
    except Exception as e:
        print(f"Xiaohongshu scrape failed: {e}")
    return None


def scrape_douyin_trends():
    queries = ["护发", "掉发怎么办", "头发护理"]
    query = random.choice(queries)
    try:
        url = f"https://www.douyin.com/search/{urllib.parse.quote(query)}?type=general"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.douyin.com/"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        return _extract_chinese_trend(html, "Douyin")
    except Exception as e:
        print(f"Douyin scrape failed: {e}")
    return None


def scrape_baidu_trends():
    queries = ["护发", "掉发", "头发生长", "头皮护理"]
    query = random.choice(queries)
    try:
        url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        return _extract_chinese_trend(html, "Baidu")
    except Exception as e:
        print(f"Baidu scrape failed: {e}")
    return None


def scrape_pinterest_trends():
    queries = ["hair care","hair growth","damaged hair","curly hair routine","hair loss"]
    query = random.choice(queries)
    try:
        url = f"https://pinterest.com/search/pins/?q={urllib.parse.quote(query)}&rs=typed"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        titles = re.findall(r'"title"\s*:\s*"([^"]{20,120})"', html)
        hair_titles = [t for t in titles if any(kw in t.lower() for kw in
            ["hair","curl","scalp","growth","damage","frizz","moisture","routine","treatment"])]
        if hair_titles:
            topic = random.choice(hair_titles[:10])
            print(f"Pinterest trend: {topic}")
            return topic
    except Exception as e:
        print(f"Pinterest scrape failed: {e}")
    return None


def scrape_reddit_trends():
    try:
        url = "https://www.reddit.com/r/Hair+Haircare+NaturalHair+curlyhair/hot.json?limit=10"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        for p in data["data"]["children"]:
            title = p["data"].get("title","")
            if len(title) > 20 and any(kw in title.lower() for kw in
                ["hair","curl","scalp","growth","damage","frizz","moisture","routine"]):
                print(f"Reddit trend: {title}")
                return title
    except Exception as e:
        print(f"Reddit scrape failed: {e}")
    return None


def _get_recent_topics(limit=10):
    """Get recently used topics from DB to avoid repeats."""
    try:
        import sqlite3
        db = sqlite3.connect(BLOG_DB)
        rows = db.execute("SELECT title FROM posts ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
        db.close()
        return [r[0].lower() for r in rows]
    except:
        return []

def _topic_is_duplicate(topic, recent_topics):
    """Check if topic is too similar to recent ones."""
    topic_words = set(topic.lower().split())
    for recent in recent_topics:
        recent_words = set(recent.lower().split())
        overlap = len(topic_words & recent_words)
        if overlap >= 3:
            return True
    return False

def get_todays_topic():
    day = datetime.datetime.now().timetuple().tm_yday
    recent_topics = _get_recent_topics(10)

    all_scrapers = [
        ("Weibo",       scrape_weibo_trends),
        ("Xiaohongshu", scrape_xiaohongshu_trends),
        ("Douyin",      scrape_douyin_trends),
        ("Baidu",       scrape_baidu_trends),
        ("Pinterest",   scrape_pinterest_trends),
        ("Reddit",      scrape_reddit_trends),
    ]
    random.shuffle(all_scrapers)
    for name, scraper in all_scrapers:
        try:
            trend = scraper()
            if trend and len(trend) > 5:
                if _topic_is_duplicate(trend, recent_topics):
                    print(f"{name} trend too similar to recent post — skipping: {trend}")
                    continue
                print(f"Topic sourced from {name}: {trend}")
                return trend
        except Exception as e:
            print(f"{name} error: {e}")

    # Pick a seed topic not used recently
    available = [t for t in SEED_TOPICS if not _topic_is_duplicate(t, recent_topics)]
    if not available:
        available = SEED_TOPICS  # all used, reset
    topic = random.choice(available)
    print(f"Using seed topic: {topic}")
    return topic


def generate_content(topic):
    prompt = f"""Write a comprehensive, SEO-optimized blog post for SupportRD about: "{topic}"

REQUIREMENTS:
- Title: compelling, includes the topic keyword naturally
- Length: 600-800 words
- Structure: intro, 3-4 subheadings with practical tips, conclusion with CTA
- Tone: warm, expert, like a knowledgeable Dominican hair care professional
- Naturally mention SupportRD products where relevant:
  * Formula Exclusiva ($55) — damaged, weak, breaking hair
  * Laciador Crece ($40) — dry hair, frizz, growth, shine
  * Gotero Rapido ($55) — hair loss, scalp issues, slow growth
  * Gotitas Brillantes ($30) — shine, finishing, frizz control
  * Mascarilla Capilar ($25) — deep conditioning
  * Shampoo Aloe Vera ($20) — scalp stimulation, daily cleanse
- Include a CTA to: Try Aria AI Hair Advisor free at {STORE_URL}
- End with: Get your free Hair Health Score at {STORE_URL}/pages/hair-dashboard
- SEO meta description (150 chars max) labeled "META:"
- Pinterest description (100 chars) labeled "PINTEREST:"
- Reddit title (under 300 chars, helpful not salesy) labeled "REDDIT_TITLE:"
- Reddit body (helpful, value-first) labeled "REDDIT_BODY:"
- Chinese title (Simplified Chinese, for trend monitoring) labeled "CHINESE_TITLE:"
- Chinese summary (150 chars Simplified Chinese) labeled "CHINESE_SUMMARY:"

Format the blog post in clean HTML (body content only). Start with <h1> for the title."""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2500,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result["content"][0]["text"].strip()


def parse_content(raw):
    def extract(label, text):
        idx = text.find(label)
        if idx == -1: return ""
        start = idx + len(label)
        end = text.find("\n", start)
        return text[start:end if end > -1 else None].strip()

    meta             = extract("META:", raw)
    pinterest        = extract("PINTEREST:", raw)
    reddit_title     = extract("REDDIT_TITLE:", raw)
    reddit_body      = extract("REDDIT_BODY:", raw)
    chinese_title    = extract("CHINESE_TITLE:", raw)
    chinese_summary  = extract("CHINESE_SUMMARY:", raw)

    html_end = raw.find("META:")
    html = raw[:html_end].strip() if html_end > -1 else raw

    title_start = html.find("<h1>") + 4
    title_end   = html.find("</h1>")
    title = html[title_start:title_end].strip() if title_start > 3 else "Hair Care Tips"

    handle = title.lower()
    for ch in ["'",'"',"?","!",",",".",":","/"]:
        handle = handle.replace(ch, "")
    handle = handle.replace(" ", "-")[:80]

    return {
        "title": title, "handle": handle, "html": html, "meta": meta,
        "pinterest_desc": pinterest, "reddit_title": reddit_title,
        "reddit_body": reddit_body, "chinese_title": chinese_title,
        "chinese_summary": chinese_summary,
    }


BLOG_DB = "/data/srd_blog.db"

def _init_blog_db():
    import sqlite3
    db = sqlite3.connect(BLOG_DB)
    db.execute("""CREATE TABLE IF NOT EXISTS posts (
        handle TEXT PRIMARY KEY,
        title TEXT,
        html TEXT,
        meta TEXT,
        chinese_title TEXT,
        chinese_summary TEXT,
        date TEXT
    )""")
    db.commit()
    db.close()

def publish_to_server(content):
    import sqlite3
    _init_blog_db()
    post_date = datetime.datetime.utcnow().isoformat()
    db = sqlite3.connect(BLOG_DB)
    db.execute("""INSERT OR REPLACE INTO posts
        (handle, title, html, meta, chinese_title, chinese_summary, date)
        VALUES (?,?,?,?,?,?,?)""",
        (content["handle"], content["title"], content["html"],
         content.get("meta",""), content.get("chinese_title",""),
         content.get("chinese_summary",""), post_date))
    db.commit()
    db.close()

    url = f"https://ai-hair-advisor.onrender.com/blog/{content['handle']}"
    print(f"Published: {url}")
    return url


def post_to_pinterest(content, article_url):
    if not PINTEREST_TOKEN:
        print("No Pinterest token — skipping")
        return False
    try:
        boards_resp = requests.get("https://api.pinterest.com/v5/boards",
            headers={"Authorization": f"Bearer {PINTEREST_TOKEN}"}, timeout=10)
        board_id = None
        if boards_resp.status_code == 200:
            boards = boards_resp.json().get("items", [])
            for b in boards:
                if any(pb.lower() in b["name"].lower() for pb in PINTEREST_BOARDS):
                    board_id = b["id"]; break
            if not board_id and boards:
                board_id = boards[0]["id"]
        if not board_id: return False
        resp = requests.post("https://api.pinterest.com/v5/pins",
            json={"title":content["title"],"description":content["pinterest_desc"] or content["meta"],
                  "link":article_url,"board_id":board_id,
                  "media_source":{"source_type":"image_url","url":f"{STORE_URL}/cdn/shop/files/supportrd-logo.png"}},
            headers={"Authorization":f"Bearer {PINTEREST_TOKEN}","Content-Type":"application/json"},timeout=10)
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"Pinterest error: {e}")
    return False


def post_to_reddit(content, article_url):
    if not REDDIT_CLIENT_ID:
        print("No Reddit credentials — skipping")
        return False
    try:
        token_resp = requests.post("https://www.reddit.com/api/v1/access_token",
            auth=(REDDIT_CLIENT_ID, REDDIT_SECRET),
            data={"grant_type":"password","username":REDDIT_USERNAME,"password":REDDIT_PASSWORD},
            headers={"User-Agent":"SupportRD-ContentBot/1.0"}, timeout=10)
        token = token_resp.json().get("access_token") if token_resp.status_code == 200 else None
        if not token: return False
        community = REDDIT_COMMUNITIES[datetime.datetime.now().timetuple().tm_yday % len(REDDIT_COMMUNITIES)]
        body = content["reddit_body"] or f"{content['title']}\n\n{content['meta']}\n\n{article_url}"
        resp = requests.post("https://oauth.reddit.com/api/submit",
            headers={"Authorization":f"bearer {token}","User-Agent":"SupportRD-ContentBot/1.0"},
            data={"sr":community,"kind":"self","title":content["reddit_title"] or content["title"],
                  "text":body,"nsfw":False,"spoiler":False}, timeout=10)
        return resp.status_code == 200 and (resp.json().get("success") or resp.json().get("json",{}).get("data"))
    except Exception as e:
        print(f"Reddit error: {e}")
    return False


def log_run(topic, shopify_url, pinterest_ok, reddit_ok, error=None):
    log_path = "/tmp/content_engine_log.json"
    try:
        with open(log_path, "r") as f:
            log = json.load(f)
    except:
        log = []
    log.append({"date":datetime.datetime.utcnow().isoformat(),"topic":topic,
                 "shopify_url":shopify_url,"pinterest":pinterest_ok,
                 "reddit":reddit_ok,"error":error})
    log = log[-90:]
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)


def run_engine():
    print(f"\n{'='*60}")
    print(f"  SupportRD Content Engine v2")
    print(f"  Scanning: Weibo, Xiaohongshu, Douyin, Baidu, Pinterest, Reddit")
    print(f"  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    topic=None; shopify_url=None; pinterest_ok=False; reddit_ok=False; error=None

    try:
        topic = get_todays_topic()
        print(f"Topic: {topic}\n")

        raw     = generate_content(topic)
        content = parse_content(raw)
        print(f"Title: {content['title']}")
        if content.get("chinese_title"):
            print(f"Chinese: {content['chinese_title']}")

        shopify_url  = publish_to_server(content)
        pinterest_ok = post_to_pinterest(content, shopify_url)
        time.sleep(2)
        reddit_ok    = post_to_reddit(content, shopify_url)

        print(f"\nDone! Blog: {shopify_url}")

    except Exception as e:
        error = str(e)
        print(f"Engine error: {error}")
    finally:
        log_run(topic, shopify_url, pinterest_ok, reddit_ok, error)

    return {"ok":error is None,"topic":topic,"shopify_url":shopify_url,
            "pinterest":pinterest_ok,"reddit":reddit_ok,"error":error}


if __name__ == "__main__":
    run_engine()
