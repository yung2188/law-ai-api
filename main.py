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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "ZPHEBVH-6RPMJ4M-NK5VP5D-H2X6DY5")
MODEL_NAME = "llama-3.3-70b-versatile"
MAX_SUB_PAGES = 3 

app = FastAPI()
client = Groq(api_key=GROQ_API_KEY)

# 修改 Request 模型，讓 url 變成選填，並增加 keyword
class ResearchRequest(BaseModel):
    url: str = None        # 設為 None 代表選填
    keyword: str = None    # 新增關鍵字欄位
    client_name: str = "Cloud_User"

# --- 核心邏輯 ---
def fetch_by_jina(url, mode="r"):
    # mode "r" 是讀取網頁，"s" 是搜尋關鍵字
    jina_url = f"https://{mode}.jina.ai/{url}"
    try:
        res = requests.get(jina_url, timeout=20) # 搜尋可能需要久一點，設 20s
        return res.text if res.status_code == 200 else None
    except: return None

def extract_links(markdown_content, base_url):
    if not base_url: return [] # 如果是搜尋模式，不抓子連結
    links = re.findall(r'\[.*?\]\((http.*?)\)', markdown_content)
    base_domain = urlparse(base_url).netloc
    return [l for l in list(set(links)) if urlparse(l).netloc == base_domain][:MAX_SUB_PAGES]

def analyze_with_groq(content_text, is_search=False):
    prompt_prefix = "你是一位專業法規分析師，請針對提供的內容，撰寫一份結構清晰的繁體中文 Markdown 報告。"
    if is_search:
        prompt_prefix = "你是一位專業法規分析師，我為你搜尋了多個相關來源，請彙整這些資訊，撰寫一份深度的繁體中文法規研究報告。"

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": prompt_prefix},
                {"role": "user", "content": content_text[:15000]} # 限制長度避免溢出
            ]
        )
        return completion.choices[0].message.content
    except Exception as e: return f"分析失敗: {e}"

# --- API 路由 ---
@app.get("/")
def home():
    return {"status": "Running", "service": "Law AI Researcher"}

@app.post("/research")
async def start_research(request: ResearchRequest):
    # 1. 判斷模式：優先處理網址，若無網址則處理關鍵字
    if request.url:
        print(f"模式：網址分析 - {request.url}")
        main_text = fetch_by_jina(request.url, mode="r")
        if not main_text: return {"error": "無法抓取該網址"}
        
        # 網址模式保留「抓取子連結」的深度分析
        sub_links = extract_links(main_text, request.url)
        sub_texts = [fetch_by_jina(l, mode="r") for l in sub_links if fetch_by_jina(l, mode="r")]
        combined_content = f"主頁內容：\n{main_text}\n" + "\n".join(sub_texts)
        
        report = analyze_with_groq(combined_content, is_search=False)
        
    elif request.keyword:
        print(f"模式：關鍵字搜尋 - {request.keyword}")
        # 搜尋模式：直接使用 s.jina.ai 抓取多個搜尋結果
        search_results = fetch_by_jina(request.keyword, mode="s")
        if not search_results: return {"error": "搜尋失敗"}
        
        report = analyze_with_groq(search_results, is_search=True)
        
    else:
        return {"error": "請提供 url 或 keyword"}
    
    return {
        "client": request.client_name,
        "mode": "URL" if request.url else "Keyword",
        "report": report
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
