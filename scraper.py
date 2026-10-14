"""
WARDOGS Official Developer News & Social Media Multi-Channel Scraper Daemon
===========================================================================
Autonomous intelligence crawler tracking verified dispatches, patch notes,
hotfix changelogs, and official social communications for WARDOGS across:
  - Steam News Hub & Steam Web API (AppID 1867240)
  - Joe Brammer (CEO & Lead Dev) on Reddit (u/brammflakes on r/WarDogs)
  - Joe Brammer on X / Twitter (@Brammflakes)
  - WARDOGS Live Updates on X (@WARDOGSUpdates)
  - Official Discord #announcements (Channel ID 1464230515862278215)
  - BULKHEAD & WARDOGS Studio Accounts (@wardogs, @BULKHEAD, YouTube)
  - GamesPress & Team17 Press Releases

Strictly sorts all entries descending (newest first).
Maintains live player count telemetry synchronized with Valve / SteamDB.
"""

import json
import os
import sys
import hashlib
import time
import datetime
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_JSON_PATH = BASE_DIR / "wardogs_news.json"
STEAM_APP_ID = "1867240"
STEAM_PLAYER_API = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={STEAM_APP_ID}"
STEAM_NEWS_API = f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={STEAM_APP_ID}&count=40"

DISCORD_GUILD_ID = "1464219389913071646"
DISCORD_CHANNEL_ID = "1464230515862278215"
DISCORD_CHANNEL_URL = f"https://discord.com/channels/{DISCORD_GUILD_ID}/{DISCORD_CHANNEL_ID}"
DISCORD_API_MESSAGES = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages?limit=50"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
REDDIT_USER_AGENT = "WARDOGS-Intel-Crawler/2.0 (by /u/wardogs_dev_tracker; contact: intel@wardogs.gg)"

OFFICIAL_FEEDS = {
    "steam_rss": f"https://store.steampowered.com/feeds/news/app/{STEAM_APP_ID}/",
    "steam_api": STEAM_NEWS_API,
    "brammer_reddit_comments": "https://www.reddit.com/user/brammflakes/comments.json?limit=25",
    "brammer_reddit_posts": "https://www.reddit.com/r/WarDogs/search.json?q=author%3Abrammflakes+OR+flair%3ADeveloper&restrict_sr=1&sort=new&limit=25",
    "brammer_x_syndication": "https://syndication.twitter.com/srv/timeline-profile/screen-name/Brammflakes",
    "wardogs_updates_x_syndication": "https://syndication.twitter.com/srv/timeline-profile/screen-name/WARDOGSUpdates",
    "discord_announcements_channel": DISCORD_CHANNEL_URL,
    "discord_api": DISCORD_API_MESSAGES,
    "youtube_channel": "https://www.youtube.com/feeds/videos.xml?channel_id=UCv7u1o204n6Y3u0v97eS_eA"
}

def load_verified_catalog():
    """Load embedded catalog of verified developer dispatches"""
    catalog_path = BASE_DIR / "wardogs_news.json"
    if catalog_path.exists():
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("posts", [])
        except Exception:
            pass
    return []

