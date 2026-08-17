import sqlite3
from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from datetime import datetime
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from huggingface_hub import login
from gmailapi import gmail_authenticate,create_message,send_message


load_dotenv()

login("YOUR_HUGGING_FACE_ACCOUNT")


llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",  # 你可以换成 gemini-1.5-pro
    temperature=0
)



@tool
def query_products(question):
    """Every time the user asks about product information or want to update/change their order (not include in history conversation), you MUST call the provided function to check the product database. 
        Never answer product-related questions without first calling the function. 
        Always return the function results exactly as they are stored in the database: do not change wording, singular/plural forms, or paraphrase any field values. 
        If the user asks a follow-up question about products, call the function again to ensure the information is up to date."""
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
    vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    results = vectorstore.similarity_search(question, k=5)
    print(results)
    return [doc.page_content for doc in results]

@tool
def chat_response(text: str) -> str:
    """use this when you want to communicate with user, and this function doesn't return anything"""
    # response = llm.invoke(text)
    # if hasattr(response, 'content'):
    #     return response.content
    return 

@tool
def search_order(session):
    """
    根据 session 中的 username 和 id 查询该用户的订单
    """
    if not session.get("is_logged_in"):
        return "⚠️ 请先登录！"

    user_id = session.get("id")
    username = session.get("username")

    con = sqlite3.connect("example.db")
    cursor = con.cursor()
    cursor.execute("""
        SELECT o.order_id, o.customer_id, o.product_id, p.name, o.order_date, 
            o.status, o.total_amount, o.tracking_number, 
            o.shipping_address, o.created_at, o.updated_at, quantity
        FROM orders o
        JOIN products p ON o.product_id = p.product_id
        WHERE o.customer_id = ?
    """, (user_id,))
    
    orders = cursor.fetchall()
    con.close()

    if not orders:
        return f"用户 {username} 暂无订单记录。"

    # 格式化订单信息
    order_list = []
    for order in orders:
        order_id, customer_id, product_id, product_name, order_date, status, total_amount, tracking_number, shipping_address, created_at, update_at, quantity = order
        order_list.append(f"订单号: {order_id} | 日期: {order_date} | 金额: {total_amount} | 产品数量：{quantity}| 产品名称:{product_name} | 状态:{status}")

    result = f"用户 {username} 的订单记录：\n" + "\n".join(order_list)
    return result

@tool
def update_order(order_id:int, product_name:str, quantity:int, session):
    """
    当用户想要更改他的产品订单,必须先使用**query_products**的tool获取产品详情,再使用这个tool,以便更了解整体的上下文
    输入该订单号(order_id),要改成什么产品的名字(product_name),和产品的数量(quantity)
    根据 session 中的 username 和 id 查询该用户的订单
    如果找不到产品时候记得先使用query_product 获取产品信息，如果真的没有该产品再回复用户
    """
    con = sqlite3.connect("example.db")
    cursor = con.cursor()
    cursor.execute('SELECT product_id, price FROM products WHERE name=?',(product_name,))

    row = cursor.fetchone()
    if not row:
        con.close()
        return {"error": f"产品 {product_name} 不存在"}
    
    product_id, product_price = row
    total_amount = float(product_price) * quantity
    customer_id = session.get("id")

    cursor.execute('SELECT p.name, o.quantity, o.total_amount FROM orders o JOIN products p ON o.product_id = p.product_id WHERE o.order_id = ? AND o.customer_id = ?',
                    (order_id, customer_id))
    row = cursor.fetchone()
    if not row:
        con.close()
        return {"error": f"订单 {order_id} 不存在"}
    
    p_product_name, p_quantity, p_total = row

    cursor.execute("""
        UPDATE orders
        SET product_id = ?, quantity = ?, total_amount = ?, updated_at = ?
        WHERE order_id = ? AND customer_id =?
    """, (product_id, quantity, total_amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), order_id, customer_id))

    con.commit()
    con.close()

    service = gmail_authenticate()
    sender = "123@gmail.com"
    to = "123@gmail.com"
    subject = "AI Ecommerce Support -- Update Order"
    message_text = f"Hello, you have change your order {order_id} \n Previous: \n Product:{p_product_name}\n Quantity:{p_quantity} \n Total Amount:{p_total} \n\n Present:Product:{product_name}\n Quantity:{quantity} \n Total Amount:{total_amount}"

    message = create_message(sender, to, subject, message_text)
    send_message(service, "me", message)

    return {
        "order_id": order_id,
        "product_name": product_name,
        "quantity": quantity,
        "total_amount": total_amount,
        "详情": "订单已更新,且已经邮件给用户了"
    }

@tool
def cancel_order(order_id:int, session):
    """
    当用户要取消他的订单，输入订单号已取消
    根据 session 中的 username 和 id 查询该用户的订单
    """
    customer_id = session.get("id")

    con = sqlite3.connect("example.db")
    cursor = con.cursor()
    cursor.execute('SELECT product_id FROM orders WHERE order_id=? AND customer_id=?',(order_id, customer_id))
    row = cursor.fetchone()
    if not row:
        con.close()
        return {"error": f"订单 {order_id} 不存在"}

    cursor.execute('UPDATE orders SET status=? WHERE order_id=? AND customer_id=?',("cancel", order_id, customer_id))

    con.commit()
    con.close()

    service = gmail_authenticate()
    sender = "123@gmail.com"
    to = "123@gmail.com"
    subject = "AI Ecommerce Support -- Cancel Order"
    message_text = f"Hello, you have cancel your order {order_id}"

    message = create_message(sender, to, subject, message_text)
    send_message(service, "me", message)

    return f"the order{order_id} is cancel"