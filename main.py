import gradio as gr
import sqlite3
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent
from langchain.agents.agent_types import AgentType
from langchain_core.tools import tool
from langchain.document_loaders import PyPDFLoader
import glob
import os
import shutil
import json
from datetime import datetime

from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
from huggingface_hub import login
from langchain_core.messages import HumanMessage, SystemMessage
from tools import query_products,chat_response,search_order,update_order,cancel_order
from pdfloader import insert_products


load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",  # 你可以换成 gemini-1.5-pro
    temperature=0
)


tools = [chat_response, query_products, search_order, update_order, cancel_order]

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    verbose=True,
    agent_kwargs={
        "prefix":"""
            You are a assistant. You can answer questions directly,if needed, use tools such as query_product.
            If the user's question does not require any tools, respond directly. 
            The user's session info will be provided in the prompt as JSON under 'Session'.
            If you are unsure or no tools apply, respond politely without using any tools.
        """
},
    max_iterations=10,
    handle_parsing_errors=True
)


def init_session():
    return {"is_logged_in": False, "username": None, "role": None, "id": None}


def user_login(username, password, session):
    conn = sqlite3.connect("example.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE name=? AND password=?", (username, password))
    result = cursor.fetchone()

    conn.close()

    if result:
        customer_id = result[0]
        session.update({"is_logged_in": True, "username": username, "role": "user", "id":customer_id})
        return f"✅ Welcome User: {username}", session, gr.update(visible=True), gr.update(visible=False), []
    return "❌ Invalid user login", session, gr.update(visible=False), gr.update(visible=False), []

# Admin 登录
def admin_login(username, password, session):
    conn = sqlite3.connect("example.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE username=? AND password=?", (username, password))
    result = cursor.fetchone()
    conn.close()

    if result:
        session.update({"is_logged_in": True, "username": username, "role": "admin", "id": None})
        return f"✅ Welcome Admin: {username}", session, gr.update(visible=False), gr.update(visible=True), []
    return "❌ Invalid admin login", session, gr.update(visible=False), gr.update(visible=False), []


def chat_fn(message, history, session):
    if not session.get("is_logged_in"):
        return [("System", "⚠️ Please login first!")], history, session
    history = history or []

    # 1. 把 history 转成文本形式（方便 AI 记忆）
    history_text = ""
    for user_msg, bot_msg in history:
        history_text += f"User: {user_msg}\nAssistant: {bot_msg}\n"

    # 2. 拼接完整输入
    session_text = json.dumps(session, ensure_ascii=False)
    full_input = f"history:{history_text}\n\nSession: {session_text}\n\nCurrent conversation: \nUser: {message}"

    # 3. 调用 agent
    bot_reply = agent.run(full_input)

    # 4. 存到本地的 history（UI 显示用）
    history.append((message, bot_reply))

    return history, history, session


def upload_pdf(file):
    if file is not None:
        os.makedirs("uploads", exist_ok=True)
        # file 是一个路径字符串（NamedString），直接拷贝到 uploads
        dest_path = os.path.join("uploads", os.path.basename(file))
        shutil.copy(file, dest_path)

        loader = PyPDFLoader(dest_path)
        docs = loader.load()
        
        all_text = "\n\n".join([doc.page_content for doc in docs])

        print(f"the pdf content is : {all_text}")

        prompt = f"""
        You are an information extraction system.  
        Task: Extract all product information from the given PDF content.  

        ⚠️ Very Important Rules:
        1. Output MUST be a valid **JSON array** in string type.  
        2. Do NOT include any explanations, text, or commentary outside the JSON.  
        3. Each element in the JSON array represents one product.  
        4. Use exactly these keys for each product:  
        - "name" (string)  
        - "category" (string)  
        - "type" (string or null if not available)  
        - "description" (string or null if not available)  
        - "price" (number or null if not available)  
        - "inventory_count" (integer or null if not available)  
        - "information" (string or null if not available)  

        Input PDF Content:  
        
        {all_text}  


        Output only the JSON with string type to insert into function that require str parameter, with no additional text.
        """

        messages = [
            SystemMessage(content="You are a helpful assistant that convert product information in pdf into json "),
            HumanMessage(content= prompt)
        ]

        response = llm.invoke(messages)
        print(f"the AI response is: {response.content}")

        insert_products(response.content)


        pdf_files = glob.glob("uploads/*.pdf")
        for pdf in pdf_files:
            os.remove(pdf)
            
        return "pdf has been added into database successfully"

    return "⚠️ No file uploaded."




#以下是Interface 的部分===================================



with gr.Blocks(css=".gradio-container {background-color: #f9fafb; font-family: Arial;}") as demo:
    session = gr.State(init_session())

    # --- 登录区 ---
    with gr.Tab("👤 User Login"):
        gr.Markdown("## 👤 User Login")
        user_username = gr.Textbox(label="Username")
        user_password = gr.Textbox(label="Password", type="password")
        user_login_btn = gr.Button("Login as User")
        user_login_status = gr.Textbox(label="Status", interactive=False)

    with gr.Tab("🔑 Admin Login"):
        gr.Markdown("## 🔑 Admin Login")
        admin_username = gr.Textbox(label="Admin Username")
        admin_password = gr.Textbox(label="Admin Password", type="password")
        admin_login_btn = gr.Button("Login as Admin")
        admin_login_status = gr.Textbox(label="Status", interactive=False)

    # --- 功能区 ---
    with gr.Tab("💬 Chatbot", visible=False) as chatbot_tab:
        gr.Markdown("## 💬 Chat with AI")
        chatbot = gr.Chatbot()
        msg = gr.Textbox(label="Type your message")
        send_btn = gr.Button("Send")

        send_btn.click(chat_fn, inputs=[msg, chatbot, session], outputs=[chatbot, chatbot, session])

    with gr.Tab("📂 Admin Panel", visible=False) as admin_tab:
        gr.Markdown("## 📂 Admin PDF Upload")
        pdf_file = gr.File(label="Upload PDF", file_types=[".pdf"])
        upload_btn = gr.Button("Upload")
        upload_status = gr.Textbox(label="Upload Status")

        upload_btn.click(upload_pdf, inputs=[pdf_file], outputs=[upload_status])

    # --- 登录逻辑绑定 ---
    user_login_btn.click(
        user_login,
        inputs=[user_username, user_password, session],
        outputs=[user_login_status, session, chatbot_tab, admin_tab, chatbot]  # user 只能开chatbot
    )

    admin_login_btn.click(
        admin_login,
        inputs=[admin_username, admin_password, session],
        outputs=[admin_login_status, session, chatbot_tab, admin_tab, chatbot]  # admin 开chatbot + admin_tab
    )

demo.launch()