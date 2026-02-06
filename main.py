import os
import requests
from flask import Flask, request, jsonify
from tavily import TavilyClient

app = Flask(__name__)

# --- 環境變數 ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "tvly-dev-BqleJF10jLZhAIJHyvO050hVi3z")
ANYTHING_LLM_BASE_URL = os.environ.get("ANYTHING_LLM_URL", "https://ela-gravid-glenda.ngrok-free.dev")
ANYTHING_LLM_API_KEY = os.environ.get("ANYTHING_LLM_KEY", "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5")
WORKSPACE_SLUG = os.environ.get("WORKSPACE_SLUG", "business_intelligence")

tavily = TavilyClient(api_key=TAVILY_API_KEY)

def get_ai_response(query):
    try:
        print(f"🔍 正在處理網頁請求: {query}")
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
        
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        
        if response.status_code == 200:
            return response.json().get("textResponse", "AI 暫時無法回答")
        else:
            return f"AnythingLLM 錯誤: {response.status_code}"
    except Exception as e:
        return f"系統異常: {str(e)}"

# --- 網頁專用接口 (對接你的 Streamlit 格式) ---
@app.route("/research", methods=['POST'])
def research():
    data = request.json
    print(f"📥 收到網頁資料: {data}")
    
    # 1. 根據你的 Streamlit 邏輯，問題可能在 'keyword' 或 'url'
    user_msg = data.get("keyword") or data.get("url")
    
    if not user_msg:
        return jsonify({"report": "後端未收到有效關鍵字或網址"}), 400
    
    # 2. 取得 AI 回答
    answer = get_ai_response(user_msg)
    
    # 3. 🚀 重要：回傳的 Key 必須叫 "report"，因為你的 Streamlit 在找這個字
    return jsonify({"report": answer})

@app.route("/", methods=['GET'])
def index():
    return "EaseMate 後端已啟動"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
