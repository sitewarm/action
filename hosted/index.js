"use strict";

// src/run.ts
var import_node_crypto2 = require("node:crypto");

// ../sdk-ts/src/generated/operations.ts
var operationTable = {
  listSites: { method: "GET", path: "/sites", idempotency: "none" },
  createSite: { method: "POST", path: "/sites", idempotency: "optional" },
  getSite: { method: "GET", path: "/sites/{siteId}", idempotency: "none" },
  updateSite: { method: "PATCH", path: "/sites/{siteId}", idempotency: "none" },
  deleteSite: { method: "DELETE", path: "/sites/{siteId}", idempotency: "none" },
  listSitemaps: { method: "GET", path: "/sites/{siteId}/sitemaps", idempotency: "none" },
  createSitemap: { method: "POST", path: "/sites/{siteId}/sitemaps", idempotency: "optional" },
  getSitemap: { method: "GET", path: "/sites/{siteId}/sitemaps/{sitemapId}", idempotency: "none" },
  deleteSitemap: { method: "DELETE", path: "/sites/{siteId}/sitemaps/{sitemapId}", idempotency: "none" },
  listUrlSets: { method: "GET", path: "/sites/{siteId}/url-sets", idempotency: "none" },
  createUrlSet: { method: "POST", path: "/sites/{siteId}/url-sets", idempotency: "optional" },
  getUrlSet: { method: "GET", path: "/sites/{siteId}/url-sets/{urlSetId}", idempotency: "none" },
  replaceUrlSet: { method: "PUT", path: "/sites/{siteId}/url-sets/{urlSetId}", idempotency: "none" },
  deleteUrlSet: { method: "DELETE", path: "/sites/{siteId}/url-sets/{urlSetId}", idempotency: "none" },
  listWarmRuns: { method: "GET", path: "/sites/{siteId}/warm-runs", idempotency: "none" },
  createWarmRun: { method: "POST", path: "/sites/{siteId}/warm-runs", idempotency: "required" },
  getWarmRun: { method: "GET", path: "/warm-runs/{runId}", idempotency: "none" },
  cancelWarmRun: { method: "POST", path: "/warm-runs/{runId}/cancel", idempotency: "optional" },
  listWarmRunResults: { method: "GET", path: "/warm-runs/{runId}/results", idempotency: "none" },
  listCacheStatusReports: { method: "GET", path: "/sites/{siteId}/cache-status-reports", idempotency: "none" },
  getCacheStatusReport: { method: "GET", path: "/cache-status-reports/{reportId}", idempotency: "none" },
  listSchedules: { method: "GET", path: "/sites/{siteId}/schedules", idempotency: "none" },
  createSchedule: { method: "POST", path: "/sites/{siteId}/schedules", idempotency: "optional" },
  getSchedule: { method: "GET", path: "/schedules/{scheduleId}", idempotency: "none" },
  updateSchedule: { method: "PATCH", path: "/schedules/{scheduleId}", idempotency: "none" },
  deleteSchedule: { method: "DELETE", path: "/schedules/{scheduleId}", idempotency: "none" },
  listWebhooks: { method: "GET", path: "/webhooks", idempotency: "none" },
  createWebhook: { method: "POST", path: "/webhooks", idempotency: "optional" },
  getWebhook: { method: "GET", path: "/webhooks/{webhookId}", idempotency: "none" },
  updateWebhook: { method: "PATCH", path: "/webhooks/{webhookId}", idempotency: "none" },
  deleteWebhook: { method: "DELETE", path: "/webhooks/{webhookId}", idempotency: "none" },
  rotateWebhookSecret: { method: "POST", path: "/webhooks/{webhookId}/rotate-secret", idempotency: "optional" },
  listApiKeys: { method: "GET", path: "/api-keys", idempotency: "none" },
  createApiKey: { method: "POST", path: "/api-keys", idempotency: "optional" },
  getApiKey: { method: "GET", path: "/api-keys/{apiKeyId}", idempotency: "none" },
  revokeApiKey: { method: "DELETE", path: "/api-keys/{apiKeyId}", idempotency: "none" }
};

