import unittest

import pyotp

from app.services.auth_service import AuthService


class AuthServiceTests(unittest.TestCase):
    def test_password_with_surrounding_spaces_is_preserved(self):
        password = " contraseña con espacios "
        password_hash = AuthService.get_password_hash(password)

        self.assertTrue(AuthService.verify_password(password, password_hash))
        self.assertFalse(AuthService.verify_password(password.strip(), password_hash))

    def test_access_token_has_expected_type(self):
        token = AuthService.create_access_token({"sub": "qa_user"})
        payload = AuthService.decode_access_token(token)

        self.assertEqual(payload["sub"], "qa_user")
        self.assertEqual(payload["type"], "access")

    def test_current_totp_code_is_valid(self):
        secret = AuthService.generate_totp_secret()
        code = pyotp.TOTP(secret).now()

        self.assertTrue(AuthService.verify_totp_code(secret, code))
        self.assertFalse(AuthService.verify_totp_code(secret, "00000"))


if __name__ == "__main__":
    unittest.main()
