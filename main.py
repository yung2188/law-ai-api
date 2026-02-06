import os
import requests
import json
from flask import Flask, request, Response
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
        print(f"🔍 處理請求: {query}")
        # A. Tavily 搜尋
        search_response = tavily.search(query=query, search_depth="advanced", max_results=2)
        context = ""
        for r in search_response['results']:
            context += f"\n來源: {r['title']}\n內容: {r['content'][:500]}\n"
        
        # B. AnythingLLM 思考 (加入強制中文指令)
        url = f"{ANYTHING_LLM_BASE_URL}/api/v1/workspace/{WORKSPACE_SLUG}/chat"
        headers = {
            "Authorization": f"Bearer {ANYTHING_LLM_API_KEY}",
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true"
        }
        
        # 這裡加入指令，要求 AI 必須用繁體中文回答
        full_prompt = f"請使用『繁體中文』回答。參考資料如下：\n{context}\n\n問題：{query}"
        payload = {"message": full_prompt, "mode": "chat"}
        
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        
        if response.status_code == 200:
            return response.json().get("textResponse", "AI 暫時無法回答")
        else:
            return f"AnythingLLM 錯誤: {response.status_code}"
    except Exception as e:
        return f"系統異常: {str(e)}"

@app.route("/research", methods=['POST'])
def research():
    data = request.json
    user_msg = data.get("keyword") or data.get("url")
    
    if not user_msg:
        result = {"report": "後端未收到有效訊息"}
    else:
        answer = get_ai_response(user_msg)
        result = {"report": answer}
    
    # 🚀 關鍵修復：強制使用 UTF-8 編碼回傳，防止中文變成 \u4f60
    response_json = json.dumps(result, ensure_ascii=False)
    return Response(response_json, content_type="application/json; charset=utf-8")

@app.route("/", methods=['GET'])
def index():
    return "EaseMate 後端已啟動"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
