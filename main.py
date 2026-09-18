import os
import time
import requests
import feedparser
from datetime import datetime

ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID")
API_TOKEN = os.environ.get("CF_API_TOKEN")
FORUM_RSS = "https://dplt.ct.ws/app.php/feed"

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
        print(f"AI 调用出错: {e}")
        return False

def main():
    print(f"[{datetime.now()}] 开始扫描论坛新帖...")
    feed = feedparser.parse(FORUM_RSS)
    
    for entry in feed.entries[:5]:
        title = entry.title
        link = entry.link
        content = entry.get("summary", entry.get("description", ""))
        
        print(f"正在检查: {title}")
        
        if check_post_with_ai(content):
            print(f"\n🚨 发现违规帖子！")
            print(f"标题: {title}")
            print(f"链接: {link}")
            print(f"内容: {content[:100]}...")
        else:
            print("  ✅ 内容正常")
        
        time.sleep(1)
    
    print(f"[{datetime.now()}] 扫描完成。")

if __name__ == "__main__":
    main()
