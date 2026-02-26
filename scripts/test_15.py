import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def test_15():
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    
    models_to_test = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro"
    ]
    
    for m in models_to_test:
        print(f"Testing {m}...")
        try:
            response = client.models.generate_content(
                model=m,
                contents=["Hi"]
            )
            print(f"✅ {m} Success: {response.text.strip()}")
        except Exception as e:
            print(f"❌ {m} Failed: {str(e)[:100]}")

if __name__ == "__main__":
    test_15()
