import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app
import core


class SchedulingTests(unittest.TestCase):
    def test_short_gap_warning(self):
        self.assertEqual(core.short_gaps(["02:00", "06:00", "11:00", "16:00", "21:00"]), [("02:00", "06:00", 240)])
        self.assertEqual(core.short_gaps(["06:00", "11:00", "16:00", "21:00"]), [])

    def test_next_request_waits_past_own_five_hour_window(self):
        previous = datetime(2026, 10, 29, 6, 0, 20)
        self.assertEqual(core.seconds_until_eligible(datetime(2026, 10, 29, 11, 0), previous), 65)
        self.assertEqual(core.seconds_until_eligible(datetime(2026, 10, 29, 11, 1, 5), previous), 0)

    def test_scheduled_slot_is_attempted_once(self):
        with tempfile.TemporaryDirectory() as directory:
            now = datetime.now()
            slot = now.strftime("%H:%M")
            point = now.replace(second=0, microsecond=0)
            with patch.dict("os.environ", {"LOCALAPPDATA": directory}), \
                 patch.object(core, "load_config", return_value={"times": [slot], "codex_path": "mock"}), \
                 patch.object(core, "trigger", return_value=(True, "ok")) as trigger:
                app.run_scheduled(slot, point)
                app.run_scheduled(slot, point)
                trigger.assert_called_once()
                state = json.loads((Path(directory) / core.APP_NAME / "attempts.json").read_text(encoding="utf-8"))
                self.assertEqual(len(state), 1)

    def test_stale_slot_is_not_run(self):
        with patch.object(core, "trigger") as trigger:
            app.run_scheduled("06:00", datetime.now() - timedelta(hours=6))
            trigger.assert_not_called()

    def test_scheduled_slot_skips_if_previous_window_is_too_recent(self):
        with tempfile.TemporaryDirectory() as directory:
            now = datetime.now()
            slot = now.strftime("%H:%M")
            with patch.dict("os.environ", {"LOCALAPPDATA": directory}), \
                 patch.object(core, "load_config", return_value={"times": [slot], "codex_path": "mock"}), \
                 patch.object(core, "last_success", return_value=now), \
                 patch.object(core, "trigger") as trigger:
                app.run_scheduled(slot, now.replace(second=0, microsecond=0))
                trigger.assert_not_called()
                self.assertIn("跳过", core.read_history())

    def test_only_completed_codex_turn_counts_as_success(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"LOCALAPPDATA": directory}):
            codex_path = Path(directory) / "codex.cmd"
            codex_path.write_text("@echo off\n", encoding="utf-8")
            config = {"codex_path": str(codex_path)}
            success = lambda *args, **kwargs: SimpleNamespace(
                returncode=0,
                stdout='{"type":"turn.completed","usage":{"input_tokens":3,"output_tokens":2}}\n',
            )
            with patch.object(core, "check_codex", return_value=(True, "mock")):
                self.assertEqual(core.trigger("test", config, runner=success), (True, "已完成一次请求，消耗 5 tokens"))
                incomplete = lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='{"type":"turn.started"}\n')
                self.assertFalse(core.trigger("test", config, runner=incomplete)[0])

    def test_model_error_explains_cli_update(self):
        events = [{"type": "turn.failed", "error": {"message": '{"error":{"code":"model_not_found","message":"unsupported"}}'}}]
        self.assertIn("自动查找", core._failure_message(events, 1))

    def test_auto_find_checks_custom_npm_prefix_outside_path(self):
        with tempfile.TemporaryDirectory() as directory:
            roaming = Path(directory) / "roaming"
            old_cli = roaming / "npm" / "codex.cmd"
            new_cli = Path(directory) / "custom-npm" / "codex.cmd"
            for path in (old_cli, new_cli):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()

            with patch.dict(os.environ, {"LOCALAPPDATA": directory, "APPDATA": str(roaming), "CODEX_INSTALL_DIR": ""}), \
                 patch.object(core.shutil, "which", return_value=None), \
                 patch.object(core, "_npm_prefix", return_value=str(new_cli.parent)), \
                 patch.object(core, "_probe_version", side_effect=lambda path: (2, 0, 0) if path == str(new_cli) else (1, 0, 0)):
                self.assertEqual(core.find_codex(), str(new_cli))

    def test_saved_old_npm_cli_is_replaced_by_desktop_cli(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"LOCALAPPDATA": directory}):
            old_cli = Path(directory) / "codex.cmd"
            new_cli = Path(directory) / "codex.exe"
            old_cli.touch()
            new_cli.touch()
            core.save_config({"times": ["06:00"], "codex_path": str(old_cli)})

            def which(name):
                return str(new_cli) if name == "codex.exe" else str(old_cli) if name == "codex.cmd" else None

            with patch.object(core.shutil, "which", side_effect=which), \
                 patch.object(core, "_probe_version", side_effect=lambda path: (2, 0, 0) if path == str(new_cli) else (1, 0, 0)):
                self.assertEqual(core.load_config()["codex_path"], str(new_cli))


if __name__ == "__main__":
    unittest.main()