// ../sdk-ts/src/errors.ts
var SiteWarmError = class extends Error {
  name = "SiteWarmError";
};
var SiteWarmConnectionError = class extends SiteWarmError {
  name = "SiteWarmConnectionError";
  constructor(message, options) {
    super(message, options);
  }
};
var SiteWarmTimeoutError = class extends SiteWarmConnectionError {
  name = "SiteWarmTimeoutError";
};
var SiteWarmApiError = class extends SiteWarmError {
  name = "SiteWarmApiError";
  status;
  problem;
  /** Problem type slug (for example `site-not-verified`), when the server sent one. */
  code;
  /** Parsed `Retry-After`, in seconds. */
  retryAfterSeconds;
  rateLimit;
  constructor(init) {
    const { problem, status } = init;
    super(`sitewarm API error ${status}${problem.title ? `: ${problem.title}` : ""}${problem.detail ? ` (${problem.detail})` : ""}`);
    this.status = status;
    this.problem = problem;
    this.code = problemCode(problem);
    this.retryAfterSeconds = init.retryAfterSeconds;
    this.rateLimit = init.rateLimit ?? {};
  }
};
var SiteWarmAuthenticationError = class extends SiteWarmApiError {
  name = "SiteWarmAuthenticationError";
};
var SiteWarmPermissionError = class extends SiteWarmApiError {
  name = "SiteWarmPermissionError";
};
var SiteWarmNotFoundError = class extends SiteWarmApiError {
  name = "SiteWarmNotFoundError";
};
var SiteWarmConflictError = class extends SiteWarmApiError {
  name = "SiteWarmConflictError";
};
var SiteWarmValidationError = class extends SiteWarmApiError {
  name = "SiteWarmValidationError";
};
var SiteWarmRateLimitError = class extends SiteWarmApiError {
  name = "SiteWarmRateLimitError";
};
var SiteWarmServerError = class extends SiteWarmApiError {
  name = "SiteWarmServerError";
};
var SiteWarmWaitTimeoutError = class extends SiteWarmError {
  name = "SiteWarmWaitTimeoutError";
  runId;
  lastStatus;
  constructor(runId, lastStatus, timeoutMs) {
    super(`warm run ${runId} did not finish within ${timeoutMs} ms (last status: ${lastStatus})`);
    this.runId = runId;
    this.lastStatus = lastStatus;
  }
};
function problemCode(problem) {
  if (typeof problem.code === "string") return problem.code;
  if (typeof problem.type === "string") {
    const slug = problem.type.split("/").filter(Boolean).pop();
    if (slug && /^[a-z0-9-]+$/.test(slug)) return slug;
  }
  return void 0;
}
function apiErrorFor(init) {
  const { status } = init;
  if (status === 401) return new SiteWarmAuthenticationError(init);
  if (status === 403) return new SiteWarmPermissionError(init);
  if (status === 404) return new SiteWarmNotFoundError(init);
  if (status === 409) return new SiteWarmConflictError(init);
  if (status === 400 || status === 422) return new SiteWarmValidationError(init);
  if (status === 429) return new SiteWarmRateLimitError(init);
  if (status >= 500) return new SiteWarmServerError(init);
  return new SiteWarmApiError(init);
}

