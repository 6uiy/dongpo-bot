import os
import time
import requests
import feedparser
from datetime import datetime
from playwright.sync_api import sync_playwright

ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID")
API_TOKEN = os.environ.get("CF_API_TOKEN")
FORUM_HOME = "https://dplt.ct.ws/"
FORUM_RSS = "https://dplt.ct.ws/app.php/feed"

def fetch_rss_with_browser():
    """用真正的无头浏览器访问论坛，执行 JS 挑战，拿到 RSS 内容"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("  正在访问论坛首页，通过 JS 挑战...")
        page.goto(FORUM_HOME, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        
        print("  正在用浏览器请求 RSS...")
        rss_content = page.evaluate("""async () => {
            const resp = await fetch('/app.php/feed');
            return await resp.text();
        }""")
        
        browser.close()
        return rss_content

def check_post_with_ai(content):
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/meta/llama-3-8b-instruct"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    prompt = f"""你是论坛审核员。判断以下帖子是否违规（广告/辱骂/色情/违法/政治敏感）。
只回答"违规"或"通过"，不要解释。
帖子内容：{content}"""
    data = {
        "messages": [
            {"role": "system", "content": "你是一个严格的论坛审核员。"},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        result = resp.json()
        if "result" in result and "response" in result["result"]:
            return "违规" in result["result"]["response"]
        return False
    except Exception as e:
        print(f"  AI 调用出错: {e}")
        return False

def main():
    print(f"[{datetime.now()}] 开始扫描论坛新帖...")
    
    try:
        rss_text = fetch_rss_with_browser()
        print(f"  拿到 RSS 内容，长度: {len(rss_text)} 字符")
        
        feed = feedparser.parse(rss_text)
        
        if len(feed.entries) == 0:
            print("  ⚠️ RSS 解析出来是空的")
            print(f"  预览: {rss_text[:200]}")
            return
        
        print(f"  ✅ 成功抓取到 {len(feed.entries)} 篇帖子，开始审核...")
        
        for entry in feed.entries[:5]:
            title = entry.title
            link = entry.link
            content = entry.get("summary", entry.get("description", ""))
            
            print(f"  正在检查: {title}")
            
            if check_post_with_ai(content):
                print(f"  🚨 发现违规帖子！")
                print(f"  标题: {title}")
                print(f"  链接: {link}")
            else:
                print("    ✅ 内容正常")
            
            time.sleep(1)
    
    except Exception as e:
        print(f"  ❌ 发生错误: {e}")
    
    print(f"[{datetime.now()}] 扫描完成。")

if __name__ == "__main__":
    main()
