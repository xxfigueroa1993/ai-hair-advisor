"""
╔══════════════════════════════════════════════════════════════════╗
║         SUPPORTRD AUTO CONTENT ENGINE                           ║
║         Runs daily — finds trending hair topics,                ║
║         writes SEO pages, posts to Pinterest & Reddit           ║
╚══════════════════════════════════════════════════════════════════╝

HOW IT WORKS:
1. Scans Google Trends + Reddit for trending hair topics daily
2. Uses Claude to write full SEO blog posts targeting those topics
3. Auto-publishes pages to your Shopify blog
4. Auto-posts to Pinterest with backlink to your site
5. Auto-posts to Reddit hair communities with valuable content
6. Logs everything — topic, URL, engagement

SETUP:
- Deploy alongside app.py on Render
- Add environment variables (see CONFIG below)
- Runs automatically via /api/content-engine/run endpoint
- Schedule via Render Cron Job: 0 9 * * * (9am daily)
"""

import os
import json
import time
import datetime
import requests
import urllib.request
import urllib.parse

# ── CONFIGURATION ─────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
SHOPIFY_STORE      = os.environ.get("SHOPIFY_STORE", "supportrd.myshopify.com")
SHOPIFY_ADMIN_TOKEN= os.environ.get("SHOPIFY_ADMIN_TOKEN", "")
PINTEREST_TOKEN    = os.environ.get("PINTEREST_TOKEN", "")
REDDIT_CLIENT_ID   = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_SECRET      = os.environ.get("REDDIT_SECRET", "")
REDDIT_USERNAME    = os.environ.get("REDDIT_USERNAME", "")
REDDIT_PASSWORD    = os.environ.get("REDDIT_PASSWORD", "")
STORE_URL          = "https://supportrd.com"

# ── HAIR TOPICS TO TARGET ─────────────────────────────────────────
# These are high-traffic TikTok/Google hair searches
# Engine rotates through these + discovers new ones daily
SEED_TOPICS = [
    "how to fix damaged hair",
    "hair growth tips for black hair",
    "Dominican hair care routine",
    "how to stop hair breakage",
    "hair loss treatment at home",
    "curly hair moisture routine",
    "how to grow hair faster",
    "scalp treatment for hair loss",
    "deep conditioning routine",
    "frizzy hair solutions",
    "hair care routine for dry hair",
    "how to repair bleached hair",
    "relaxed hair care tips",
    "hair thinning solutions women",
    "best hair growth serum",
    "how to get shiny hair naturally",
    "dandruff treatment home remedy",
    "hair breakage causes and treatment",
    "postpartum hair loss solutions",
    "protein treatment for hair",
]

# Reddit communities to post in
REDDIT_COMMUNITIES = [
    "Hair",
    "Haircare",
    "BlackHair",
    "curlyhair",
    "FancyFollicles",
    "NaturalHair",
]

# Pinterest boards to post to (create these in your Pinterest account)
PINTEREST_BOARDS = [
    "Hair Care Tips",
    "Hair Growth",
    "Damaged Hair Repair",
]

# ── CLAUDE CONTENT GENERATOR ──────────────────────────────────────
def generate_content(topic):
    """Use Claude to write a full SEO blog post about a hair topic."""
    
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
- SEO meta description (150 chars max) at the very end, labeled "META:"
- Pinterest description (100 chars) at the very end, labeled "PINTEREST:"
- Reddit title (under 300 chars, helpful not salesy) labeled "REDDIT_TITLE:"
- Reddit body (helpful, value-first, mention SupportRD naturally) labeled "REDDIT_BODY:"

