# hosted/index.js

Bundle of the hosted mode (the former `node24` Action), run by the composite step "Warm and verify (hosted)" with `node`.

- Built from `packages/github-action` of the private sitewarm repo at commit `8d2013e` (stacked on `4dee323`; the private branch is unmerged), with `node scripts/check-dist.mjs` reporting that the committed `dist/index.js` equals a fresh build.
- 32949 bytes, sha256 `6aa7eaf97046c8b2a9f2bb67d5591fa759bd6f08154c6bc4405617ec4a7e413f`. This file is byte for byte the `dist/index.js` of `8d2013e`.
- `8d2013e` adds to `4dee323` one change in `resolveSource`: a 404 from `GET /sites/{id}/sitemaps` fails with "this sitewarm host does not support sitemaps listing yet" instead of the generic API error. Before the change was in the private source, this file carried it as a hand patch (the previous commit); the rebuild gave the identical bytes.
- The 4dee323 build is 32649 bytes, sha256 `5883687b6075fb02f016ff27b31a2b7e350fb1c2ad20820ddad2c20d25ab5e98`.
- It is copied, not built here. The source and a rebuild check in this repository are task T-E (spec section 8); until then, replace this file only with a bundle whose provenance is written here.
- Build target `node20`, format CJS, no network access at install or run time except the calls to `api-url`.

History: 0893bb9 (32554 bytes, sha256 `a967ad02a8747734763fe635592e8f5a91e2ed75a1be3914a473097ebb6ccca2`) crashed the job summary when `options.fail_on` was missing; a3d1c1b fixes it.
Then 9869c0f made `getInput` also read `SITEWARM_<NAME>` (underscores) so the composite step passes the key through its `env:` block without launching `env`.
Then 4dee323 renamed the composite's variables to `SITEWARM_ACTION_INPUT_<NAME>` so the product's own `SITEWARM_API_URL` and friends can never stand in for an input (9869c0f bundle: 32636 bytes, sha256 `8dc86cadb0225f060765489d3d31d204f46133fa5ed789ce9f95efe10c56759f`).

The SHAs above are those of the private repository after a rebase onto its main on 2026-11-01; the trees are the same as before it, and the rebuilt `dist/index.js` is byte for byte this file.
