import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def ping_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not found in .env")
        return

    print(f"Testing API key: {api_key[:10]}...{api_key[-5:]}")
    
    try:
        client = genai.Client(api_key=api_key)
        
        print("\n--- Listing All Available Models ---")
        for model in client.models.list():
            print(f"- {model.name} (DisplayName: {model.display_name})")
            
        test_models = [
            'gemini-2.0-flash', 
            'gemini-1.5-flash', 
            'models/gemini-1.5-flash',
            'gemini-1.5-flash-8b', 
            'models/gemini-1.5-flash-8b',
            'gemini-1.5-pro',
            'models/gemini-1.5-pro'
        ]
        
        for model_id in test_models:
            print(f"Pinging {model_id}...")
            try:
                response = client.models.generate_content(
                    model=model_id,
                    contents=["Hello, are you there? Reply with 'YES'"]
                )
                print(f"✅ {model_id} is working! Response: {response.text.strip()}")
            except Exception as e:
                print(f"❌ {model_id} failed: {e}")

    except Exception as e:
        print(f"❌ General Error: {e}")

if __name__ == "__main__":
    ping_gemini()
