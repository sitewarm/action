# hosted/index.js

Bundle of the hosted mode (the former `node24` Action), run by the composite step "Warm and verify (hosted)" with `node`.

- Built from `packages/github-action` of the private sitewarm repo at commit `8f0b242` (branch `sitework/open-source-action-hardening`, local and unmerged when this was copied), with `node scripts/check-dist.mjs` reporting that the committed `dist/index.js` equals a fresh build.
- 32636 bytes, sha256 `8dc86cadb0225f060765489d3d31d204f46133fa5ed789ce9f95efe10c56759f`.
- It is copied, not built here. The source and a rebuild check in this repository are task T-E (spec section 8); until then, replace this file only with a bundle whose provenance is written here.
- Build target `node20`, format CJS, no network access at install or run time except the calls to `api-url`.

History: 926eb69 (32554 bytes, sha256 `a967ad02a8747734763fe635592e8f5a91e2ed75a1be3914a473097ebb6ccca2`) crashed the job summary when `options.fail_on` was missing; 3d3f939 fixes it.
Then 8f0b242 made `getInput` also read `SITEWARM_<NAME>` (underscores) so the composite step passes the key through its `env:` block without launching `env`.
