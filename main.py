import os
import requests
import time
import re
from urllib.parse import urlparse
from groq import Groq
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import uvicorn

# --- 雲端環境設定 ---
# 在雲端部署時，我們通常不把 Key 寫死，但為了讓你先跑通，你可以先填入
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5")
MODEL_NAME = "llama-3.3-70b-versatile"
MAX_SUB_PAGES = 3  # 雲端免費版建議先設 3，避免執行太久被切斷

app = FastAPI()
client = Groq(api_key=GROQ_API_KEY)

class ResearchRequest(BaseModel):
    url: str
    client_name: str = "Cloud_User"

# --- 核心邏輯 ---
def fetch_by_jina(url):
    jina_url = f"https://r.jina.ai/{url}"
    try:
        res = requests.get(jina_url, timeout=15)
        return res.text if res.status_code == 200 else None
    except: return None

def extract_links(markdown_content, base_url):
    links = re.findall(r'\[.*?\]\((http.*?)\)', markdown_content)
    base_domain = urlparse(base_url).netloc
    return [l for l in list(set(links)) if urlparse(l).netloc == base_domain][:MAX_SUB_PAGES]

def analyze_with_groq(main_content, sub_contents):
    combined_text = f"主頁內容：\n{main_content}\n" + "\n".join(sub_contents)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": "你是一位專業法規分析師，請用繁體中文提供 Markdown 報告。"},
                      {"role": "user", "content": combined_text[:15000]}]
        )
        return completion.choices[0].message.content
    except Exception as e: return f"分析失敗: {e}"

# --- API 路由 ---
@app.get("/")
def home():
    return {"status": "Running", "service": "Law AI Researcher"}

@app.post("/research")
async def start_research(request: ResearchRequest, background_tasks: BackgroundTasks):
    # 雲端版我們不存本地檔案，直接返回分析結果（或發送 Email/Webhook）
    # 這裡示範直接返回結果的簡化流程
    print(f"收到請求: {request.url}")
    
    # 執行抓取與分析
    main_text = fetch_by_jina(request.url)
    if not main_text: return {"error": "無法抓取該網址"}
    
    sub_links = extract_links(main_text, request.url)
    sub_texts = [fetch_by_jina(l) for l in sub_links if fetch_by_jina(l)]
    
    report = analyze_with_groq(main_text, sub_texts)
    
    return {
        "client": request.client_name,
        "report": report
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)