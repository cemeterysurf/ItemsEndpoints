import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import databases


from fastapi.encoders import jsonable_encoder
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Float


from pydantic import BaseModel


SQLALCHEMY_DATABASE_URL = "sqlite:///./data.db"


Base = declarative_base()

database = databases.Database(SQLALCHEMY_DATABASE_URL)

metadata = sqlalchemy.MetaData()

items = sqlalchemy.Table(
    "items",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String),
    sqlalchemy.Column("description", sqlalchemy.String),
    sqlalchemy.Column("price", sqlalchemy.Integer),
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, echo=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()

Base.metadata.create_all(bind=engine)


class ItemM(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), nullable=False, unique=True, index=True)
    description = Column(String(200))
    price = Column(Float(precision=2), nullable=False)


class ItemSBase(BaseModel):
    name: str
    description: Optional[str] = None
    price : float


class ItemSCreate(ItemSBase):
    pass


class ItemS(ItemSBase):
    id: int

    class Config:
        orm_mode = True


class ItemRepo:

    async def create(db: SessionLocal, item: ItemSCreate):
        db_item = ItemM(name=item.name, description=item.description, price=item.price,)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item

    def fetch_by_id(db: SessionLocal, _id):
        return db.query(ItemM).filter(ItemM.id == _id).first()

    def fetch_by_name(db: SessionLocal, name):
        return db.query(ItemM).filter(ItemM.name == name).first()

    def fetch_all(db: SessionLocal, skip: int = 0, limit: int = 100):
        return db.query(ItemM).offset(skip).limit(limit).all()

    async def delete(db: SessionLocal, item_id):
        db_item = db.query(ItemM).filter_by(id=item_id).first()
        db.delete(db_item)
        db.commit()

    async def update(db: SessionLocal, item_data):
        updated_item = db.merge(item_data)
        db.commit()
        return updated_item


@app.post('/items', tags=["Item"], response_model=ItemS, status_code=201)
async def create_item(item_request: ItemSCreate, db: SessionLocal = Depends(get_db)):

    db_item = ItemRepo.fetch_by_name(db, name=item_request.name)
    if db_item:
        raise HTTPException(status_code=400, detail="Item already exists!")

    return await ItemRepo.create(db=db, item=item_request)


@app.get('/items', tags=["Item"], response_model=List[ItemS])
def get_all_items(name: Optional[str] = None, db: SessionLocal = Depends(get_db)):

    if name:
        items = []
        db_item = ItemRepo.fetch_by_name(db, name)
        items.append(db_item)
        return items
    else:
        return ItemRepo.fetch_all(db)


@app.get('/items/{item_id}', tags=["Item"], response_model=ItemS)
def get_item(item_id: int, db: SessionLocal = Depends(get_db)):

    db_item = ItemRepo.fetch_by_id(db, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found with the given ID")
    return db_item


@app.delete('/items/{item_id}', tags=["Item"])
async def delete_item(item_id: int, db: SessionLocal = Depends(get_db)):

    db_item = ItemRepo.fetch_by_id(db, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found with the given ID")
    await ItemRepo.delete(db, item_id)
    return "Item deleted successfully!"


@app.put('/items/{item_id}', tags=["Item"], response_model=ItemS)
async def update_item(item_id: int, item_request: ItemS, db: SessionLocal = Depends(get_db)):

    db_item = ItemRepo.fetch_by_id(db, item_id)
    if db_item:
        update_item_encoded = jsonable_encoder(item_request)
        db_item.name = update_item_encoded['name']
        db_item.price = update_item_encoded['price']
        db_item.description = update_item_encoded['description']
        return await ItemRepo.update(db=db, item_data=db_item)
    else:
        raise HTTPException(status_code=400, detail="Item not found with the given ID")

if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)
