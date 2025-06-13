from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
from linebot.models.events import PostbackEvent
import requests
import os
from urllib.parse import quote
import random
from urllib.parse import quote

app = Flask(__name__)

# LINE channel credentials
LINE_CHANNEL_ACCESS_TOKEN = '6DQX9lE2dr0uLj5i9+9v0Wip0kM4pr5pPnSdYzdSsXh7m7KTl07lacZmXE/AB0Ghwlnm7ZrwtDhpGj1im6BHSKZ2e5ZewKs2/EDElNQlDitj+RcvDtBzWIOETBLW23y1AzzSOPX4GjMEbwu4chby2gdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = '2344e18e0d06043a28bd67be2f0c7ac3'

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

SUPABASE_API_URL = "https://rqzntaosutboujcmnibw.supabase.co/rest/v1/restaurants"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJxem50YW9zdXRib3VqY21uaWJ3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk2NTA0NTAsImV4cCI6MjA2NTIyNjQ1MH0.zLruC4wchcev23dFOATK9YpYHvfDAScYaj-nFV0MvPI"


#暫存使用者查詢狀態
user_sessions = {}  # {user_id: {categories: [...], price: ..., rating: ...}}


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
    user_id = event.source.user_id
    query = event.message.text.strip()

    print(query)
    print("🔥 query =", repr(query))

    
    if query.startswith("抽 "):
        categories = query[2:].strip().split()
        user_sessions[user_id] = {"categories": categories, "price": None, "rating": None}
        line_bot_api.reply_message(event.reply_token, get_price_flex())
        return

    if query == "抽":
        user_sessions[user_id] = {"categories": [], "price": None, "rating": None}
        check_and_recommend(user_id, event.reply_token)
        return

    print("在MessageEvent沒做任何動作")
    # query_encoded = quote(f"%{query}%")
    # full_url = f"{SUPABASE_API_URL}?name=ilike.{query_encoded}"

    # print("🔍 full_url =", full_url)

    # headers = {
    #     "apikey": SUPABASE_ANON_KEY,
    #     "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    #     "Prefer": "return=representation"
    # }

    # r = requests.get(full_url, headers=headers)
    # print("🔥 status code:", r.status_code)
    # print("🔥 response:", r.text)

    # try:
    #     results = r.json()
    # except Exception as e:
    #     print("🔥 JSON parse error:", e)
    #     print("🔥 Raw response:", r.text)
    #     results = []

    # # 安全檢查結果是否為 list 且有東西
    # if not isinstance(results, list) or len(results) == 0:
    #     reply = TextSendMessage(text="找不到符合的店家 😢")
    # else:
    #     restaurant = results[0]
    #     reply = FlexSendMessage(
    #         alt_text="推薦餐廳",
    #         contents={
    #             "type": "bubble",
    #             "body": {
    #                 "type": "box",
    #                 "layout": "vertical",
    #                 "spacing": "sm",
    #                 "contents": [
    #                     {
    #                         "type": "text",
    #                         "text": f"🍽 推薦你：{restaurant['name']}（{restaurant['category']}）",
    #                         "wrap": True,
    #                         "weight": "bold",
    #                         "size": "md"
    #                     },
    #                     {
    #                         "type": "text",
    #                         "text": f"⭐ 評分：{restaurant['rating']}",
    #                         "wrap": True,
    #                         "size": "sm"
    #                     },
    #                     {
    #                         "type": "text",
    #                         "text": f"💰 價格：{restaurant['price']}",
    #                         "wrap": True,
    #                         "size": "sm"
    #                     }
    #                 ]
    #             },
    #             "footer": {
    #                 "type": "box",
    #                 "layout": "vertical",
    #                 "spacing": "sm",
    #                 "contents": [
    #                     {
    #                         "type": "button",
    #                         "style": "link",
    #                         "height": "sm",
    #                         "action": {
    #                             "type": "uri",
    #                             "label": "👉 點我看地圖",
    #                             "uri": restaurant["url"]
    #                         }
    #                     }
    #                 ],
    #                 "flex": 0
    #             }
    #         }
    #     )

    # line_bot_api.reply_message(event.reply_token, reply)


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
  
    
    if data.startswith("價格"):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你選擇了：" + data))
        if user_id in user_sessions:
            user_sessions[user_id]["price"] = data.replace("價格", "")
            line_bot_api.reply_message(event.reply_token, get_rating_flex())
        return

    if data.startswith("評分"):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你選擇了：" + data))
        if user_id in user_sessions:
            user_sessions[user_id]["rating"] = data.replace("評分", "")
            check_and_recommend(user_id, event.reply_token)
        return



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


