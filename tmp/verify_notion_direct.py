import os
import httpx
from dotenv import load_dotenv

# Load config
load_dotenv()
token = (os.getenv("NOTION_TOKEN") or "").strip()
db_id = (os.getenv("NOTION_DATABASE_ID") or "").strip()

print(f"--- VERIFICATION START ---")
print(f"Target DB: {db_id}")

headers = {
    "Authorization": f"Bearer {token}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

try:
    with httpx.Client() as client:
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        print(f"URL: {url}")
        response = client.post(url, headers=headers, json={})
        
        print(f"HTTP Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            print(f"SUCCESS: Found {len(results)} items.")
            
            # Print actual data as evidence
            for i, p in enumerate(results[:3]): # Show first 3 for brevity
                props = p.get("properties", {})
                title_p = props.get("Name") or props.get("名前") or {}
                title = "".join(t.get("plain_text", "") for t in title_p.get("title", []))
                print(f"  [{i+1}] {title}")
        else:
            print(f"FAILED: {response.text}")
except Exception as e:
    print(f"EXCEPTION: {str(e)}")
