"""Use only synthetic values and a unique disposable credential entry."""
import uuid

import win32cred
import pywintypes

from emart24.windows import credential, save_credential


def main():
    name = "Emart24/Test/" + uuid.uuid4().hex
    saved = False
    try:
        sample = " test-한글-🔐-" + uuid.uuid4().hex + " "
        save_credential(name, "test-user", sample)
        saved = True
        if credential(name) != ("test-user", sample):
            raise RuntimeError("Credential roundtrip mismatch")
    finally:
        if saved:
            win32cred.CredDelete(name, win32cred.CRED_TYPE_GENERIC)
    try:
        win32cred.CredRead(name, win32cred.CRED_TYPE_GENERIC)
    except pywintypes.error as exc:
        if exc.winerror != 1168:
            raise
    else:
        raise RuntimeError("Temporary credential cleanup failed")
    print("PASS: Unicode credential save/read and temporary-entry cleanup")


if __name__ == "__main__":
    main()
