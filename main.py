import os
import requests
import time
import re
import urllib.parse
from urllib.parse import urlparse
from groq import Groq
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# --- 雲端環境設定 ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5")
MODEL_NAME = "llama-3.3-70b-versatile"

app = FastAPI()
client = Groq(api_key=GROQ_API_KEY)

class ResearchRequest(BaseModel):
    url: str = None
    keyword: str = None
    client_name: str = "Cloud_User"

# --- 核心邏輯 ---

def fetch_content(target, is_search=False):
    """
    整合讀取與搜尋。如果搜尋失敗，嘗試使用替代方案。
    """
    safe_target = urllib.parse.quote(target)
    
    # 根據模式選擇 Jina 前綴
    prefix = "s" if is_search else "r"
    jina_url = f"https://{prefix}.jina.ai/{safe_target}"
    
    print(f"--- 呼叫 Jina ({prefix}) --- Target: {target}")
    
    try:
        # 增加超時到 60 秒
        response = requests.get(jina_url, timeout=60)
        if response.status_code == 200 and len(response.text.strip()) > 200:
            return response.text
    except Exception as e:
        print(f"Jina 請求異常: {e}")

    # --- 備案邏輯 (如果搜尋失敗) ---
    if is_search:
        print("⚠️ Jina 搜尋無回應，嘗試改用網頁讀取模式作為備案...")
        # 備案：直接去抓 Google 搜尋結果頁面 (透過 Jina 轉譯)
        backup_url = f"https://r.jina.ai/https://www.google.com/search?q={safe_target}+法規+標準"
        try:
            res = requests.get(backup_url, timeout=30)
            if res.status_code == 200: return res.text
        except: pass
        
    return None

def analyze_with_groq(content_text, is_search=False):
    system_prompt = "你是一位專業法規分析師。請根據提供的內容撰寫一份結構清晰的繁體中文 Markdown 報告。"
    
    # 如果內容太長，截斷它以符合 Groq 限制
    truncated_content = content_text[:12000] 

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"請分析以下內容並生成報告：\n\n{truncated_content}"}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"AI 分析失敗: {str(e)}"

# --- API 路由 ---

@app.post("/research")
async def start_research(request: ResearchRequest):
    print(f"\n[收到請求] Mode: {'URL' if request.url else 'Keyword'}")
    
    target = request.url if request.url else request.keyword
    is_search = True if request.keyword else False
    
    content = fetch_content(target, is_search=is_search)
    
    if not content:
        return {
            "error": "資料抓取失敗",
            "details": "目前無法取得相關法規資訊，請檢查網址或嘗試更換關鍵字。"
        }
    
    report = analyze_with_groq(content, is_search=is_search)
    
    return {
        "client": request.client_name,
        "report": report
    }

@app.get("/")
def home(): return {"status": "online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
