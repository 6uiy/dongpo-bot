import os
import time
import requests
import feedparser
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID")
API_TOKEN = os.environ.get("CF_API_TOKEN")
FORUM_HOME = "https://dplt.ct.ws/"
FORUM_RSS = "https://dplt.ct.ws/app.php/feed"

QQ_APPID = os.environ.get("QQ_APPID")
QQ_SECRET = os.environ.get("QQ_SECRET")
QQ_GROUP_ID = os.environ.get("QQ_GROUP_ID")

def clean_html(text):
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def fetch_rss_with_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto(FORUM_HOME, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        rss_content = page.evaluate("""async () => {
            const resp = await fetch('/app.php/feed');
            return await resp.text();
        }""")
        browser.close()
        return rss_content

def check_post_with_ai(content):
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/meta/llama-3.1-8b-instruct"
    headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}
    prompt = f"你是论坛审核员。判断以下帖子是否违规（广告/辱骂/色情/违法/政治敏感）。只回答'违规'或'通过'，不要解释。帖子内容：{content}"
    data = {
        "messages": [
            {"role": "system", "content": "你是一个严格的论坛审核员。"},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        result = resp.json()
        if result.get("success") and result.get("result") and "response" in result["result"]:
            answer = result["result"]["response"]
            print(f"    AI 回答: {answer}")
            return "违规" in answer
        else:
            print(f"    ⚠️ API 返回错误: {str(result)[:200]}")
            return False
    except Exception as e:
        print(f"    AI 调用出错: {e}")
        return False

def send_qq_notification(title, link):
    """每次发现违规都尝试发送QQ通知，不限制次数"""
    try:
        token_url = "https://bots.qq.com/app/getAppAccessToken"
        token_resp = requests.post(token_url, json={"appId": QQ_APPID, "clientSecret": QQ_SECRET}, timeout=10)
        access_token = token_resp.json().get("access_token")
        
        if not access_token:
            print("    ❌ 获取 QQ access_token 失败，请检查 AppID/Secret。")
            return

        msg_url = f"https://api.sgroup.qq.com/v2/groups/{QQ_GROUP_ID}/messages"
        headers = {
            "Authorization": f"QQBot {access_token}",
            "Content-Type": "application/json"
        }
        msg_data = {
            "content": f"🚨 发现违规帖子！\n标题：{title}\n链接：{link}\n请管理员及时处理！",
            "msg_type": 0
        }
        
        resp = requests.post(msg_url, headers=headers, json=msg_data, timeout=10)
        if resp.status_code == 200:
            print("    ✅ QQ 群通知发送成功！")
        else:
            print(f"    ❌ QQ 发送失败，状态码: {resp.status_code}, 返回: {resp.text[:200]}")
            
    except Exception as e:
        print(f"    ❌ 发送 QQ 通知出错: {e}")

def main():
    print(f"[{datetime.now()}] 开始扫描论坛新帖...")
    
    try:
        rss_text = fetch_rss_with_browser()
        feed = feedparser.parse(rss_text)
        
        if len(feed.entries) == 0:
            print("  ⚠️ RSS 解析出来是空的")
            return
        
        print(f"  ✅ 成功抓取到 {len(feed.entries)} 篇帖子，开始审核...")
        
        for entry in feed.entries[:5]:
            title = entry.title
            link = entry.link
            raw_content = entry.get("summary", entry.get("description", ""))
            content = clean_html(raw_content)
            
            print(f"  正在检查: {title}")
            
            if check_post_with_ai(content):
                print(f"  🚨 发现违规帖子！")
                print(f"  标题: {title}")
                print(f"  链接: {link}")
                send_qq_notification(title, link)
            else:
                print("    ✅ 内容正常")
            
            time.sleep(1)
    
    except Exception as e:
        print(f"  ❌ 发生错误: {e}")
    
    print(f"[{datetime.now()}] 扫描完成。")

if __name__ == "__main__":
    main()
