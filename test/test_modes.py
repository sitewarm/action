"""Mode selection, input validation and the hosted step of action.yml. Needs bash and python3; the hosted tests also need node
(they are skipped, and reported as skipped, when node is missing). No test calls a real API: the hosted bundle talks to a fake
server on the loopback interface."""
import hashlib
import http.server
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from extract_step import step_script  # noqa: E402
from test_action import render  # noqa: E402

ACTION = str(ROOT / "action.yml")
FIX = HERE / "fixtures"
KEY = "swk_test_abc123"
TOKEN = "tok_secret_987"
HAVE_NODE = shutil.which("node") is not None

LOCAL_STEPS = ["Decide whether to run", "Download and verify the sitewarm CLI", "Read the previous Production receipt", "Scan", "Build the verdict", "Publish the Check"]
VALIDATE = "Validate the inputs"
HOSTED = "Warm and verify (hosted)"
REQUIRE = "Require site-url (local)"
CONCLUSION = "Set the hosted conclusion"


def bash(script: str, env: dict) -> subprocess.CompletedProcess:
    full = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp")}
    full.update(env)
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=full)


def validate(**inputs):
    """Runs the validation step; returns (returncode, stdout, GITHUB_OUTPUT text)."""
    names = ["MODE", "SITE_URL", "URLS_FILE", "API_KEY", "API_URL", "SITE", "SITEMAP_URL", "WAIT", "TIMEOUT", "SITE_TOKEN"]
    out = pathlib.Path(tempfile.mkdtemp()) / "gho"
    out.write_text("")
    env = {n: "" for n in names}
    env.update({k.upper(): v for k, v in inputs.items()})
    env["GITHUB_OUTPUT"] = str(out)
    r = bash(step_script(ACTION, VALIDATE), env)
    return r.returncode, r.stdout, out.read_text()


class StepsAreGatedByMode(unittest.TestCase):
    def blocks(self):
        text = pathlib.Path(ACTION).read_text()
        return {m.group(1): m.group(0) for m in re.finditer(r"    - name: (.+)\n(?:      .*\n|\n)*", text)}

    def test_validate_runs_first_and_every_local_step_waits_for_local_mode(self):
        b = self.blocks()
        order = [m.group(1) for m in re.finditer(r"^    - name: (.+)$", pathlib.Path(ACTION).read_text(), re.M)]
        self.assertEqual(order[0], VALIDATE)
        self.assertEqual(order.index(REQUIRE), order.index("Decide whether to run") + 1)
        self.assertNotIn("if:", b[VALIDATE])
        for n in LOCAL_STEPS:
            self.assertIn("steps.validate.outputs.mode == 'local'", b[n], n)
        self.assertIn("steps.validate.outputs.mode == 'hosted'", b[HOSTED])
        self.assertNotIn("steps.validate.outputs.mode == 'local'", b[HOSTED])

    def test_local_scripts_are_byte_identical_to_the_ones_before_this_change(self):
        want = json.loads((FIX / "local-steps.sha256.json").read_text())
        got = {n: hashlib.sha256(step_script(ACTION, n).encode()).hexdigest() for n in LOCAL_STEPS}
        self.assertEqual(got, want)  # any edit of a local script must be a reviewed change of this fixture

    def test_exact_conditions_and_outputs(self):
        text = pathlib.Path(ACTION).read_text()
        b = self.blocks()
        for n in LOCAL_STEPS[1:] + [REQUIRE]:
            self.assertRegex(b[n], r"\n      if: steps\.validate\.outputs\.mode == 'local' && steps\.guard\.outputs\.run == 'true'\n", n)
        self.assertRegex(b["Decide whether to run"], r"\n      if: steps\.validate\.outputs\.mode == 'local'\n")
        self.assertRegex(b[HOSTED], r"\n      if: steps\.validate\.outputs\.mode == 'hosted'\n")
        self.assertRegex(b[CONCLUSION], r"\n      if: always\(\) && steps\.validate\.outputs\.mode == 'hosted'\n")
        self.assertIn("value: ${{ steps.render.outputs.conclusion || steps.hosted_conclusion.outputs.conclusion }}", text)
        for o in ("run-id", "hit-ratio", "report-url"):
            self.assertIn("value: ${{ steps.hosted.outputs.%s }}" % o, text)
        env_lines = re.findall(r"^        (SITEWARM_ACTION_INPUT_[A-Z_]+): \$\{\{ inputs\.([a-z-]+) \}\}$", b[HOSTED], re.M)
        want = {"SITEWARM_ACTION_INPUT_" + i.upper().replace("-", "_"): i for i in ("api-key", "api-url", "site", "sitemap-url", "wait", "timeout", "fail-on", "site-token")}
        self.assertEqual(len(env_lines), len(want))  # no duplicates, nothing else in the block
        self.assertEqual(dict(env_lines), want)  # each of the 8 variables carries its own input, none cross-wired

    def test_the_bundle_is_the_one_provenance_names(self):
        sha = hashlib.sha256((ROOT / "hosted" / "index.js").read_bytes()).hexdigest()
        self.assertIn(sha, (ROOT / "hosted" / "PROVENANCE.md").read_text())

    def test_defaults(self):
        text = pathlib.Path(ACTION).read_text()
        head = text.split("outputs:")[0]
        self.assertRegex(head, r"  mode:\n(?:    .*\n)*?    default: local\n")
        self.assertRegex(head, r"  site-url:\n(?:    .*\n)*?    required: false\n")
        self.assertRegex(head, r"  fail-on:\n(?:    .*\n)*?    default: ''\n")

    def test_the_secret_reaches_the_hosted_step_only_through_env(self):
        run_body = step_script(ACTION, HOSTED)
        self.assertNotIn("${{", run_body)
        self.assertNotIn("inputs.", run_body)
        self.assertNotRegex(run_body, r"SITEWARM_ACTION_INPUT_API_KEY|SITEWARM_ACTION_INPUT_SITE_TOKEN|\benv\b")  # not even named in the script: no expansion, no launcher
        names = re.findall(r"^    - name: (.+)$", pathlib.Path(ACTION).read_text(), re.M)
        self.assertEqual(len(names), pathlib.Path(ACTION).read_text().count("\n      run: |\n"))  # every step is a run: | step the loop below reads
        for n in names:
            body = step_script(ACTION, n)
            self.assertTrue(body.strip(), n + ": empty script body, the check below would pass vacuously")
            self.assertNotIn("${{", body, n)  # every input reaches a script through env: only
        block = self.blocks()[HOSTED]
        self.assertIn("        SITEWARM_ACTION_INPUT_API_KEY: ${{ inputs.api-key }}\n", block)
        self.assertIn("        SITEWARM_ACTION_INPUT_SITE_TOKEN: ${{ inputs.site-token }}\n", block)


