from google import genai
import os
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options={'api_version': 'v1beta'})
with open('exact_models.txt', 'w') as f:
    for m in client.models.list():
        f.write(f"{m.name}\n")
