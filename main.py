import os
import requests
import threading
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

# --- 2. 核心邏輯函式 (優化搜尋與超時) ---
def get_ai_response(query):
    try:
        # A. Tavily 搜尋 (限制結果為 2 份，減少 AI 思考負擔)
        print(f"🔍 正在搜尋: {query}")
        context = ""
        try:
            search_response = tavily.search(query=query, search_depth="advanced", max_results=2)
            for r in search_response['results']:
                context += f"\n來源: {r['title']}\n內容: {r['content'][:500]}\n" # 限制每篇內容長度
        except Exception as se:
            print(f"⚠️ 搜尋暫時不可用: {se}")
            context = "無法取得即時搜尋結果。"

        # B. AnythingLLM 思考
        url = f"{ANYTHING_LLM_BASE_URL}/api/v1/workspace/{WORKSPACE_SLUG}/chat"
        headers = {
            "Authorization": f"Bearer {ANYTHING_LLM_API_KEY}",
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true"
        }
        
        # 組合 Prompt，並限制總長度
        full_prompt = f"參考資料：{context}\n\n問題：{query}"
        payload = {"message": full_prompt, "mode": "chat"}
        
        print(f"🧠 正在請求 AnythingLLM (Timeout=120s)...")
        # 增加 timeout 到 120 秒，應對慢速回應
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        
        if response.status_code == 200:
            return response.json().get("textResponse", "AI 暫時無法回答")
        else:
            print(f"❌ AnythingLLM 報錯: {response.status_code} - {response.text}")
            return f"AnythingLLM 錯誤: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return "系統忙碌中（AI 思考超時），請稍後再試一次。"
    except Exception as e:
        print(f"❌ 系統異常: {str(e)}")
        return f"系統異常: {str(e)}"

# --- 3. 背景任務 (專給 LINE 使用，防止已讀不回) ---
def line_background_task(reply_token, query):
    answer = get_ai_response(query)
    try:
        line_bot_api.reply_message(reply_token, TextSendMessage(text=answer))
        print("✅ 成功回傳訊息給 LINE")
    except Exception as e:
        print(f"❌ LINE 回傳失敗: {e}")

# --- 4. 路由設定 ---

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK' # 立刻回傳 OK 給 LINE

@app.route("/research", methods=['POST'])
def research():
    data = request.json
    user_msg = data.get("message")
    if not user_msg:
        return jsonify({"textResponse": "請輸入訊息"}), 400
    
    # 網頁版同步回傳結果
    answer = get_ai_response(user_msg)
    return jsonify({"textResponse": answer})

# --- 5. LINE 訊息處理 ---
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    reply_token = event.reply_token
    
    # 開啟背景執行緒處理 LINE 訊息
    thread = threading.Thread(target=line_background_task, args=(reply_token, user_msg))
    thread.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