class LocalModeVerdictIsUnchanged(unittest.TestCase):
    def test_fail_on_unset_gives_the_v1_0_1_verdict(self):
        golden = json.loads((FIX / "benign.golden.json").read_text())
        self.assertEqual(render("benign-report.json", "benign-prev.json", fail_on=""), golden)  # the v1.0.1 default, now applied in the script


class ValidateInputs(unittest.TestCase):
    def test_local_with_the_v1_0_1_inputs_passes(self):
        rc, _, gho = validate(mode="local", site_url="https://example.com", urls_file="u.csv")
        self.assertEqual(rc, 0)
        self.assertIn("mode=local", gho)

    def test_hosted_with_its_inputs_passes(self):
        rc, _, gho = validate(mode="hosted", api_key=KEY, api_url="https://api.example.test/v1", site="example.com", wait="false", timeout="5m")
        self.assertEqual(rc == 0 or not HAVE_NODE, True)
        if HAVE_NODE:
            self.assertIn("mode=hosted", gho)

    def test_unknown_or_empty_mode_fails(self):
        for m in ("", "Local", "both", "hosted "):
            rc, out, gho = validate(mode=m, site_url="https://example.com", api_key=KEY)
            self.assertNotEqual(rc, 0, repr(m))
            self.assertIn("mode must be local or hosted", out)
            self.assertNotIn("mode=", gho)

    def test_local_requires_site_url_only_after_the_guard_lets_the_run_go_ahead(self):
        # Parity with v1.0.1: an event the guard skips must not fail on an empty site-url.
        rc, _, gho = validate(mode="local")
        self.assertEqual(rc, 0)
        self.assertIn("mode=local", gho)
        out = pathlib.Path(tempfile.mkdtemp()) / "gho"
        out.write_text("")
        g = bash(step_script(ACTION, "Decide whether to run"), {"WANT_ENV": "production", "GITHUB_SHA": "abc", "GITHUB_EVENT_NAME": "pull_request", "GITHUB_OUTPUT": str(out)})
        self.assertEqual(g.returncode, 0)
        self.assertIn("run=false", out.read_text())  # so the step below is skipped by its if:
        text = pathlib.Path(ACTION).read_text()
        self.assertRegex(text, r"- name: Require site-url \(local\)\n      if: steps\.validate\.outputs\.mode == 'local' && steps\.guard\.outputs\.run == 'true'\n")
        # and when it does run, an empty site-url fails clearly while a set one passes
        r = bash(step_script(ACTION, REQUIRE), {"SITE_URL": ""})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("site-url is required when mode is local", r.stdout)
        self.assertEqual(bash(step_script(ACTION, REQUIRE), {"SITE_URL": "https://example.com"}).returncode, 0)

    def test_local_rejects_each_hosted_input(self):
        for name, v in (("api_key", KEY), ("api_url", "https://x.test/v1"), ("site", "example.com"), ("wait", "true"), ("timeout", "5m")):
            rc, out, gho = validate(mode="local", site_url="https://example.com", **{name: v})
            self.assertNotEqual(rc, 0, name)
            self.assertIn(name.replace("_", "-") + " is only for mode: hosted", out)
            self.assertNotIn("mode=", gho)

    def test_hosted_rejects_each_local_input(self):
        base = dict(mode="hosted", api_key=KEY, api_url="https://x.test/v1", site="example.com")
        for name, v in (("site_url", "https://example.com"), ("urls_file", "u.csv")):
            rc, out, gho = validate(**base, **{name: v})
            self.assertNotEqual(rc, 0, name)
            self.assertIn(name.replace("_", "-") + " is only for mode: local", out)

    def test_hosted_needs_url_and_a_site(self):
        rc, out, _ = validate(mode="hosted", api_key=KEY, site="example.com")
        self.assertIn("api-url is required", out)
        rc, out, _ = validate(mode="hosted", api_key=KEY, api_url="https://x.test/v1")
        self.assertIn("set site or sitemap-url", out)

    def test_fork_pull_request_without_the_secret_fails_clearly_and_never_runs_local(self):
        # On a fork the secret expands to the empty string. The workflow still names site-url, as a local workflow would.
        for extra in ({}, {"site_url": "https://example.com"}):
            rc, out, gho = validate(mode="hosted", api_key="", api_url="https://x.test/v1", site="example.com", **extra)
            self.assertNotEqual(rc, 0)
            self.assertIn("::error title=sitewarm::api-key is empty in mode: hosted", out)
            self.assertIn("never falls back to a local run", out)
            self.assertNotIn("mode=", gho)  # no mode output, so no local step can run
        # and it is the mode, not the key, that decides: the same inputs with mode local do not pass as hosted
        rc, _, gho = validate(mode="local", site_url="https://example.com")
        self.assertIn("mode=local", gho)

    def test_wait_accepts_only_what_both_parsers_read_the_same_way(self):
        base = dict(mode="hosted", api_key=KEY, api_url="https://x.test/v1", site="example.com")
        for bad in (" false", "false ", "0", "no", "off", "yes", "1"):
            rc, out, gho = validate(wait=bad, **base)
            self.assertNotEqual(rc, 0, repr(bad))
            self.assertIn("wait must be true or false", out)
            self.assertNotIn("mode=", gho)
        if HAVE_NODE:
            for ok in ("", "true", "false", "TRUE", "False"):
                self.assertEqual(validate(wait=ok, **base)[0], 0, ok)

    def test_the_mask_command_escapes_its_value_and_multiline_credentials_are_refused(self):
        rc, out, _ = validate(mode="hosted", api_key="a%25b%0Ac", api_url="https://x.test/v1", site="example.com")
        self.assertEqual(out.splitlines()[0], "::add-mask::a%2525b%250Ac")  # '%' escaped, so the runner masks the real value
        rc, out, gho = validate(mode="hosted", api_key="x\n::warning::y", api_url="https://x.test/v1", site="example.com")
        self.assertNotEqual(rc, 0)
        self.assertEqual(out.splitlines()[0], "::add-mask::x%0A::warning::y")
        self.assertEqual([l for l in out.splitlines() if l.startswith("::") and not l.startswith(("::add-mask::", "::error title=sitewarm::"))], [])
        self.assertIn("single line", out)
        self.assertNotIn("mode=", gho)

    def test_site_token_fails_in_both_modes_and_is_never_echoed(self):
        for kw in (dict(mode="local", site_url="https://example.com"), dict(mode="hosted", api_key=KEY, api_url="https://x.test/v1", site="example.com")):
            rc, out, _ = validate(site_token=TOKEN, **kw)
            self.assertNotEqual(rc, 0)
            self.assertIn("site-token is not available yet", out)
            self.assertEqual([l for l in out.splitlines() if TOKEN in l], [f"::add-mask::{TOKEN}"])

    def test_no_message_echoes_a_value_and_the_key_is_masked_first(self):
        rc, out, _ = validate(mode="local", site_url="https://example.com", api_key=KEY)
        self.assertNotEqual(rc, 0)
        self.assertEqual(out.splitlines()[0], f"::add-mask::{KEY}")
        self.assertEqual([l for l in out.splitlines() if KEY in l], [f"::add-mask::{KEY}"])


