"""Check root dotenv resolution without reading real demo credentials."""

from contextlib import contextmanager
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from sandbox_tracker import config as tracker_config
from soc_handoff import config as app_config


class ConfigurationTest(TestCase):
    @contextmanager
    def configuration(self, module, environment):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "backend" / module.__package__
            package.mkdir(parents=True)
            (root / ".env").write_text(
                "MONGODB_URI=mongodb://root-app\n"
                "TRACKER_MONGODB_URI=mongodb://root-tracker\n"
                "SOC_DEMO_PASSWORD=synthetic-password\n"
                "TRACKER_TOKEN=synthetic-token\n", encoding="utf-8",
            )
            other = root / "unrelated"
            other.mkdir()
            (other / ".env").write_text("TRACKER_TOKEN=wrong-directory\n", encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(other)
                with (
                    patch.object(module, "__file__", str(package / "config.py")),
                    patch.dict(os.environ, environment, clear=True),
                ):
                    yield
            finally:
                os.chdir(previous)

    def test_root_file_is_used_from_an_unrelated_directory(self):
        for module, settings_class, expected_uri in (
            (app_config, app_config.Settings, "mongodb://root-app"),
            (tracker_config, tracker_config.TrackerSettings, "mongodb://root-tracker"),
        ):
            with self.subTest(service=module.__package__), self.configuration(module, {}):
                settings = settings_class.from_environment()
                self.assertEqual(settings.mongodb_uri, expected_uri)
                for secret in (expected_uri, "synthetic-password", "synthetic-token"):
                    self.assertNotIn(secret, repr(settings))

    def test_process_environment_takes_precedence(self):
        environment = {
            "MONGODB_URI": "mongodb://process-app",
            "TRACKER_MONGODB_URI": "mongodb://process-tracker",
            "TRACKER_TOKEN": "process-token",
        }
        for module, settings_class, uri_key, token_field in (
            (app_config, app_config.Settings, "MONGODB_URI", "tracker_token"),
            (tracker_config, tracker_config.TrackerSettings, "TRACKER_MONGODB_URI", "token"),
        ):
            with self.subTest(service=module.__package__), self.configuration(module, environment):
                settings = settings_class.from_environment()
                self.assertEqual(settings.mongodb_uri, environment[uri_key])
                self.assertEqual(getattr(settings, token_field), "process-token")

    def test_disabled_dotenv_does_not_load_root_file(self):
        for module, settings_class in (
            (app_config, app_config.Settings),
            (tracker_config, tracker_config.TrackerSettings),
        ):
            with self.subTest(service=module.__package__), self.configuration(
                module, {"PYTHON_DOTENV_DISABLED": "1"}
            ):
                with self.assertRaises(RuntimeError):
                    settings_class.from_environment()
