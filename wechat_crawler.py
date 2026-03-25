"""
微信公众号文章爬虫

使用方式：
1. 登录微信公众号后台 https://mp.weixin.qq.com
2. 打开浏览器开发者工具(F12)，找到任意请求，复制 Cookie
3. 在「素材管理 -> 新建图文 -> 超链接 -> 查找文章」中搜索目标公众号
   观察网络请求，获取 token（URL 参数中的 token）和 fakeid（目标公众号的 fakeid）
4. 将 Cookie、token、fakeid 填入配置文件或命令行参数

原创作者: @马哥python说
"""

import json
import os
import random
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlencode

import requests


class WeChatCrawler:
    """微信公众号文章爬虫"""

    BASE_URL = "https://mp.weixin.qq.com/cgi-bin"

    # 默认请求头
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://mp.weixin.qq.com/",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }

    def __init__(self, cookie: str, token: str):
        """
        初始化爬虫

        Args:
            cookie: 登录微信公众号后台后的 Cookie
            token:  URL 中的 token 参数
        """
        self.cookie = cookie
        self.token = token
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.session.headers["Cookie"] = cookie

    # ------------------------------------------------------------------
    # 搜索公众号，获取 fakeid
    # ------------------------------------------------------------------
    def search_account(self, account_name: str) -> list[dict]:
        """
        搜索公众号，返回匹配的公众号列表

        Args:
            account_name: 公众号名称

        Returns:
            公众号信息列表，包含 fakeid、nickname 等
        """
        url = f"{self.BASE_URL}/searchbiz"
        params = {
            "action": "search_biz",
            "begin": 0,
            "count": 5,
            "query": account_name,
            "token": self.token,
            "lang": "zh_CN",
            "f": "json",
            "ajax": 1,
        }
        resp = self.session.get(url, params=params)
        data = resp.json()

        if data.get("base_resp", {}).get("ret") != 0:
            print(f"[错误] 搜索失败: {data.get('base_resp', {}).get('err_msg', '未知错误')}")
            return []

        accounts = data.get("list", [])
        print(f"[信息] 搜索到 {len(accounts)} 个公众号:")
        for i, acc in enumerate(accounts):
            print(f"  {i + 1}. {acc['nickname']} (fakeid: {acc['fakeid']})")
        return accounts

    # ------------------------------------------------------------------
    # 获取文章列表
    # ------------------------------------------------------------------
    def get_articles(
        self,
        fakeid: str,
        count: int = 5,
        begin: int = 0,
    ) -> dict:
        """
        获取指定公众号的文章列表（单页）

        Args:
            fakeid: 目标公众号的 fakeid
            count:  每页数量（最大 5）
            begin:  偏移量

        Returns:
            包含 app_msg_list 和 app_msg_cnt 的字典
        """
        url = f"{self.BASE_URL}/appmsgpublish"
        params = {
            "sub": "list",
            "search_field": None,
            "begin": begin,
            "count": count,
            "query": "",
            "fakeid": fakeid,
            "type": 101,
            "free_publish_type": 1,
            "sub_action": "list_ex",
            "token": self.token,
            "lang": "zh_CN",
            "f": "json",
            "ajax": 1,
        }
        resp = self.session.get(url, params=params)
        return resp.json()

    def get_all_articles(
        self,
        fakeid: str,
        max_count: int = 0,
        delay_range: tuple[float, float] = (3.0, 8.0),
    ) -> list[dict]:
        """
        获取指定公众号的全部文章

        Args:
            fakeid:      目标公众号的 fakeid
            max_count:   最多采集多少篇（0 表示全部）
            delay_range: 每次请求之间的随机延迟范围（秒）

        Returns:
            文章信息列表
        """
        all_articles = []
        begin = 0
        page_size = 5

        print(f"\n[信息] 开始采集文章，fakeid={fakeid}")

        while True:
            data = self.get_articles(fakeid, count=page_size, begin=begin)
            base_resp = data.get("base_resp", {})

            if base_resp.get("ret") != 0:
                err_msg = base_resp.get("err_msg", "未知错误")
                print(f"[错误] 请求失败 (begin={begin}): {err_msg}")
                # ret=200013 通常表示频率限制
                if base_resp.get("ret") == 200013:
                    print("[警告] 请求频率过高，等待 60 秒后重试...")
                    time.sleep(60)
                    continue
                break

            total = data.get("publish_page", {}).get("total_count", 0)
            publish_list = data.get("publish_page", {}).get("publish_list", [])

            if not publish_list:
                print("[信息] 没有更多文章了")
                break

            for item in publish_list:
                publish_info = json.loads(item.get("publish_info", "{}"))
                publish_time = publish_info.get("publish_time", 0)

                # 每次推送可能包含多篇文章（多图文）
                appmsgex = publish_info.get("appmsgex", [])
                for article in appmsgex:
                    article_data = {
                        "title": article.get("title", ""),
                        "digest": article.get("digest", ""),
                        "link": article.get("link", ""),
                        "cover": article.get("cover", ""),
                        "publish_time": publish_time,
                        "publish_date": (
                            datetime.fromtimestamp(publish_time).strftime("%Y-%m-%d %H:%M:%S")
                            if publish_time
                            else ""
                        ),
                        "aid": article.get("aid", ""),
                        "appmsgid": article.get("appmsgid", ""),
                        "itemidx": article.get("itemidx", 0),
                    }
                    all_articles.append(article_data)

            collected = len(all_articles)
            print(f"[进度] 已采集 {collected}/{total} 篇文章")

            if max_count and collected >= max_count:
                all_articles = all_articles[:max_count]
                print(f"[信息] 达到最大采集数 {max_count}，停止采集")
                break

            begin += page_size
            if begin >= total:
                print("[信息] 全部文章采集完成")
                break

            # 随机延迟，避免被封
            delay = random.uniform(*delay_range)
            print(f"[等待] {delay:.1f} 秒...")
            time.sleep(delay)

        return all_articles

    # ------------------------------------------------------------------
    # 获取文章正文
    # ------------------------------------------------------------------
    @staticmethod
    def get_article_content(url: str) -> dict:
        """
        获取文章正文内容（HTML）

        Args:
            url: 文章链接

        Returns:
            包含 html、content_text 的字典
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        resp = requests.get(url, headers=headers, timeout=15)
        html = resp.text

        # 提取正文区域
        content_match = re.search(
            r'<div class="rich_media_content[^"]*"[^>]*>(.*?)</div>\s*<!---->',
            html,
            re.DOTALL,
        )
        content_html = content_match.group(1).strip() if content_match else ""

        # 提取纯文本（去除 HTML 标签）
        content_text = re.sub(r"<[^>]+>", "", content_html).strip()
        content_text = re.sub(r"\s+", " ", content_text)

        return {
            "html": content_html,
            "text": content_text,
        }

    # ------------------------------------------------------------------
    # 保存结果
    # ------------------------------------------------------------------
    @staticmethod
    def save_to_json(articles: list[dict], filepath: str):
        """保存文章列表为 JSON 文件"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        print(f"[保存] 已保存 {len(articles)} 篇文章到 {filepath}")

    @staticmethod
    def save_to_csv(articles: list[dict], filepath: str):
        """保存文章列表为 CSV 文件"""
        import csv

        if not articles:
            print("[警告] 没有文章数据可保存")
            return

        fieldnames = ["title", "digest", "link", "publish_date", "aid"]
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(articles)
        print(f"[保存] 已保存 {len(articles)} 篇文章到 {filepath}")


