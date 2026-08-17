from __future__ import print_function
import base64
import os.path
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def gmail_authenticate():
    creds = None
    # 如果已经登录过，直接用 token.json 里的授权
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # 如果没有 token.json，就重新登录一次
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "YOURJSONFILENAME", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # 保存 token.json 供下次用
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

def create_message(sender, to, subject, message_text):
    """创建邮件格式"""
    message = MIMEText(message_text, "plain", "utf-8")
    message["to"] = to
    message["from"] = sender
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}

def send_message(service, user_id, message):
    """发送邮件"""
    try:
        sent_message = (
            service.users().messages().send(userId=user_id, body=message).execute()
        )
        print(f'✅ 邮件已发送，ID: {sent_message["id"]}')
        return sent_message
    except Exception as error:
        print(f"❌ 出错: {error}")
        return None
