import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS  # 👈 新增：解決網頁跨域連線問題
from tavily import TavilyClient

app = Flask(__name__)
CORS(app) # 👈 開啟全域支援

# --- 環境變數 ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "tvly-dev-BqleJF10jLZhAIJHyvO050hVi3z")
ANYTHING_LLM_BASE_URL = os.environ.get("ANYTHING_LLM_URL", "https://ela-gravid-glenda.ngrok-free.dev")
ANYTHING_LLM_API_KEY = os.environ.get("ANYTHING_LLM_KEY", "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5")
WORKSPACE_SLUG = os.environ.get("WORKSPACE_SLUG", "business_intelligence")

tavily = TavilyClient(api_key=TAVILY_API_KEY)

def get_ai_response(query):
    try:
        print(f"🔍 搜尋中: {query}")
        search_response = tavily.search(query=query, search_depth="advanced", max_results=2)
        context = ""
        for r in search_response['results']:
            context += f"\n來源: {r['title']}\n內容: {r['content'][:800]}\n"
        
        url = f"{ANYTHING_LLM_BASE_URL}/api/v1/workspace/{WORKSPACE_SLUG}/chat"
        headers = {
            "Authorization": f"Bearer {ANYTHING_LLM_API_KEY}",
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true"
        }
        
        system_prompt = "你是 EaseMate AI，請用繁體中文、親切且專業地回答問題，並列出重點摘要。"
        full_prompt = f"{system_prompt}\n\n參考資料：\n{context}\n\n問題：{query}"
        
        response = requests.post(url, json={"message": full_prompt, "mode": "chat"}, headers=headers, timeout=150)
        
        if response.status_code == 200:
            return response.json().get("textResponse", "AI 暫時無法回答")
        return f"AnythingLLM 錯誤: {response.status_code}"
    except Exception as e:
        return f"連線超時或異常，請稍後再試。({str(e)})"

@app.route("/research", methods=['POST'])
def research():
    data = request.json
    user_msg = data.get("keyword") or data.get("url")
    if not user_msg:
        return jsonify({"report": "請輸入問題"}), 400
    
    answer = get_ai_response(user_msg)
    # 使用 jsonify 並確保不使用 ASCII 編碼以支援中文
    app.config['JSON_AS_ASCII'] = False 
    return jsonify({"report": answer})

@app.route("/", methods=['GET'])
def index():
    return "EaseMate Backend is Running"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