# ======================================================================
# 命令行入口
# ======================================================================
def print_usage():
    print(
        """
用法:
  python wechat_crawler.py --cookie <COOKIE> --token <TOKEN> --fakeid <FAKEID> [选项]
  python wechat_crawler.py --cookie <COOKIE> --token <TOKEN> --search <公众号名称>

选项:
  --cookie    登录微信公众号后台后的 Cookie（必填）
  --token     URL 中的 token 参数（必填）
  --fakeid    目标公众号的 fakeid
  --search    搜索公众号名称（获取 fakeid）
  --max       最大采集文章数，0 表示全部（默认 0）
  --output    输出文件路径（默认 articles.json）
  --format    输出格式 json / csv（默认 json）
  --content   是否采集正文内容（加上此参数表示是）

示例:
  # 1. 先搜索公众号获取 fakeid
  python wechat_crawler.py --cookie "your_cookie" --token "123456" --search "人民日报"

  # 2. 用 fakeid 采集文章
  python wechat_crawler.py --cookie "your_cookie" --token "123456" --fakeid "MzA1..." --max 50

获取 Cookie 和 Token 的方法:
  1. 浏览器登录 https://mp.weixin.qq.com
  2. 按 F12 打开开发者工具 → Network 面板
  3. 在后台操作（如点击「素材管理」），观察请求
  4. 从请求头中复制 Cookie
  5. 从请求 URL 中找到 token=xxx 参数
  6. 在「新建图文 → 超链接 → 查找文章」中搜索目标公众号
     从请求结果中获取目标公众号的 fakeid
"""
    )


