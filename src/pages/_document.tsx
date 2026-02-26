import { Html, Head, Main, NextScript } from 'next/document';

/**
 * Custom Document — Security meta tags.
 * 
 * NOTE: Content-Security-Policy should be configured at the hosting layer
 * (CloudFront response headers policy) rather than as a meta tag, since
 * this app uses output: 'export' (static site) and has many external
 * dependencies (Cognito, Razorpay, GA, Facebook SDK, etc.).
 */
export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <meta httpEquiv="X-Content-Type-Options" content="nosniff" />
        <meta httpEquiv="X-Frame-Options" content="DENY" />
        <meta name="referrer" content="strict-origin-when-cross-origin" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