def check_and_recommend(user_id, reply_token):
    session = user_sessions.get(user_id)
    if not session or not session.get("categories"):
        line_bot_api.reply_message(reply_token, TextSendMessage(text="請先輸入：抽 類別1 類別2...，來進行有條件的抽餐廳"))
        return

    filters = {
        "categories": session["categories"],
        "price_cond": None if session["price"] in [None, "不限"] else session["price"],
        "rating_cond": None if session["rating"] in [None, "不限"] else session["rating"]
    }

    url = build_supabase_url(filters)
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Prefer": "return=representation"
    }
    r = requests.get(url, headers=headers)
    try:
        results = r.json()
    except:
        results = []

    if not isinstance(results, list) or not results:
        line_bot_api.reply_message(reply_token, TextSendMessage(text="找不到符合條件的餐廳 😢"))
        return

    restaurant = random.choice(results)
    flex = build_recommendation_flex(restaurant)
    line_bot_api.reply_message(reply_token, flex)

def build_supabase_url(filters):
    conditions = []
    if filters["categories"]:
        category_conds = [f"category=eq.{quote(c)}" for c in filters["categories"]]
        conditions.append("or=(" + ",".join(category_conds) + ")")
    if filters["rating_cond"]:
        conditions.append(f"rating={filters['rating_cond']}")
    if filters["price_cond"]:
        conditions.append(f"price_range={filters['price_cond']}")
    if not conditions:
        return SUPABASE_API_URL
    return f"{SUPABASE_API_URL}?and=(" + ",".join(conditions) + ")"

def build_recommendation_flex(r):
    return FlexSendMessage(
        alt_text="推薦餐廳",
        contents={
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": f"🍽 {r['name']}（{r['category']}）", "weight": "bold", "size": "md", "wrap": True},
                    {"type": "text", "text": f"⭐ 評分：{r.get('rating', '無')}", "size": "sm", "wrap": True},
                    {"type": "text", "text": f"💰 價格：{r.get('price', '未提供')}", "size": "sm", "wrap": True}
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "link",
                        "action": {
                            "type": "uri",
                            "label": "👉 點我看地圖",
                            "uri": r["map_url"]
                        }
                    }
                ]
            }
        }
    )



def get_price_flex():
    return FlexSendMessage(
        alt_text="選擇價格",
        contents={
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "請選擇價格區間 💰", "weight": "bold", "size": "md"}
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                    {"type": "button", "style": "primary", "action": {"type": "postback", "label": "$100~200", "data": "價格$100~200"}},
                    {"type": "button", "style": "primary", "action": {"type": "postback", "label": "$200~400", "data": "價格$200~400"}},
                    {"type": "button", "style": "primary", "action": {"type": "postback", "label": "$400~600", "data": "價格$400~600"}},
                    {"type": "button", "style": "primary", "action": {"type": "postback", "label": "$600~800", "data": "價格$600~800"}},
                    {"type": "button", "style": "secondary", "action": {"type": "postback", "label": "$800~1000", "data": "價格$800~1000"}},
                    {"type": "button", "style": "secondary", "action": {"type": "postback", "label": "大於$1000", "data": "價格$>1000"}},
                    {"type": "button", "style": "primary", "action": {"type": "postback", "label": "不限價格", "data": "價格不限"}}
                ]
            }
        }
    )

def get_rating_flex():
    return FlexSendMessage(
        alt_text="選擇評分",
        contents={
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "請選擇最低評分 ⭐", "weight": "bold", "size": "md"}
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                    {"type": "button", "style": "primary", "action": {"type": "postback", "label": "⭐ 1.0↑", "data": "評分1.0"}},
                    {"type": "button", "style": "primary", "action": {"type": "postback", "label": "⭐ 2.0↑", "data": "評分2.0"}},
                    {"type": "button", "style": "primary", "action": {"type": "postback", "label": "⭐ 3.0↑", "data": "評分3.0"}},
                    {"type": "button", "style": "primary", "action": {"type": "postback", "label": "⭐ 4.0↑", "data": "評分4.0"}},
                    {"type": "button", "style": "secondary", "action": {"type": "postback", "label": "不限評分", "data": "評分不限"}}
                ]
            }
        }
    )





