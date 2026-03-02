import os
import requests
from dotenv import load_dotenv
load_dotenv()
api_key = os.environ.get('GEMINI_API_KEY')
m = 'gemini-2.0-flash-lite'
url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
data = {"contents": [{"parts":[{"text": "hola"}]}]}
resp = requests.post(url, json=data)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")
