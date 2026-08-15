import httpx

r = httpx.get("https://api.groq.com")
print(r.status_code)