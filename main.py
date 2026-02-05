import os
import requests
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
WORKSPACE_SLUG = "business_intelligence"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
tavily = TavilyClient(api_key=TAVILY_API_KEY)

# --- 2. 核心邏輯函式 ---
def search_and_ask(query):
    """整合 Tavily 搜尋與 AnythingLLM 回答的邏輯"""
    try:
        # A. Tavily 搜尋
        search_response = tavily.search(query=query, search_depth="advanced", max_results=3)
        context = ""
        for r in search_response['results']:
            context += f"\n來源: {r['title']}\n內容: {r['content']}\n"
        
        # B. AnythingLLM 思考
        url = f"{ANYTHING_LLM_BASE_URL}/api/v1/workspace/{WORKSPACE_SLUG}/chat"
        headers = {"Authorization": f"Bearer {ANYTHING_LLM_API_KEY}", "Content-Type": "application/json"}
        full_prompt = f"請根據以下參考資訊回答問題：\n{context}\n\n問題：{query}"
        
        payload = {"message": full_prompt, "mode": "chat"}
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            return response.json().get("textResponse", "AI 暫時無法回答")
        else:
            return f"AnythingLLM 錯誤: {response.status_code}"
    except Exception as e:
        return f"系統錯誤: {str(e)}"

# --- 3. 路由設定 ---

# A. 給 LINE Bot 用的路徑
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# B. 給網頁版 (Streamlit) 用的路徑 (修復 404 錯誤)
@app.route("/research", methods=['POST'])
def research():
    data = request.json
    user_msg = data.get("message")
    if not user_msg:
        return jsonify({"error": "No message provided"}), 400
    
    answer = search_and_ask(user_msg)
    return jsonify({"textResponse": answer})

# --- 4. LINE 訊息處理 ---
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    final_answer = search_and_ask(user_msg)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=final_answer))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

