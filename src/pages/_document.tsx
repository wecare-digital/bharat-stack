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
        {/* Inter font for better readability and modern look */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
