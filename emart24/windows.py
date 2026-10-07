from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from .core import Retryable, StopRun


@contextmanager
def run_lock(path):
    import msvcrt
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+b")
    try:
        if f.tell() == 0:
            f.write(b"0")
            f.flush()
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise Retryable("다른 실행이 진행 중입니다.") from exc
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        f.close()


@contextmanager
def protect_target(path):
    """Deny other writers while allowing atomic rename of the held original."""
    import win32con
    import win32file
    if Path(path).with_name("~$" + Path(path).name).exists():
        raise Retryable("대상 Excel 파일이 열려 있습니다. 닫은 뒤 재실행하세요.")
    try:
        handle = win32file.CreateFile(str(path), win32con.GENERIC_READ,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_DELETE, None,
            win32con.OPEN_EXISTING, win32con.FILE_ATTRIBUTE_NORMAL, None)
    except Exception as exc:
        raise Retryable("대상 파일을 보호할 수 없습니다. 파일 사용 여부를 확인하세요.") from exc
    try:
        yield
    finally:
        handle.Close()


def replace_file(work, target):
    """ReplaceFileW works with our deny-write handle; MoveFileEx does not."""
    import ctypes
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    replace = api.ReplaceFileW
    replace.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                        ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    replace.restype = ctypes.c_int
    recovery = Path(work).with_suffix(".previous.xlsx")
    ok = replace(str(target), str(work), str(recovery), 0, None, None)
    if not ok:
        error = ctypes.get_last_error()
        # Windows documents rare failures that rename the original. Restore its
        # name only if absent; never overwrite a concurrently created target.
        if not Path(target).exists() and recovery.exists():
            os.rename(recovery, target)
        if error in (5, 32, 33, 1175):
            raise PermissionError(error, "Windows file replacement blocked")
        raise StopRun(f"Windows 파일 교체 실패({error}). 백업과 .previous 파일을 확인하세요.")
    if recovery.exists():
        try:
            recovery.unlink()
        except OSError:
            pass  # Extra backup is harmless; the verified target is committed.


def credential(name):
    import win32cred
    try:
        c = win32cred.CredRead(name, win32cred.CRED_TYPE_GENERIC)
    except Exception as exc:
        raise StopRun("로그인 자격 증명이 없습니다. credentials 명령으로 등록하세요.") from exc
    blob = c["CredentialBlob"]
    return c["UserName"], blob.decode("utf-16-le") if isinstance(blob, bytes) else blob


def save_credential(name, username, password):
    import win32cred
    if not username.strip() or not password:
        raise StopRun("아이디와 비밀번호를 모두 입력해 주세요.")
    try:
        # pywin32 CredWrite accepts Unicode and performs the Windows encoding.
        win32cred.CredWrite({"Type": win32cred.CRED_TYPE_GENERIC, "TargetName": name,
            "UserName": username.strip(), "CredentialBlob": password,
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE}, 0)
    except Exception:
        # Do not include API arguments or credential values in UI/log output.
        raise StopRun("Windows 자격 증명 저장에 실패했습니다. 현재 Windows 로그인 상태를 확인하고 다시 시도해 주세요.") from None


def set_credential(name):
    # A local GUI avoids passwords in chat, command history, or stdout.
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.title("이마트24 자동화 — CJ 로그인 정보 등록")
    root.geometry("470x210")
    tk.Label(root, text="CJ대한통운 로그인 정보를 Windows 자격 증명 관리자에 저장합니다.").pack(pady=10)
    tk.Label(root, text="아이디").pack()
    user = tk.Entry(root, width=42)
    user.pack()
    tk.Label(root, text="비밀번호").pack()
    password = tk.Entry(root, show="●", width=42)
    password.pack()
    def save():
        try:
            save_credential(name, user.get(), password.get())
        except StopRun as exc:
            messagebox.showerror("등록 실패", str(exc), parent=root)
            return
        password.delete(0, tk.END)
        messagebox.showinfo("등록 완료", "로그인 정보를 안전하게 저장했습니다.")
        root.destroy()
    tk.Button(root, text="저장", command=save).pack(pady=10)
    root.mainloop()


def notify(text):
    # Nonblocking Windows tray notification via a short-lived helper process.
    import subprocess
    helper = Path(__file__).resolve().parent.parent / "scripts" / "notify.ps1"
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(helper), "-Message", text],
        creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
