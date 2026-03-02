import os
import requests
from dotenv import load_dotenv
load_dotenv()
api_key = os.environ.get('GEMINI_API_KEY')
models = ['gemini-flash-latest', 'gemini-flash-lite-latest']
with open('probe_aliases.txt', 'w') as f:
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        data = {"contents": [{"parts":[{"text": "ping"}]}]}
        resp = requests.post(url, json=data)
        f.write(f"Model: {m} | Status: {resp.status_code} | Error: {resp.json().get('error', {}).get('message', 'OK')}\n")