// ../sdk-ts/src/retry.ts
function parseRetryAfter(value, now = Date.now()) {
  if (value == null) return void 0;
  const v = value.trim();
  if (v === "") return void 0;
  if (/^\d+$/.test(v)) return Number(v);
  const at = Date.parse(v);
  if (Number.isNaN(at)) return void 0;
  return Math.max(0, Math.ceil((at - now) / 1e3));
}
function backoffDelayMs(attempt, baseMs, maxMs, random = Math.random) {
  const ceiling = Math.min(maxMs, baseMs * 2 ** attempt);
  return Math.floor(ceiling / 2 + random() * (ceiling / 2));
}
function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason);
    const onAbort = () => {
      clearTimeout(timer);
      reject(signal?.reason);
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

// ../sdk-ts/src/resources.ts
var isTerminal = (status) => status === "completed" || status === "canceled" || status === "failed";
function createResources(c) {
  return {
    sites: {
      list: (query, o) => c.call("listSites", { query, ...o }),
      listAll: (query, o) => c.paginate("listSites", { query, ...o }),
      get: (siteId, o) => c.call("getSite", { path: { siteId }, ...o }),
      create: (body, o) => c.call("createSite", { body, ...o }),
      update: (siteId, body, o) => c.call("updateSite", { path: { siteId }, body, ...o }),
      delete: (siteId, o) => c.call("deleteSite", { path: { siteId }, ...o })
    },
    sitemaps: {
      list: (siteId, query, o) => c.call("listSitemaps", { path: { siteId }, query, ...o }),
      listAll: (siteId, query, o) => c.paginate("listSitemaps", { path: { siteId }, query, ...o }),
      get: (siteId, sitemapId, o) => c.call("getSitemap", { path: { siteId, sitemapId }, ...o }),
      create: (siteId, body, o) => c.call("createSitemap", { path: { siteId }, body, ...o }),
      delete: (siteId, sitemapId, o) => c.call("deleteSitemap", { path: { siteId, sitemapId }, ...o })
    },
    warmRuns: {
      /** Starts a run (`202`). Sends `Idempotency-Key` (generated if you do not pass `idempotencyKey`). */
      create: (siteId, body, o) => c.call("createWarmRun", { path: { siteId }, body, ...o }),
      get: (runId, o) => c.call("getWarmRun", { path: { runId }, ...o }),
      cancel: (runId, o) => c.call("cancelWarmRun", { path: { runId }, ...o }),
      listForSite: (siteId, query, o) => c.call("listWarmRuns", { path: { siteId }, query, ...o }),
      listAllForSite: (siteId, query, o) => c.paginate("listWarmRuns", { path: { siteId }, query, ...o }),
      results: (runId, query, o) => c.call("listWarmRunResults", { path: { runId }, query, ...o }),
      listAllResults: (runId, query, o) => c.paginate("listWarmRunResults", { path: { runId }, query, ...o }),
      /**
       * Polls the run until `status` is `completed`, `canceled` or `failed`, honoring the `Retry-After` of each
       * poll. `outcome` is only set on `completed` runs. Throws {@link SiteWarmWaitTimeoutError} on timeout
       * (the run is NOT canceled).
       */
      wait: async (runId, w = {}) => {
        const timeoutMs = w.timeoutMs ?? 9e5;
        const dflt = w.pollIntervalMs ?? 5e3;
        const min = w.minPollIntervalMs ?? 1e3;
        const max = w.maxPollIntervalMs ?? 6e4;
        const deadline = Date.now() + timeoutMs;
        for (; ; ) {
          const { data: run2, headers } = await c.callRaw("getWarmRun", { path: { runId }, signal: w.signal });
          w.onPoll?.(run2);
          if (isTerminal(run2.status)) return run2;
          const remaining = deadline - Date.now();
          if (remaining <= 0) throw new SiteWarmWaitTimeoutError(runId, run2.status, timeoutMs);
          const hinted = parseRetryAfter(headers.get("Retry-After"));
          const delay = Math.min(max, Math.max(min, hinted !== void 0 ? hinted * 1e3 : dflt));
          if (delay >= remaining) {
            await sleep(remaining, w.signal);
            const final = await c.call("getWarmRun", { path: { runId }, signal: w.signal });
            w.onPoll?.(final);
            if (isTerminal(final.status)) return final;
            throw new SiteWarmWaitTimeoutError(runId, final.status, timeoutMs);
          }
          await sleep(delay, w.signal);
        }
      }
    },
    cacheStatusReports: {
      listForSite: (siteId, query, o) => c.call("listCacheStatusReports", { path: { siteId }, query, ...o }),
      get: (reportId, o) => c.call("getCacheStatusReport", { path: { reportId }, ...o })
    }
  };
}

// ../sdk-ts/src/client.ts
var LOOPBACK = /* @__PURE__ */ new Set(["localhost", "127.0.0.1", "[::1]"]);
var DEFAULT_MAX_RETRIES = 3;
var SiteWarm = class {
  sites;
  sitemaps;
  warmRuns;
  cacheStatusReports;
  #apiKey;
  #baseUrl;
  #fetch;
  #maxRetries;
  #retryBaseDelayMs;
  #maxRetryDelayMs;
  #timeoutMs;
  #userAgent;
  constructor(options) {
    if (typeof options.apiKey !== "string" || !/^[\x21-\x7e]+$/.test(options.apiKey)) {
      throw new SiteWarmError("apiKey must be a non-empty string without whitespace or control characters");
    }
    this.#apiKey = options.apiKey;
    this.#baseUrl = normalizeBaseUrl(options.baseUrl);
    const f = options.fetch ?? globalThis.fetch;
    if (typeof f !== "function") throw new SiteWarmError("no fetch implementation available; pass options.fetch");
    this.#fetch = f;
    this.#maxRetries = options.maxRetries ?? DEFAULT_MAX_RETRIES;
    this.#retryBaseDelayMs = options.retryBaseDelayMs ?? 500;
    this.#maxRetryDelayMs = options.maxRetryDelayMs ?? 3e4;
    this.#timeoutMs = options.timeoutMs ?? 3e4;
    this.#userAgent = options.userAgent;
    const resources = createResources(this);
    this.sites = resources.sites;
    this.sitemaps = resources.sitemaps;
    this.warmRuns = resources.warmRuns;
    this.cacheStatusReports = resources.cacheStatusReports;
  }
  /** Calls one operation by its `operationId` and returns the decoded body. */
  async call(operationId, args = {}) {
    return (await this.callRaw(operationId, args)).data;
  }
  /** Like {@link call} but also returns status and response headers. */
  async callRaw(operationId, args = {}) {
    const op = operationTable[operationId];
    const a = args;
    const url = this.#baseUrl + expandPath(op.path, a.path) + queryString(a.query);
    const headers = {
      Authorization: `Bearer ${this.#apiKey}`,
      Accept: "application/json, application/problem+json"
    };
    if (this.#userAgent) headers["User-Agent"] = this.#userAgent;
    let body;
    if (a.body !== void 0) {
      body = JSON.stringify(a.body);
      headers["Content-Type"] = "application/json";
    }
    const sendsKey = op.idempotency !== "none" && op.method === "POST";
    if (sendsKey) headers["Idempotency-Key"] = a.idempotencyKey ?? crypto.randomUUID();
    const safeToRetryAmbiguous = op.method !== "POST" || sendsKey;
    for (let attempt = 0; ; attempt++) {
      const last = attempt >= this.#maxRetries;
      let response;
      try {
        response = await this.#fetch(url, {
          method: op.method,
          headers,
          body,
          redirect: "manual",
          signal: combineSignals(a.signal, this.#timeoutMs)
        });
      } catch (err) {
        if (a.signal?.aborted) throw a.signal.reason ?? err;
        const timedOut = err instanceof Error && err.name === "TimeoutError";
        if (!last && safeToRetryAmbiguous) {
          await sleep(backoffDelayMs(attempt, this.#retryBaseDelayMs, this.#maxRetryDelayMs), a.signal);
          continue;
        }
        throw timedOut ? new SiteWarmTimeoutError(`request timed out after ${this.#timeoutMs} ms`, { cause: err }) : new SiteWarmConnectionError(`request failed: ${err instanceof Error ? err.message : "network error"}`, { cause: err });
      }
      if (response.ok) return { data: await parseBody(response), status: response.status, headers: response.headers };
      const retryAfter = parseRetryAfter(response.headers.get("Retry-After"));
      const retryable = response.status === 429 || response.status >= 500 && response.status !== 501 && safeToRetryAmbiguous;
      if (retryable && !last) {
        const waitMs = retryAfter !== void 0 ? retryAfter * 1e3 : backoffDelayMs(attempt, this.#retryBaseDelayMs, this.#maxRetryDelayMs);
        if (waitMs <= this.#maxRetryDelayMs) {
          await discard(response);
          await sleep(waitMs, a.signal);
          continue;
        }
      }
      throw apiErrorFor({
        status: response.status,
        problem: await parseProblem(response),
        retryAfterSeconds: retryAfter,
        rateLimit: readRateLimit(response.headers)
      });
    }
  }
  /** Iterates the pages (`{ data, page }`) of a list operation, following `page.next_cursor`. */
  async *pages(operationId, args = {}, options = {}) {
    const maxPages = options.maxPages ?? 1e4;
    let cursor = args.query?.cursor;
    for (let n = 0; n < maxPages; n++) {
      const query = { ...args.query, ...cursor ? { cursor } : {} };
      const page = await this.call(operationId, { ...args, query });
      yield page;
      const next = page.page.next_cursor;
      if (!page.page.has_more || !next) return;
      if (next === cursor) throw new SiteWarmError("pagination cursor did not advance");
      cursor = next;
    }
  }
  /** Iterates every item of a list operation across pages. */
  async *paginate(operationId, args = {}, options = {}) {
    for await (const page of this.pages(operationId, args, options)) {
      yield* page.data;
    }
  }
  toJSON() {
    return { baseUrl: this.#baseUrl };
  }
  [/* @__PURE__ */ Symbol.for("nodejs.util.inspect.custom")]() {
    return `SiteWarm { baseUrl: '${this.#baseUrl}' }`;
  }
};
function normalizeBaseUrl(raw) {
  let u;
  try {
    u = new URL(raw);
  } catch {
    throw new SiteWarmError("baseUrl must be an absolute URL such as https://<host>/v1");
  }
  const loopback = LOOPBACK.has(u.hostname);
  if (u.protocol !== "https:" && !(u.protocol === "http:" && loopback)) {
    throw new SiteWarmError("baseUrl must use https (http is only allowed for localhost)");
  }
  if (u.username || u.password) throw new SiteWarmError("baseUrl must not contain credentials");
  if (u.search || u.hash) throw new SiteWarmError("baseUrl must not contain a query or fragment");
  return u.origin + u.pathname.replace(/\/+$/, "");
}
function expandPath(template, values) {
  return template.replace(/\{(\w+)\}/g, (_m, name) => {
    const v = values?.[name];
    if (v === void 0 || v === "") throw new SiteWarmError(`missing path parameter "${name}"`);
    return encodeURIComponent(String(v));
  });
}
function queryString(query) {
  if (!query) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== void 0 && v !== null) p.append(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}
function combineSignals(user, timeoutMs) {
  const timeout = AbortSignal.timeout(timeoutMs);
  return user ? AbortSignal.any([user, timeout]) : timeout;
}
async function discard(response) {
  try {
    await response.body?.cancel();
  } catch {
  }
}
async function parseBody(response) {
  if (response.status === 204) return void 0;
  const text = await response.text();
  if (text === "") return void 0;
  try {
    return JSON.parse(text);
  } catch {
    throw new SiteWarmError(`invalid JSON in ${response.status} response`);
  }
}
async function parseProblem(response) {
  const fallback = { type: "about:blank", title: response.statusText || `HTTP ${response.status}`, status: response.status };
  try {
    const text = await response.text();
    const json = JSON.parse(text);
    if (json && typeof json === "object" && !Array.isArray(json)) {
      const p = json;
      return {
        ...p,
        type: typeof p.type === "string" ? p.type : fallback.type,
        title: typeof p.title === "string" ? p.title : fallback.title,
        status: typeof p.status === "number" ? p.status : response.status
      };
    }
  } catch {
  }
  return fallback;
}
function readRateLimit(h) {
  const num = (name) => {
    const v = h.get(name);
    return v !== null && /^\d+$/.test(v.trim()) ? Number(v) : void 0;
  };
  const info2 = {};
  const limit = num("RateLimit-Limit");
  const remaining = num("RateLimit-Remaining");
  const reset = num("RateLimit-Reset");
  if (limit !== void 0) info2.limit = limit;
  if (remaining !== void 0) info2.remaining = remaining;
  if (reset !== void 0) info2.reset = reset;
  return info2;
}

// src/workflow.ts
var import_node_fs = require("node:fs");
var import_node_crypto = require("node:crypto");
var escapeData = (s) => s.replace(/%/g, "%25").replace(/\r/g, "%0D").replace(/\n/g, "%0A");
var escapeProperty = (s) => escapeData(s).replace(/:/g, "%3A").replace(/,/g, "%2C");
function getInput(io, name) {
  const upper = name.replace(/ /g, "_").toUpperCase();
  return (io.env[`INPUT_${upper}`] ?? io.env[`SITEWARM_${upper.replace(/-/g, "_")}`] ?? "").trim();
}
function addMask(io, secret) {
  if (secret) io.out(`::add-mask::${escapeData(secret)}`);
}
var info = (io, msg) => io.out(msg);
var notice = (io, msg) => io.out(`::notice::${escapeData(msg)}`);
var warning = (io, msg) => io.out(`::warning::${escapeData(msg)}`);
var error = (io, msg) => io.out(`::error::${escapeData(msg)}`);
function setOutput(io, name, value) {
  const file = io.env.GITHUB_OUTPUT;
  if (!file) {
    io.out(`::set-output name=${escapeProperty(name)}::${escapeData(value)}`);
    return;
  }
  const delim = `ghadelim_${(0, import_node_crypto.randomBytes)(16).toString("hex")}`;
  (0, import_node_fs.appendFileSync)(file, `${name}<<${delim}
${value}
${delim}
`);
}
function appendSummary(io, markdown) {
  const file = io.env.GITHUB_STEP_SUMMARY;
  if (file) (0, import_node_fs.appendFileSync)(file, markdown + "\n");
}

// src/inputs.ts
var InputError = class extends Error {
  name = "InputError";
};
var DEFAULT_TIMEOUT = "15m";
var LOOPBACK2 = /* @__PURE__ */ new Set(["localhost", "127.0.0.1", "[::1]"]);
var TOKEN = /^[a-z][a-z0-9-]*$/;
function parseBool(name, raw, dflt) {
  if (raw === "") return dflt;
  const v = raw.toLowerCase();
  if (v === "true") return true;
  if (v === "false") return false;
  throw new InputError(`input "${name}" must be "true" or "false", got "${raw}"`);
}
function parseDuration(name, raw) {
  const m = /^(\d+)(s|m|h)$/.exec(raw);
  const n = m ? Number(m[1]) : 0;
  if (!m || n <= 0) throw new InputError(`input "${name}" must look like 90s, 15m or 2h, got "${raw}"`);
  return n * { s: 1e3, m: 6e4, h: 36e5 }[m[2]];
}
function parseFailOn(raw) {
  if (raw === "") return void 0;
  const tokens = raw.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
  if (tokens.length === 0) throw new InputError('input "fail-on" has no tokens; use "none" to fail on nothing');
  if (tokens.includes("none")) {
    if (tokens.length > 1) throw new InputError('input "fail-on": "none" cannot be combined with other values');
    return [];
  }
  for (const t of tokens) {
    if (!TOKEN.test(t)) throw new InputError(`input "fail-on": "${t}" is not a valid state name`);
  }
  return [...new Set(tokens)];
}
function checkApiUrl(raw) {
  let u;
  try {
    u = new URL(raw);
  } catch {
    throw new InputError('input "api-url" must be an absolute URL such as https://<host>/v1');
  }
  if (u.protocol !== "https:" && !(u.protocol === "http:" && LOOPBACK2.has(u.hostname))) {
    throw new InputError('input "api-url" must use https (http is only allowed for localhost)');
  }
  if (u.username || u.password) throw new InputError('input "api-url" must not contain credentials');
  return raw;
}
function readInputs(io) {
  if (getInput(io, "site-token")) {
    throw new InputError('input "site-token" is not available yet: this version accepts only "api-key" (see the action README)');
  }
  const apiKey = getInput(io, "api-key");
  if (!apiKey) throw new InputError('input "api-key" is required (store it as a secret, for example secrets.SITEWARM_API_KEY)');
  const apiUrl = getInput(io, "api-url");
  if (!apiUrl) throw new InputError('input "api-url" is required: the base URL of the sitewarm API including the version prefix, for example https://<host>/v1');
  const site = getInput(io, "site");
  const sitemapUrl = getInput(io, "sitemap-url");
  if (!site && !sitemapUrl) throw new InputError('set "site" (hostname or site id) or "sitemap-url"');
  return {
    apiKey,
    apiUrl: checkApiUrl(apiUrl),
    site,
    sitemapUrl,
    wait: parseBool("wait", getInput(io, "wait"), true),
    timeoutMs: parseDuration("timeout", getInput(io, "timeout") || DEFAULT_TIMEOUT),
    failOn: parseFailOn(getInput(io, "fail-on"))
  };
}

// src/resolve.ts
var canonicalHost = (h) => h.trim().toLowerCase().replace(/\.$/, "").replace(/^www\./, "");
function hostOf(value) {
  if (!value.includes("://")) return value;
  try {
    return new URL(value).hostname;
  } catch {
    throw new InputError(`"${value}" is not a valid URL`);
  }
}
async function resolveSource(client, input) {
  const wantedHost = canonicalHost(hostOf(input.site || input.sitemapUrl));
  let site;
  for await (const s of client.sites.listAll()) {
    if (input.site && s.id === input.site || canonicalHost(s.hostname) === wantedHost) {
      site = s;
      break;
    }
  }
  if (!site) {
    throw new InputError(`no site "${input.site || wantedHost}" in this organization (the API key can only see its own organization's sites)`);
  }
  if (input.site && input.sitemapUrl && canonicalHost(hostOf(input.sitemapUrl)) !== canonicalHost(site.hostname)) {
    throw new InputError(`sitemap-url host does not belong to site ${site.hostname}`);
  }
  const sitemaps = [];
  for await (const m of client.sitemaps.listAll(site.id)) sitemaps.push(m);
  if (input.sitemapUrl) {
    const want = normalizeUrl(input.sitemapUrl);
    const hit = sitemaps.find((m) => normalizeUrl(m.url) === want);
    if (!hit) {
      throw new InputError(`sitemap ${input.sitemapUrl} is not registered for site ${site.hostname}; register it first (the action does not create sitemaps)`);
    }
    return { site, sitemap: hit };
  }
  if (sitemaps.length === 1) return { site, sitemap: sitemaps[0] };
  if (sitemaps.length === 0) throw new InputError(`site ${site.hostname} has no registered sitemap; register one first`);
  throw new InputError(`site ${site.hostname} has ${sitemaps.length} sitemaps; set "sitemap-url" to choose one`);
}
function normalizeUrl(u) {
  try {
    return new URL(u).href;
  } catch {
    return u;
  }
}

// src/summary.ts
var oneLine = (s) => String(s ?? "").replace(/[\r\n]+/g, " ");
var cell = (s) => oneLine(s).replace(/\\/g, "\\\\").replace(/[|[\]]/g, "\\$&").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/@/g, "&#64;");
var code = (s) => "`" + oneLine(s).replace(/`/g, "'").replace(/\|/g, "\\|") + "`";
function hitRatio(run2) {
  if (!run2) return "";
  let hits = 0;
  let total = 0;
  for (const vp of run2.vantage_points) {
    total += vp.n;
    hits += vp.counts["hit"] ?? 0;
  }
  return total > 0 ? (hits / total).toFixed(4) : "";
}
function renderSummary(r) {
  const run2 = r.run;
  const o = run2?.outcome ?? null;
  const lines = ["## sitewarm warm run", ""];
  let verdict;
  if (r.problem) verdict = `**Did not complete.** ${cell(r.problem)}`;
  else if (!r.waited) verdict = "Run started. The action did not wait for the result (`wait: false`), so no pass/fail verdict was evaluated.";
  else if (o?.failed) verdict = `**Failed.** ${o.reason === "no_verifications" ? "No URL could be verified, which fails the run whatever `fail-on` says." : `States matching the effective fail-on: ${o.failing_states.map(code).join(", ") || "none reported"}.`}`;
  else if (o) verdict = "**Passed.**";
  else verdict = `Run is \`${cell(run2?.status)}\`.`;
  lines.push(verdict, "");
  lines.push("| | |", "|---|---|");
  if (run2) lines.push(`| Run | ${code(run2.id)} |`, `| Status | ${code(run2.status)} |`);
  if (r.siteHostname) lines.push(`| Site | ${cell(r.siteHostname)} |`);
  if (run2) {
    const failOn = run2.options?.fail_on;
    lines.push(`| Effective fail-on | ${failOn == null ? "not reported yet" : failOn.length ? failOn.map(code).join(", ") : "none"} |`);
  }
  if (r.hitRatio) lines.push(`| Hit ratio | ${r.hitRatio} (hit results / all observed results) |`);
  if (r.reportUrl) lines.push(`| Cache status report | ${cell(r.reportUrl)} |`);
  lines.push("");
  if (run2 && run2.vantage_points.length > 0) {
    const states = [...new Set(run2.vantage_points.flatMap((vp) => Object.keys(vp.counts)))].sort((a, b) => a.localeCompare(b));
    lines.push("### Results by vantage point", "");
    lines.push(`| Vantage point | Region | Results | ${states.map(cell).join(" | ")} |`);
    lines.push(`|---|---|---:|${states.map(() => "---:").join("|")}|`);
    for (const vp of run2.vantage_points) {
      lines.push(`| ${code(vp.vantage_point_id)} | ${cell(vp.region)} | ${vp.n} | ${states.map((s) => vp.counts[s] ?? 0).join(" | ")} |`);
    }
    lines.push("");
  }
  return lines.join("\n");
}

// src/run.ts
var ACTION_VERSION = "0.1.0";
function idempotencyKey(env, sitemapId) {
  const { GITHUB_REPOSITORY: repo, GITHUB_RUN_ID: runId, GITHUB_RUN_ATTEMPT: attempt } = env;
  if (!repo || !runId) return void 0;
  const raw = [repo, runId, attempt ?? "1", env.GITHUB_JOB ?? "", env.GITHUB_ACTION ?? "", sitemapId].join("|");
  return "swa-" + (0, import_node_crypto2.createHash)("sha256").update(raw).digest("hex").slice(0, 32);
}
async function run(ctx) {
  const rawKey = getInput(ctx, "api-key");
  addMask(ctx, rawKey);
  const rawToken = getInput(ctx, "site-token");
  addMask(ctx, rawToken);
  const report = { waited: false, hitRatio: "", reportUrl: "" };
  const scrub = (s) => [rawKey, rawToken].reduce((acc, v) => v ? acc.split(v).join("***") : acc, s);
  let failed = false;
  const fail = (msg, verdict = false) => {
    failed = true;
    const m = scrub(msg);
    if (!verdict) report.problem = m;
    error(ctx, m);
  };
  try {
    const inputs = readInputs(ctx);
    report.waited = inputs.wait;
    if (!inputs.wait && inputs.failOn !== void 0) {
      warning(ctx, '"fail-on" has no effect with wait: false (no result is evaluated)');
    }
    const client = new SiteWarm({
      apiKey: inputs.apiKey,
      baseUrl: inputs.apiUrl,
      userAgent: `sitewarm-action/${ACTION_VERSION}`,
      ...ctx.fetch ? { fetch: ctx.fetch } : {}
    });
    const { site, sitemap } = await resolveSource(client, inputs);
    report.siteHostname = site.hostname;
    info(ctx, `Warming ${site.hostname} from ${sitemap.url}`);
    const options = inputs.failOn === void 0 ? {} : { fail_on: inputs.failOn };
    const started = await client.warmRuns.create(
      site.id,
      {
        source: { type: "sitemap", sitemap_id: sitemap.id },
        deployment: {
          ...ctx.env.GITHUB_RUN_ID ? { id: `github-${ctx.env.GITHUB_RUN_ID}-${ctx.env.GITHUB_RUN_ATTEMPT ?? "1"}` } : {},
          ...ctx.env.GITHUB_SHA ? { ref: ctx.env.GITHUB_SHA } : {}
        },
        ...Object.keys(options).length ? { options } : {}
      },
      { idempotencyKey: idempotencyKey(ctx.env, sitemap.id) }
    );
    report.run = started;
    setOutput(ctx, "run-id", started.id);
    notice(ctx, `Started warm run ${started.id}`);
    if (inputs.wait) {
      let lastStatus = started.status;
      let final;
      try {
        final = await client.warmRuns.wait(started.id, {
          timeoutMs: inputs.timeoutMs,
          onPoll: (r) => {
            report.run = r;
            if (r.status !== lastStatus) info(ctx, `Run ${r.id}: ${r.status}`);
            lastStatus = r.status;
          }
        });
      } catch (err) {
        if (err instanceof SiteWarmWaitTimeoutError) {
          throw new Error(`timed out after ${Math.round(inputs.timeoutMs / 1e3)}s waiting for run ${started.id} (last status: ${err.lastStatus}). The run keeps going on the server; it was not canceled.`);
        }
        throw err;
      }
      report.run = final;
      report.hitRatio = hitRatio(final);
      if (final.status === "completed") {
        report.reportUrl = await findReportUrl(client, ctx, final, inputs.apiUrl);
        const o = final.outcome;
        if (!o) fail(`run ${final.id} completed without an outcome`);
        else if (o.failed) {
          fail(
            o.reason === "no_verifications" ? `run ${final.id} failed: no URL could be verified` : `run ${final.id} failed: ${o.failing_states.join(", ") || "fail-on matched"}`,
            true
          );
        } else info(ctx, `Run ${final.id} passed`);
      } else {
        fail(`run ${final.id} was ${final.status}`, true);
      }
    }
  } catch (err) {
    fail(err instanceof InputError ? err.message : describe(err));
  } finally {
    setOutput(ctx, "hit-ratio", report.hitRatio);
    setOutput(ctx, "report-url", report.reportUrl);
    if (!report.run) setOutput(ctx, "run-id", "");
    appendSummary(ctx, scrub(renderSummary(report)));
  }
  return failed ? 1 : 0;
}
function describe(err) {
  if (err instanceof SiteWarmApiError) {
    const hint = err.status === 401 ? " (check the api-key)" : err.status === 403 ? " (the API key lacks a required scope: sites:read, warm-runs:read, warm-runs:write)" : err.status === 409 && err.code === "site-not-verified" ? " (verify the site in the dashboard, then re-run the job)" : "";
    return `${err.message}${hint}`;
  }
  return err instanceof Error ? err.message : "unexpected error";
}
async function findReportUrl(client, ctx, run2, apiUrl) {
  try {
    const page = await client.cacheStatusReports.listForSite(run2.site_id, { warm_run_id: run2.id, limit: 1 });
    const first = page.data[0];
    return first ? `${apiUrl.replace(/\/+$/, "")}/cache-status-reports/${encodeURIComponent(first.id)}` : "";
  } catch (err) {
    warning(ctx, `could not look up the cache status report (needs the cache-reports:read scope): ${err instanceof Error ? err.message : "error"}`);
    return "";
  }
}

// src/index.ts
run({
  env: process.env,
  out: (line) => process.stdout.write(line + "\n")
}).then(
  (code2) => {
    process.exitCode = code2;
  },
  () => {
    process.stdout.write("::error::sitewarm action crashed\n");
    process.exitCode = 1;
  }
);
