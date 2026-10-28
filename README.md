# sitewarm

After a Production deploy, this action runs the [sitewarm](https://github.com/sitewarm/sitewarm) CLI on the GitHub Actions runner over the pages you choose and posts a GitHub Check named `sitewarm`: which pages the CDN serves from cache, which answer with an error or `noindex`, why, and what changed since your previous Production deploy.

It is measured from the GitHub Actions runner, from one CDN point of presence (the Check prints it). It does not say anything about other regions.

## Use it

Create `.github/workflows/sitewarm.yml` in the repository that deploys your site:

```yaml
name: sitewarm
on:
  deployment_status:

permissions:
  contents: read
  checks: write
  deployments: read

jobs:
  receipt:
    if: github.event.deployment_status.state == 'success'
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4 # pin to a commit SHA
      - uses: sitewarm/action@v1
        with:
          site-url: https://www.example.com
          urls-file: .github/sitewarm-urls.csv
```

`.github/sitewarm-urls.csv` lists your most important pages, most important first (20 to 50 is a good size):

```csv
path
/
/about
/blog
/products/best-seller
```

Vercel and Cloudflare create `deployment_status` events for every deploy. The action runs only when the state is `success` and the environment is `production` (case does not matter). Workflows for `deployment_status` run from your default branch, so merge the file there first. If your host does not create deployments, run the action as a step after your own deploy job instead.

## Inputs

| Input | Default | What it does |
|---|---|---|
| `mode` | `local` | `local` (this page) or `hosted` (see "Hosted mode"). Never inferred from `api-key`. |
| `site-url` | required in local mode | Origin of the site, for example `https://www.example.com`. |
| `urls-file` | empty | CSV in your repo with a `path` or `url` column. If empty, the first URLs of the sitemap are used, which are not necessarily your most important pages. |
| `sitemap-url` | `site-url` + `/sitemap.xml` | Used when `urls-file` is empty. |
| `top` | `30` | How many URLs to check, 1 to 50. |
| `environment` | `production` | Deployment environment that triggers the check. |
| `fail-on` | empty (local uses `5xx,noindex,regression`) | What turns the Check red. Add `miss`, `client-error` or `incomplete` for a stricter Check. |
| `version` | `1.0.2` | sitewarm CLI release, without the leading `v`. Only versions pinned in the action together with their SHA-256 are accepted (today: `1.0.2`). Anything that is not a semantic version fails, and a valid version that is not pinned fails with the list of pinned ones; neither makes any request. Empty means the default. A new CLI version arrives with a new release of the action. The download is verified against the pinned SHA-256 before it runs. |
| `github-token` | the workflow token | Needs `checks: write`, `deployments: read` and `contents: read`. |

Output: `conclusion` (`success`, `neutral` or `failure`). `run-id`, `hit-ratio` and `report-url` are empty in local mode.

## Hosted mode

`mode: hosted` starts a run in the sitewarm service for a site you have verified there, waits for it and fails the step by its verdict. It needs `node` 20 or later on the runner and no `GITHUB_TOKEN` permission.

```yaml
      - uses: sitewarm/action@v1
        with:
          mode: hosted
          api-url: https://<host>/v1
          api-key: ${{ secrets.SITEWARM_API_KEY }}
          site: www.example.com
```

Hosted inputs: `api-key`, `api-url` (https), `site` or `sitemap-url`, `wait` (default `true`), `timeout` (default `15m`) and `fail-on` (cache states and `noindex`, or `none`; unset, the service default applies). They must be empty in local mode, and `site-url` and `urls-file` must be empty in hosted mode: a mismatch fails the step before any request. `top`, `environment`, `version` and `github-token` have defaults, so they are ignored in hosted mode rather than rejected. `conclusion` is empty when the inputs are rejected (no run happened); the step itself fails. An empty `api-key` fails too, and never turns into a local run; this is what happens on pull requests from forks, where secrets are empty. Use one key per repository with only the scopes `sites:read`, `warm-runs:read` and `warm-runs:write` (plus `cache-reports:read` for `report-url`).

## What the Check says

- **Green:** every checked page is served from cache and nothing got worse.
- **Neutral:** nothing got worse, but some pages are not served from cache (a MISS, a bypass, a bot challenge) or nothing could be verified. Each page comes with the likely cause and a fix when the response headers show one.
- **Red:** a regression against your previous Production deploy: a page that became an error or 5xx, a page that became `noindex`, or a page that was a HIT and no longer is.

The first run is the baseline and compares nothing. The comparison uses the state after the CLI's warm-up retries, so a purge during the deploy does not turn every page red.

## Limits

- Linux runners only.
- One vantage point: the runner. A HIT here says nothing about other points of presence.
- Canonical URLs are not measured yet.
- The previous deploy is found through your repository's deployments and the Checks of that commit; if they are missing (a new repository, an old Check removed), the run is a baseline again.
- Runner IP addresses are shared. A bot protection rule can answer them with a challenge; the Check shows that as `challenged`.

## Good behavior

The CLI sends an honest `User-Agent` that names `sitewarm`, never presents itself as a search engine crawler, and respects `robots.txt` for sitemap URLs. Only check sites you own or are allowed to test.

## License

Apache-2.0.
