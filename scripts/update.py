#!/usr/bin/env python3
"""ベリンガム ニュース自動収集スクリプト

Google ニュースのRSS（日本語・英語）から Jude Bellingham 関連の記事を集め、
data/news.json に貯めて、docs/index.html（スマホで見るページ）を作り直す。

使い方:
    python scripts/update.py           # 実際にニュースを取ってくる（GitHub上で毎日自動実行）
    python scripts/update.py --sample  # サンプルデータで見た目だけ確認する

外部ライブラリは使わない（Python標準機能だけで動く）。
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "news.json"
TEMPLATE_FILE = ROOT / "scripts" / "template.html"
OUTPUT_FILE = ROOT / "docs" / "index.html"

JST = timezone(timedelta(hours=9))

# 何日分の記事を残すか / 最大件数
KEEP_DAYS = 30
MAX_ITEMS = 400


def google_news_rss(query: str, hl: str, gl: str, ceid: str) -> str:
    q = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


# 集めるニュースの入り口。言語を足したいときはここに1行追加する。
FEEDS = [
    {"lang": "ja", "url": google_news_rss("ベリンガム when:7d", "ja", "JP", "JP:ja")},
    {"lang": "en", "url": google_news_rss('"Jude Bellingham" when:7d', "en-GB", "GB", "GB:en")},
]

# 見出しにこの言葉が入っている記事だけ残す
MUST_MATCH = re.compile(r"bellingham|ベリンガム|ベリンガム", re.IGNORECASE)
# 弟のジョーブだけの記事は外す（ジュードの名前も出ていれば残す）
JOBE_ONLY = re.compile(r"jobe|ジョーブ", re.IGNORECASE)
JUDE = re.compile(r"jude|ジュード", re.IGNORECASE)

# 載せたくない媒体（機械翻訳サイトやスパム的なまとめサイトなど）。見つけたらここに足す
BLOCK_SOURCES = {
    "Vietnam.vn",
    "Unisba Media",
}
# 見出しの末尾に「(M2J3bnl8Uh)」のような謎の記号が付いているのはスパムサイトの特徴
SPAM_TITLE = re.compile(r"\([A-Za-z0-9]{8,}\)\s*$")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bellingham-news bot)"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


def clean_title(title: str, source: str) -> str:
    title = html.unescape(title).strip()
    # Google ニュースは「見出し - 媒体名」の形なので末尾の媒体名を外す
    if source and title.endswith(f" - {source}"):
        title = title[: -len(f" - {source}")].strip()
    return title


def is_relevant(title: str) -> bool:
    if not MUST_MATCH.search(title):
        return False
    if JOBE_ONLY.search(title) and not JUDE.search(title):
        return False
    return True


def parse_feed(xml_bytes: bytes, lang: str) -> list[dict]:
    items = []
    root = ET.fromstring(xml_bytes)
    for it in root.iter("item"):
        source_el = it.find("source")
        source = (source_el.text or "").strip() if source_el is not None else ""
        title = clean_title(it.findtext("title", ""), source)
        link = (it.findtext("link", "") or "").strip()
        pub = it.findtext("pubDate", "")
        if not title or not link or not is_relevant(title):
            continue
        if source in BLOCK_SOURCES or SPAM_TITLE.search(title):
            continue
        try:
            published = parsedate_to_datetime(pub).astimezone(timezone.utc)
        except Exception:
            published = datetime.now(timezone.utc)
        items.append(
            {
                "title": title,
                "link": link,
                "source": source,
                "lang": lang,
                "published": published.isoformat(),
            }
        )
    return items


def title_key(title: str) -> str:
    # Yahoo!ニュースは見出しの最後に「（サッカーキング）」のように元媒体名が付くので外して比べる
    title = re.sub(r"\s*[（(][^（）()]{1,30}[）)]\s*$", "", title)
    return re.sub(r"[\W_]+", "", title.lower())


def merge(old: list[dict], new: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for item in old + new:
        key = title_key(item["title"])
        if not key:
            continue
        if key not in seen:
            seen[key] = item
        elif seen[key]["source"].startswith("Yahoo") and not item["source"].startswith("Yahoo"):
            seen[key] = item  # 同じ記事なら元の媒体のほうを残す
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    kept = [i for i in seen.values() if datetime.fromisoformat(i["published"]) >= cutoff]
    kept.sort(key=lambda i: i["published"], reverse=True)
    return kept[:MAX_ITEMS]


def load_data() -> list[dict]:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8")).get("items", [])
    return []


def save_data(items: list[dict], updated: datetime) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated": updated.isoformat(), "items": items}
    DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def render(items: list[dict], updated: datetime) -> None:
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    payload = json.dumps({"updated": updated.isoformat(), "items": items}, ensure_ascii=False)
    payload = payload.replace("</", "<\\/")  # scriptタグの中に安全に埋め込むため
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(template.replace("__NEWS_DATA__", payload), encoding="utf-8")


def sample_items() -> list[dict]:
    """見た目確認用のダミー記事（実在のニュースではない）"""
    now = datetime.now(timezone.utc)
    rows = [
        ("ja", 1, "サンプル記事：ベリンガム、週末のリーグ戦で先発予想", "サンプル通信"),
        ("en", 2, "Sample headline: Jude Bellingham trains with the squad ahead of the weekend", "Sample Sports"),
        ("ja", 5, "サンプル記事：ベリンガムが語った新シーズンへの意気込み", "サンプルスポーツ"),
        ("en", 20, "Sample headline: Bellingham's role in midfield analysed", "Sample Football Weekly"),
        ("ja", 27, "サンプル記事：ベリンガム、代表合流へ", "サンプル新聞"),
        ("en", 30, "Sample headline: Five takeaways from Bellingham's latest match", "Sample Daily"),
        ("en", 50, "Sample headline: Bellingham named in team of the week", "Sample Sport"),
        ("ja", 74, "サンプル記事：ベリンガムの今季スタッツをチェック", "サンプルWEB"),
    ]
    return [
        {
            "title": t,
            "link": "https://example.com/",
            "source": s,
            "lang": lang,
            "published": (now - timedelta(hours=h)).isoformat(),
        }
        for lang, h, t, s in rows
    ]


def main() -> int:
    now = datetime.now(timezone.utc)

    if "--sample" in sys.argv:
        render(sample_items(), now)
        print(f"サンプルでページを作成: {OUTPUT_FILE}")
        return 0

    new_items: list[dict] = []
    errors = 0
    for feed in FEEDS:
        try:
            got = parse_feed(fetch(feed["url"]), feed["lang"])
            print(f"[{feed['lang']}] {len(got)} 件")
            new_items += got
        except Exception as e:  # 1つ失敗しても他は続ける
            errors += 1
            print(f"[{feed['lang']}] 取得失敗: {e}", file=sys.stderr)

    if errors == len(FEEDS):
        print("すべての取得に失敗したので、今回は更新しません", file=sys.stderr)
        return 1

    items = merge(load_data(), new_items)
    save_data(items, now)
    render(items, now)
    print(f"合計 {len(items)} 件でページを更新しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
