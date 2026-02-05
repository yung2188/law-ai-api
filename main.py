import os
import requests
import threading  # 👈 新增：用於背景處理
from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from tavily import TavilyClient

app = Flask(__name__)

# --- 1. 環境變數設定 ---
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "tvly-dev-BqleJF10jLZhAIJHyvO050hVi3z")
ANYTHING_LLM_BASE_URL = os.environ.get("ANYTHING_LLM_URL", "https://ela-gravid-glenda.ngrok-free.dev")
ANYTHING_LLM_API_KEY = os.environ.get("ANYTHING_LLM_KEY", "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5")
WORKSPACE_SLUG = os.environ.get("WORKSPACE_SLUG", "business_intelligence")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
tavily = TavilyClient(api_key=TAVILY_API_KEY)

# --- 2. 核心邏輯函式 ---
def search_and_ask_task(reply_token, query):
    """在背景執行的任務：搜尋 + AI 思考 + 回傳 LINE"""
    try:
        # A. Tavily 搜尋
        print(f"🔍 正在搜尋: {query}")
        search_response = tavily.search(query=query, search_depth="advanced", max_results=3)
        context = ""
        for r in search_response['results']:
            context += f"\n來源: {r['title']}\n內容: {r['content']}\n"
        
        # B. AnythingLLM 思考
        url = f"{ANYTHING_LLM_BASE_URL}/api/v1/workspace/{WORKSPACE_SLUG}/chat"
        headers = {
            "Authorization": f"Bearer {ANYTHING_LLM_API_KEY}",
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true"
        }
        full_prompt = f"請根據以下參考資訊回答問題：\n{context}\n\n問題：{query}"
        payload = {"message": full_prompt, "mode": "chat"}
        
        print(f"🧠 正在請求 AnythingLLM...")
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        if response.status_code == 200:
            answer = response.json().get("textResponse", "AI 暫時無法回答")
        else:
            answer = f"AnythingLLM 錯誤: {response.status_code}"
            print(f"❌ Error: {response.text}")

        # C. 回傳給 LINE (使用 reply_token)
        line_bot_api.reply_message(reply_token, TextSendMessage(text=answer))
        print("✅ 成功回傳訊息給 LINE")

    except Exception as e:
        print(f"❌ 系統異常: {str(e)}")

# --- 3. 路由設定 ---

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'  # 👈 這裡立刻回傳 OK 給 LINE，避免逾時

@app.route("/research", methods=['POST'])
def research():
    data = request.json
    user_msg = data.get("message")
    # 網頁版不需要非同步，直接呼叫
    # (為了簡化，這裡暫時直接回傳搜尋結果，或你可以另外寫一個同步函式)
    return jsonify({"textResponse": "網頁版請稍候..."})

# --- 4. LINE 訊息處理 ---
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    reply_token = event.reply_token
    
    # 🚀 關鍵：開啟一個新執行緒 (Thread) 來處理耗時任務
    # 這樣主程式可以立刻回傳 'OK' 給 LINE 伺服器
    thread = threading.Thread(target=search_and_ask_task, args=(reply_token, user_msg))
    thread.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
