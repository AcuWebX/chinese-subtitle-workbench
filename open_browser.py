import time
import urllib.request
import webbrowser

url = "http://127.0.0.1:8766/"
for _ in range(60):
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            if response.status == 200:
                webbrowser.open(url)
                raise SystemExit(0)
    except Exception:
        time.sleep(0.5)
print("无法自动打开浏览器，请手动打开：" + url)