Format the blog post in clean HTML (just the body content, no <html> or <head> tags).
Start with <h1> for the title."""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"❌ API Error {e.code}: {body}")
        raise


def parse_content(raw):
    """Extract blog HTML, meta, pinterest desc, reddit title/body from Claude output."""
    
    def extract(label, text):
        idx = text.find(label)
        if idx == -1: return ""
        start = idx + len(label)
        end   = text.find("\n", start)
        return text[start:end if end > -1 else None].strip()

    meta       = extract("META:", raw)
    pinterest  = extract("PINTEREST:", raw)
    reddit_title = extract("REDDIT_TITLE:", raw)
    reddit_body  = extract("REDDIT_BODY:", raw)

    # HTML is everything before the first META: line
    html_end = raw.find("META:")
    html = raw[:html_end].strip() if html_end > -1 else raw

    # Extract title from first <h1>
    title_start = html.find("<h1>") + 4
    title_end   = html.find("</h1>")
    title = html[title_start:title_end].strip() if title_start > 3 else "Hair Care Tips"

    # Generate URL handle from title
    handle = title.lower()
    for ch in ["'", '"', "?", "!", ",", ".", ":", "/"]:
        handle = handle.replace(ch, "")
    handle = handle.replace(" ", "-")[:80]

    return {
        "title": title,
        "handle": handle,
        "html": html,
        "meta": meta,
        "pinterest_desc": pinterest,
        "reddit_title": reddit_title,
        "reddit_body": reddit_body,
    }


# ── BLOG PUBLISHER — saves to server ──────────────────────────────
BLOG_DIR = "/tmp/srd_blog"

def publish_to_server(content):
    """Save article as HTML file on the server."""
    import os
    os.makedirs(BLOG_DIR, exist_ok=True)

    # Save individual post
    filename = f"{content['handle']}.json"
    post = {
        "title":   content["title"],
        "handle":  content["handle"],
        "html":    content["html"],
        "meta":    content["meta"],
        "date":    datetime.datetime.utcnow().isoformat(),
    }
    with open(f"{BLOG_DIR}/{filename}", "w") as f:
        json.dump(post, f)

    # Update index
    index_path = f"{BLOG_DIR}/index.json"
    try:
        with open(index_path, "r") as f:
            index = json.load(f)
    except:
        index = []

    # Add to index if not already there
    handles = [p["handle"] for p in index]
    if content["handle"] not in handles:
        index.insert(0, {
            "title":  content["title"],
            "handle": content["handle"],
            "meta":   content["meta"],
            "date":   post["date"],
        })
    index = index[:90]  # Keep last 90 posts
    with open(index_path, "w") as f:
        json.dump(index, f)

    url = f"https://ai-hair-advisor.onrender.com/blog/{content['handle']}"
    print(f"✅ Published to server: {url}")
    return url


# ── PINTEREST PUBLISHER ────────────────────────────────────────────
def post_to_pinterest(content, article_url):
    """Post article to Pinterest."""
    if not PINTEREST_TOKEN:
        print("⚠️  No Pinterest token — skipping")
        return False

    # Get board ID
    boards_resp = requests.get(
        "https://api.pinterest.com/v5/boards",
        headers={"Authorization": f"Bearer {PINTEREST_TOKEN}"},
        timeout=10
    )
    
    board_id = None
    if boards_resp.status_code == 200:
        boards = boards_resp.json().get("items", [])
        for board in boards:
            if any(b.lower() in board["name"].lower() for b in PINTEREST_BOARDS):
                board_id = board["id"]
                break

    if not board_id and boards_resp.status_code == 200:
        boards = boards_resp.json().get("items", [])
        if boards:
            board_id = boards[0]["id"]

    if not board_id:
        print("⚠️  No Pinterest board found")
        return False

    pin = {
        "title":       content["title"],
        "description": content["pinterest_desc"] or content["meta"],
        "link":        article_url,
        "board_id":    board_id,
        "media_source": {
            "source_type": "image_url",
            "url": f"{STORE_URL}/cdn/shop/files/supportrd-logo.png"
        }
    }

    resp = requests.post(
        "https://api.pinterest.com/v5/pins",
        json=pin,
        headers={
            "Authorization":  f"Bearer {PINTEREST_TOKEN}",
            "Content-Type":   "application/json"
        },
        timeout=10
    )

    if resp.status_code in (200, 201):
        print(f"✅ Posted to Pinterest: {content['title']}")
        return True
    else:
        print(f"⚠️  Pinterest post failed: {resp.status_code}")
        return False


# ── REDDIT PUBLISHER ───────────────────────────────────────────────
def get_reddit_token():
    """Get Reddit OAuth token."""
    if not REDDIT_CLIENT_ID or not REDDIT_SECRET:
        return None
    resp = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(REDDIT_CLIENT_ID, REDDIT_SECRET),
        data={
            "grant_type": "password",
            "username":   REDDIT_USERNAME,
            "password":   REDDIT_PASSWORD
        },
        headers={"User-Agent": "SupportRD-ContentBot/1.0"},
        timeout=10
    )
    if resp.status_code == 200:
        return resp.json().get("access_token")
    return None


def post_to_reddit(content, article_url):
    """Post helpful content to Reddit hair communities."""
    if not REDDIT_CLIENT_ID:
        print("⚠️  No Reddit credentials — skipping")
        return False

    token = get_reddit_token()
    if not token:
        print("⚠️  Reddit auth failed")
        return False

    # Pick one community per run (rotate daily)
    day_of_year = datetime.datetime.now().timetuple().tm_yday
    community   = REDDIT_COMMUNITIES[day_of_year % len(REDDIT_COMMUNITIES)]

    body = content["reddit_body"] or f"""
{content['title']}

{content['meta']}

