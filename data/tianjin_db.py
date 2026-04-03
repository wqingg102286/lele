from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import time
from urllib.parse import urljoin


def scrape_tj_gov_documents():
    # 目标列表页网址
    list_url = "https://tj.bendibao.com/tour/"

    # 建立保存数据的文件夹
    save_dir = "天津知识库/旅游"
    os.makedirs(save_dir, exist_ok=True)

    with sync_playwright() as p:
        # 启动浏览器 (headless=False 可以让你看着它自动操作，调试完可改成 True)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print(f"🔄 正在访问列表页: {list_url}")
        # 访问列表页，等待网络空闲
        page.goto(list_url, wait_until="networkidle")
        time.sleep(2)  # 让人类肉眼看一下页面，顺便防反爬

        # 获取列表页的 HTML
        soup = BeautifulSoup(page.content(), "lxml")

        # 【核心 1：定位列表】
        # 政府网站的文章列表通常包裹在 ul, li 里，带有一些特定的 class，比如 .list 或 .nav
        # 这里我们通过抓取主要区域内的 <a> 标签来获取链接
        # 注意：如果抓不到，请在网页按 F12 检查实际的 class 名称，这里用相对宽泛的策略
        content_area = soup.find("div", class_="content") or soup.find("body")
        links = content_area.find_all("a")

        # 过滤出真正的文章链接（排除导航栏、翻页等无效链接）
        article_urls = []
        for a in links:
            href = a.get("href")
            title = a.get_text(strip=True)
            # 政府文件链接通常包含日期数字（如 202407/t20240716...）且标题较长
            if href and len(title) > 8 and "20" in href:
                # 把相对路径 (./xxx.html) 转换成完整的 http 链接
                full_url = urljoin(list_url, href)
                if full_url not in [item['url'] for item in article_urls]:
                    article_urls.append({"title": title, "url": full_url})

        print(f"✅ 成功提取到 {len(article_urls)} 篇文章链接！准备挨个抓取正文...")

        # 开始挨个抓取正文
        for idx, article in enumerate(article_urls):
            url = article["url"]
            # 过滤掉非法字符，防止文件名报错
            safe_title = "".join([c for c in article["title"] if c not in r'\/:*?"<>|'])
            save_path = os.path.join(save_dir, f"{safe_title}.txt")

            # 如果文件已存在，直接跳过（支持断点续传）
            if os.path.exists(save_path):
                print(f"⏭️ 文件已存在，跳过: {safe_title}")
                continue

            print(f"  -> 正在抓取 [{idx + 1}/{len(article_urls)}]: {safe_title}")
            try:
                # 访问正文页
                page.goto(url, wait_until="domcontentloaded")
                time.sleep(1.5)  # 💡 政府网站防反爬的核心：一定要喘口气！

                article_soup = BeautifulSoup(page.content(), "lxml")

                # 【核心 2：定位正文 - 终极加强版】
                # 尝试更多政府网站常用的 CSS 容器名
                content_div = (
                        article_soup.find(class_="xl-content") or
                        article_soup.find(id="zoom") or
                        article_soup.find(class_="article-content") or
                        article_soup.find(class_="view-TRS-HUDON") or
                        article_soup.find(class_="TRS_Editor") or  # 补充 TRS 常见类
                        article_soup.find(id="ucap-content") or  # 补充常见正文 ID
                        article_soup.find(class_="content")  # 最宽泛的 content
                )

                text = ""
                if content_div:
                    # 如果命中了上面的某个容器，直接提取里面的纯文本
                    text = content_div.get_text(separator="\n", strip=True)
                else:
                    # 💡 终极兜底方案：如果所有名字都没对上，直接把网页里所有 <p> (段落) 标签里的字抠出来！
                    paragraphs = article_soup.find_all("p")
                    text = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

                # 只要提取到的文字超过 50 个字，我们就认为抓取成功了
                if len(text) > 50:
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(f"【标题】{safe_title}\n【来源】{url}\n\n{text}")
                    print(f"  ✅ 正文抓取成功！字数: {len(text)}")
                else:
                    print(f"  ⚠️ 警告: 依然未能提取到有效正文，可能页面是纯图片或已失效: {url}")

            except Exception as e:
                print(f"  ❌ 抓取失败: {url}, 错误: {e}")

        browser.close()
        print("\n🎉 全部抓取任务完成！请查看本地文件夹。")


if __name__ == "__main__":
    scrape_tj_gov_documents()