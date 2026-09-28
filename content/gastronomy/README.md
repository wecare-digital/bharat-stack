# Gastronomy publishing state

This directory is the durable state for the 340-post Gastronomy programme.

- Current verified baseline: GAST-001 through GAST-040.
- Automatic batch size: 25.
- Next batch: GAST-041 through GAST-065.
- Source material stays outside Git; only original WECARE.DIGITAL article packages are committed.
- Batch manifests live in `content/gastronomy/batches/`.
- `progress.json` advances only after the whole batch is published to Wix and passes the live backend audit.
- The working branch is `gastronomy-publishing`; it does not trigger the production Amplify app.
- `stack` is updated only once after a completed batch so there is one production rebuild per batch.

A batch manifest is validated with:

```bash
python scripts/gastronomy_batch.py validate --manifest content/gastronomy/batches/GAST-041-GAST-065.json
```

Publishing and live audit are deliberately separate gates. A generated manifest is not treated as published or complete.
