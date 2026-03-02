from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

models = [
    'gemini-2.0-flash', 
    'gemini-2.5-flash', 
    'gemini-flash-latest', 
    'gemini-2.0-flash-lite',
    'gemini-1.5-flash-8b'
]

with open('quota_final_test.txt', 'w', encoding='utf-8') as f:
    for model in models:
        f.write(f"Testing {model}...\n")
        try:
            res = client.models.generate_content(model=model, contents="Responde solo con la palabra OK")
            f.write(f"  {model}: SUCCESS (Response: {res.text})\n")
        except Exception as e:
            f.write(f"  {model}: FAILED - {str(e)}\n")
        f.write("-" * 20 + "\n")
