import os
import requests
import time
import urllib.parse
from groq import Groq
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import uvicorn

# --- 雲端環境設定 ---
# 建議在 Render 的 Environment 設定 GROQ_API_KEY
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "你的_GROQ_KEY")
MODEL_NAME = "llama-3.3-70b-versatile"

# --- AnythingLLM 設定 (請根據你的 Ngrok 網址更新) ---
ANYTHING_LLM_BASE_URL = "https://ela-gravid-glenda.ngrok-free.dev" 
ANYTHING_LLM_API_KEY = "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5"
WORKSPACE_SLUG = "business-intelligence" # 根據你的截圖名稱轉換為小寫與連字號

app = FastAPI()
client = Groq(api_key=GROQ_API_KEY)

class ChatRequest(BaseModel):
    url: str = None
    keyword: str = None
    client_name: str = "User"

# --- 核心邏輯：自動寫入右側大腦並 Embedding ---
def save_to_anything_llm(content, title):
    """
    直接將抓取到的內容推送到 AnythingLLM 右側 Workspace 並自動觸發向量化
    """
    if not ANYTHING_LLM_BASE_URL or "你的" in ANYTHING_LLM_BASE_URL:
        print("⚠️ 未設定 AnythingLLM 網址，跳過自動學習。")
        return

    # API 端點：update-embeddings 會直接把內容塞進右側並讓 AI 學習
    api_url = f"{ANYTHING_LLM_BASE_URL}/api/v1/workspace/{WORKSPACE_SLUG}/update-embeddings"
    headers = {
        "Authorization": f"Bearer {ANYTHING_LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 建立唯一的標題，避免重複
    unique_title = f"AutoLearn_{int(time.time())}_{title[:20]}"
    
    payload = {
        "adds": [
            {
                "textContent": content,
                "metadata": {
                    "title": unique_title,
                    "source": "EaseMate_AI_Crawler",
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        ]
    }
    
    try:
        print(f"--- 嘗試自動寫入大腦: {unique_title} ---")
        res = requests.post(api_url, json=payload, headers=headers, timeout=40)
        
        if res.status_code == 200:
            print(f"✅ 成功！知識已自動寫入右側工作區並完成 Embedding。")
        else:
            print(f"⚠️ 自動寫入失敗 ({res.status_code})，嘗試備案路徑...")
            # 備案：如果 update-embeddings 失敗，改用 raw-text 存入左側
            backup_url = f"{ANYTHING_LLM_BASE_URL}/api/v1/workspace/{WORKSPACE_SLUG}/raw-text"
            requests.post(backup_url, json={"textContent": content, "metadata": {"title": title}}, headers=headers)
            
    except Exception as e:
        print(f"❌ AnythingLLM 連線異常: {e}")

# --- 核心邏輯：抓取資料 ---
def fetch_jina_data(target, is_search=False):
    safe_target = urllib.parse.quote(target)
    prefix = "s" if is_search else "r"
    jina_url = f"https://{prefix}.jina.ai/{safe_target}"
    
    print(f"--- 啟動 Jina 請求 ({prefix}) --- Target: {target}")
    
    try:
        response = requests.get(jina_url, timeout=45)
        if response.status_code == 200 and len(response.text.strip()) > 200:
            return response.text
    except Exception as e:
        print(f"Jina 請求出錯: {e}")
    return None

# --- 核心邏輯：AI 對話 ---
def get_ai_response(user_input, reference_content=None):
    system_prompt = (
        "你是一位親切且專業的 AI 助手 EaseMate。你擅長法律與食品法規分析。"
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
        return f"AI 思考出錯：{str(e)}"

# --- API 路由 ---
@app.post("/research")
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    # 判斷輸入類型
    target = request.url if request.url else request.keyword
    is_search = True if request.keyword else False
    
    if not target:
        return {"report": "請輸入問題或網址。"}

    # 1. 抓取即時資料
    reference = fetch_jina_data(target, is_search=is_search)
    
    # 2. 如果抓取成功，使用背景任務自動寫入 AnythingLLM 大腦
    if reference:
        background_tasks.add_task(save_to_anything_llm, reference, target)
    
    # 3. 取得 AI 回答
    answer = get_ai_response(target, reference)
    
    return {"report": answer}

@app.get("/")
def home(): return {"status": "EaseMate AI Autonomous Learning Online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
