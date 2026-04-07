import os
import httpx
from dotenv import load_dotenv

load_dotenv()
token = (os.getenv("NOTION_TOKEN") or "").strip()
db_id = (os.getenv("NOTION_DATABASE_ID") or "").strip()

headers = {
    "Authorization": f"Bearer {token}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def list_all():
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    res = httpx.post(url, headers=headers, json={}).json()
    
    print("--- PAGE LIST IN DATABASE ---")
    results = res.get("results", [])
    if not results:
        print("No pages found.")
        print(f"API Response: {res}")
        return

    for p in results:
        pid = p["id"]
        props = p.get("properties", {})
        # Find any typical title property
        title = ""
        for name, prop in props.items():
            if prop.get("type") == "title":
                title = "".join(t.get("plain_text", "") for t in prop.get("title", []))
                break
        print(f"ID: {pid} | Title: [{title}]")

if __name__ == "__main__":
    list_all()
