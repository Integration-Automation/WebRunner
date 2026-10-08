"""Under TestPioneer a report asked for under a relative name goes below ``TEST_PIONEER_ARTIFACT_DIR``."""
import json
from pathlib import Path

import pytest

from je_web_runner.utils.generate_report.generate_allure_report import generate_allure_report
from je_web_runner.utils.generate_report.generate_html_report import generate_html_report
from je_web_runner.utils.generate_report.generate_json_report import generate_json_report
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml_report
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml_report
from je_web_runner.utils.generate_report.interactive_html_report import generate_interactive_html_report
from je_web_runner.utils.generate_report.report_manifest import generate_all_reports
from je_web_runner.utils.generate_report.report_path import ARTIFACT_DIR_VARIABLE, report_path
from je_web_runner.utils.test_record.test_record_class import record_action_to_list, test_record_instance


@pytest.fixture(autouse=True)
def _records():
    recording = test_record_instance.init_record
    test_record_instance.clean_record()
    test_record_instance.init_record = True
    record_action_to_list("ok_func", None, None)
    record_action_to_list("bad_func", None, RuntimeError("boom"))
    yield
    test_record_instance.clean_record()
    test_record_instance.init_record = recording


@pytest.fixture
def artifact_dir(tmp_path, monkeypatch):
    """A TestPioneer run: the variable is set, and the working directory is somewhere else."""
    directory = tmp_path / "artifacts" / "run-1" / "runners" / "web-runner" / "01-web"
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setenv(ARTIFACT_DIR_VARIABLE, str(directory))
    return directory


def test_a_name_is_returned_as_given_outside_testpioneer(monkeypatch):
    monkeypatch.delenv(ARTIFACT_DIR_VARIABLE, raising=False)
    assert report_path("reports/web") == "reports/web"


def test_an_empty_variable_counts_as_unset(monkeypatch):
    monkeypatch.setenv(ARTIFACT_DIR_VARIABLE, "  ")
    assert report_path("reports/web") == "reports/web"


def test_a_relative_name_goes_below_the_artifact_directory(artifact_dir):
    target = Path(report_path("reports/web_success.json"))
    assert target == artifact_dir.resolve() / "reports" / "web_success.json"
    assert target.parent.is_dir()


def test_an_absolute_name_is_left_alone(artifact_dir, tmp_path):
    name = str(tmp_path / "elsewhere" / "web.json")
    assert report_path(name) == name
    assert not artifact_dir.exists()


def test_a_name_that_leaves_the_directory_is_left_alone(artifact_dir):
    assert report_path("../outside.json") == "../outside.json"
    assert not artifact_dir.exists()


def test_a_directory_that_cannot_be_created_falls_back_to_the_name(tmp_path, monkeypatch):
    not_a_directory = tmp_path / "file"
    not_a_directory.write_text("x", encoding="utf-8")
    monkeypatch.setenv(ARTIFACT_DIR_VARIABLE, str(not_a_directory))
    assert report_path("reports/web.json") == "reports/web.json"


@pytest.mark.parametrize("generate, written", [
    (generate_json_report, ["reports/web_success.json", "reports/web_failure.json"]),
    (generate_xml_report, ["reports/web_success.xml", "reports/web_failure.xml"]),
    (generate_html_report, ["reports/web.html"]),
    (generate_junit_xml_report, ["reports/web_junit.xml"]),
    (generate_interactive_html_report, ["reports/web.html"]),
], ids=["json", "xml", "html", "junit", "interactive-html"])
def test_a_report_is_written_below_the_artifact_directory(artifact_dir, generate, written):
    generate("reports/web")
    assert [(artifact_dir / path).is_file() for path in written] == [True] * len(written)
    # Nothing is left in the working directory, where the name used to point.
    assert not Path("reports").exists()


def test_the_allure_results_are_written_below_the_artifact_directory(artifact_dir):
    results = generate_allure_report("allure-results")
    assert results
    assert {Path(result).parent for result in results} == {artifact_dir.resolve() / "allure-results"}
    assert not Path("allure-results").exists()


def test_the_manifest_lists_the_files_where_they_are(artifact_dir):
    outcome = generate_all_reports("reports/web")
    manifest = Path(outcome["manifest_path"])
    assert manifest == artifact_dir.resolve() / "reports" / "web.manifest.json"
    produced = json.loads(manifest.read_text(encoding="utf-8"))["produced"]
    assert produced["json"]
    assert all(Path(path).is_file() for paths in produced.values() for path in paths)
    assert not Path("reports").exists()


def test_outside_testpioneer_a_report_stays_in_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.delenv(ARTIFACT_DIR_VARIABLE, raising=False)
    monkeypatch.chdir(tmp_path)
    generate_json_report("web")
    assert (tmp_path / "web_success.json").is_file()