For personalized advice based on your specific hair type, Aria (SupportRD's free AI hair advisor) can analyze your hair concerns and give you a tailored routine: {article_url}

Hope this helps! Happy to answer questions in the comments.
"""

    resp = requests.post(
        "https://oauth.reddit.com/api/submit",
        headers={
            "Authorization": f"bearer {token}",
            "User-Agent":    "SupportRD-ContentBot/1.0"
        },
        data={
            "sr":    community,
            "kind":  "self",
            "title": content["reddit_title"] or content["title"],
            "text":  body,
            "nsfw":  False,
            "spoiler": False,
        },
        timeout=10
    )

    if resp.status_code == 200:
        result = resp.json()
        if result.get("success") or result.get("json", {}).get("data"):
            print(f"✅ Posted to r/{community}")
            return True
    print(f"⚠️  Reddit post failed: {resp.status_code} {resp.text[:100]}")
    return False


# ── TOPIC DISCOVERY ────────────────────────────────────────────────
def scrape_pinterest_trends():
    """Scrape trending hair topics from Pinterest public search."""
    queries = ["hair care", "hair growth", "damaged hair", "curly hair routine", "hair loss"]
    import random, re
    query = random.choice(queries)
    try:
        url = f"https://pinterest.com/search/pins/?q={urllib.parse.quote(query)}&rs=typed"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        # Extract pin titles from meta tags and script data
        titles = re.findall(r'"title"\s*:\s*"([^"]{20,120})"', html)
        hair_titles = [t for t in titles if any(kw in t.lower() for kw in 
            ["hair", "curl", "scalp", "growth", "damage", "frizz", "moisture", "routine", "treatment"])]
        if hair_titles:
            topic = random.choice(hair_titles[:10])
            print(f"📌 Pinterest trend found: {topic}")
            return topic
    except Exception as e:
        print(f"⚠️ Pinterest scrape failed: {e}")
    return None

def scrape_reddit_trends():
    """Scrape trending hair topics from Reddit."""
    try:
        url = "https://www.reddit.com/r/Hair+Haircare+NaturalHair+curlyhair/hot.json?limit=10"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        posts = data["data"]["children"]
        for p in posts:
            title = p["data"].get("title","")
            if len(title) > 20 and any(kw in title.lower() for kw in ["hair","curl","scalp","growth","damage","frizz","moisture","routine"]):
                print(f"🤖 Reddit trend found: {title}")
                return title
    except Exception as e:
        print(f"⚠️ Reddit scrape failed: {e}")
    return None

def get_todays_topic():
    """Get trending topic from multiple platforms or fall back to seed topics."""
    import random
    day = datetime.datetime.now().timetuple().tm_yday

    # Try platforms in random order
    scrapers = [scrape_pinterest_trends, scrape_reddit_trends]
    random.shuffle(scrapers)
    for scraper in scrapers:
        trend = scraper()
        if trend:
            return trend

    # Fall back to seed topic rotation
    topic = SEED_TOPICS[day % len(SEED_TOPICS)]
    print(f"📋 Using seed topic: {topic}")
    return topic


# ── LOGGING ───────────────────────────────────────────────────────
def log_run(topic, shopify_url, pinterest_ok, reddit_ok, error=None):
    """Log content engine run to a simple JSON file."""
    log_path = "/tmp/content_engine_log.json"
    
    try:
        with open(log_path, "r") as f:
            log = json.load(f)
    except:
        log = []

    log.append({
        "date":       datetime.datetime.utcnow().isoformat(),
        "topic":      topic,
        "shopify_url": shopify_url,
        "pinterest":  pinterest_ok,
        "reddit":     reddit_ok,
        "error":      error
    })

    # Keep last 90 days
    log = log[-90:]
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)


# ── MAIN RUN ──────────────────────────────────────────────────────
def run_engine():
    """Main function — runs once daily."""
    print(f"\n{'='*60}")
    print(f"  SupportRD Content Engine — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    topic       = None
    shopify_url = None
    pinterest_ok= False
    reddit_ok   = False
    error       = None

    print(f"🚀 Engine starting...")
    print(f"   ANTHROPIC_API_KEY set: {bool(ANTHROPIC_API_KEY)}")
    print(f"   SHOPIFY_ADMIN_TOKEN set: {bool(SHOPIFY_ADMIN_TOKEN)}")
    print(f"   SHOPIFY_STORE: {SHOPIFY_STORE}")

    try:
        # 1. Get today's topic
        topic = get_todays_topic()
        print(f"🎯 Topic: {topic}\n")

        # 2. Generate content with Claude
        print("✍️  Generating content with Claude...")
        raw     = generate_content(topic)
        content = parse_content(raw)
        print(f"📝 Title: {content['title']}")

        # 3. Publish to Shopify blog
        print("\n🛍️  Publishing to Shopify...")
        shopify_url = publish_to_server(content)

        # 4. Post to Pinterest
        if shopify_url:
            print("\n📌 Posting to Pinterest...")
            pinterest_ok = post_to_pinterest(content, shopify_url)

            # 5. Post to Reddit (value-first, not spammy)
            print("\n🤖 Posting to Reddit...")
            time.sleep(2)  # Be respectful of rate limits
            reddit_ok = post_to_reddit(content, shopify_url)

        print(f"\n✅ Engine complete!")
        print(f"   Shopify: {shopify_url or 'skipped'}")
        print(f"   Pinterest: {'✓' if pinterest_ok else '✗'}")
        print(f"   Reddit: {'✓' if reddit_ok else '✗'}")

    except Exception as e:
        error = str(e)
        print(f"\n❌ Engine error: {error}")

    finally:
        log_run(topic, shopify_url, pinterest_ok, reddit_ok, error)

    return {
        "ok":           error is None,
        "topic":        topic,
        "shopify_url":  shopify_url,
        "pinterest":    pinterest_ok,
        "reddit":       reddit_ok,
        "error":        error
    }


if __name__ == "__main__":
    run_engine()

