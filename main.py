import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from tavily import TavilyClient

app = Flask(__name__)

# --- 1. 環境變數與 API 金鑰設定 ---
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

# Tavily 設定
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "tvly-dev-BqleJF10jLZhAIJHyvO050hVi3z")
tavily = TavilyClient(api_key=TAVILY_API_KEY)

# AnythingLLM 設定
ANYTHING_LLM_BASE_URL = os.environ.get("ANYTHING_LLM_URL", "https://ela-gravid-glenda.ngrok-free.dev")
ANYTHING_LLM_API_KEY = os.environ.get("ANYTHING_LLM_KEY", "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5")
WORKSPACE_SLUG = "business-intelligence"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- 2. 核心功能函式 ---

def search_with_tavily(query):
    """使用 Tavily 獲取即時法規或資訊"""
    try:
        print(f"🔍 正在搜尋：{query}")
        response = tavily.search(query=query, search_depth="advanced", max_results=3)
        context = ""
        for r in response['results']:
            context += f"\n來源: {r['title']}\n內容: {r['content']}\n"
        return context
    except Exception as e:
        print(f"Tavily 錯誤: {e}")
        return ""

def ask_anything_llm(question, context=""):
    """將問題與搜尋到的資料送往 AnythingLLM 進行總結回答"""
    try:
        url = f"{ANYTHING_LLM_BASE_URL}/api/v1/workspace/{WORKSPACE_SLUG}/chat"
        headers = {
            "Authorization": f"Bearer {ANYTHING_LLM_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 組合 Prompt：讓 AI 根據搜尋結果回答
        full_prompt = f"請根據以下參考資訊回答問題：\n{context}\n\n問題：{question}" if context else question
        
        payload = {
            "message": full_prompt,
            "mode": "chat"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json().get("textResponse", "AI 暫時無法回答")
        else:
            return f"AnythingLLM 錯誤: {response.status_code}"
    except Exception as e:
        return f"連線到 AnythingLLM 失敗: {str(e)}"

# --- 3. Line Bot 路由與事件處理 ---

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
    user_msg = event.message.text.strip()
    
    # 1. 先進行 Tavily 搜尋
    search_context = search_with_tavily(user_msg)
    
    # 2. 將搜尋結果餵給 AnythingLLM 進行整理
    final_answer = ask_anything_llm(user_msg, search_context)
    
    # 3. 回傳最終結果給 Line 使用者
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=final_answer)
    )

if __name__ == "__main__":
    # 這行非常重要：Render 會隨機分配 Port，必須讀取環境變數
    port = int(os.environ.get('PORT', 10000))
    # 必須設定 host='0.0.0.0'
    app.run(host='0.0.0.0', port=port)
