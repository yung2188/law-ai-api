import os
import requests
import time
import urllib.parse
from groq import Groq
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import uvicorn

# --- 雲端環境設定 ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MODEL_NAME = "llama-3.3-70b-versatile"

# --- AnythingLLM 設定 ---
ANYTHING_LLM_BASE_URL = "https://ela-gravid-glenda.ngrok-free.dev" 
ANYTHING_LLM_API_KEY = "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5"
WORKSPACE_SLUG = "business-intelligence"

app = FastAPI()
client = Groq(api_key=GROQ_API_KEY)

class ChatRequest(BaseModel):
    url: str = None
    keyword: str = None
    history: list = []  # 新增：接收前端傳來的對話歷史
    client_name: str = "User"

# --- 核心邏輯：AI 對話 (含記憶處理) ---
def get_ai_response(user_input, reference_content=None, history=[]):
    # 1. 設定系統指令
    messages = [
        {"role": "system", "content": "你是一位全能 AI 助手 EaseMate。你擅長法律、食品法規分析，也能進行日常對話。請根據對話上下文精準回答。請始終使用繁體中文。"}
    ]
    
    # 2. 注入歷史紀錄 (只取最近 6 則，避免超出限制)
    for msg in history[-6:]:
        if msg["role"] in ["user", "assistant"]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    # 3. 加入當前問題與參考資料
    current_user_msg = user_input
    if reference_content:
        current_user_msg += f"\n\n【即時參考資料】\n{reference_content[:8000]}"
    
    messages.append({"role": "user", "content": current_user_msg})

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"AI 思考出錯：{str(e)}"

# --- 核心邏輯：抓取資料 ---
def fetch_jina_data(target, is_search=False):
    safe_target = urllib.parse.quote(target)
    prefix = "s" if is_search else "r"
    jina_url = f"https://{prefix}.jina.ai/{safe_target}"
    try:
        response = requests.get(jina_url, timeout=40)
        if response.status_code == 200 and len(response.text.strip()) > 200:
            return response.text
    except: pass
    return None

# --- API 路由 ---
@app.post("/research")
async def chat_endpoint(request: ChatRequest):
    target = request.url if request.url else request.keyword
    is_search = True if request.keyword else False
    
    # 1. 抓取即時資料 (如果是網址或長問題)
    reference = None
    if target and (target.startswith("http") or len(target) > 3):
        reference = fetch_jina_data(target, is_search=is_search)
    
    # 2. 取得 AI 回答 (傳入歷史紀錄)
    answer = get_ai_response(target, reference, request.history)
    
    return {"report": answer}

@app.get("/")
def home(): return {"status": "EaseMate AI with Memory is Online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
