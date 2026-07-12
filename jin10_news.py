"""金十数据快讯拉取工具"""
import requests
import re
import json
import sys


def get_jin10_news(keywords=None, hours=24):
    """
    获取金十数据最新快讯
    
    Args:
        keywords: 关键词列表，如 ['美伊','伊朗','冲突']。None则返回全部
        hours: 获取最近几小时的新闻，默认24小时
    
    Returns:
        list: 快讯列表，每条包含 time, content
    """
    url = 'https://www.jin10.com/flash_newest.js'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return [{"error": f"请求失败: {e}"}]
    
    # 解析JS变量
    match = re.search(r'var newest = (\[.*?\]);', r.text, re.DOTALL)
    if not match:
        return [{"error": "解析失败"}]
    
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        return [{"error": f"JSON解析失败: {e}"}]
    
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(hours=hours)
    
    results = []
    for item in data:
        t = item.get('time', '')
        content = item.get('data', {}).get('content', '') or item.get('data', {}).get('title', '')
        content = re.sub('<[^>]+>', '', str(content))
        
        # 时间过滤
        try:
            item_time = datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
            if item_time < cutoff:
                continue
        except:
            continue
        
        # 关键词过滤
        if keywords:
            if not any(k in content for k in keywords):
                continue
        
        results.append({"time": t, "content": content})
    
    return results


def print_news(news_list):
    """格式化打印快讯"""
    if not news_list:
        print("无相关快讯")
        return
    
    if "error" in news_list[0]:
        print(f"错误: {news_list[0]['error']}")
        return
    
    print(f"共 {len(news_list)} 条快讯")
    print("=" * 60)
    for item in news_list:
        print(f"  {item['time']}")
        print(f"  {item['content'][:150]}")
        print()


if __name__ == "__main__":
    # 默认关键词
    default_kw = ['美伊', '伊朗', '冲突', '霍尔木兹', '海峡', '油轮', '袭击', '制裁', 
                  '原油', '停火', '谈判', '战争', '导弹', '无人机']
    
    if len(sys.argv) > 1:
        # 支持自定义关键词
        keywords = sys.argv[1].split(',')
    else:
        keywords = default_kw
    
    hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    
    news = get_jin10_news(keywords=keywords, hours=hours)
    print_news(news)
