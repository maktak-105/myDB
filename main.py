import os
from fastapi import FastAPI, Depends, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
import traceback
from typing import List, Optional, Dict, Any
import google.generativeai as genai
from dotenv import load_dotenv

import models
import schemas
import httpx
import database
from typing import Dict, Any, List

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI(title="Tents Database AI API")

# Helper for tool sessions
def get_db_session():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Tool: List and Filter Tents
def list_tents(skip: int = 0, min_price: Optional[float] = None, max_price: Optional[float] = None):
    """List all available tents with optional price filtering."""
    db = next(get_db_session())
    try:
        # Cast skip to int to ensure type safety
        skip = int(skip)
        
        query = db.query(models.Tent)
        if min_price is not None:
            query = query.filter(models.Tent.price >= min_price)
        if max_price is not None:
            query = query.filter(models.Tent.price <= max_price)
            
        tents = query.offset(skip).all()
        print(f"[DEBUG] Tool: list_tents(skip={skip}, min_price={min_price}, max_price={max_price}) - Found {len(tents)}")
        return [{"id": t.id, "name": t.name, "brand": t.brand, "price": t.price} for t in tents]
    finally:
        db.close()

# Tool: Search Tents by Name
def search_tents(query: str):
    """Search for tents by name or brand keyword."""
    db = next(get_db_session())
    try:
        tents = db.query(models.Tent).filter(
            (models.Tent.name.ilike(f"%{query}%")) | (models.Tent.brand.ilike(f"%{query}%"))
        ).limit(20).all()
        print(f"[DEBUG] Tool: search_tents(query='{query}') - Found {len(tents)}")
        return [{"id": t.id, "name": t.name, "brand": t.brand, "price": t.price} for t in tents]
    finally:
        db.close()

def get_tent_by_id(tent_id: int):
    """
    指定したIDのテントの詳細情報を取得します。
    """
    print(f"[DEBUG] Tool: get_tent_by_id(id={tent_id})")
    db = next(get_db_session())
    try:
        t = db.query(models.Tent).filter(models.Tent.id == tent_id).first()
        if not t:
            return f"テントID {tent_id} は見つかりませんでした。"
        return {
            "id": t.id, "name": t.name, "brand": t.brand, "price": t.price,
            "capacity": t.capacity, "material": t.material, "purchase_date": str(t.purchase_date)
        }
    finally:
        db.close()

def get_tent_stats():
    """
    テントの統計データ（合計数、平均価格など）を取得します。
    """
    print("[DEBUG] Tool: get_tent_stats()")
    db = next(get_db_session())
    try:
        count = db.query(func.count(models.Tent.id)).scalar()
        avg_price = db.query(func.avg(models.Tent.price)).scalar()
        return {
            "total_count": count,
            "avg_price": round(avg_price, 2) if avg_price else 0
        }
    finally:
        db.close()

def update_tent_fields(tent_id: int, updates: Dict[str, Any]):
    """
    指定したIDのテントの情報を「画面上のみ」更新提案します。
    更新可能なフィールド: name, brand, price, capacity, weight_kg, material, purchase_date, size_w, size_d, size_h, pack_w, pack_d, pack_h
    注意: このツールはDBを書き換えません。画面上で赤字（未保存）にするだけです。
    """
    import json
    proposal = {"id": tent_id, "updates": updates}
    return f"[UI_PROPOSAL: {json.dumps(proposal)}]"

def bulk_update_tents(tent_ids: List[int], updates: Dict[str, Any]):
    """
    複数のテントに対して、同一の変更を一括で「画面上のみ」更新提案します。
    注意: このツールはDBを書き換えません。画面上で赤字（未保存）にするだけです。
    """
    import json
    proposal = {"ids": tent_ids, "updates": updates}
    return f"[UI_BULK_PROPOSAL: {json.dumps(proposal)}]"

def delete_tent_by_id(tent_id: int):
    """
    指定したIDのテントを削除します。
    """
    print(f"[DEBUG] Tool: delete_tent_by_id(id={tent_id})")
    db = next(get_db_session())
    try:
        db_tent = db.query(models.Tent).filter(models.Tent.id == tent_id).first()
        if not db_tent:
            return f"テントID {tent_id} は見つかりませんでした。"
        name = db_tent.name
        db.delete(db_tent)
        db.commit()
        return f"テント {name} (ID: {tent_id}) を削除しました。"
    finally:
        db.close()

