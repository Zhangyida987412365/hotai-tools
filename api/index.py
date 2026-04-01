import os
import imaplib
import email
from email.header import decode_header
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_verification_code(text):
    """从文本中提取 6 位数字验证码"""
    if text is None: return None
    match = re.search(r'\b\d{6}\b', str(text))
    if match:
        return match.group(0)
    return None

@app.get("/api/codes")
def get_verification_codes():
    try:
        # 1. 账号尽量也用环境变量，若没有则用默认
        EMAIL_ACCOUNT = os.environ.get("GMAIL_ACCOUNT", "yunfengyunyang@gmail.com")
        # 2. 从 Vercel 环境变量安全读取密码！！！这非常重要
        APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
        
        if not APP_PASSWORD:
            return {"status": "error", "message": "Vercel 环境变量中未设置 GMAIL_APP_PASSWORD 请去后台面板配置"}

        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, '(FROM "team@mail.perplexity.ai")')
        if status != "OK" or not messages[0]:
            return {"status": "success", "codes": []}

        mail_ids = messages[0].split()
        if not mail_ids:
            return {"status": "success", "codes": []}

        latest_id = mail_ids[-1]
        codes_data = []

        status, msg_data = mail.fetch(latest_id, "(RFC822)")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                subject_header = msg.get("Subject", "")
                subject = ""
                if subject_header:
                    decoded_list = decode_header(subject_header)
                    for text, encoding in decoded_list:
                        if isinstance(text, bytes):
                            subject += text.decode(encoding if encoding else "utf-8", errors="ignore")
                        else:
                            subject += str(text)
                
                from_ = msg.get("From", "")
                date_str = msg.get("Date", "")
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(date_str)
                    formatted_time = dt.astimezone().strftime("%m-%d %H:%M:%S")
                except Exception:
                    formatted_time = date_str
                
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            parsed_payload = part.get_payload(decode=True)
                            if parsed_payload:
                                body = parsed_payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                            break
                else:
                    parsed_payload = msg.get_payload(decode=True)
                    if parsed_payload:
                        body = parsed_payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")

                extracted_code = extract_verification_code(subject) or extract_verification_code(body)

                codes_data.append({
                    "from": from_,
                    "subject": subject,
                    "date": formatted_time,
                    "code": extracted_code,
                    "body_preview": body[:100] + "..." if body else "None"
                })

        mail.close()
        mail.logout()

        return {"status": "success", "codes": codes_data}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# 移除了原有的 uvicorn.run 因为 Vercel Serverless 环境会自动接管 app 对象实例
