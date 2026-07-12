"""发现报告 API 直接调用工具"""
import json
import sys
import urllib.request
import urllib.error

API_KEY = "sk-PSDVXUZKVYM02M54aUUbafd923fe3lkl"
BASE_URL = "https://api.fxbaogao.com/mcp/"


def call_api(method: str, params: dict) -> dict:
    """调用发现报告 MCP API"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    
    req = urllib.request.Request(
        BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}


def search_reports(keywords: str, start_time: str = None, org_names: list = None) -> dict:
    """搜索研报"""
    params = {"keywords": keywords}
    if start_time:
        params["startTime"] = start_time
    if org_names:
        params["orgNames"] = org_names
    return call_api("tools/call", {"name": "search_reports", "arguments": params})


def get_paragraphs(report_id: int, keyword: str) -> dict:
    """获取报告段落"""
    return call_api("tools/call", {
        "name": "get_paragraphs",
        "arguments": {"reportId": report_id, "keyword": keyword}
    })


def get_pdf_url(report_id: int) -> dict:
    """获取PDF下载地址"""
    return call_api("tools/call", {
        "name": "get_pdf_url",
        "arguments": {"reportId": report_id}
    })


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python fxbaogao_api.py search <关键词> [时间范围]")
        print("  python fxbaogao_api.py paragraphs <报告ID> <关键词>")
        print("  python fxbaogao_api.py pdf <报告ID>")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "search":
        keywords = sys.argv[2] if len(sys.argv) > 2 else ""
        start_time = sys.argv[3] if len(sys.argv) > 3 else None
        result = search_reports(keywords, start_time)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif action == "paragraphs":
        report_id = int(sys.argv[2])
        keyword = sys.argv[3] if len(sys.argv) > 3 else ""
        result = get_paragraphs(report_id, keyword)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif action == "pdf":
        report_id = int(sys.argv[2])
        result = get_pdf_url(report_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
