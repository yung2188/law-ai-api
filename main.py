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
        print(f"🔍 正在深度搜尋: {query}")
        # A. Tavily 搜尋 (增加 max_results 並提升內容長度)
        search_response = tavily.search(query=query, search_depth="advanced", max_results=3)
        context = ""
        for r in search_response['results']:
            # 增加到 1000 字，讓 AI 有更多素材
            context += f"\n來源: {r['title']} ({r['url']})\n內容: {r['content'][:1000]}\n"
        
        # B. AnythingLLM 思考 (優化角色設定)
        url = f"{ANYTHING_LLM_BASE_URL}/api/v1/workspace/{WORKSPACE_SLUG}/chat"
        headers = {
            "Authorization": f"Bearer {ANYTHING_LLM_API_KEY}",
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true"
        }
        
        # 🚀 強大的角色設定 Prompt
        system_instruction = (
            "你是一位專業且親切的 EaseMate AI 助手。請遵循以下規則回答：\n"
            "1. 使用『繁體中文』回答，語氣要自然、像真人對話，不要太死板。\n"
            "2. 針對搜尋到的資料進行『重點摘要』，使用列點方式讓結構清晰。\n"
            "3. 如果資料中有具體的數據或法律條文，請務必保留。\n"
            "4. 在回答最後，請列出參考的來源連結。\n"
            "5. 如果搜尋不到相關資料，請根據你的知識庫回答，並誠實告知。"
        )
        
        full_prompt = f"{system_instruction}\n\n參考資料：\n{context}\n\n用戶問題：{query}"
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
        result = {"report": "請輸入您想查詢的內容。"}
    else:
        answer = get_ai_response(user_msg)
        result = {"report": answer}
    
    response_json = json.dumps(result, ensure_ascii=False)
    return Response(response_json, content_type="application/json; charset=utf-8")

@app.route("/", methods=['GET'])
def index():
    return "EaseMate 後端已啟動"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
