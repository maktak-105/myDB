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
import database

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

def update_tent_price(tent_id: int, new_price: int):
    """
    指定したIDのテントの価格を更新します。
    """
    print(f"[DEBUG] Tool: update_tent_price(id={tent_id}, price={new_price})")
    db = next(get_db_session())
    try:
        db_tent = db.query(models.Tent).filter(models.Tent.id == tent_id).first()
        if not db_tent:
            return f"テントID {tent_id} は見つかりませんでした。"
        old_price = db_tent.price
        db_tent.price = new_price
        db.commit()
        return f"テント {db_tent.name} (ID: {tent_id}) の価格を {old_price} 円から {new_price} 円に更新しました。"
    except Exception as e:
        return f"エラーが発生しました: {str(e)}"
    finally:
        db.close()

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

def add_tent(name: str, brand: str = None, price: int = None, capacity: int = None):
    """
    新しいテントをデータベースに追加します。
    """
    print(f"[DEBUG] Tool: add_tent(name={name}, brand={brand})")
    db = next(get_db_session())
    try:
        new_tent = models.Tent(name=name, brand=brand, price=price, capacity=capacity)
        db.add(new_tent)
        db.commit()
        db.refresh(new_tent)
        return f"新しいテント {name} (ID: {new_tent.id}) を登録しました。"
    finally:
        db.close()

# Initialize Gemini Model with Tools
model = genai.GenerativeModel(
    model_name='models/gemini-1.5-flash-latest',
    tools=[list_tents, search_tents, get_tent_by_id, get_tent_stats, update_tent_price, delete_tent_by_id, add_tent]
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
        
        print(f"[DEBUG] AI response: {response.text}")
        return {"response": response.text}
    except Exception as e:
        print(f"[ERROR] Chat error: {str(e)}")
        traceback.print_exc()
        # If error occurs (e.g. session expired or invalid), reset session
        if session_id in chats:
            del chats[session_id]
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

# Serve Frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")
