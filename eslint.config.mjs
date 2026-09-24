// ESLint flat config (ESLint 10 / Next 16).
//
// Why this file exists: package.json carried `"lint": "next lint"`, but Next 16
// removed the `next lint` subcommand entirely — `next --help` lists only build,
// dev and start. The script therefore failed with "Invalid project directory
// provided, no such directory: .../lint", because Next parsed "lint" as a
// positional directory argument. There was also no ESLint package, binary or
// config anywhere in the repo, so this project had no working linter at all.
//
// eslint-config-next 16.3.5 is pinned to the same minor as next itself, and
// ships flat-config-ready entrypoints ("." and "./core-web-vitals").

import next from 'eslint-config-next';
import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';

export default [
  {
    // Generated, vendored and non-source output. Linting these produces noise
    // and, for .next/, is actively misleading since it is compiler output.
    ignores: [
      '.next/**',
      'out/**',
      'node_modules/**',
      '.venv/**',
      'coverage/**',
      'ios/**',
      'android/**',
      '.amplify/**',
      'amplify_outputs.json',
      '**/__pycache__/**',
      // NOTE: there was a 'docs/reference/**' ignore here for a vendored copy of Wix's
      // own Next.js headless examples. That tree has been deleted, so the ignore went
      // with it rather than being left behind as inert config.
      //
      // DO NOT re-add a blanket ignore if you vendor reference code again. That is what
      // hid the real problem last time: the tree was excluded from ESLint and tsc, so it
      // looked handled - but CodeQL still scans the whole repository, and it raised a
      // high-severity "clear text storage of sensitive information" alert on the Wix
      // demo's localStorage OAuth write, which then blocked a pull request on code that
      // was never built or shipped. Lint/type exclusions do not make third-party code
      // invisible to security scanning.
    ],
  },
  ...(Array.isArray(next) ? next : [next]),
  ...(Array.isArray(nextCoreWebVitals) ? nextCoreWebVitals : [nextCoreWebVitals]),
];
