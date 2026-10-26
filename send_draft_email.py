"""Email an AI-generated draft to the owner's review inbox. No publishing."""
import os
from pathlib import Path
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from email.header import Header

RECIPIENT = "lovethursday@naver.com"

def send_draft(path):
    username = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("SMTP_USER and SMTP_PASSWORD GitHub Secrets are required")
    draft = Path(path)
    if not draft.is_file() or not draft.stat().st_size:
        raise RuntimeError("Draft file missing or empty; email not sent")
    content = draft.read_text(encoding="utf-8")
    heading = next((line.removeprefix("# ").strip() for line in content.splitlines() if line.startswith("# ")), "AI 블로그 원고")
    subject = ("[블로그 원고 검토] " + heading)[:160]
    message = EmailMessage()
    message["From"] = formataddr((str(Header("블로그 AI 초안", "utf-8")), username))
    message["To"] = RECIPIENT
    message["Subject"] = subject
    message.set_content("이 글은 AI가 생성한 검증 전 초안입니다. 사실관계를 확인하기 전에는 발행하지 마세요.\n\n" + content, charset="utf-8")
    message.add_attachment(content.encode("utf-8"), maintype="text", subtype="markdown", filename="free-draft.md")
    with smtplib.SMTP_SSL("smtp.naver.com", 465, context=ssl.create_default_context(), timeout=25) as server:
        server.login(username, password)
        server.send_message(message)
    print("Draft review email sent to " + RECIPIENT)

if __name__ == "__main__":
    send_draft("output/drafts/free-draft.md")
