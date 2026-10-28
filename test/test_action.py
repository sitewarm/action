"""Tests for the embedded scripts of action.yml. Needs bash, jq and python3; run: python3 -m unittest discover -s test -v"""
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from extract_step import step_script  # noqa: E402

ACTION = str(ROOT / "action.yml")
FIX = HERE / "fixtures"


def run_script(script: str, env: dict, path_prefix: str = "") -> subprocess.CompletedProcess:
    full = {"PATH": (path_prefix + ":" if path_prefix else "") + os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp")}
    full.update(env)
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=full)


def render(report: str, prev: str | None, fail_on: str = "5xx,noindex,regression") -> dict:
    """Runs the 'Build the verdict' step on a fixture and returns the files it writes."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    if prev:
        (tmp / "sitewarm-prev.json").write_text((FIX / prev).read_text())
    out = tmp / "sitewarm-out"
    env = {"RUNNER_TEMP": str(tmp), "GITHUB_OUTPUT": str(tmp / "gho"), "REPORT": str(FIX / report), "FAIL_ON": fail_on,
           "SITE_URL": "https://example.com", "SHA": "0123456789abcdef0123456789abcdef01234567", "OUT": str(out)}
    r = run_script(step_script(ACTION, "Build the verdict"), env)
    assert r.returncode == 0, r.stderr
    return {n: (out / n).read_text() for n in ("summary.md", "title.txt", "conclusion.txt")}


class BenignOutputIsUnchanged(unittest.TestCase):
    def test_matches_golden_made_from_v1_0_1(self):
        got = render("benign-report.json", "benign-prev.json")
        want = json.loads((FIX / "benign.golden.json").read_text())
        self.assertEqual(got, want)


class SummaryEscaping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = render("hostile-report.json", "hostile-prev.json")
        cls.lines = cls.out["summary.md"].split("\n")

    def test_plain_text_has_no_html_mentions_or_link_syntax(self):
        for line in self.lines:
            unescaped_ticks = line.replace("\\`", "")
            self.assertEqual(unescaped_ticks.count("`") % 2, 0, "unbalanced code span: " + line)
            plain = re.sub(r"`[^`]*`", "", unescaped_ticks)
            for bad in ("<", ">", "@"):
                self.assertNotIn(bad, plain, line)
            for m in re.finditer(r"[\[\]]", plain):
                self.assertEqual(plain[m.start() - 1], "\\", "unescaped bracket in: " + line)

    def test_a_backtick_in_a_url_cannot_break_the_code_span(self):
        text = self.out["summary.md"]
        self.assertNotIn("a`b", text)
        self.assertIn("`/a'b @user [x](http://evil.test) <img src=x>`", text)  # literal inside a code span

    def test_cells_stay_in_their_columns(self):
        rows = [l for l in self.lines if l.startswith("| `")]
        self.assertGreaterEqual(len(rows), 1)
        for row in rows:
            self.assertEqual(len(re.findall(r"(?<!\\)\|", row)), 6, row)

    def test_escapes_are_present_not_just_deletions(self):
        text = self.out["summary.md"]
        for want in ("&lt;b&gt;x&lt;/b&gt;", "\\[click\\]", "&#64;everyone", "&#64;here", "\\`tick", "\\|", "&lt;script&gt;"):
            self.assertIn(want, text)

    def test_the_verdict_is_still_computed(self):
        self.assertEqual(self.out["conclusion.txt"].strip(), "failure")  # HIT -> miss is a regression, and a noindex page
        self.assertIn("1 regressions", self.out["title.txt"])


class VersionValidation(unittest.TestCase):
    def run_download(self, version: str):
        tmp = pathlib.Path(tempfile.mkdtemp())
        bindir = tmp / "bin"
        bindir.mkdir()
        log = tmp / "curl.log"
        curl = bindir / "curl"
        curl.write_text('#!/bin/sh\necho "$@" >> "$CURL_LOG"\nexit 0\n')
        curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
        env = {"VERSION": version, "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "RUNNER_TEMP": str(tmp), "CURL_LOG": str(log)}
        r = run_script(step_script(ACTION, "Download and verify the sitewarm CLI"), env, str(bindir))
        return r, (log.read_text() if log.exists() else "")

    def test_accepts_semver(self):
        for v in ("1.0.2", "10.20.30", "0.0.1", "1.1.0-rc.1", "2.0.0-alpha", "1.0.0-0.3.7", "1.0.0+build.5", "1.0.0-rc.1+build.5"):
            _, curl = self.run_download(v)
            self.assertIn(f"v{v}/", curl, v)

    def test_rejects_everything_else_before_any_request(self):
        for v in ("", "1.0", "1", "v1.0.2", "latest", " 1.0.2", "1.0.2 ", "1.0.2\n", "01.0.0", "1.0.0-", "1.0.0-01", "1.0.0-rc..1",
                  "1.0.2/../../x", "../1.0.2", "1.0.2;id", "1.0.2$(id)", "1.0.2\n::set-output name=x::y", "1.0.2%2e%2e"):
            r, curl = self.run_download(v)
            self.assertNotEqual(r.returncode, 0, repr(v))
            self.assertEqual(curl, "", repr(v))
            self.assertIn("::error title=sitewarm::", r.stdout, repr(v))
            self.assertIn("version", r.stdout, repr(v))
            self.assertNotIn("set-output", r.stdout, repr(v))  # the rejected value is never echoed


if __name__ == "__main__":
    unittest.main()
