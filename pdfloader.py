import sqlite3
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
from huggingface_hub import login
from langchain_community.vectorstores import Chroma
import json


login("YOUR_HUGGING_FACE_ACCOUNT")

def load_products():
    con = sqlite3.connect("example.db")
    cursor = con.cursor()
    cursor.execute("SELECT product_id, name, category, type, description, price, inventory_count FROM products;")
    rows = cursor.fetchall()
    con.close()
    
    docs, ids = [], []
    for row in rows:
        product_id, name, category, type_, description, price, inventory = row
        text = f"""
        Product: {name}
        Category: {category}
        Type: {type_}
        Description: {description}
        Price: {price}
        Inventory: {inventory}
        """
        docs.append(Document(page_content=text, metadata={"product_id": product_id}))
        ids.append(str(product_id))   # 用 product_id 作为唯一 ID
    return docs, ids

def build_vectorstore():
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
    docs, ids = load_products()
    # persist_directory = "./chroma_db" 用来存储向量库
    vectorstore = Chroma(embedding_function=embeddings, persist_directory="./chroma_db")
    vectorstore.add_documents(docs, ids=ids)
    vectorstore.persist()
    
    print("✅ Chroma vectorstore 已保存到 ./chroma_db")

build_vectorstore()

def insert_products(products_json: str):
    """
    插入多条产品数据到数据库。
    输入必须是一个 JSON 数组，每个元素是一个产品。
    """

    print(products_json)
    cleaned = products_json.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    try:
        data_list = json.loads(cleaned)
        print("it use json.loads")

        # data_list = products_json  # 兼容 dict/list
        # print("it use dict or list")

        con = sqlite3.connect("example.db")
        cursor = con.cursor()

        for data in data_list:
            name = data.get("name")
            category = data.get("category")
            type = data.get("type")
            description = data.get("description")
            price = data.get("price")
            inventory_count = data.get("inventory_count")
            information = data.get("information", "")

            cursor.execute("SELECT product_id FROM products WHERE name = ?", (name,))
            existing = cursor.fetchone()

            if existing:  # 存在则更新
                cursor.execute("""
                    UPDATE products
                    SET category = ?, type = ?, description = ?, price = ?, inventory_count = ?, information = ?, updated_at = datetime('now','localtime')
                    WHERE name = ?
                """, (category, type, description, price, inventory_count, information, name))
                
            else:  # 不存在则插入
                cursor.execute("""
                    INSERT INTO products (name, category, type, description, price, inventory_count, information)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (name, category, type, description, price, inventory_count, information))
                
        con.commit()
        con.close()

        build_vectorstore()

        return f"✅ 插入成功 {len(data_list)} 条产品"
    except Exception as e:
        return f"❌ 插入失败: {str(e)}"