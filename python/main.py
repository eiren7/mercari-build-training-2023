import os
import logging
import pathlib
import sqlite3
import hashlib
from fastapi import FastAPI, Form, HTTPException, status, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
logger = logging.getLogger("uvicorn")
logger.level = logging.INFO
images = pathlib.Path(__file__).parent.resolve() / "images"
origins = [ os.environ.get('FRONT_URL', 'http://localhost:3000') ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET","POST","PUT","DELETE"],
    allow_headers=["*"],
)

#import json
with open("items.json") as f:
    items = json.load(f)
items_list = items["items"]

@app.get("/")
def root():
    return {"message": "Hello, world!"}

@app.post("/items")
async def add_item(name: str = Form(...),
                   category: str = Form(...),
                   image: UploadFile = File(...)):
    ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png']
    def is_image_file(filename: str) -> bool:
        extension = os.path.splitext(filename)[1].lower()
        return extension in ALLOWED_IMAGE_EXTENSIONS
    if not is_image_file(image.filename):
        raise HTTPException(status_code=400, detail="Invalid image file")
    
    image_bytes = await image.read() # turn the image into a buffer-like object
    image_hashed = hashlib.sha256(image_bytes).hexdigest()  # hash the image
    new_image_name = image_hashed + ".jpg"
    with open(f"./images/{new_image_name}", "wb") as f:
        f.write(image_bytes)  # write the hashed image to a file
    
    connection = sqlite3.connect("../db/mercari.sqlite3") # connect to database
    cursor = connection.cursor()

    category_sql = "INSERT INTO category (name) VALUES (?)"
    cursor.execute(category_sql, (category,))

    sql = "INSERT INTO items (name, category_id, image_name) VALUES (?, ?, ?)"
    new_item = (name, category, new_image_name)
    cursor.execute(sql, new_item)
    connection.commit()

    logger.info(f"Receive item: {name}")
    return {"message": f"item received: {name}"}

@app.get("/items")
def listed_items():
    connection = sqlite3.connect("../db/mercari.sqlite3")
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM items")
    rows = cursor.fetchall()
    connection.close()

    return {"items": rows}

@app.get("/search")
def search_items(keyword: str):
    connection = sqlite3.connect("../db/mercari.sqlite3")
    cursor = connection.cursor()

    if keyword:
        cursor.execute(
            "SELECT items.id, items.name, category.name AS category_name, items.image_name "
            "FROM items "
            "JOIN category ON items.category_id = category.id "
            "WHERE items.name LIKE ?",
            ('%' + keyword + '%',))
    else:
        return {"message": "Not found"}

    rows = cursor.fetchall()

    items = []  
    for row in rows:
        id, name, category_name, image_name = row
        item = {
            "id": id,
            "name": name,
            "category_name": category_name,
            "image_name": image_name
        }
        items.append(item)

    if len(items) == 0:
        return {"message": "Not found"}
    
    return {"items": items}

@app.get("/image/{image_filename}")
async def get_image(image_filename):
# Create image path
    image = images / image_filename

    if not image_filename.endswith(".jpg"):
        raise HTTPException(status_code=400, detail="Image path does not end with .jpg")

    if not image.exists():
        logger.debug(f"Image not found: {image}")
        image = images / "default.jpg"
    return FileResponse(image)
