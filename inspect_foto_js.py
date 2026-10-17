import httpx

client = httpx.Client(verify=False, follow_redirects=True)
for path in ["common/foto.js", "common/services.js", "app/config.js", "common/biometria.js"]:
    r = client.get(f"https://localhost:30443/{path}")
    print(f"=== {path} (status: {r.status_code}) ===")
    if r.status_code == 200:
        lines = r.text.split("\n")
        print("\n".join(lines[:60]))