class FakeApi(http.server.BaseHTTPRequestHandler):
    log: list = []
    script: dict = {}

    def log_message(self, *a):
        pass

    def _send(self, status, body, ctype="application/json"):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n)) if n else None
        type(self).log.append({"method": self.command, "path": self.path.split("?")[0], "auth": self.headers.get("Authorization"), "ua": self.headers.get("User-Agent"), "body": body})
        path = self.path.split("?")[0].removeprefix("/v1")
        page = lambda data: {"data": data, "page": {"has_more": False, "next_cursor": None}}
        s = type(self).script
        if s.get("status") and path == "/sites":
            return self._send(s["status"], {"type": "/problems/x", "title": "rejected", "status": s["status"]}, "application/problem+json")
        if path == "/sites":
            return self._send(200, page([{"id": "site_1", "hostname": "example.com", "verification": {"status": "verified"}, "paused": False, "settings": {}, "created_at": "2026-10-01T00:00:00Z"}]))
        if path == "/sites/site_1/sitemaps" and s.get("sitemaps_status"):
            return self._send(s["sitemaps_status"], {"type": "/problems/x", "title": "nope", "status": s["sitemaps_status"]}, "application/problem+json")
        if path == "/sites/site_1/sitemaps":
            return self._send(200, page([{"id": "sm_1", "site_id": "site_1", "url": "https://example.com/sitemap.xml", "created_at": "2026-10-01T00:00:00Z"}]))
        run = {"id": "run_1", "site_id": "site_1", "status": "queued", "trigger": {"type": "api"}, "options": s.get("options", {"fail_on": ["miss", "error", "incomplete", "noindex"]}), "outcome": None, "vantage_points": [], "created_at": "2026-10-18T00:00:00Z"}
        if path == "/sites/site_1/warm-runs" and self.command == "POST":
            return self._send(202, run)
        if path == "/warm-runs/run_1":
            run.update(status="completed", outcome=s["outcome"], vantage_points=[{"vantage_point_id": "vp_1", "region": "eu", "status": "completed", "n": 10, "counts": {"hit": 9, "miss": 1}}])
            return self._send(200, run)
        if path == "/sites/site_1/cache-status-reports":
            return self._send(200, page([{"id": "rep_1", "site_id": "site_1", "warm_run_id": "run_1", "created_at": "2026-10-18T00:01:00Z"}]))
        return self._send(404, {"type": "/problems/not-found", "title": "nope", "status": 404}, "application/problem+json")

    do_GET = do_POST = _handle


