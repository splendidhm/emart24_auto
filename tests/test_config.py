import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from emart24.core import TARGET_FILENAME, StopRun, config_hash, load_config, local_config_path, save_target_directory


class PortableConfiguration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps({"target_directory": None, "runtime": "runtime", "sheet": "DB"}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def folder(self, name):
        folder = self.root / name
        folder.mkdir()
        (folder / TARGET_FILENAME).write_bytes(b"test path only")
        return folder

    def test_setup_required_on_new_pc(self):
        with self.assertRaisesRegex(StopRun, "configure"):
            load_config(self.config)

    def test_one_setting_used_by_all_consumers(self):
        folder = self.folder("다른 PC 업무자료")
        save_target_directory(self.config, folder)
        cfg = load_config(self.config)
        self.assertEqual(Path(cfg["target"]), folder / TARGET_FILENAME)
        self.assertEqual(Path(cfg["runtime"]), self.root / "runtime")
        self.assertIsNone(json.loads(self.config.read_text())["target_directory"])

    def test_missing_file_leaves_previous_setting_unchanged(self):
        save_target_directory(self.config, self.folder("first"))
        original = local_config_path(self.config).read_bytes()
        missing = self.root / "missing"
        missing.mkdir()
        with self.assertRaises(StopRun):
            save_target_directory(self.config, missing)
        self.assertEqual(local_config_path(self.config).read_bytes(), original)

    def test_environment_variable_and_relative_paths(self):
        folder = self.folder("한글 폴더")
        with patch.dict(os.environ, {"EMART24_TEST_HOME": str(self.root)}):
            save_target_directory(self.config, "$EMART24_TEST_HOME/한글 폴더")
        self.assertEqual(Path(load_config(self.config)["target"]).parent, folder)
        save_target_directory(self.config, "한글 폴더")
        self.assertEqual(Path(load_config(self.config)["target"]).parent, folder)

    def test_unresolved_environment_variable_rejected(self):
        with self.assertRaisesRegex(StopRun, "환경 변수"):
            save_target_directory(self.config, "%NONEXISTENT_EMART24_TEST_7744%/folder")

    def test_local_path_change_invalidates_site_verification(self):
        save_target_directory(self.config, self.folder("pc1"))
        before = config_hash(load_config(self.config))
        save_target_directory(self.config, self.folder("pc2"))
        self.assertNotEqual(before, config_hash(load_config(self.config)))

    def test_custom_config_gets_own_local_settings(self):
        other = self.root / "other.json"
        other.write_bytes(self.config.read_bytes())
        save_target_directory(other, self.folder("other-folder"))
        self.assertTrue((self.root / "other.local.json").exists())
        with self.assertRaises(StopRun):
            load_config(self.config)

    def test_legacy_path_only_accepts_fixed_filename(self):
        folder = self.folder("legacy")
        self.config.write_text(json.dumps({"target": str(folder/TARGET_FILENAME), "runtime": "runtime"}),encoding="utf-8")
        self.assertEqual(Path(load_config(self.config)["target"]),folder/TARGET_FILENAME)
        self.config.write_text(json.dumps({"target": str(folder/"other.xlsx"), "runtime": "runtime"}),encoding="utf-8")
        with self.assertRaises(StopRun):
            load_config(self.config)


if __name__ == "__main__":
    unittest.main()
