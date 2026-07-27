import os
import json
import requests
import xml.etree.ElementTree as ET

# ====== 設定 ======
# 監視するチャンネルの一覧は config.json に書きます(このファイルは秘密情報を含まないので
# リポジトリにそのままコミットして構いません)。
# Webhook URLは秘密情報なので、GitHub Secretsの WEBHOOKS_JSON に1つのJSON文字列としてまとめて入れます。
#
# WEBHOOKS_JSON の例:
# {
#   "channel_a": {"video": "https://discord.com/api/webhooks/xxxx", "live": "https://discord.com/api/webhooks/yyyy"},
#   "channel_b": {"video": "https://discord.com/api/webhooks/zzzz", "live": "https://discord.com/api/webhooks/wwww"}
# }

YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
WEBHOOKS = json.loads(os.environ["WEBHOOKS_JSON"])

CONFIG_FILE = "config.json"
STATE_FILE = "state.json"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_latest_video_ids(channel_id):
    """RSSフィードから最新の動画ID一覧を取得(通常5〜15件くらい)。APIクォータは消費しません。"""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }
    video_ids = []
    for entry in root.findall("atom:entry", ns):
        vid_el = entry.find("yt:videoId", ns)
        if vid_el is not None:
            video_ids.append(vid_el.text)
    return video_ids


def get_video_status(video_id):
    """YouTube Data APIで動画の状態を取得(1件につき1ユニット消費)
    戻り値: (status, snippet)
    status: "live"(配信中) / "upcoming"(配信予定) / "none"(通常動画)
    """
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet",
        "id": video_id,
        "key": YOUTUBE_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return "none", None
    snippet = items[0]["snippet"]
    status = snippet.get("liveBroadcastContent", "none")  # "live" / "upcoming" / "none"
    return status, snippet


def send_discord_message(content, webhook_url):
    resp = requests.post(webhook_url, json={"content": content}, timeout=10)
    resp.raise_for_status()


def build_video_url(video_id):
    return f"https://www.youtube.com/watch?v={video_id}"


def process_channel(channel_cfg, channel_state):
    """1チャンネル分の処理。APIクォータ節約のため、
    「まだ結果が確定していない動画(新規・配信予定中)」だけをAPIで確認します。
    """
    name = channel_cfg["name"]
    channel_id = channel_cfg["channel_id"]
    webhooks = WEBHOOKS[name]

    known_ids = set(channel_state.get("known_video_ids", []))
    pending_ids = set(channel_state.get("pending_ids", []))  # 配信予定でまだ開始してない動画
    notified_live = set(channel_state.get("notified_live", []))

    for vid in fetch_latest_video_ids(channel_id):
        # 既に結果が確定済み(通常動画として通知済み、または配信開始まで通知済み)ならAPIを呼ばずスキップ
        if vid in known_ids and vid not in pending_ids:
            continue

        status, snippet = get_video_status(vid)
        title = snippet["title"] if snippet else "(タイトル不明)"

        if vid not in known_ids:
            # 初めて見つかった動画・配信
            known_ids.add(vid)
            if status == "upcoming":
                send_discord_message(
                    f"🔴 配信の枠が立ちました!\n**{title}**\n{build_video_url(vid)}",
                    webhooks["live"],
                )
                pending_ids.add(vid)  # 開始したらまた通知するので「保留中」にする
            elif status == "live":
                send_discord_message(
                    f"🔴 ライブ配信が始まりました!\n**{title}**\n{build_video_url(vid)}",
                    webhooks["live"],
                )
                notified_live.add(vid)
            else:
                send_discord_message(
                    f"📹 新しい動画が投稿されました!\n**{title}**\n{build_video_url(vid)}",
                    webhooks["video"],
                )
        else:
            # 保留中(配信予定)の動画 →「配信開始」への変化を確認
            if status == "live" and vid not in notified_live:
                send_discord_message(
                    f"🔴 ライブ配信が始まりました!\n**{title}**\n{build_video_url(vid)}",
                    webhooks["live"],
                )
                notified_live.add(vid)
                pending_ids.discard(vid)
            elif status != "upcoming":
                # 配信が終了しアーカイブ化された等、もう保留する必要がない
                pending_ids.discard(vid)

    return {
        "known_video_ids": list(known_ids),
        "pending_ids": list(pending_ids),
        "notified_live": list(notified_live),
    }


def main():
    config = load_config()
    state = load_state()

    for channel_cfg in config:
        name = channel_cfg["name"]
        channel_state = state.get(name, {})
        try:
            state[name] = process_channel(channel_cfg, channel_state)
        except Exception as e:
            print(f"[{name}] エラーが発生しました: {e}")

    save_state(state)


if __name__ == "__main__":
    main()
