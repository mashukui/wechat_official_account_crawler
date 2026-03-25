# wechat_official_account_crawler
微信公众号文章爬虫

## Project Overview

微信公众号文章爬虫 — scrapes published articles from WeChat Official Accounts via the mp.weixin.qq.com backend API. Single-file Python CLI tool (`wechat_crawler.py`).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Search for an account (get fakeid)
python wechat_crawler.py --cookie "..." --token "..." --search "公众号名称"

# Crawl articles
python wechat_crawler.py --cookie "..." --token "..." --fakeid "..." --max 50

# Crawl with article body content, output as CSV
python wechat_crawler.py --cookie "..." --token "..." --fakeid "..." --content --format csv
```

Credentials can also be passed via environment variables `WX_COOKIE` and `WX_TOKEN`.

## Architecture

All logic lives in `wechat_crawler.py`:

- **`WeChatCrawler`** — core class. Holds a `requests.Session` authenticated with cookie/token.
  - `search_account()` → calls `/cgi-bin/searchbiz` to find accounts by name, returns fakeid
  - `get_articles()` / `get_all_articles()` → calls `/cgi-bin/appmsgpublish` to paginate through published articles (page size 5, 3–8s random delay between pages)
  - `get_article_content()` → fetches article HTML and extracts body text via regex
  - `save_to_json()` / `save_to_csv()` → output serialization
- **`main()`** — CLI entry point with manual arg parsing (no argparse)

## Key API Details

- Article list endpoint returns `publish_list` where each item's `publish_info` is a **JSON string** that must be parsed with `json.loads()`
- Each publish can contain multiple articles (多图文) in `appmsgex` array
- Rate limit error code `200013` triggers a 60-second backoff
- Cookie/token are session-scoped and expire; must be re-obtained from browser

## Conventions

- Python 3.10+ (uses `list[dict]` and `tuple[float, float]` type hints)
- Only dependency: `requests`
- Console output uses bracketed prefixes: `[信息]`, `[错误]`, `[进度]`, `[等待]`, `[保存]`
