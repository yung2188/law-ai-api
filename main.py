import os
import requests
from flask import Flask, request, jsonify
from tavily import TavilyClient

app = Flask(__name__)

# --- 環境變數 (請確保 Render 後台已填寫) ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "tvly-dev-BqleJF10jLZhAIJHyvO050hVi3z")
ANYTHING_LLM_BASE_URL = os.environ.get("ANYTHING_LLM_URL", "https://ela-gravid-glenda.ngrok-free.dev")
ANYTHING_LLM_API_KEY = os.environ.get("ANYTHING_LLM_KEY", "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5")
WORKSPACE_SLUG = os.environ.get("WORKSPACE_SLUG", "business_intelligence")

tavily = TavilyClient(api_key=TAVILY_API_KEY)

def get_ai_response(query):
    try:
        print(f"🔍 網頁正在搜尋: {query}")
        # A. Tavily 搜尋
        search_response = tavily.search(query=query, search_depth="advanced", max_results=2)
        context = ""
        for r in search_response['results']:
            context += f"\n來源: {r['title']}\n內容: {r['content'][:500]}\n"
        
        # B. AnythingLLM 思考
        url = f"{ANYTHING_LLM_BASE_URL}/api/v1/workspace/{WORKSPACE_SLUG}/chat"
        headers = {
            "Authorization": f"Bearer {ANYTHING_LLM_API_KEY}",
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true"
        }
        payload = {"message": f"參考資料：{context}\n\n問題：{query}", "mode": "chat"}
        
        print(f"🧠 正在請求 AnythingLLM...")
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        
        if response.status_code == 200:
            return response.json().get("textResponse", "AI 暫時無法回答")
        else:
            print(f"❌ AnythingLLM 報錯: {response.text}")
            return f"AnythingLLM 錯誤: {response.status_code}"
    except Exception as e:
        print(f"❌ 系統異常: {str(e)}")
        return f"系統異常: {str(e)}"

# --- 網頁專用接口 ---
@app.route("/research", methods=['POST'])
def research():
    # 這裡會印出網頁到底傳了什麼，方便我們在 Render Logs 監看
    data = request.json
    print(f"📥 網頁傳來的原始資料: {data}")
    
    if not data:
        return jsonify({"textResponse": "錯誤：後端未收到任何 JSON 資料"}), 400

    # 自動偵測多種可能的欄位名稱
    user_msg = data.get("message") or data.get("query") or data.get("question") or data.get("text")
    
    if not user_msg:
        return jsonify({"textResponse": f"錯誤：無法從資料中找到訊息內容。收到的資料為: {data}"}), 400
    
    answer = get_ai_response(user_msg)
    return jsonify({"textResponse": answer})

# 首頁測試 (讓你直接瀏覽網址時不會看到 404)
@app.route("/", methods=['GET'])
def index():
    return "法規 AI 助手後端運行中！"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
