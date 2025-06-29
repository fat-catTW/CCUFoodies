from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, LocationMessage, CarouselContainer, BubbleContainer, TextComponent, BoxComponent, ButtonComponent, URIAction, ImageComponent
from linebot.models.events import PostbackEvent
import requests
import os
from urllib.parse import quote
import random
from supabase import create_client, Client
import json
import openai
from openai import OpenAI


app = Flask(__name__)

# LINE channel credentials
LINE_CHANNEL_ACCESS_TOKEN = '6DQX9lE2dr0uLj5i9+9v0Wip0kM4pr5pPnSdYzdSsXh7m7KTl07lacZmXE/AB0Ghwlnm7ZrwtDhpGj1im6BHSKZ2e5ZewKs2/EDElNQlDitj+RcvDtBzWIOETBLW23y1AzzSOPX4GjMEbwu4chby2gdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = '2344e18e0d06043a28bd67be2f0c7ac3'

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

SUPABASE_API_RESTAURANTSTABLE_URL = "https://rqzntaosutboujcmnibw.supabase.co/rest/v1/restaurants"
SUPABASE_API_BASIC_URL = "https://rqzntaosutboujcmnibw.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJxem50YW9zdXRib3VqY21uaWJ3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk2NTA0NTAsImV4cCI6MjA2NTIyNjQ1MH0.zLruC4wchcev23dFOATK9YpYHvfDAScYaj-nFV0MvPI"
supabase: Client = create_client(SUPABASE_API_BASIC_URL, SUPABASE_ANON_KEY)

client = OpenAI(api_key=os.environ["CHATGPT_API_KEY"])

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
    
    elif query == "抽":
        user_sessions[user_id] = {"categories": [], "price": None, "rating": None}
        check_and_recommend(user_id, event.reply_token)
        return
    
    elif query == "使用說明":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=""" 
圖文選單使用說明:📄
-------------------------------------------
良言獻策:🪄
向 美食底嘉 提出改善、優化的建議。
                
指北針:🧭
不知道要吃啥嗎? 隨機抽一家店吧!

使用說明:📚
查看 美食底嘉 如何使用

回報錯誤:🚨
如果有遇到Bug、店家資訊有誤等等 按此來進行回報。

美食地圖:🗺️
獲取近 300 家店的嘉義美食地點

回報新店:🔍
發現新店了嗎? 快和大家分享!!
            """)
            )
    else:
        print(f"User ask: {query}")

        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
            encoding_format="float"
        )
        
        user_vector = response.data[0].embedding
        

        response = supabase.rpc("match_restaurants_vector", {
            "query_embedding": user_vector,
            "threshold": 0.75
        }).execute()

        results = response.data# 回傳的是最多五筆、且 similarity > 0.75 的資料

        print(results)

        RAGData = ""

        if results:
            RAGData = "參考資料:"
            RAGData += "\n".join(
                f"{r['name']}，{r['category']}，評分{r['rating']}，價格{r['price']}"
                for r in results
            )

        print(f"RAG:{RAGData}")

        response = client.responses.create(
            model="gpt-4.1-nano-2025-04-14",
            instructions=f"""你是一個嘉義的美食專家，專門幫助中正的學生們尋找嘉義的美味。
    根據使用者的需求，回答他們的問題。
    你和使用者之間的對話只能和嘉義美食相關。 如果使用者問了一個和美食不相關的問題˙，那就跟他說: 抱歉 我只知道和嘉義美食相關的問題，你的問題我沒辦法回答。 
    {RAGData}
    """,
            input=query,
        )

        print(response.output_text)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=response.output_text))

    print("在MessageEvent沒做任何動作")

@handler.add(MessageEvent, message=LocationMessage)
def handle_location(event):
    lat = event.message.latitude
    lng = event.message.longitude
    print(f"lat: {lat}  lng:{lng}")

    data = [] # 初始化 data
    response_content = None # 用於儲存原始響應內容

    try:
        # 執行 RPC 呼叫
        response = supabase.rpc("nearby_restaurants_json", {"lat": lat, "lng": lng}).execute()

        # 打印原始響應對象和數據
        print("Raw RPC response object:", response)
        print("Raw RPC data:", response.data)

        # 檢查 response.data，確保它是列表且不是 None
        if response.data is not None and isinstance(response.data, list):
            data = response.data[:10]  # 只取前 10 筆
        else:
            print("RPC returned None or non-list data:", response.data)
            data = []

    # 捕獲更具體的 PostgREST APIError
    # 這是你收到的錯誤類型
    except Exception as e: # 如果不行，可以先用通用的 Exception 捕獲所有錯誤
        print(f"解析 RPC 回傳資料時出錯: {e}")
        # 如果捕獲到錯誤，嘗試訪問 response 對象的 content 屬性
        # 注意: response 對象可能在錯誤發生時未被完全賦值或不同步
        if isinstance(e, Client) and hasattr(e, 'response') and hasattr(e.response, 'content'):
            response_content = e.response.content.decode('utf-8')
            print(f"原始錯誤響應內容: {response_content}")
        else:
            print(f"無法從錯誤對象獲取原始響應內容: {e}")
        data = []

    if not data:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="附近 500 公尺內沒有找到店家喔！")
        )
    else:

        bubbles = [build_shop_bubble(shop) for shop in data[:10]]  # 最多取前 10 家
        carousel = CarouselContainer(contents=bubbles)
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text="附近的店家", contents=carousel)
        )