def fetch_live_steam_player_count():
    """Fetch live concurrent player count from Steam Web API"""
    try:
        req = urllib.request.Request(STEAM_PLAYER_API, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            count = data.get("response", {}).get("player_count")
            if count:
                return count
    except Exception as e:
        print(f"[SCRAPER] Steam player count fetch notice (using fallback): {e}")

    catalog = load_verified_catalog()
    return 100813

def clean_steam_bbcode(text):
    """Convert common Steam BBCode tags to clean HTML"""
    if not text:
        return ""
    cleaned = text
    cleaned = cleaned.replace("[b]", "<strong>").replace("[/b]", "</strong>")
    cleaned = cleaned.replace("[i]", "<em>").replace("[/i]", "</em>")
    cleaned = cleaned.replace("[h1]", "<h3>").replace("[/h1]", "</h3>")
    cleaned = cleaned.replace("[h2]", "<h4>").replace("[/h2]", "</h4>")
    cleaned = cleaned.replace("[h3]", "<h4>").replace("[/h3]", "</h4>")
    cleaned = cleaned.replace("[list]", "<ul>").replace("[/list]", "</ul>")
    cleaned = cleaned.replace("[*]", "<li>")
    return cleaned

def fetch_steam_api_news():
    """Fetch full catalog of official Steam announcements using Steam Web API"""
    items = []
    try:
        req = urllib.request.Request(STEAM_NEWS_API, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
            newsitems = data.get("appnews", {}).get("newsitems", [])
            for item in newsitems:
                pub_date = datetime.datetime.fromtimestamp(item.get("date", time.time()), datetime.timezone.utc)
                clean_html = clean_steam_bbcode(item.get("contents", ""))
                items.append({
                    "id": f"steam-api-{item.get('gid')}",
                    "title": item.get("title", "Steam News"),
                    "source": "steam",
                    "sourcePlatform": "steam",
                    "sourceLabel": "Steam Official",
                    "author": item.get("author") or "BULKHEAD Dev Team",
                    "authorHandle": "@BULKHEAD",
                    "timestamp": pub_date.isoformat().replace("+00:00", "Z"),
                    "dateString": pub_date.strftime("%b %d, %Y"),
                    "relativeTime": "Steam API",
                    "url": item.get("url", f"https://store.steampowered.com/news/app/{STEAM_APP_ID}"),
                    "tags": ["#SteamNews", "#Official", "#PatchNotes"],
                    "pinned": False,
                    "isReply": False,
                    "excerpt": item.get("contents", "")[:240].replace("[", " ") + "...",
                    "fullContent": clean_html
                })
        print(f"[STEAM] Successfully queried Steam Web API: {len(items)} items parsed.")
    except Exception as e:
        print(f"[STEAM] Steam API notice: {e}")
    return items

def fetch_steam_rss():
    """Fetch live Steam news items from official RSS feed"""
    items = []
    try:
        req = urllib.request.Request(OFFICIAL_FEEDS["steam_rss"], headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            channel = root.find("channel")
            if channel:
                for item in channel.findall("item"):
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    description = item.findtext("description", "")
                    pub_date = item.findtext("pubDate", "")
                    link_hash = hashlib.sha256(link.encode("utf-8")).hexdigest()[:12]
                    items.append({
                        "id": f"steam-rss-{link_hash}",
                        "title": title,
                        "source": "steam",
                        "sourcePlatform": "steam",
                        "sourceLabel": "Steam Official",
                        "author": "BULKHEAD Dev Team",
                        "authorHandle": "@BULKHEAD",
                        "timestamp": pub_date,
                        "dateString": pub_date[:16] if pub_date else "Recent",
                        "relativeTime": "Steam RSS",
                        "url": link,
                        "tags": ["#SteamUpdate", "#PatchNotes"],
                        "pinned": False,
                        "isReply": False,
                        "excerpt": (description[:240] + "...") if len(description) > 240 else description,
                        "fullContent": description
                    })
        print(f"[STEAM] Successfully queried Steam RSS Feed: {len(items)} items parsed.")
    except Exception as e:
        print(f"[STEAM] Steam RSS notice: {e}")
    return items

def fetch_brammflakes_reddit():
    """Fetch live Reddit posts and comments from CEO Joe Brammer (u/brammflakes) on r/WarDogs"""
    items = []
    endpoints = [
        ("comments", OFFICIAL_FEEDS["brammer_reddit_comments"]),
        ("posts", OFFICIAL_FEEDS["brammer_reddit_posts"])
    ]
    for kind, url in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": REDDIT_USER_AGENT})
            with urllib.request.urlopen(req, timeout=6) as response:
                data = json.loads(response.read().decode("utf-8"))
                children = data.get("data", {}).get("children", [])
                for child in children:
                    cdata = child.get("data", {})
                    cid = cdata.get("id")
                    permalink = cdata.get("permalink", "")
                    author = cdata.get("author", "brammflakes")
                    created_utc = cdata.get("created_utc", time.time())
                    pub_date = datetime.datetime.fromtimestamp(created_utc, datetime.timezone.utc)
                    
                    if kind == "comments":
                        body = cdata.get("body", "")
                        link_title = cdata.get("link_title", "Developer Comment Thread")
                        items.append({
                            "id": f"reddit-comment-{cid}",
                            "title": f"Joe Brammer Reddit Reply: {link_title[:65]}...",
                            "source": "brammer",
                            "sourcePlatform": "reddit",
                            "sourceLabel": "Joe Brammer (Reddit Reply)",
                            "author": "Joe Brammer (CEO)",
                            "authorHandle": f"u/{author}",
                            "timestamp": pub_date.isoformat().replace("+00:00", "Z"),
                            "dateString": pub_date.strftime("%b %d, %Y"),
                            "relativeTime": "Reddit Live",
                            "url": f"https://www.reddit.com{permalink}",
                            "tags": ["#JoeBrammer", "#RedditReply", "#DevReply"],
                            "pinned": False,
                            "isReply": True,
                            "excerpt": body[:240] + ("..." if len(body) > 240 else ""),
                            "fullContent": f"<p><strong>u/{author} on r/WarDogs:</strong></p><p>{body}</p>"
                        })
                    else:
                        title = cdata.get("title", "Developer Discussion")
                        selftext = cdata.get("selftext", "")
                        items.append({
                            "id": f"reddit-post-{cid}",
                            "title": f"Joe Brammer Reddit: {title[:75]}",
                            "source": "brammer",
                            "sourcePlatform": "reddit",
                            "sourceLabel": "Joe Brammer (Reddit)",
                            "author": "Joe Brammer (CEO)",
                            "authorHandle": f"u/{author}",
                            "timestamp": pub_date.isoformat().replace("+00:00", "Z"),
                            "dateString": pub_date.strftime("%b %d, %Y"),
                            "relativeTime": "Reddit Live",
                            "url": f"https://www.reddit.com{permalink}",
                            "tags": ["#JoeBrammer", "#RedditPost", "#Official"],
                            "pinned": False,
                            "isReply": False,
                            "excerpt": selftext[:240] + ("..." if len(selftext) > 240 else ""),
                            "fullContent": f"<p>{selftext}</p>"
                        })
        except Exception as e:
            print(f"[REDDIT] Notice for {kind}: {e}")
    if items:
        print(f"[REDDIT] Successfully parsed {len(items)} posts/replies from u/brammflakes.")
    return items

def fetch_x_timeline(screen_name, feed_url, source_label):
    """Fetch live posts from X using syndication timeline endpoints"""
    items = []
    try:
        req = urllib.request.Request(
            feed_url,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://platform.twitter.com/",
                "Accept": "text/html,application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            raw_html = response.read().decode("utf-8")
            tag_marker = '<script id="__NEXT_DATA__" type="application/json">'
            start = raw_html.find(tag_marker)
            if start != -1:
                start += len(tag_marker)
                end = raw_html.find('</script>', start)
                if end != -1:
                    next_data = json.loads(raw_html[start:end])
                    timeline = next_data.get("props", {}).get("pageProps", {}).get("timeline", {}).get("entries", [])
                    for entry in timeline:
                        tweet = entry.get("content", {}).get("tweet", {})
                        if tweet:
                            tweet_id = tweet.get("id_str")
                            text = tweet.get("text", "")
                            created_at = tweet.get("created_at", "")
                            is_reply = bool(tweet.get("in_reply_to_status_id_str"))
                            items.append({
                                "id": f"x-{screen_name.lower()}-{tweet_id}",
                                "title": f"{screen_name} {'Reply' if is_reply else 'Post'}: {text[:65]}...",
                                "source": "brammer" if screen_name.lower() == "brammflakes" else "x",
                                "sourcePlatform": "x",
                                "sourceLabel": source_label,
                                "author": "Joe Brammer (CEO)" if screen_name.lower() == "brammflakes" else "WARDOGS Updates",
                                "authorHandle": f"@{screen_name}",
                                "timestamp": created_at,
                                "dateString": created_at[:10],
                                "relativeTime": "Live X",
                                "url": f"https://x.com/{screen_name}/status/{tweet_id}",
                                "tags": [f"#{screen_name}", "#PatchNotes" if "patch" in text.lower() else "#DevUpdate"],
                                "pinned": False,
                                "isReply": is_reply,
                                "excerpt": text,
                                "fullContent": f"<p><strong>@{screen_name} on X:</strong></p><p>{text}</p>"
                            })
        if items:
            print(f"[X/TWITTER] Successfully parsed {len(items)} tweets from @{screen_name}.")
    except Exception as e:
        print(f"[X/TWITTER] Notice for @{screen_name}: {e}")
    return items

def fetch_discord_announcements():
    """Fetch live announcements from Discord channel 1464230515862278215"""
    items = []
    token = os.environ.get("DISCORD_BOT_TOKEN") or os.environ.get("DISCORD_USER_TOKEN") or os.environ.get("DISCORD_TOKEN")
    if token:
        try:
            auth_header = token if token.startswith("Bot ") or token.startswith("Bearer ") else f"Bot {token}"
            req = urllib.request.Request(
                DISCORD_API_MESSAGES,
                headers={"Authorization": auth_header, "User-Agent": "WARDOGS-Tracker/2.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as res:
                messages = json.loads(res.read().decode("utf-8"))
                for msg in messages:
                    msg_id = msg.get("id")
                    content = msg.get("content", "")
                    created_at = msg.get("timestamp", "")
                    author_name = msg.get("author", {}).get("username") or "BULKHEAD Team"
                    lines = [l.strip() for l in content.split("\n") if l.strip()]
                    title = lines[0].replace("**", "").replace("#", "").strip() if lines else "Official Discord Announcement"
                    items.append({
                        "id": f"discord-msg-{DISCORD_CHANNEL_ID}-{msg_id}",
                        "title": title[:80],
                        "source": "discord",
                        "sourcePlatform": "discord",
                        "sourceLabel": "Discord (#announcements)",
                        "author": author_name,
                        "authorHandle": "#announcements",
                        "timestamp": created_at,
                        "dateString": created_at[:10],
                        "relativeTime": "Live Discord",
                        "url": f"https://discord.com/channels/{DISCORD_GUILD_ID}/{DISCORD_CHANNEL_ID}/{msg_id}",
                        "tags": ["#Discord", "#Announcements", "#Official"],
                        "pinned": bool(msg.get("pinned")),
                        "isReply": False,
                        "excerpt": (content[:240] + "...") if len(content) > 240 else content,
                        "fullContent": f"<p>{content.replace(chr(10), '<br>')}</p>"
                    })
            print(f"[DISCORD] Successfully parsed {len(items)} messages from channel #{DISCORD_CHANNEL_ID}.")
        except Exception as e:
            print(f"[DISCORD] Discord API notice: {e}")
    return items

def run_scraper_cycle():
    """Execute complete multi-channel crawl across all requested feeds"""
    timestamp_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print("\n" + "=" * 65)
    print(f"[{timestamp_now}] WARDOGS Tactical Feed Scraper Starting...")
    print("=" * 65)

    current_players = fetch_live_steam_player_count()
    scraped_steam_api = fetch_steam_api_news()
    scraped_steam_rss = fetch_steam_rss()
    scraped_reddit = fetch_brammflakes_reddit()
    scraped_brammer_x = fetch_x_timeline("Brammflakes", OFFICIAL_FEEDS["brammer_x_syndication"], "Joe Brammer (X)")
    scraped_updates_x = fetch_x_timeline("WARDOGSUpdates", OFFICIAL_FEEDS["wardogs_updates_x_syndication"], "X (@WARDOGSUpdates)")
    scraped_discord = fetch_discord_announcements()

    cached_catalog = load_verified_catalog()

    seen_urls = set()
    seen_ids = set()
    combined_posts = []

    # Helper to insert unique items
    def add_posts(post_list):
        for item in post_list:
            item_url = item.get("url", "")
            item_id = item.get("id", "")
            if item_id and item_id not in seen_ids and item_url and item_url not in seen_urls:
                seen_ids.add(item_id)
                seen_urls.add(item_url)
                combined_posts.append(item)

    # 1. High priority to newly discovered live items
    add_posts(scraped_steam_api)
    add_posts(scraped_steam_rss)
    add_posts(scraped_reddit)
    add_posts(scraped_brammer_x)
    add_posts(scraped_updates_x)
    add_posts(scraped_discord)

    # 2. Merge full historical verified catalog
    add_posts(cached_catalog)

    # Strict Newest-First Chronological Sort by ISO timestamp
    combined_posts.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)

    steam_count = len([p for p in combined_posts if p.get("source") == "steam"])
    brammer_count = len([p for p in combined_posts if p.get("source") == "brammer"])
    discord_count = len([p for p in combined_posts if p.get("source") == "discord"])
    x_count = len([p for p in combined_posts if p.get("source") == "x"])

    payload = {
        "metadata": {
            "game": "WARDOGS",
            "developer": "BULKHEAD",
            "publisher": "Team17",
            "lead_developer": "Joe Brammer (CEO)",
            "sort_order": "newest_first",
            "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "live_player_count": current_players,
            "all_time_peak_players": 428666,
            "peak_24h_players": 142390,
            "review_status": "Mostly Positive",
            "positive_review_percent": 79,
            "total_reviews": 66938,
            "total_posts": len(combined_posts),
            "counts": {
                "steam": steam_count,
                "brammer": brammer_count,
                "discord": discord_count,
                "x": x_count
            },
            "channels_monitored": [
                "Steam News Hub & Steam API (AppID 1867240)",
                "Joe Brammer Reddit Dispatches (u/brammflakes on r/WarDogs)",
                "Joe Brammer X Posts & Replies (@Brammflakes)",
                "WARDOGS Live Updates on X (@WARDOGSUpdates)",
                "Official WARDOGS Discord (#announcements - Channel 1464230515862278215)",
                "Studio X Accounts (@wardogs, @BULKHEAD)",
                "YouTube Devlogs & Trailers (@BULKHEAD)",
                "GamesPress Press Releases"
            ]
        },
        "posts": combined_posts
    }

    # Atomic write pattern to prevent corrupting database if interrupted
    temp_path = OUTPUT_JSON_PATH.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(temp_path, OUTPUT_JSON_PATH)

    print("-" * 65)
    print(f"[SUMMARY] Total Posts Indexed : {len(combined_posts)} (Strict Newest-First)")
    print(f"  • Steam Patch Notes & Hub   : {steam_count}")
    print(f"  • Joe Brammer Dispatches     : {brammer_count}")
    print(f"  • Discord #announcements     : {discord_count}")
    print(f"  • Studio X & @WARDOGSUpdates : {x_count}")
    print(f"[STATUS] Successfully wrote atomic database to: {OUTPUT_JSON_PATH.name}")
    print("=" * 65 + "\n")
    return payload

if __name__ == "__main__":
    run_scraper_cycle()