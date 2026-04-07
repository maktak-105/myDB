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

def scan():
    print("--- 1. Searching for '煩悩テント' ---")
    query_url = f"https://api.notion.com/v1/databases/{db_id}/query"
    # Find the page named '煩悩テント'
    filter_data = {"filter": {"property": "名前", "title": {"contains": "煩悩テント"}}}
    res = httpx.post(query_url, headers=headers, json=filter_data).json()
    
    if not res.get("results"):
        print("BONNOU-TENT page not found in DB.")
        return
    
    parent_id = "10c9fa68-e7ac-809a-8512-eca278b82750" # 煩悩テント
    print(f"Parent ID (Hardcoded): {parent_id}")
    
    print("\n--- 2. Listing child pages/blocks ---")
    blocks_url = f"https://api.notion.com/v1/blocks/{parent_id}/children"
    children = httpx.get(blocks_url, headers=headers).json()
    
    results = children.get("results", [])
    print(f"Found {len(results)} children.")
    
    # Try finding the first 'child_page' type block
    tent_pages = [b for b in results if b["type"] == "child_page"]
    print(f"Tent pages found: {len(tent_pages)}")
    
    if tent_pages:
        first_tent = tent_pages[0]
        print(f"Sample Tent Page: {first_tent['child_page']['title']} (ID: {first_tent['id']})")
        
        print("\n--- 3. Reading content blocks of the first tent ---")
        content_url = f"https://api.notion.com/v1/blocks/{first_tent['id']}/children"
        content = httpx.get(content_url, headers=headers).json()
        
        print("Page Content Snippet:")
        for block in content.get("results", [])[:10]:
            btype = block["type"]
            if btype == "paragraph":
                text = "".join(t.get("plain_text", "") for t in block["paragraph"].get("rich_text", []))
                print(f"  [Text] {text}")
            elif btype == "bulleted_list_item":
                text = "".join(t.get("plain_text", "") for t in block["bulleted_list_item"].get("rich_text", []))
                print(f"  [List] {text}")
            else:
                print(f"  [{btype}] ...")

if __name__ == "__main__":
    scan()
