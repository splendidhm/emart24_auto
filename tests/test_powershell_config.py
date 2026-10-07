import base64
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from emart24.core import TARGET_FILENAME


@unittest.skipUnless(shutil.which("powershell.exe"), "Windows PowerShell required")
class PowerShellConfig(unittest.TestCase):
    def test_korean_target_survives_legacy_codepage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_dir = root / "한글 업무자료 ☆"
            target_dir.mkdir()
            config = root / "config.json"
            config.write_text(json.dumps({"target_directory": str(target_dir),
                                          "runtime": "runtime"}), encoding="utf-8")
            def quote(value):
                return "'" + str(value).replace("'", "''") + "'"
            script = (
                "$ErrorActionPreference='Stop'; "
                "[Console]::OutputEncoding=[Text.Encoding]::GetEncoding(949); "
                f"$raw = & {quote(sys.executable)} -m emart24 --config {quote(config)} show-config --ascii; "
                "if ($LASTEXITCODE -ne 0) { throw 'show-config failed' }; "
                '$cfg = ($raw -join "`n") | ConvertFrom-Json; '
                "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($cfg.target))"
            )
            encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
            result = subprocess.run(["powershell.exe", "-NoProfile", "-EncodedCommand", encoded],
                                    capture_output=True, check=True, timeout=30,
                                    cwd=Path(__file__).resolve().parents[1])
            actual = base64.b64decode(result.stdout.strip()).decode("utf-8")
            self.assertEqual(actual, str((target_dir / TARGET_FILENAME).resolve()))
