import unittest
from unittest.mock import patch

import win32cred

from emart24.core import StopRun
from emart24.windows import credential, save_credential


class CredentialStorage(unittest.TestCase):
    def test_unicode_password_and_whitespace_preserved(self):
        with patch.object(win32cred, "CredWrite") as write:
            save_credential("test", " user ", " 한글!🔐 ")
        values = write.call_args.args[0]
        self.assertEqual(values["CredentialBlob"], " 한글!🔐 ")
        self.assertIsInstance(values["CredentialBlob"], str)
        self.assertEqual(values["UserName"], "user")

    def test_read_unicode_bytes(self):
        with patch.object(win32cred, "CredRead", return_value={"UserName":"user", "CredentialBlob":" 한글!🔐 ".encode("utf-16-le")}):
            self.assertEqual(credential("test"), ("user", " 한글!🔐 "))

    def test_missing_input_does_not_write(self):
        with patch.object(win32cred, "CredWrite") as write:
            for user, password in [(" ","x"),("user","")]:
                with self.assertRaises(StopRun):
                    save_credential("test",user,password)
            write.assert_not_called()

    def test_error_does_not_expose_password(self):
        with patch.object(win32cred, "CredWrite", side_effect=TypeError("sensitive-test-value")):
            with self.assertRaises(StopRun) as result:
                save_credential("test", "user", "sensitive-test-value")
        self.assertNotIn("sensitive-test-value", str(result.exception))


if __name__ == "__main__":
    unittest.main()
