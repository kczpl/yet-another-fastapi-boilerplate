import os
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

LOGIN_EMAIL_TEMPLATE = "login-email.html.jinja2"

# TODO: clean up templates #

def get_jinja_env() -> Environment:
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    return env


def _get_template(template_name: str, language: str = "pl", localized: bool = True):
    env = get_jinja_env()
    if localized:
        try:
            return env.get_template(f"{language}-{template_name}")
        except TemplateNotFound:
            return env.get_template(f"pl-{template_name}")
    else:
        return env.get_template(template_name)


def _render_template(template_name: str, language: str = "pl", localized: bool = True, **context) -> str:
    template = _get_template(template_name, language, localized)
    context["language"] = language
    return template.render(**context)


def render_login_email_template(magic_link_url: str, email_subject: str, language: str = "pl") -> str:
    return _render_template(
        LOGIN_EMAIL_TEMPLATE, language, localized=False, magic_link_url=magic_link_url, subject=email_subject
    )
