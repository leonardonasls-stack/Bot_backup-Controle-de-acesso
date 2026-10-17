import httpx
import re

client = httpx.Client(verify=False, follow_redirects=True)
resp = client.get("https://localhost:30443")
scripts = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', resp.text)
for s in scripts:
    s_clean = s.lstrip('.').lstrip('/')
    try:
        r = client.get(f"https://localhost:30443/{s_clean}")
        if "resourceFactory" in r.text:
            print("resourceFactory encontrada em:", s)
            for line in r.text.split("\n"):
                if "resourceFactory" in line or "$resource" in line:
                    print("   ", line.strip()[:140])
    except Exception as e:
        pass
