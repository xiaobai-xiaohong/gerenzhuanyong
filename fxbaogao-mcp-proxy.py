"""本地 MCP 代理：桥接 Hermes → fxbaogao MCP
启动方式：python fxbaogao-mcp-proxy.py
"""
import json
import sys
import urllib.request
import urllib.error

API_KEY = "sk-PSDVXUZKVYM02M54aUUbafd923fe3lkl"
REMOTE_URL = "https://api.fxbaogao.com/mcp/"


def proxy_request(request_bytes: bytes) -> bytes:
    """转发 JSON-RPC 请求到远程 MCP 服务器"""
    req = urllib.request.Request(
        REMOTE_URL,
        data=request_bytes,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": f"HTTP {e.code}: {e.reason}"},
            "id": None,
        }).encode()


def main():
    """stdio MCP 代理主循环"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        # 转发到远程服务器
        response = proxy_request(line.encode("utf-8"))
        sys.stdout.buffer.write(response)
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
