# YouTube通知Bot セットアップ手順(16チャンネル対応・GitHub Actions版)

## この構成でのポイント

- 16チャンネル分を **1つのワークフロー・1つのスクリプト** でまとめて処理します(チャンネルごとに別ワークフローを作りません)
- 既に通知済みの動画にはAPIを問い合わせないよう最適化しているので、YouTube Data APIの無料枠(1日10,000ユニット)に余裕を持って収まります
- GitHub Actionsの実行時間を無制限にするため、**リポジトリはPublicで作成**することを推奨します
  - config.jsonに書くチャンネルIDは元々公開情報なので問題ありません
  - Webhook URLなどの秘密情報はGitHub Secretsに入れるので、Publicリポジトリでも他人には見えません

## 1. Discord Webhookをチャンネル分作る

各チャンネルごとに「動画通知用」「配信通知用」の2つのWebhookを作成します
(同じチャンネルにまとめたい場合は動画用・配信用に同じURLを使ってOKです)。

1. 各Discordチャンネルの設定(⚙️)→「連携サービス」→「ウェブフックを作成」
2. 名前を決めて「ウェブフックURLをコピー」

## 2. YouTube Data APIキーを取得する

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. 「APIとサービス」→「ライブラリ」から **YouTube Data API v3** を有効化
3. 「認証情報」→「認証情報を作成」→「APIキー」を発行 → これが `YOUTUBE_API_KEY`

## 3. 16チャンネルのIDを調べる

各チャンネルのURLが `https://www.youtube.com/channel/UCxxxx...` の形式ならその `UCxxxx...` の部分。
`@ハンドル名` のURLしかない場合は[チャンネルID確認サイト](https://commentpicker.com/youtube-channel-id.php)などで変換してください。

## 4. GitHubリポジトリを作る(Public推奨)

1. [GitHub](https://github.com/) でアカウント作成
2. 「New repository」で作成する際、**Public** を選択(Actionsの実行時間が無制限になります)
3. 添付ファイルを以下の構成でアップロード
   ```
   main.py
   requirements.txt
   config.json
   .github/workflows/check.yml
   ```

## 5. config.json を編集する

添付した `config.json` のサンプルを、実際のチャンネル分に書き換えます。
`name` は好きな名前(半角英数字推奨、後でWebhook設定と紐付けに使います)、`channel_id` は手順3で調べたIDです。

```json
[
  { "name": "channel_01", "channel_id": "UCxxxxxxxxxxxxxxxxxxxxxx" },
  { "name": "channel_02", "channel_id": "UCyyyyyyyyyyyyyyyyyyyyyy" },
  ...
  { "name": "channel_16", "channel_id": "UCzzzzzzzzzzzzzzzzzzzzzz" }
]
```

## 6. Secretsを設定する

リポジトリの「Settings」→「Secrets and variables」→「Actions」→「New repository secret」

- `YOUTUBE_API_KEY` → 手順2で取得したキー
- `WEBHOOKS_JSON` → チャンネル分のWebhookをまとめた1つのJSON文字列(下記の形式で、config.jsonの`name`と対応させます)

```json
{
  "channel_01": { "video": "https://discord.com/api/webhooks/xxxx", "live": "https://discord.com/api/webhooks/yyyy" },
  "channel_02": { "video": "https://discord.com/api/webhooks/zzzz", "live": "https://discord.com/api/webhooks/wwww" },
  ...
  "channel_16": { "video": "https://discord.com/api/webhooks/aaaa", "live": "https://discord.com/api/webhooks/bbbb" }
}
```

※ 改行や余分なスペースがあっても問題ありません(JSONとして正しければOK)。VS Codeやメモ帳で組み立ててから貼り付けると間違いにくいです。

## 7. 動作確認

1. リポジトリの「Actions」タブ →「YouTube to Discord Notifier」→「Run workflow」で手動実行
2. 緑のチェックが付けば成功(初回は既存動画がまとめて通知されるので注意)
3. 以降は5分おきに自動実行されます

## クォータ・実行時間の見積もり

- **YouTube APIクォータ**: 通知済みの動画は二度と問い合わせないので、実際に消費するのは「新しく投稿された動画」と「配信予定でまだ結果待ちの動画」だけです。16チャンネルでも通常は1日あたり数百ユニット程度で収まり、1日10,000ユニットの上限には十分余裕があります
- **GitHub Actions実行時間**: Publicリポジトリなら無制限なので気にする必要はありません。Privateリポジトリのまま使う場合は無料枠が月2,000分なので、チャンネル数が多いなら `check.yml` の `cron` を5分おきから10〜15分おきに変更することを検討してください

## 注意点

- RSSフィードへの反映には数分のタイムラグがあることがあります
- チャンネルが増えるほど1回の実行時間が延びます。あまりに時間がかかる場合はチェック間隔を延ばすか、チャンネルを複数のワークフローに分割することも可能です(その場合は各ワークフローで`config.json`を分ける形になります)
- `state.json` はリポジトリに自動コミットされます。誤って手動編集すると通知の重複や欠落が起きるので触らないでください
