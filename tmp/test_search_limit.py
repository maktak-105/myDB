import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def test_grounding():
    model_name = 'models/gemini-3.1-flash-lite-preview'
    print(f"Testing Google Search Grounding with {model_name}...")
    
    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            tools=[{"google_search_retrieval": {}}]
        )
        
        response = model.generate_content("AmazonでのColemanツーリングドームの最新価格を調べて")
        print("--- Response ---")
        print(response.text)
        print("--- Grounding Metadata ---")
        if response.candidates[0].grounding_metadata:
            print(response.candidates[0].grounding_metadata)
    except Exception as e:
        print(f"\n[ERROR] Failed: {e}")

if __name__ == "__main__":
    test_grounding()
