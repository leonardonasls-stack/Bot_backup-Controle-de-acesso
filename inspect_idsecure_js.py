import httpx
import re

client = httpx.Client(verify=False, follow_redirects=True)
resp = client.get("https://localhost:30443")
scripts = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', resp.text)
print("Scripts encontrados:", scripts)

for s in scripts:
    s_url = f"https://localhost:30443/{s.lstrip('/')}"
    try:
        r_js = client.get(s_url)
        content = r_js.text
        if "templatesImages" in content or "canUseFacial" in content or "photoTimestamp" in content:
            print(f"Match importante em: {s}")
            # Procura trechos de upload ou atribuição
            matches = re.findall(r'[^;{}]{0,50}(?:templatesImages|photoTimestamp|fotoDoc|foto)[^;{}]{0,50}', content)
            for m in matches[:10]:
                print("   Snippet:", m.strip())
    except Exception as e:
        print("Erro lendo script:", e)