@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
  
    
    if data.startswith("價格"):

        if user_id in user_sessions:
            user_sessions[user_id]["price"] = data.replace("價格", "")
            line_bot_api.reply_message(event.reply_token, messages=[
                TextSendMessage(text="你選擇了：" + data),
                get_rating_flex()
            ])
        return

    if data.startswith("評分"):
        if user_id in user_sessions:
            user_sessions[user_id]["rating"] = data.replace("評分", "")
            check_and_recommend(user_id, event.reply_token)
        return



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


def check_and_recommend(user_id, reply_token):
    session = user_sessions.get(user_id)
    if not session:
        line_bot_api.reply_message(reply_token, TextSendMessage(text="請先輸入：抽 類別1 類別2...，來進行有條件的抽餐廳"))
        return

    filters = {
        "categories": session["categories"],
        "price_cond": None if session["price"] in [None, "不限"] else session["price"],
        "rating_cond": None if session["rating"] in [None, "不限"] else session["rating"]
    }
    print(filters)

    url = build_supabase_url(filters)

    print(url)
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

    if(filters["rating_cond"] == None):
        line_bot_api.reply_message(reply_token, messages=[
                    flex
                ])
    else:
        line_bot_api.reply_message(reply_token, messages=[
                    TextSendMessage(text="你選擇了：" + filters["rating_cond"]),
                    flex
                ])

def build_supabase_url(filters):
    conditions = []
    if filters["categories"]:
        category_conds = [f"category.eq.{quote(c.strip())}" for c in filters["categories"]]
        conditions.append("or(" + ",".join(category_conds) + ")")
    if filters["rating_cond"]:
        rating_val = filters['rating_cond']
        conditions.append(f"rating.gte.{rating_val}")
    if filters["price_cond"]:
        conditions.append(f"price.eq.{quote(filters['price_cond'])}")


    if not conditions:
        return SUPABASE_API_RESTAURANTSTABLE_URL
    return f"{SUPABASE_API_RESTAURANTSTABLE_URL}?and=(" + ",".join(conditions) + ")"

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
                            "uri": r["url"]
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
                    {"type": "button", "style": "primary","color": "#4d94ff", "action": {"type": "postback", "label": "$100~200", "data": "價格$100~200"}},
                    {"type": "button", "style": "primary","color": "#4d94ff", "action": {"type": "postback", "label": "$200~400", "data": "價格$200~400"}},
                    {"type": "button", "style": "primary","color": "#4d94ff", "action": {"type": "postback", "label": "$400~600", "data": "價格$400~600"}},
                    {"type": "button", "style": "primary","color": "#4d94ff", "action": {"type": "postback", "label": "$600~800", "data": "價格$600~800"}},
                    {"type": "button", "style": "primary","color": "#4d94ff", "action": {"type": "postback", "label": "$800~1000", "data": "價格$800~1000"}},
                    {"type": "button", "style": "primary","color": "#4d94ff", "action": {"type": "postback", "label": "大於$1000", "data": "價格$>1000"}},
                    {"type": "button", "style": "primary","color": "#4d94ff", "action": {"type": "postback", "label": "不限價格", "data": "價格不限"}}
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
                    {"type": "button", "style": "primary","color": "#4d94ff","action": {"type": "postback", "label": "⭐ 1.0↑", "data": "評分1.0"}},
                    {"type": "button", "style": "primary","color": "#4d94ff","action": {"type": "postback", "label": "⭐ 2.0↑", "data": "評分2.0"}},
                    {"type": "button", "style": "primary","color": "#4d94ff","action": {"type": "postback", "label": "⭐ 3.0↑", "data": "評分3.0"}},
                    {"type": "button", "style": "primary","color": "#4d94ff","action": {"type": "postback", "label": "⭐ 4.0↑", "data": "評分4.0"}},
                    {"type": "button", "style": "primary","color": "#4d94ff","action": {"type": "postback", "label": "不限評分", "data": "評分不限"}}
                ]
            }
        }
    )


def build_shop_bubble(shop):
    return BubbleContainer(
        hero = ImageComponent(
            url=shop.get('image_url', "https://lh3.googleusercontent.com/gps-cs-s/AC9h4nqyDXlob20SzumctedCefs9AZNW2NbCKsjRbc8NSyxfeu9ygtH5JZ9JlnFTX_26ocfgKJSOzPjhRrsD7n912INgSVfbuvBR1Rk5iV74SvohMqIqbndveIRvwwMLu0nRzcEzSnn_=w408-h306-k-no"),  # 圖片 URL（建議使用 https）
            size="full",
            aspectRatio="1.51:1",
            aspectMode="cover",
            action=URIAction(
                uri=shop.get('url', "https://maps.app.goo.gl/61xHY5MmeE8ZjXs76"),  # 點圖片可導向 Google Maps 或商店頁面
                label="查看地圖"
            )
        ),
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(text=shop.get("name", "未知店家"), weight="bold", size="lg"),
                TextComponent(text=f"分類：{shop.get('category', '未知')}", size="sm", color="#666666"),
                TextComponent(text=f"評分：{shop.get('rating', 0)}⭐", size="sm", color="#666666"),
                TextComponent(text=f"價格：{shop.get('price', '未知')}", size="sm", color="#666666"),
                TextComponent(text=f"距離：約 {int(shop.get('distance', 0))} 公尺", size="sm", color="#666666"),
                
            ]
        ),
        footer=BoxComponent(
            layout="vertical",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#4d94ff",
                    action=URIAction(
                        label="前往 Google 地圖",
                        uri=shop.get('url', "https://maps.app.goo.gl/61xHY5MmeE8ZjXs76")
                    )
                )
            ]
        )
    )




