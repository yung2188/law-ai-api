import os
import requests
import time
import re
import urllib.parse
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

# Request 模型
class ResearchRequest(BaseModel):
    url: str = None
    keyword: str = None
    client_name: str = "Cloud_User"

# --- 核心邏輯 ---

def fetch_by_jina(target, mode="r"):
    """
    mode "r": 讀取單一網頁 (r.jina.ai)
    mode "s": 搜尋關鍵字 (s.jina.ai)
    """
    # 對中文進行編碼，避免網址解析錯誤
    safe_target = urllib.parse.quote(target)
    jina_url = f"https://{mode}.jina.ai/{safe_target}"
    
    print(f"--- 啟動 Jina 請求 ({mode}) ---")
    print(f"目標: {target}")
    print(f"網址: {jina_url}")
    
    # 嘗試最多 2 次重試機制
    for attempt in range(2):
        try:
            # 搜尋模式 (s) 需要較長時間，設定 50 秒超時
            timeout_sec = 50 if mode == "s" else 30
            response = requests.get(jina_url, timeout=timeout_sec)
            
            if response.status_code == 200 and len(response.text.strip()) > 100:
                print(f"✅ Jina 請求成功 (長度: {len(response.text)})")
                return response.text
            
            print(f"⚠️ 第 {attempt+1} 次嘗試失敗: Status {response.status_code}")
            if attempt == 0: 
                print("等待 2 秒後重試...")
                time.sleep(2)
        except Exception as e:
            print(f"❌ 第 {attempt+1} 次連線異常: {str(e)}")
            if attempt == 0: time.sleep(2)
            
    return None

def extract_links(markdown_content, base_url):
    if not base_url: return []
    links = re.findall(r'\[.*?\]\((http.*?)\)', markdown_content)
    base_domain = urlparse(base_url).netloc
    valid_links = [l for l in list(set(links)) if urlparse(l).netloc == base_domain]
    return valid_links[:MAX_SUB_PAGES]

def analyze_with_groq(content_text, is_search=False):
    system_prompt = (
        "你是一位專業法規分析師。請根據提供的內容撰寫一份結構清晰、"
        "具備專業見解的繁體中文 Markdown 報告。若內容包含多個來源，請進行彙整對比。"
    )

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"請分析以下內容並生成報告：\n\n{content_text[:15000]}"}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"❌ Groq 分析出錯: {str(e)}")
        return f"AI 分析失敗: {str(e)}"

# --- API 路由 ---

@app.get("/")
def home():
    return {"status": "Running", "service": "EaseMate AI Law Researcher"}

@app.post("/research")
async def start_research(request: ResearchRequest):
    print(f"\n[收到請求] Client: {request.client_name}")
    
    # 模式 1：網址分析
    if request.url:
        print(f"執行模式: 網址分析 -> {request.url}")
        main_text = fetch_by_jina(request.url, mode="r")
        
        if not main_text:
            return {"error": "無法讀取該網址內容", "details": "Jina 讀取網頁失敗，請確認網址是否公開可存取。"}
        
        sub_links = extract_links(main_text, request.url)
        sub_texts = []
        for link in sub_links:
            stext = fetch_by_jina(link, mode="r")
            if stext: sub_texts.append(stext)
        
        combined_content = f"【主頁內容】\n{main_text}\n" + "\n".join([f"【參考子頁】\n{t}" for t in sub_texts])
        report = analyze_with_groq(combined_content, is_search=False)
        
    # 模式 2：關鍵字搜尋
    elif request.keyword:
        print(f"執行模式: 關鍵字搜尋 -> {request.keyword}")
        search_results = fetch_by_jina(request.keyword, mode="s")
        
        if not search_results:
            return {
                "error": "搜尋失敗", 
                "details": "Jina 搜尋服務目前無回應。這可能是因為搜尋量過大或關鍵字過於複雜，請嘗試更簡單的關鍵字或稍後再試。"
            }
        
        report = analyze_with_groq(search_results, is_search=True)
        
    else:
        return {"error": "請提供 url 或 keyword 參數"}
    
    return {
        "client": request.client_name,
        "mode": "URL" if request.url else "Keyword",
        "report": report
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
