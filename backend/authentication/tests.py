import re

from django.test import Client, SimpleTestCase, override_settings

from .console_auth import CONSOLE_SESSION_KEY


@override_settings(
    CONSOLE_PASSWORD="console-test-password",
    SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    DEBUG=False,
)
class AdminConsolePasswordTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def _csrf_token_from_login(self):
        response = self.client.get("/console/")
        match = re.search(
            rb'name="csrfmiddlewaretoken" value="([^"]+)"',
            response.content,
        )
        self.assertIsNotNone(match)
        return match.group(1).decode()

    def test_console_and_data_apis_require_password_session(self):
        response = self.client.get("/console/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="password"')
        self.assertNotContains(response, "Live Production Operations")
        self.assertEqual(self.client.get("/api/llm/usage/").status_code, 403)
        self.assertEqual(
            self.client.get(
                "/api/auth/admin/users/?admin_user_id=111822298300726667407"
            ).status_code,
            403,
        )

    def test_correct_password_opens_session_and_logout_closes_it(self):
        csrf_token = self._csrf_token_from_login()
        response = self.client.post(
            "/console/",
            {"password": "console-test-password"},
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIs(self.client.session.get(CONSOLE_SESSION_KEY), True)

        response = self.client.post(
            "/console/",
            {"action": "logout"},
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(CONSOLE_SESSION_KEY, self.client.session)

    def test_console_admin_api_mutations_require_csrf(self):
        csrf_token = self._csrf_token_from_login()
        self.client.post(
            "/console/",
            {"password": "console-test-password"},
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        response = self.client.post(
            "/api/auth/admin/users/",
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            "/api/auth/admin/users/",
            data="{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 400)

    def test_wrong_password_does_not_create_console_session(self):
        csrf_token = self._csrf_token_from_login()
        response = self.client.post(
            "/console/",
            {"password": "wrong-password"},
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(CONSOLE_SESSION_KEY, self.client.session)

    @override_settings(DEBUG=True, CONSOLE_PASSWORD="")
    def test_unconfigured_password_disables_console_even_in_debug(self):
        self.assertEqual(self.client.get("/console/").status_code, 503)
        self.assertEqual(self.client.get("/api/llm/usage/").status_code, 403)
        self.assertEqual(
            self.client.get(
                "/api/auth/admin/users/?admin_user_id=111822298300726667407"
            ).status_code,
            403,
        )
