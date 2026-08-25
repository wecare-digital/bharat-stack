import { Html, Head, Main, NextScript } from 'next/document';

/**
 * Custom Document — Security meta tags + Google Tag Manager.
 *
 * NOTE: Content-Security-Policy should be configured at the hosting layer
 * (CloudFront response headers policy) rather than as a meta tag, since
 * this app uses output: 'export' (static site) and has many external
 * dependencies (Cognito, Razorpay, GA, Facebook SDK, etc.).
 *
 * GOOGLE TAGS — single-layer policy.
 * Google tracking on this property is delivered EXCLUSIVELY through the GTM
 * container below. Do not add a direct gtag.js / GA4 / Google Ads snippet
 * here or in any page: the container already fires GA4 (G-GNRPFFBXMF) and
 * Google Ads (AW-18396505964). Adding a direct tag alongside the container
 * double-counts every pageview and conversion — which is the exact defect
 * present on the www.wecare.digital Wix property.
 *
 * Set NEXT_PUBLIC_GTM_ID to '' to disable all Google tracking at build time.
 */
const GTM_ID = process.env.NEXT_PUBLIC_GTM_ID ?? 'GTM-TXZ8JT78';

/**
 * Google Consent Mode v2 defaults. Denied-by-default means GA4 and Ads send
 * only cookieless pings until consent is granted, so analytics never loads
 * ahead of a consent decision. Grant it by calling, from your consent UI:
 *
 *   gtag('consent', 'update', { analytics_storage: 'granted', ... })
 *
 * Override the default with NEXT_PUBLIC_ANALYTICS_CONSENT_DEFAULT=granted
 * only if you have established a lawful basis for doing so.
 */
const CONSENT_DEFAULT =
  process.env.NEXT_PUBLIC_ANALYTICS_CONSENT_DEFAULT === 'granted' ? 'granted' : 'denied';

const consentBootstrap = `
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('consent', 'default', {
  ad_storage: '${CONSENT_DEFAULT}',
  ad_user_data: '${CONSENT_DEFAULT}',
  ad_personalization: '${CONSENT_DEFAULT}',
  analytics_storage: '${CONSENT_DEFAULT}',
  wait_for_update: 500
});
`.trim();

const gtmLoader = `
(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});
var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';
j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','${GTM_ID}');
`.trim();

export default function Document () {
  return (
    <Html lang="en">
      <Head>
        <meta httpEquiv="X-Content-Type-Options" content="nosniff" />
        <meta httpEquiv="X-Frame-Options" content="DENY" />
        <meta name="referrer" content="strict-origin-when-cross-origin" />
        {/* Inter font for better readability and modern look */ }
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
        { GTM_ID ? (
          <>
            {/* Consent Mode v2 must run BEFORE the container loads. */ }
            <script dangerouslySetInnerHTML={ { __html: consentBootstrap } } />
            <link rel="preconnect" href="https://www.googletagmanager.com" />
            <script dangerouslySetInnerHTML={ { __html: gtmLoader } } />
          </>
        ) : null }
      </Head>
      <body>
        { GTM_ID ? (
          <noscript
            dangerouslySetInnerHTML={ {
              __html:
                `<iframe src="https://www.googletagmanager.com/ns.html?id=${GTM_ID}"` +
                ` height="0" width="0" style="display:none;visibility:hidden"></iframe>`,
            } }
          />
        ) : null }
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
