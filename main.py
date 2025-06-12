from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import requests
import os
from urllib.parse import quote

app = Flask(__name__)

# LINE channel credentials
LINE_CHANNEL_ACCESS_TOKEN = '6DQX9lE2dr0uLj5i9+9v0Wip0kM4pr5pPnSdYzdSsXh7m7KTl07lacZmXE/AB0Ghwlnm7ZrwtDhpGj1im6BHSKZ2e5ZewKs2/EDElNQlDitj+RcvDtBzWIOETBLW23y1AzzSOPX4GjMEbwu4chby2gdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = '2344e18e0d06043a28bd67be2f0c7ac3'

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

SUPABASE_API_URL = "https://rqzntaosutboujcmnibw.supabase.co/rest/v1/restaurants"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJxem50YW9zdXRib3VqY21uaWJ3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk2NTA0NTAsImV4cCI6MjA2NTIyNjQ1MH0.zLruC4wchcev23dFOATK9YpYHvfDAScYaj-nFV0MvPI"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    query = event.message.text.strip()

    print(query)
    print("🔥 query =", repr(query))

    query_encoded = quote(f"%{query}%")
    full_url = f"{SUPABASE_API_URL}?name=ilike.{query_encoded}"

    print("🔍 full_url =", full_url)

    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Prefer": "return=representation"
    }

    r = requests.get(full_url, headers=headers)
    print("🔥 status code:", r.status_code)
    print("🔥 response:", r.text)

    try:
        results = r.json()
    except Exception as e:
        print("🔥 JSON parse error:", e)
        print("🔥 Raw response:", r.text)
        results = []

    # 安全檢查結果是否為 list 且有東西
    if not isinstance(results, list) or len(results) == 0:
        reply = TextSendMessage(text="找不到符合的店家 😢")
    else:
        restaurant = results[0]
        reply = TextSendMessage(
            text=f"推薦你：{restaurant['name']}（{restaurant['category']}）\n評分：{restaurant['rating']}⭐\n地圖連結：{restaurant['url']}"
        )

    line_bot_api.reply_message(event.reply_token, reply)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
