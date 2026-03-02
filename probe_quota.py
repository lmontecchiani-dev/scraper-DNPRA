import os
import requests
from dotenv import load_dotenv
load_dotenv()
api_key = os.environ.get('GEMINI_API_KEY')
models_to_test = [
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
    'gemini-1.5-flash',
    'gemini-2.0-flash-exp'
]
with open('quota_probe.txt', 'w') as f:
    for m in models_to_test:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        data = {"contents": [{"parts":[{"text": "ping"}]}]}
        resp = requests.post(url, json=data)
        status = resp.status_code
        error = resp.json().get('error', {}).get('message', 'OK')
        f.write(f"Model: {m} | Status: {status} | Error: {error}\n")
