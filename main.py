import os
import requests
import time
import urllib.parse
from groq import Groq
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import uvicorn

# --- 1. 雲端環境設定 ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MODEL_NAME = "llama-3.3-70b-versatile"

# --- 2. AnythingLLM 設定 ---
ANYTHING_LLM_BASE_URL = os.environ.get("ANYTHING_LLM_URL", "https://ela-gravid-glenda.ngrok-free.dev")
ANYTHING_LLM_API_KEY = os.environ.get("ANYTHING_LLM_KEY", "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5")
WORKSPACE_SLUG = "business-intelligence"

app = FastAPI()
client = Groq(api_key=GROQ_API_KEY)

class ChatRequest(BaseModel):
    url: str = None
    keyword: str = None
    history: list = []
    client_name: str = "User"

# --- 3. 核心邏輯：自動寫入 AnythingLLM 右側大腦 ---
def save_to_anything_llm(content, title):
    if not ANYTHING_LLM_BASE_URL or "ngrok" not in ANYTHING_LLM_BASE_URL:
        return

    api_url = f"{ANYTHING_LLM_BASE_URL.rstrip('/')}/api/v1/workspace/{WORKSPACE_SLUG}/update-embeddings"
    headers = {
        "Authorization": f"Bearer {ANYTHING_LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "adds": [
            {
                "textContent": content,
                "metadata": {
                    "title": f"AutoLearn_{int(time.time())}",
                    "description": title[:50],
                    "source": "EaseMate_AI_Crawler"
                }
            }
        ]
    }
    
    try:
        res = requests.post(api_url, json=payload, headers=headers, timeout=30)
        if res.status_code == 200:
            print(f"✅ 知識已自動寫入 AnythingLLM: {title[:20]}")
        else:
            print(f"⚠️ AnythingLLM 寫入失敗: {res.status_code}")
    except Exception as e:
        print(f"❌ AnythingLLM 連線異常: {e}")

# --- 4. 核心邏輯：抓取資料 (含 Google 備案搜尋) ---
def fetch_jina_data(target, is_search=False):
    safe_target = urllib.parse.quote(target)
    
    # 第一次嘗試：使用 Jina 標準模式 (r 或 s)
    prefix = "s" if is_search else "r"
    jina_url = f"https://{prefix}.jina.ai/{safe_target}"
    
    print(f"--- 啟動 Jina 請求 ({prefix}) --- Target: {target}")
    
    try:
        response = requests.get(jina_url, timeout=35)
        if response.status_code == 200 and len(response.text.strip()) > 200:
            return response.text
    except:
        pass

    # --- 關鍵備案邏輯：如果搜尋模式失敗，強制爬取 Google 搜尋結果頁面 ---
    if is_search:
        print(f"⚠️ Jina 搜尋失敗，啟動 Google 備案搜尋...")
        google_url = f"https://www.google.com/search?q={safe_target}"
        backup_url = f"https://r.jina.ai/{google_url}"
        try:
            res = requests.get(backup_url, timeout=30)
            if res.status_code == 200:
                print("✅ Google 備案搜尋成功！")
                return res.text
        except:
            pass
            
    return None

# --- 5. 核心邏輯：AI 對話 (含記憶處理) ---
def get_ai_response(user_input, reference_content=None, history=[]):
# 在 main.py 中修改這段指令
system_message = {
    "role": "system", 
    "content": (
        "你是一位全能且主動的 AI 助手 EaseMate。你具備博學的知識，能處理任何話題。"
        "【重要指令】："
        "1. 務必根據上下文回答。如果用戶問法規，即使搜尋結果有限，也要根據你已知的知識庫（如標檢局、食藥署的一般準則）給出具體的方向，不要只說『我沒有資料』。"
        "2. 如果搜尋結果包含網頁內容，請詳細摘要重點。"
        "3. 保持專業、主動、且具備解決問題的態度。請使用繁體中文並以 Markdown 格式回答。"
    )
}
    
    messages = [system_message]
    
    # 注入歷史紀錄
    for msg in history[-8:]:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    # 加入當前問題
    current_content = user_input
    if reference_content:
        current_content += f"\n\n【即時參考資料】\n{reference_content[:8000]}"
    
    messages.append({"role": "user", "content": current_content})

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"AI 思考出錯：{str(e)}"

# --- 6. API 路由 ---
@app.post("/research")
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    target = request.url if request.url else request.keyword
    
    reference = None
    if target:
        # 智慧觸發：網址或長度 > 6 的問題才爬蟲
        if target.startswith("http") or len(target) > 6:
            is_search = not target.startswith("http")
            reference = fetch_jina_data(target, is_search=is_search)
            
            # 爬取成功則背景存入知識庫
            if reference:
                background_tasks.add_task(save_to_anything_llm, reference, target)
    
    answer = get_ai_response(target, reference, request.history)
    return {"report": answer}

@app.get("/")
def home(): return {"status": "EaseMate AI Ultimate Online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

