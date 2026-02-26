import os
import requests
from google import genai
from dotenv import load_dotenv

load_dotenv()

def final_verification():
    api_key = os.getenv("GEMINI_API_KEY")
    
    print("--- 1. Testing with DIRECT URL (v1beta) ---")
    m = 'gemini-flash-latest'
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
    data = {"contents": [{"parts":[{"text": "ping"}]}]}
    try:
        resp = requests.post(url, json=data)
        print(f"Model: {m} | Status: {resp.status_code}")
        if resp.status_code == 200:
            print("✅ Direct URL is WORKING.")
        else:
            print(f"❌ Direct URL failed: {resp.text[:200]}")
    except Exception as e:
        print(f"Error direct URL: {e}")

    print("\n--- 2. Testing with SDK (google-genai) ---")
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=["Hello, are you ready?"]
        )
        print(f"✅ SDK is WORKING. Response: {response.text.strip()}")
    except Exception as e:
        print(f"❌ SDK failed: {e}")

if __name__ == "__main__":
    final_verification()
