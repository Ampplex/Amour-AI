CONSOLE_SESSION_KEY = "admin_console_authenticated"


def is_console_authenticated(request) -> bool:
    session = getattr(request, "session", None)
    if session is None:
        session = getattr(getattr(request, "_request", None), "session", None)
    return session is not None and session.get(CONSOLE_SESSION_KEY) is True


def is_console_authorized(request) -> bool:
    if is_console_authenticated(request):
        return True
    user = getattr(request, "user", None)
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.is_superuser)
    )
