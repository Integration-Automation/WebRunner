"""``scripts/dev_release.py`` numbers and gates the ``je_web_runner_dev`` releases CI publishes.

A wrong version is refused by PyPI (a number is never reused) and a wrong comparison either
publishes on every push or never again, so both are pinned here without touching the network.
"""
import importlib.util
import io
import re
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "dev_release.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test_dev.yml"


def _load_script():
    spec = importlib.util.spec_from_file_location("dev_release", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dev_release = _load_script()


def _wheel(version: str, source: str = "VALUE = 1\n", requires: str = "selenium>=4.0.0") -> bytes:
    info = f"je_web_runner_dev-{version}.dist-info"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("je_web_runner/__init__.py", source)
        archive.writestr(f"{info}/METADATA",
                         f"Name: je_web_runner_dev\nVersion: {version}\nRequires-Dist: {requires}\n")
        archive.writestr(f"{info}/RECORD", f"je_web_runner/__init__.py,sha256={version}\n")
        archive.writestr(f"{info}/WHEEL", f"Generator: setuptools ({version})\n")
        archive.writestr(f"{info}/licenses/LICENSE", "MIT\n")
    return buffer.getvalue()


@pytest.mark.parametrize("floor, released, expected", [
    ((0, 0, 99), {(0, 0, 99): None, (0, 0, 98): None}, "0.0.100"),
    ((0, 0, 99), {(0, 0, 104): None}, "0.0.105"),
    ((0, 1, 0), {(0, 0, 104): None}, "0.1.1"),
    ((0, 0, 99), {}, "0.0.100"),
])
def test_next_version_is_one_patch_above_the_floor_and_every_release(floor, released, expected):
    assert dev_release.next_version(floor, released) == expected  # nosec B101


def test_published_keeps_plain_releases_and_their_wheels(monkeypatch):
    payload = (
        b'{"releases": {'
        b'"0.0.98": [{"packagetype": "sdist", "url": "https://files.pythonhosted.org/a.tar.gz"}],'
        b'"0.0.99": [{"packagetype": "sdist", "url": "https://files.pythonhosted.org/b.tar.gz"},'
        b' {"packagetype": "bdist_wheel", "url": "https://files.pythonhosted.org/b.whl"}],'
        b'"0.0.100.dev1": [{"packagetype": "bdist_wheel", "url": "https://files.pythonhosted.org/c.whl"}],'
        b'"0.0.97": []}}'
    )
    monkeypatch.setattr(dev_release, "fetch", lambda url: payload)
    assert dev_release.published("je_web_runner_dev") == {  # nosec B101
        (0, 0, 98): None,
        (0, 0, 99): "https://files.pythonhosted.org/b.whl",
    }


def test_fetch_refuses_a_host_that_is_not_pypi():
    with pytest.raises(ValueError):
        dev_release.fetch("https://example.com/je_web_runner_dev.whl")


def test_prepare_writes_pyproject_from_dev_toml_with_the_next_version(tmp_path, monkeypatch):
    dev_toml = (REPO_ROOT / "dev.toml").read_text(encoding="utf-8")
    (tmp_path / "dev.toml").write_text(dev_toml, encoding="utf-8")
    asked = []
    monkeypatch.setattr(dev_release, "published", lambda name: asked.append(name) or {(9, 9, 9): None})

    assert dev_release.prepare(tmp_path) == "9.9.10"  # nosec B101

    written = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert asked == ["je_web_runner_dev"]  # nosec B101
    assert written == dev_release.VERSION_LINE.sub(r'\g<1>"9.9.10"', dev_toml, count=1)  # nosec B101
    assert written.count('version = "9.9.10"') == 1  # nosec B101


def test_fingerprint_ignores_what_only_the_version_number_changes():
    assert dev_release.fingerprint(_wheel("0.0.99")) == dev_release.fingerprint(_wheel("0.0.100"))  # nosec B101


@pytest.mark.parametrize("difference", [{"source": "VALUE = 2\n"}, {"requires": "selenium>=4.1.0"}])
def test_fingerprint_sees_changed_code_and_changed_metadata(difference):
    assert dev_release.fingerprint(_wheel("0.0.99")) != dev_release.fingerprint(  # nosec B101
        _wheel("0.0.100", **difference))


@pytest.mark.parametrize("latest, expected", [
    ({}, True),
    ({"source": "VALUE = 0\n"}, True),
    ({"source": "VALUE = 1\n"}, False),
])
def test_changed_compares_the_built_wheel_with_the_newest_published_one(
        tmp_path, monkeypatch, latest, expected):
    (tmp_path / "je_web_runner_dev-0.0.100-py3-none-any.whl").write_bytes(_wheel("0.0.100"))
    url = "https://files.pythonhosted.org/je_web_runner_dev-0.0.99-py3-none-any.whl"
    released = {(0, 0, 98): "https://files.pythonhosted.org/old.whl", (0, 0, 99): url} if latest else {}
    monkeypatch.setattr(dev_release, "published", lambda name: released)
    monkeypatch.setattr(dev_release, "fetch", lambda asked: _wheel("0.0.99", **latest) if asked == url else b"")

    assert dev_release.changed(tmp_path) is expected  # nosec B101


def test_changed_publishes_when_the_newest_release_has_no_wheel(tmp_path, monkeypatch):
    (tmp_path / "je_web_runner_dev-0.0.100-py3-none-any.whl").write_bytes(_wheel("0.0.100"))
    monkeypatch.setattr(dev_release, "published", lambda name: {(0, 0, 99): None})

    assert dev_release.changed(tmp_path) is True  # nosec B101


def test_main_writes_the_result_where_the_workflow_reads_it(tmp_path, monkeypatch):
    output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(dev_release, "changed", lambda dist: False)

    assert dev_release.main(["changed", str(tmp_path)]) == 0  # nosec B101
    assert output.read_text(encoding="utf-8") == "changed=false\n"  # nosec B101
    assert dev_release.main(["publish"]) == 2  # nosec B101


def _publish_job() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    return re.split(r"^  publish-dev:\s*$", text, maxsplit=1, flags=re.MULTILINE)[1]


def test_the_workflow_publishes_only_a_tested_push_to_dev():
    job = _publish_job()
    assert "needs: [unit-test, integration-test]" in job  # nosec B101
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/dev'" in job  # nosec B101


def test_the_workflow_uploads_only_a_changed_build_and_keeps_no_credentials():
    job = _publish_job()
    upload = job.index("twine upload")
    assert job.index("dev_release.py prepare") < job.index("python -m build") < upload  # nosec B101
    assert job.index("dev_release.py changed dist") < upload  # nosec B101
    assert job.index("git ls-remote origin refs/heads/dev") < upload  # nosec B101
    assert ("if: steps.compare.outputs.changed == 'true' && steps.tip.outputs.current == 'true'"  # nosec B101
            in job)
    assert "persist-credentials: false" in job  # nosec B101
