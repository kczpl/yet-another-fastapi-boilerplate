from app.core.config import aws_config
from app.core.logger import log
from app.utils.aws import get_ses_client
from app.utils.templates import render_login_email_template


def _send_ses_email(recipient_address: str, html_content: str, email_subject: str) -> str | None:
    if not recipient_address or not html_content or not email_subject:
        log.warning("missing email data", recipient=recipient_address)
        return None

    from_address = f"noreply@{aws_config.EMAIL_DOMAIN}"
    ses_client = get_ses_client()

    try:
        response = ses_client.send_email(
            Source=from_address,
            Destination={"ToAddresses": [recipient_address]},
            Message={
                "Subject": {"Data": email_subject},
                "Body": {"Html": {"Data": html_content}},
            },
        )
        return response.get("MessageId")
    except Exception as e:
        log.error("failed to send email", recipient=recipient_address, error=str(e))
        return None


def send_login_email(recipient_address: str, magic_link_url: str, language: str = "pl") -> str | None:
    email_subject = "Zaloguj się do myapp" if language == "pl" else "Sign in to myapp"

    html_content = render_login_email_template(
        magic_link_url=magic_link_url, email_subject=email_subject, language=language
    )
    return _send_ses_email(recipient_address, html_content, email_subject)
