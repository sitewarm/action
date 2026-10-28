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


DOWNLOAD = "Download and verify the sitewarm CLI"
PIN_AMD64 = "8daad022e9eed93e435d843f0a9a984c6b70bd00615518571a48c308e5e70abc"
PIN_ARM64 = "a2f5beaec3b6700fd53496b227115c23e7859b003aea1b80e561e03ce803a2fa"
SEMVER_ERROR = "version must be a semantic version"


def fake_archive(tmp: pathlib.Path) -> tuple[pathlib.Path, str]:
    """A tar.gz with a `sitewarm` shell stub, and its SHA-256."""
    import hashlib
    import io
    import tarfile

    path = tmp / "fake.tar.gz"
    data = b'#!/bin/sh\necho "sitewarm version stub"\n'
    with tarfile.open(path, "w:gz") as t:
        info = tarfile.TarInfo("sitewarm")
        info.size, info.mode = len(data), 0o755
        t.addfile(info, io.BytesIO(data))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


class PinTable(unittest.TestCase):
    def run_download(self, version: str, arch: str = "X64", pin_to_fake: bool = False, serve_fake: bool = True):
        """Runs the download step against a fake curl that logs its arguments and copies a stub archive to -o."""
        tmp = pathlib.Path(tempfile.mkdtemp())
        bindir = tmp / "bin"
        bindir.mkdir()
        archive, fake_sha = fake_archive(tmp)
        log = tmp / "curl.log"
        curl = bindir / "curl"
        body = 'cp "$ARCHIVE" "$out"\n' if serve_fake else ""
        curl.write_text('#!/bin/sh\necho "$@" >> "$CURL_LOG"\nout=""\nwhile [ $# -gt 0 ]; do [ "$1" = "-o" ] && out="$2"; shift; done\n' + body + "exit 0\n")
        curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
        script = step_script(ACTION, DOWNLOAD)
        if pin_to_fake:  # same script, the pin for this architecture replaced by the hash of the stub archive
            old = PIN_AMD64 if arch == "X64" else PIN_ARM64
            assert script.count(old) == 1
            script = script.replace(old, fake_sha)
        env = {"VERSION": version, "RUNNER_OS": "Linux", "RUNNER_ARCH": arch, "RUNNER_TEMP": str(tmp), "CURL_LOG": str(log), "ARCHIVE": str(archive)}
        r = run_script(script, env, str(bindir))
        return r, (log.read_text() if log.exists() else ""), tmp / "sitewarm-cli"

    def test_version_in_the_table_downloads_that_archive_and_checks_it(self):
        for arch, name in (("X64", "amd64"), ("ARM64", "arm64")):
            r, curl, d = self.run_download("1.0.2", arch, pin_to_fake=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(curl.strip().splitlines().__len__(), 1, curl)  # one request, for the archive only
            self.assertIn(f"/v1.0.2/sitewarm_1.0.2_linux_{name}.tar.gz", curl)
            self.assertNotIn("checksums.txt", curl)
            self.assertIn("sitewarm version stub", r.stdout)  # extracted and run
            self.assertEqual((d / "expected.sha256").read_text().split()[1], f"sitewarm_1.0.2_linux_{name}.tar.gz")

    def test_a_wrong_checksum_fails_and_nothing_is_extracted(self):
        r, curl, d = self.run_download("1.0.2")  # the real pin against a stub archive
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("FAILED", r.stdout + r.stderr)
        self.assertFalse((d / "sitewarm").exists())
        self.assertNotIn("sitewarm version stub", r.stdout)

    def test_a_valid_version_that_is_not_in_the_table_fails_before_any_request(self):
        for v in ("1.0.1", "1.0.3", "1.1.0", "1.1.0-rc.1", "2.0.0", "0.0.1", "1.0.2-rc.1", "1.0.2+build.5", "10.20.30"):
            r, curl, _ = self.run_download(v)
            self.assertNotEqual(r.returncode, 0, v)
            self.assertEqual(curl, "", v)  # no request of any kind, checksums.txt included
            self.assertIn("::error title=sitewarm::", r.stdout, v)
            self.assertIn(f"version {v} is not pinned", r.stdout, v)
            self.assertIn("pinned: 1.0.2", r.stdout, v)
            self.assertNotIn(SEMVER_ERROR, r.stdout, v)

    def test_a_malformed_version_fails_before_any_request_and_is_never_echoed(self):
        for v in ("1.0", "1", "v1.0.2", "latest", " 1.0.2", "1.0.2 ", "1.0.2\n", " ", "01.0.0", "1.0.0-", "1.0.0-01", "1.0.0-rc..1",
                  "1.0.2/../../x", "../1.0.2", "1.0.2;id", "1.0.2$(id)", "1.0.2\n::set-output name=x::y", "1.0.2%2e%2e"):
            r, curl, _ = self.run_download(v)
            self.assertNotEqual(r.returncode, 0, repr(v))
            self.assertEqual(curl, "", repr(v))
            self.assertIn(SEMVER_ERROR, r.stdout, repr(v))
            self.assertNotIn("set-output", r.stdout, repr(v))
            self.assertNotIn("is not pinned", r.stdout, repr(v))

    def test_an_empty_override_means_the_pinned_default(self):
        r, curl, _ = self.run_download("", pin_to_fake=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("/v1.0.2/sitewarm_1.0.2_linux_amd64.tar.gz", curl)
        self.assertNotIn("checksums.txt", curl)

    def test_other_platforms_still_fail_before_any_request(self):
        r, curl, _ = self.run_download("1.0.2", "X86")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(curl, "")
        self.assertIn("Unsupported architecture", r.stdout)

    def test_the_table_is_well_formed_and_holds_the_default(self):
        script = step_script(ACTION, DOWNLOAD)
        m = re.search(r"^pins='([^']*)'$", script, re.M)
        self.assertIsNotNone(m)
        rows = [l.split(" ") for l in m.group(1).split("\n")]
        seen = set()
        for row in rows:
            self.assertEqual(len(row), 3, row)
            v, a, h = row
            self.assertRegex(v, r"^\d+\.\d+\.\d+$")
            self.assertIn(a, ("amd64", "arm64"))
            self.assertRegex(h, r"^[0-9a-f]{64}$")
            self.assertNotIn((v, a), seen)
            seen.add((v, a))
        for v in {r[0] for r in rows}:
            self.assertEqual({a for vv, a in seen if vv == v}, {"amd64", "arm64"}, v)  # every pinned version has both architectures
        default = re.search(r"\n  version:\n(?:    .*\n)*?    default: '([^']+)'\n", pathlib.Path(ACTION).read_text())
        self.assertIsNotNone(default)
        self.assertIn(default.group(1), {r[0] for r in rows})  # the input default is pinned
        self.assertIn(f'default_version="{default.group(1)}"', script)

    def test_no_request_ever_names_a_checksums_file(self):
        script = step_script(ACTION, DOWNLOAD)
        code = "\n".join(l for l in script.split("\n") if not l.lstrip().startswith("#"))  # the comments explain why it is not used
        self.assertNotIn("checksums.txt", code)
        self.assertIn("never downloads a CLI it has no SHA-256 for", script)
        self.assertNotIn("checksums.txt", (ROOT / "README.md").read_text().split("`version`")[1].split("\n")[0])


if __name__ == "__main__":
    unittest.main()
