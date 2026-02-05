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

# --- AnythingLLM 設定 (請替換為你的資訊) ---
# 如果使用 Ngrok，網址會像 https://xxxx.ngrok-free.app
ANYTHING_LLM_BASE_URL = "https://ela-gravid-glenda.ngrok-free.dev" 
ANYTHING_LLM_API_KEY = "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5"
WORKSPACE_SLUG = "Business_Intelligence" # 例如: law-knowledge

app = FastAPI()
client = Groq(api_key=GROQ_API_KEY)

class ChatRequest(BaseModel):
    url: str = None
    keyword: str = None
    client_name: str = "User"

# --- 核心邏輯：寫入 AnythingLLM 知識庫 ---
def save_to_anything_llm(content, title):
    """
    透過 API 將抓取到的資料存入 AnythingLLM 的向量資料庫
    """
    if not ANYTHING_LLM_BASE_URL or "你的" in ANYTHING_LLM_BASE_URL:
        print("⚠️ 未設定 AnythingLLM API 資訊，跳過存儲。")
        return

    # AnythingLLM API 端點：直接上傳文字內容並嵌入 (Embed)
    api_url = f"{ANYTHING_LLM_BASE_URL}/api/v1/workspace/{WORKSPACE_SLUG}/raw-text"
    headers = {
        "Authorization": f"Bearer {ANYTHING_LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "textContent": content,
        "metadata": {
            "title": title,
            "source": "AI_Auto_Crawler",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    }
    
    try:
        res = requests.post(api_url, json=payload, headers=headers, timeout=20)
        if res.status_code == 200:
            print(f"✅ 成功將知識存入 AnythingLLM: {title}")
        else:
            print(f"❌ AnythingLLM 儲存失敗: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ 連線至 AnythingLLM 發生異常: {e}")

# --- 核心邏輯：抓取資料 ---
def fetch_jina_data(target, is_search=False):
    safe_target = urllib.parse.quote(target)
    prefix = "s" if is_search else "r"
    jina_url = f"https://{prefix}.jina.ai/{safe_target}"
    
    try:
        response = requests.get(jina_url, timeout=45)
        if response.status_code == 200 and len(response.text.strip()) > 200:
            return response.text
    except:
        pass
    return None

# --- 核心邏輯：AI 對話 ---
def get_ai_response(user_input, reference_content=None):
    system_prompt = (
        "你是一位全能 AI 助手 EaseMate。你具備專業的法律與食品法規知識。"
        "我會提供你即時抓取的參考資料，請結合資料與你的知識回答。"
        "請始終使用繁體中文，並以 Markdown 格式輸出。"
    )
    
    user_content = f"用戶問題：{user_input}"
    if reference_content:
        user_content += f"\n\n【即時參考資料】\n{reference_content[:10000]}"

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
        return f"思考出錯：{str(e)}"

# --- API 路由 ---
@app.post("/research")
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    target = request.url if request.url else request.keyword
    is_search = True if request.keyword else False
    
    # 1. 抓取即時資料
    reference = None
    if target:
        reference = fetch_jina_data(target, is_search=is_search)
    
    # 2. 如果抓取成功，使用「背景任務」偷偷存入 AnythingLLM
    # 這樣用戶不需要等待存儲過程，反應速度會更快
    if reference:
        background_tasks.add_task(save_to_anything_llm, reference, target)
    
    # 3. 取得 AI 回答
    answer = get_ai_response(target, reference)
    
    return {"report": answer}

@app.get("/")
def home(): return {"status": "EaseMate AI with Knowledge Base is Online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
