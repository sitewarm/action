# hosted/index.js

Bundle of the hosted mode (the former `node24` Action), run by the composite step "Warm and verify (hosted)" with `node`.

- Built from `packages/github-action` of the private sitewarm repo at commit `926eb69` (branch `sitework/open-source-action-hardening`, local and unmerged when this was copied), with `node scripts/check-dist.mjs` reporting that the committed `dist/index.js` equals a fresh build.
- 32554 bytes, sha256 `a967ad02a8747734763fe635592e8f5a91e2ed75a1be3914a473097ebb6ccca2`.
- It is copied, not built here. The source and a rebuild check in this repository are task T-E (spec section 8); until then, replace this file only with a bundle whose provenance is written here.
- Build target `node20`, format CJS, no network access at install or run time except the calls to `api-url`.