def add_tent(name: str, brand: str = None, price: float = None, capacity: float = None):
    """
    新しいテントをデータベースに追加します。
    """
    print(f"[DEBUG] Tool: add_tent(name={name}, brand={brand}, price={price}, capacity={capacity})")
    db = next(get_db_session())
    try:
        # Cast price to int if it's not None
        p_val = int(price) if price is not None else None
        new_tent = models.Tent(name=name, brand=brand, price=p_val, capacity=capacity)
        db.add(new_tent)
        db.commit()
        db.refresh(new_tent)
        return f"SUCCESS: 新しいテント {name} (ID: {new_tent.id}) を登録しました。"
    except Exception as e:
        db.rollback()
        print(f"[ERROR] add_tent failed: {str(e)}")
        return f"ERROR: 登録に失敗しました - {str(e)}"
    finally:
        db.close()

# --- Notion API Tools via Direct HTTP (httpx) ---

NOTION_API_VERSION = "2022-06-28"
# 「煩悩テント」親ページ ID
BONNOU_TENT_PARENT_ID = "10c9fa68-e7ac-809a-8512-eca278b82750"

def list_notion_tents() -> Any:
    """
    「煩悩テント」親ページの下にある子ページ（各テント）の一覧を取得します。
    """
    token = (os.getenv("NOTION_TOKEN") or "").strip()
    print(f"[DEBUG] Notion Sync: Fetching children of {BONNOU_TENT_PARENT_ID}")
    
    if not token: return "ERROR: Notion token missing."
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_API_VERSION
    }
    
    try:
        with httpx.Client() as client:
            url = f"https://api.notion.com/v1/blocks/{BONNOU_TENT_PARENT_ID}/children"
            response = client.get(url, headers=headers)
            
            if response.status_code != 200:
                return f"ERROR: API {response.status_code} - {response.text}"
                
            data = response.json()
            results = data.get("results", [])
            
            # Filter only child_page types
            output = []
            for b in results:
                if b["type"] == "child_page":
                    output.append({
                        "page_id": b["id"],
                        "name": b["child_page"].get("title", "Untitled Page")
                    })
            
            print(f"[DEBUG] Notion Sync: Found {len(output)} tent pages.")
            return output if output else "煩悩テントの下に子ページが見つかりませんでした。"
    except Exception as e:
        print(f"[ERROR] Notion Sync Exception: {str(e)}")
        return f"Error connecting to Notion: {str(e)}"

def get_notion_tent_detail(page_id: str) -> Any:
    """
    指定されたテントページの「本文（テキストブロック）」をすべて読み取り、平文（非構造化データ）として返します。
    """
    token = (os.getenv("NOTION_TOKEN") or "").strip()
    if not token: return "ERROR: Notion token missing."
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_API_VERSION
    }
    
    print(f"[DEBUG] Notion Content (Direct API): Reading blocks for {page_id}")
    try:
        with httpx.Client() as client:
            # Get block children (the page content)
            url = f"https://api.notion.com/v1/blocks/{page_id}/children"
            response = client.get(url, headers=headers)
            
            if response.status_code != 200:
                return f"ERROR: API {response.status_code} - {response.text}"
                
            data = response.json()
            results = data.get("results", [])
            
            # Extract plain text from paragraphs, list items, etc.
            text_parts = []
            for b in results:
                btype = b["type"]
                content_obj = b.get(btype, {})
                rich_text = content_obj.get("rich_text", [])
                text = "".join(t.get("plain_text", "") for t in rich_text)
                if text:
                    text_parts.append(text)
            
            full_text = "\n".join(text_parts)
            print(f"[DEBUG] Notion Content: Extracted {len(full_text)} characters.")
            
            # Return result as a dictionary containing the unstructured text for AI to parse
            return {
                "page_id": page_id,
                "unstructured_content": full_text
            }
    except Exception as e:
        print(f"[ERROR] Notion Content Failure: {str(e)}")
        return f"Failed to retrieve Notion page text: {str(e)}"