def parse_args(argv: list[str]) -> dict:
    args = {}
    i = 0
    while i < len(argv):
        if argv[i] == "--cookie" and i + 1 < len(argv):
            args["cookie"] = argv[i + 1]
            i += 2
        elif argv[i] == "--token" and i + 1 < len(argv):
            args["token"] = argv[i + 1]
            i += 2
        elif argv[i] == "--fakeid" and i + 1 < len(argv):
            args["fakeid"] = argv[i + 1]
            i += 2
        elif argv[i] == "--search" and i + 1 < len(argv):
            args["search"] = argv[i + 1]
            i += 2
        elif argv[i] == "--max" and i + 1 < len(argv):
            args["max"] = int(argv[i + 1])
            i += 2
        elif argv[i] == "--output" and i + 1 < len(argv):
            args["output"] = argv[i + 1]
            i += 2
        elif argv[i] == "--format" and i + 1 < len(argv):
            args["format"] = argv[i + 1]
            i += 2
        elif argv[i] == "--content":
            args["content"] = True
            i += 1
        elif argv[i] in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        else:
            i += 1
    return args


def main():
    args = parse_args(sys.argv[1:])

    cookie = args.get("cookie") or os.environ.get("WX_COOKIE", "")
    token = args.get("token") or os.environ.get("WX_TOKEN", "")

    if not cookie or not token:
        print("[错误] 必须提供 --cookie 和 --token 参数（或设置环境变量 WX_COOKIE / WX_TOKEN）")
        print_usage()
        sys.exit(1)

    crawler = WeChatCrawler(cookie, token)

    # 搜索模式
    if "search" in args:
        accounts = crawler.search_account(args["search"])
        if not accounts:
            sys.exit(1)
        # 如果未指定 fakeid，只显示搜索结果
        if "fakeid" not in args:
            print("\n[提示] 请使用上面的 fakeid 进行文章采集")
            sys.exit(0)

    fakeid = args.get("fakeid", "")
    if not fakeid:
        print("[错误] 必须提供 --fakeid 参数（或先用 --search 搜索获取）")
        sys.exit(1)

    max_count = args.get("max", 0)
    output_format = args.get("format", "json")
    output_file = args.get("output", f"articles.{output_format}")
    fetch_content = args.get("content", False)

    # 采集文章列表
    articles = crawler.get_all_articles(fakeid, max_count=max_count)

    if not articles:
        print("[信息] 未采集到任何文章")
        sys.exit(0)

    # 可选：采集文章正文
    if fetch_content:
        print(f"\n[信息] 开始采集文章正文（共 {len(articles)} 篇）...")
        for i, article in enumerate(articles):
            try:
                content = crawler.get_article_content(article["link"])
                article["content_text"] = content["text"]
                print(f"[正文] ({i + 1}/{len(articles)}) {article['title'][:30]}")
            except Exception as e:
                article["content_text"] = ""
                print(f"[错误] ({i + 1}/{len(articles)}) 获取正文失败: {e}")
            time.sleep(random.uniform(1.0, 3.0))

    # 保存结果
    if output_format == "csv":
        crawler.save_to_csv(articles, output_file)
    else:
        crawler.save_to_json(articles, output_file)

    print(f"\n[完成] 共采集 {len(articles)} 篇文章")


if __name__ == "__main__":
    main()
