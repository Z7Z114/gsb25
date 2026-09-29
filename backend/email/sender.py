import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from pathlib import Path
from typing import List, Dict, Optional
import logging
import markdown

logger = logging.getLogger(__name__)


class EmailSender:
    """发送Markdown格式的会议纪要邮件给投资者和合作伙伴"""

    def __init__(
        self,
        smtp_host: str = None,
        smtp_port: int = None,
        smtp_user: str = None,
        smtp_password: str = None,
        smtp_from: str = None
    ):
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", 587))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.smtp_from = smtp_from or os.getenv("SMTP_FROM", self.smtp_user)

    def send_meeting_summary(
        self,
        to_recipients: List[str],
        subject: str,
        markdown_content: str,
        cc_recipients: List[str] = None,
        attachments: List[str] = None,
        meeting_data: Dict = None
    ) -> bool:
        """
        发送会议纪要邮件
        """
        logger.info(f"准备发送会议纪要邮件给: {to_recipients}")

        if cc_recipients is None:
            cc_recipients = []
        if attachments is None:
            attachments = []

        msg = MIMEMultipart("alternative")
        msg["From"] = self.smtp_from
        msg["To"] = ", ".join(to_recipients)
        if cc_recipients:
            msg["Cc"] = ", ".join(cc_recipients)
        msg["Subject"] = subject

        html_content = self._markdown_to_html(markdown_content)

        intro_text = self._build_intro(meeting_data)

        full_markdown = intro_text + "\n\n" + markdown_content
        full_html = self._markdown_to_html(intro_text) + "<br><br>" + html_content

        msg.attach(MIMEText(full_markdown, "plain", "utf-8"))
        msg.attach(MIMEText(full_html, "html", "utf-8"))

        for attachment_path in attachments:
            self._add_attachment(msg, attachment_path)

        all_recipients = to_recipients + cc_recipients

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_from, all_recipients, msg.as_string())

            logger.info(f"邮件成功发送给 {len(all_recipients)} 位收件人")
            return True

        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
            return False

    def _build_intro(self, meeting_data: Dict = None) -> str:
        """构建邮件引言"""
        intro = """尊敬的投资者和合作伙伴：

您好！这是本次昆虫蛋白产业化会议的详细纪要，包含养殖环境数据分析、营养成分评估、扩产方案、法规挑战分析及营销策略建议。

如需进一步讨论或获取更多信息，请随时与我们联系。

---

"""
        if meeting_data:
            date = meeting_data.get("date", "")
            location = meeting_data.get("location", "")
            if date:
                intro += f"**会议日期**: {date}  \n"
            if location:
                intro += f"**会议地点**: {location}  \n"
            intro += "\n"

        return intro

    def _markdown_to_html(self, md_content: str) -> str:
        """将Markdown转换为HTML"""
        html = markdown.markdown(
            md_content,
            extensions=[
                "tables",
                "fenced_code",
                "attr_list",
                "def_list",
                "nl2br"
            ]
        )

        styled_html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #34495e; margin-top: 30px; }}
                h3 {{ color: #5d6d7e; margin-top: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #3498db; color: white; }}
                tr:nth-child(even) {{ background-color: #f8f9fa; }}
                code {{ background-color: #f4f4f4; padding: 2px 6px; border-radius: 4px; }}
                pre {{ background-color: #f4f4f4; padding: 15px; border-radius: 8px; overflow-x: auto; }}
                blockquote {{ border-left: 4px solid #3498db; margin: 15px 0; padding: 10px 20px; background-color: #f8f9fa; }}
                ul, ol {{ margin: 15px 0; padding-left: 30px; }}
                li {{ margin: 5px 0; }}
                strong {{ color: #2c3e50; }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>
        """
        return styled_html

    def _add_attachment(self, msg: MIMEMultipart, file_path: str) -> None:
        """添加附件"""
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"附件不存在: {file_path}")
            return

        with open(file_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {path.name}"
        )
        msg.attach(part)
        logger.info(f"已添加附件: {path.name}")

    def send_to_investors(
        self,
        investors: List[str],
        markdown_content: str,
        meeting_data: Dict = None
    ) -> bool:
        """发送给投资者的定制邮件"""
        subject = "【重要】昆虫蛋白产业化会议纪要 - 投资机会分析"
        return self.send_meeting_summary(
            to_recipients=investors,
            subject=subject,
            markdown_content=markdown_content,
            meeting_data=meeting_data
        )

    def send_to_partners(
        self,
        partners: List[str],
        markdown_content: str,
        meeting_data: Dict = None
    ) -> bool:
        """发送给合作伙伴的定制邮件"""
        subject = "【会议纪要】昆虫蛋白产业合作推进会议"
        return self.send_meeting_summary(
            to_recipients=partners,
            subject=subject,
            markdown_content=markdown_content,
            meeting_data=meeting_data
        )
