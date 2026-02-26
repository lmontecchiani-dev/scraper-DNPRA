import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

def verify_farm():
    results = {
        "farm_status": "starting",
        "keys": []
    }
    
    gemini_keys_str = os.getenv("GEMINI_API_KEYS")
    if not gemini_keys_str:
        results["farm_status"] = "error: no keys found"
        with open("verify_farm_results.json", "w") as f:
            json.dump(results, f, indent=4)
        return

    keys = [k.strip() for k in gemini_keys_str.split(",") if k.strip()]
    results["farm_status"] = "processing"
    
    for i, key in enumerate(keys):
        key_info = {
            "index": i + 1,
            "key_prefix": key[:10] + "...",
            "status": "unknown"
        }
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model='gemini-flash-latest',
                contents=["Hi"]
            )
            key_info["status"] = "OK"
            key_info["response"] = response.text.strip()
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                key_info["status"] = "QUOTA_EXHAUSTED"
            elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
                key_info["status"] = "PERMISSION_DENIED"
            else:
                key_info["status"] = "ERROR"
                key_info["error_details"] = error_msg[:100]
        
        results["keys"].append(key_info)
    
    results["farm_status"] = "complete"
    with open("verify_farm_results.json", "w") as f:
        json.dump(results, f, indent=4)
    print("Verification complete. Results saved to verify_farm_results.json")

if __name__ == "__main__":
    verify_farm()
