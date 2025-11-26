import os
from jinja2 import Environment, FileSystemLoader

LOGIN_EMAIL_TEMPLATE = "login-email.html.jinja2"


def get_jinja_env() -> Environment:
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    return Environment(loader=FileSystemLoader(template_dir))


def render_login_email_template(magic_link_url: str, email_subject: str, language: str = "pl") -> str:
    env = get_jinja_env()
    template = env.get_template(LOGIN_EMAIL_TEMPLATE)
    return template.render(magic_link_url=magic_link_url, subject=email_subject, language=language)
