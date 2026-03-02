import os
import requests
from dotenv import load_dotenv
load_dotenv()
api_key = os.environ.get('GEMINI_API_KEY')
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
try:
    resp = requests.get(url)
    models = resp.json().get('models', [])
    for m in models:
        print(m['name'])
except Exception as e:
    print(e)
