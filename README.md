# Bellingham Daily

ジュード・ベリンガムのニュースを毎日自動で集めて、スマホで見られるページにする仕組み。

- 収集元：Google ニュースのRSS（日本語・英語）
- 更新：毎日 6:07 と 18:07（日本時間）に GitHub Actions が自動実行
- 公開：GitHub Pages（`docs/` フォルダ）
- 費用：無料（公開リポジトリなら GitHub Actions・Pages とも無料）

## しくみ

| ファイル | 役割 |
|---|---|
| `scripts/update.py` | ニュースを取ってきて、重複を除いて保存し、ページを作り直す |
| `scripts/template.html` | ページの見た目（デザイン） |
| `data/news.json` | これまで集めた記事（30日分・最大400件） |
| `docs/index.html` | 公開されるページ（自動で作られるので直接いじらない） |
| `.github/workflows/update.yml` | 毎日の自動実行の設定 |

## はじめの設定（1回だけ）

1. このフォルダの中身を GitHub の新しいリポジトリ（Public）にアップロードする
2. リポジトリの **Settings → Pages** で、Source を「Deploy from a branch」、Branch を `main` / フォルダを `/docs` にして保存
3. **Actions** タブを開き、「ニュース更新」→「Run workflow」で1回目を手動実行
4. 数分後、Settings → Pages に表示されるURLを開くと完成。スマホのホーム画面に追加しておくとアプリのように使える

## カスタマイズの例

- 言語を増やす：`scripts/update.py` の `FEEDS` に1行足す（例：スペイン語メディア）
- 更新時刻を変える：`.github/workflows/update.yml` の `cron`
- 見た目を変える：`scripts/template.html`

手元で見た目だけ確認したいとき：

```
python scripts/update.py --sample
```