def add_notion_tent_to_db(page_id: str):
    """
    Notionのデータを取得し、ローカルのデータベースに「一発登録」します。
    """
    print(f"[DEBUG] Tool: add_notion_tent_to_db(page_id={page_id})")
    detail = get_notion_tent_detail(page_id)
    if isinstance(detail, str): return detail # Return error string
    
    if not detail.get("name") or detail.get("name") == "Unnamed Tent": 
        return "ERROR: Page has no valid name, cannot import."
    
    # Ensure numerical values are correctly typed for models.Tent
    try:
        price = float(detail.get("price")) if detail.get("price") is not None else 0.0
        capacity = float(detail.get("capacity")) if detail.get("capacity") is not None else 0.0
    except (ValueError, TypeError):
        price = 0.0
        capacity = 0.0

    return add_tent(
        name=detail["name"],
        brand=detail.get("brand"),
        price=price,
        capacity=capacity
    )

# --- End Notion Tools ---

# Initialize Gemini Model with Tools
model = genai.GenerativeModel(
    model_name='models/gemini-3.1-flash-lite-preview',
    tools=[
        list_tents, search_tents, get_tent_by_id, get_tent_stats, 
        update_tent_fields, bulk_update_tents, delete_tent_by_id, add_tent,
        list_notion_tents, get_notion_tent_detail, add_notion_tent_to_db
    ]
)

# In-memory chat storage
chats: Dict[str, Any] = {}

@app.post("/api/chat")
async def chat_with_agent(
    message: str = Body(..., embed=True),
    session_id: str = Body("default", embed=True)
):
    print(f"[DEBUG] Chat request from session {session_id}: {message}")
    try:
        # Get or create chat session
        if session_id not in chats:
            print(f"[DEBUG] Creating new session: {session_id}")
            chats[session_id] = model.start_chat(enable_automatic_function_calling=True)
        
        chat = chats[session_id]
        response = chat.send_message(message)
        
        # AI response rendering
        return {"response": response.text}
    except Exception as e:
        err_msg = f"Chat interaction failed: {str(e)}"
        print(f"[ERROR] {err_msg}")
        traceback.print_exc()
        
        # Reset session on error to allow recovery
        if session_id in chats:
            print(f"[DEBUG] Resetting session {session_id} due to error.")
            del chats[session_id]
            
        # Return a meaningful error to the UI instead of a raw 500 if possible
        # but here we still raise so the UI 'catch' block handles it locally
        raise HTTPException(status_code=500, detail=str(e))

# Existing CRUD Endpoints
@app.get("/tents", response_model=List[schemas.Tent])
def read_tents(skip: int = 0, db: Session = Depends(database.get_db)):
    tents = db.query(models.Tent).offset(skip).all()
    return tents

@app.get("/tents/stats", response_model=schemas.TentAggregates)
def get_stats_endpoint(db: Session = Depends(database.get_db)):
    return get_tent_stats()

@app.get("/tents/{tent_id}", response_model=schemas.Tent)
def read_tent(tent_id: int, db: Session = Depends(database.get_db)):
    db_tent = db.query(models.Tent).filter(models.Tent.id == tent_id).first()
    if db_tent is None:
        raise HTTPException(status_code=404, detail="Tent not found")
    return db_tent

@app.put("/tents/{tent_id}", response_model=schemas.Tent)
def update_tent(tent_id: int, tent: schemas.TentUpdate, db: Session = Depends(database.get_db)):
    db_tent = db.query(models.Tent).filter(models.Tent.id == tent_id).first()
    if db_tent is None:
        raise HTTPException(status_code=404, detail="Tent not found")
    update_data = tent.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tent, key, value)
    db.commit()
    db.refresh(db_tent)
    return db_tent

@app.post("/tents/batch")
def batch_update_tents(updates: Dict[int, Dict[str, Any]], db: Session = Depends(database.get_db)):
    """
    一括で複数のテント情報を更新します。
    """
    updated_count = 0
    for tent_id_str, fields in updates.items():
        try:
            tent_id = int(tent_id_str)
            db_tent = db.query(models.Tent).filter(models.Tent.id == tent_id).first()
            if db_tent:
                for key, value in fields.items():
                    setattr(db_tent, key, value)
                updated_count += 1
        except ValueError:
            continue
    db.commit()
    return {"status": "success", "updated_count": updated_count}

# Serve Frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")