PASS = {"failed": False, "failing_states": [], "reason": None}
FAILED = {"failed": True, "failing_states": ["miss"], "reason": None}


@unittest.skipUnless(HAVE_NODE, "node is not installed: the hosted bundle was not run")
class HostedAgainstAFakeServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeApi)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def hosted(self, outcome=PASS, status=None, options=None, sitemaps_status=None, **over):
        FakeApi.log = []
        FakeApi.script = {"outcome": outcome, "status": status, "sitemaps_status": sitemaps_status, **({"options": options} if options is not None else {})}
        tmp = pathlib.Path(tempfile.mkdtemp())
        gho, summary = tmp / "gho", tmp / "summary.md"
        gho.write_text("")
        summary.write_text("")
        shim = tmp / "bin"
        shim.mkdir()
        argv_log = tmp / "argv.log"
        (shim / "node").write_text('#!/bin/sh\necho "node $*" >> "$ARGV_LOG"\nexec "$REAL_NODE" "$@"\n')
        (shim / "node").chmod(0o755)
        self.argv_log = argv_log
        env = {"PATH": f"{shim}:{os.environ['PATH']}", "ARGV_LOG": str(argv_log), "REAL_NODE": shutil.which("node"), "SITEWARM_ACTION_INPUT_API_KEY": KEY, "SITEWARM_ACTION_INPUT_API_URL": f"http://127.0.0.1:{self.port}/v1", "SITEWARM_ACTION_INPUT_SITE": "example.com", "SITEWARM_ACTION_INPUT_SITEMAP_URL": "", "SITEWARM_ACTION_INPUT_WAIT": "", "SITEWARM_ACTION_INPUT_TIMEOUT": "", "SITEWARM_ACTION_INPUT_FAIL_ON": "",
               "GITHUB_ACTION_PATH": str(ROOT), "GITHUB_OUTPUT": str(gho), "GITHUB_STEP_SUMMARY": str(summary), "GITHUB_REPOSITORY": "acme/web", "GITHUB_RUN_ID": "42",
               "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "0123abcd", "GITHUB_JOB": "deploy", "GITHUB_ACTION": "__run",
               "HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9", "NO_PROXY": "127.0.0.1"}
        env.update(over)
        r = bash(step_script(ACTION, HOSTED), env)
        outputs = {m[0]: m[2] for m in re.findall(r"^([\w-]+)<<(\S+)\n([^\n]*)\n\2$", gho.read_text(), re.M)}
        c = bash(step_script(ACTION, CONCLUSION), {"OUTCOME": "success" if r.returncode == 0 else "failure", "WAIT": env["SITEWARM_ACTION_INPUT_WAIT"], "GITHUB_OUTPUT": str(tmp / "c")})
        conclusion = (tmp / "c").read_text().strip() if (tmp / "c").exists() else ""
        return r, outputs, summary.read_text(), conclusion

    def test_ambient_cli_variables_change_nothing(self):
        ambient = {"SITEWARM_API_KEY": "ambient-key", "SITEWARM_API_URL": "http://127.0.0.1:9/v1", "SITEWARM_FAIL_ON": "none", "SITEWARM_SITE": "other.example", "SITEWARM_WAIT": "false", "SITEWARM_TIMEOUT": "1", "SITEWARM_SITEMAP_URL": "http://127.0.0.1:9/s.xml", "SITEWARM_SITE_TOKEN": "t"}
        r, outputs, _, conclusion = self.hosted(**ambient)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(all(c["auth"] == f"Bearer {KEY}" for c in FakeApi.log))
        self.assertNotIn("options", next(c for c in FakeApi.log if c["method"] == "POST")["body"])  # ambient fail-on was not read
        self.assertEqual(conclusion, "conclusion=success")

    def test_an_empty_input_is_not_filled_from_an_ambient_variable(self):
        # api-url empty while SITEWARM_API_URL points at the live fake server: the run must fail without a single request.
        r, _, _, _ = self.hosted(SITEWARM_ACTION_INPUT_API_URL="", SITEWARM_API_URL=f"http://127.0.0.1:{self.port}/v1")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(FakeApi.log, [])
        self.assertIn("api-url", r.stdout + r.stderr)

    def test_a_passing_run_sets_outputs_and_talks_only_to_the_fake_server(self):
        r, outputs, summary, conclusion = self.hosted()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], f"::add-mask::{KEY}")
        self.assertEqual(outputs.get("run-id"), "run_1")
        self.assertEqual(outputs.get("hit-ratio"), "0.9000")
        self.assertTrue(outputs.get("report-url", "").endswith("/v1/cache-status-reports/rep_1"))
        self.assertEqual(conclusion, "conclusion=success")
        self.assertIn("**Passed.**", summary)
        self.assertGreaterEqual(len(FakeApi.log), 4)
        self.assertTrue(all(c["auth"] == f"Bearer {KEY}" for c in FakeApi.log))
        self.assertTrue(all((c["ua"] or "").startswith("sitewarm-action/") for c in FakeApi.log))
        post = next(c for c in FakeApi.log if c["method"] == "POST")
        self.assertEqual(post["body"]["source"], {"type": "sitemap", "sitemap_id": "sm_1"})
        self.assertNotIn("options", post["body"])  # fail-on unset: the service default applies
        self.assertEqual([l for l in (r.stdout + r.stderr).splitlines() if KEY in l], [f"::add-mask::{KEY}"])
        argv = self.argv_log.read_text()
        self.assertIn("hosted/index.js", argv)  # the shim really saw the launch
        self.assertNotIn(KEY, argv)  # the key is never an argument of the process that receives it

    def test_a_run_without_options_fail_on_still_passes_and_says_not_reported(self):
        # The API contract is a list or null; the first bundle crashed the summary on a missing field (fixed in 3d3f939).
        for options in ({}, {"fail_on": None}):
            r, _, summary, conclusion = self.hosted(options=options)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("crashed", r.stdout)
            self.assertIn("| Effective fail-on | not reported yet |", summary)
            self.assertEqual(conclusion, "conclusion=success")

    def test_fail_on_is_sent_when_set(self):
        r, _, _, _ = self.hosted(SITEWARM_ACTION_INPUT_FAIL_ON="miss,noindex")
        self.assertEqual(r.returncode, 0, r.stdout)
        post = next(c for c in FakeApi.log if c["method"] == "POST")
        self.assertEqual(post["body"]["options"], {"fail_on": ["miss", "noindex"]})

    def test_a_failed_verdict_fails_the_step_and_the_conclusion(self):
        r, outputs, summary, conclusion = self.hosted(outcome=FAILED)
        self.assertEqual(r.returncode, 1)
        self.assertIn("::error::", r.stdout)
        self.assertEqual(conclusion, "conclusion=failure")
        self.assertEqual(outputs.get("run-id"), "run_1")

    def test_wait_false_only_starts_the_run_and_is_neutral(self):
        r, outputs, _, _ = self.hosted(SITEWARM_ACTION_INPUT_WAIT="false")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(outputs.get("hit-ratio"), "")
        self.assertFalse(any(c["path"] == "/v1/warm-runs/run_1" for c in FakeApi.log))
        c = bash(step_script(ACTION, CONCLUSION), {"OUTCOME": "success", "WAIT": "False", "GITHUB_OUTPUT": "/dev/stdout"})
        self.assertEqual(c.stdout.strip(), "conclusion=neutral")

    def test_a_rejected_key_fails_once_with_a_hint_and_never_prints_the_key(self):
        r, _, _, conclusion = self.hosted(status=401)
        self.assertEqual(r.returncode, 1)
        self.assertIn("check the api-key", r.stdout)
        self.assertEqual(len([c for c in FakeApi.log if c["method"] == "GET" and c["path"] == "/v1/sites"]), 1)
        self.assertEqual(conclusion, "conclusion=failure")
        self.assertEqual([l for l in (r.stdout + r.stderr).splitlines() if KEY in l], [f"::add-mask::{KEY}"])

    def test_a_host_without_sitemaps_listing_fails_clearly_and_never_prints_the_key(self):
        r, _, summary, conclusion = self.hosted(sitemaps_status=404)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 1)
        self.assertIn("this sitewarm host does not support sitemaps listing yet", out)
        self.assertIn("this sitewarm host does not support sitemaps listing yet", summary)
        self.assertEqual(conclusion, "conclusion=failure")
        # It stops there: no run is started, and the listing is asked once.
        self.assertEqual([c for c in FakeApi.log if c["method"] == "POST"], [])
        self.assertEqual(len([c for c in FakeApi.log if c["path"] == "/v1/sites/site_1/sitemaps"]), 1)
        for text in (out, summary):
            self.assertEqual([l for l in text.splitlines() if KEY in l and l != f"::add-mask::{KEY}"], [])
        # Any other status keeps its own message: a 403 is a missing scope, not a missing route.
        r, _, _, _ = self.hosted(sitemaps_status=403)
        self.assertNotIn("does not support sitemaps listing", r.stdout + r.stderr)
        self.assertIn("lacks a required scope", r.stdout + r.stderr)

    def test_a_plain_http_non_loopback_url_is_refused_before_any_request(self):
        r, _, _, _ = self.hosted(SITEWARM_ACTION_INPUT_API_URL="http://api.example.test/v1")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(FakeApi.log, [])


class ConclusionStep(unittest.TestCase):
    def conclusion(self, outcome, wait):
        gho = pathlib.Path(tempfile.mkdtemp()) / "o"
        bash(step_script(ACTION, CONCLUSION), {"OUTCOME": outcome, "WAIT": wait, "GITHUB_OUTPUT": str(gho)})
        return gho.read_text().strip()

    def test_table(self):
        self.assertEqual(self.conclusion("success", ""), "conclusion=success")
        self.assertEqual(self.conclusion("success", "true"), "conclusion=success")
        self.assertEqual(self.conclusion("success", "FALSE"), "conclusion=neutral")
        self.assertEqual(self.conclusion("failure", "false"), "conclusion=failure")
        self.assertEqual(self.conclusion("skipped", ""), "conclusion=failure")


if __name__ == "__main__":
    unittest.main()
