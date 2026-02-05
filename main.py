import os
import requests
import time
import urllib.parse
from groq import Groq
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# --- 雲端環境設定 ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5")
MODEL_NAME = "llama-3.3-70b-versatile"

app = FastAPI()
client = Groq(api_key=GROQ_API_KEY)

class ChatRequest(BaseModel):
    url: str = None
    keyword: str = None
    client_name: str = "User"

# --- 核心邏輯：抓取資料 ---
def fetch_jina_data(target, is_search=False):
    safe_target = urllib.parse.quote(target)
    prefix = "s" if is_search else "r"
    jina_url = f"https://{prefix}.jina.ai/{safe_target}"
    
    try:
        # 設定 45 秒超時
        response = requests.get(jina_url, timeout=45)
        if response.status_code == 200 and len(response.text.strip()) > 200:
            return response.text
    except:
        pass
    return None

# --- 核心邏輯：AI 對話 ---
def get_ai_response(user_input, reference_content=None):
    system_prompt = (
        "你是一位親切且專業的 AI 助手 EaseMate。你擅長法律與食品法規分析，也能進行日常對話。"
        "如果我有提供參考資料，請結合資料回答；如果資料不相關或抓取失敗，請直接以你的專業知識回答。"
        "請始終使用繁體中文，並以 Markdown 格式輸出。"
    )
    
    # 組合訊息
    user_content = f"用戶問題：{user_input}"
    if reference_content:
        user_content += f"\n\n【參考資料】\n{reference_content[:10000]}"

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"抱歉，我現在思考有點困難，請稍後再試。錯誤：{str(e)}"

# --- API 路由 ---
@app.post("/research")
async def chat_endpoint(request: ChatRequest):
    # 1. 判斷用戶輸入的是網址還是問題
    target = request.url if request.url else request.keyword
    is_search = True if request.keyword else False
    
    # 2. 嘗試抓取即時資料 (如果是網址或特定查詢)
    reference = None
    if target and ("http" in target or len(target) > 2):
        reference = fetch_jina_data(target, is_search=is_search)
    
    # 3. 取得 AI 回答
    answer = get_ai_response(target, reference)
    
    return {"report": answer}

@app.get("/")
def home(): return {"status": "EaseMate AI is Online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
