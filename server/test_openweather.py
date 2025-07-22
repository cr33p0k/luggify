import httpx

key = "dacbd5f796e027ca2e33edaff6cc7204"
url = "http://api.openweathermap.org/geo/1.0/direct"
params = {"q": "lond", "limit": 1, "appid": key}

response = httpx.get(url, params=params)
print(response.status_code)
print(response.text)
