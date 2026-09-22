/**
 * Bharat Stack by WECARE.DIGITAL
 * Simplified auth - just wrap protected pages with Authenticator
 */

import type { AppProps } from 'next/app';
import Head from 'next/head';
import Script from 'next/script';
import { useRouter } from 'next/router';
import { useState, useEffect } from 'react';
import { Amplify } from 'aws-amplify';
import { Authenticator, ThemeProvider, Theme, useAuthenticator } from '@aws-amplify/ui-react';
// Brand line above the sign-in form. Lives in its own file and styles itself,
// because styled-jsx cannot scope a composite component from here.
import AuthBrandHeader from '../components/AuthBrand';
import '@aws-amplify/ui-react/styles.css';
import '../styles/Pages.css';
import '../styles/Layout.css';
import '../styles/Dashboard.css';
import '../styles/inner-pages.css';
import '../styles/inner-ux.css';
import '../styles/flex-layout.css';
import '../styles/button.css';
import FloatingAgent from '../components/FloatingAgent';
import LanguageBar from '../components/LanguageBar';
import ErrorBoundary from '../components/ErrorBoundary';
import Header from '../components/Header';
import Footer from '../components/Footer';
import { ToastProvider } from '../contexts/ToastContext';
import { ConfirmProvider } from '../contexts/ConfirmContext';
import { initCapacitor, isNative } from '../lib/capacitor';

// Configure Amplify — all secrets from env vars
Amplify.configure( {
  Auth: {
    Cognito: {
      userPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || '',
      userPoolClientId: process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID || '',
      identityPoolId: process.env.NEXT_PUBLIC_COGNITO_IDENTITY_POOL_ID || '',
      loginWith: {
        oauth: {
          domain: process.env.NEXT_PUBLIC_COGNITO_OAUTH_DOMAIN || '',
          scopes: [ 'openid', 'email', 'profile' ],
          redirectSignIn: [
            process.env.NEXT_PUBLIC_APP_URL || 'https://stack.wecare.digital/',
          ],
          redirectSignOut: [
            process.env.NEXT_PUBLIC_APP_URL || 'https://stack.wecare.digital/',
          ],
          responseType: 'code' as const
        },
        username: true,
        email: true
      }
    }
  }
} );

const LOGO_URL = 'https://app.wecare.digital/stream/media/m/wecaredigital.png';
const LOGO_SVG_URL = 'https://app.wecare.digital/stream/media/m/wecare-digital.svg';
const FAVICON_URL = 'https://app.wecare.digital/stream/media/m/wecare-digital.ico';
const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || '';

// Custom Amplify UI Theme - Lime + Dark Green matching site design
const authTheme: Theme = {
  name: 'stack-crm-theme',
  tokens: {
    colors: {
      brand: {
        primary: {
          10: { value: '#f9fafb' },
          20: { value: '#f3f4f6' },
          40: { value: '#d1f470' },
          60: { value: '#d1f470' },
          80: { value: '#1a3a2a' },
          90: { value: '#0f2a1d' },
          100: { value: '#0a1f15' },
        },
      },
      font: {
        interactive: { value: '#1a3a2a' },
      },
      background: {
        primary: { value: '#ffffff' },
        secondary: { value: '#f9fafb' },
      },
    },
    components: {
      authenticator: {
        router: {
          borderWidth: { value: '0' },
          boxShadow: { value: '0 4px 24px rgba(0, 0, 0, 0.08)' },
        },
      },
      button: {
        primary: {
          backgroundColor: { value: '#d1f470' },
          color: { value: '#1a3a2a' },
          _hover: {
            backgroundColor: { value: '#c5e866' },
          },
          _active: {
            backgroundColor: { value: '#b8dc5a' },
          },
        },
        link: {
          color: { value: '#1a3a2a' },
          _hover: {
            color: { value: '#0f2a1d' },
            backgroundColor: { value: 'transparent' },
          },
        },
      },
      fieldcontrol: {
        borderRadius: { value: '13px' },
        // #e5e7eb at rest, NOT lime. The design contract's hairline rule is that
        // the colour is always #e5e7eb and lime marks an interactive state; a lime
        // resting border made every idle input on the sign-in card read as focused,
        // and spent the page's one accent on three inert outlines. Lime returns
        // below, in the focus ring, which is where the contract puts it.
        borderColor: { value: '#e5e7eb' },
        _focus: {
          borderColor: { value: '#1a3a2a' },
          boxShadow: { value: '0 0 0 3px rgba(209, 244, 112, 0.3)' },
        },
      },
      // INERT while the Authenticator is mounted with hideSignUp - with sign-up
      // hidden, Amplify renders no tab list at all, so nothing below is visible on
      // /access today (measured in a browser: zero elements match [role="tab"]).
      // Kept and corrected rather than deleted so that flipping hideSignUp cannot
      // ship off-palette tabs: the idle colour was #6b7280, which is the legacy
      // --color-muted from Pages.css and not a palette value at all.
      //
      // The active state is the palette's own tab treatment - #d1f470 fill with
      // #1a3a2a type, the pair used by .pp-tab.active, .msg.sent and BrandBadge -
      // rather than the underline-only version this had before.
      tabs: {
        item: {
          color: { value: 'rgba(0, 0, 0, 0.54)' },
          _active: {
            color: { value: '#1a3a2a' },
            backgroundColor: { value: '#d1f470' },
            borderColor: { value: '#d1f470' },
          },
          _hover: {
            color: { value: '#1a3a2a' },
          },
        },
      },
    },
    radii: {
      small: { value: '10px' },
      medium: { value: '13px' },
      large: { value: '16px' },
    },
    space: {
      small: { value: '0.75rem' },
      medium: { value: '1rem' },
      large: { value: '1.5rem' },
    },
    fontSizes: {
      small: { value: '0.875rem' },
      medium: { value: '1rem' },
      large: { value: '1.125rem' },
    },
    // Amplify ships its own stack - 'InterVariable','Inter var','Inter',… - which
    // resolves to the same face the rest of the site uses, so this was never a
    // visible bug. It is pinned to the site stack anyway so the sign-in card cannot
    // drift onto a different font than .page declares: InterVariable is a
    // *different file* from the Inter that _app loads from Google Fonts at
    // 400;500;600;700;800, and if a variable build ever resolves locally on a
    // visitor's machine the card would render in it while every other surface did
    // not. Same list, same order as grahak-os/index.tsx .page.
    fonts: {
      default: {
        variable: { value: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" },
        static: { value: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" },
      },
    },
  },
};

// Structured data for the organization
const organizationSchema = {
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "WECARE.DIGITAL",
  "alternateName": "Bharat Stack",
  "url": "https://wecare.digital",
  "logo": LOGO_URL,
  "image": LOGO_URL,
  "description": "Enterprise WhatsApp Business API platform for multi-channel customer engagement",
  "foundingDate": "2020",
  "sameAs": [
    "https://www.linkedin.com/company/wecare-digital",
    "https://twitter.com/wecaredotdigital"
  ],
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "customer service",
    "url": "https://www.wecare.digital/contact",
    "availableLanguage": [ "English", "Hindi" ]
  },
  "address": {
    "@type": "PostalAddress",
    "addressCountry": "IN"
  }
};

// Structured data for the software application
const softwareSchema = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Bharat Stack by WECARE.DIGITAL",
  "alternateName": "Bharat Stack",
  "applicationCategory": "BusinessApplication",
  "applicationSubCategory": "CRM Software",
  "operatingSystem": "Web Browser",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "INR",
    "availability": "https://schema.org/InStock"
  },
  "description": "Enterprise multi-channel messaging CRM platform with WhatsApp Business API, SMS, Email, Voice integration, and AI-powered automation. Features include bulk messaging, payment collection via Razorpay, customer data platform, and analytics.",
  "featureList": [
    "WhatsApp Business API Integration",
    "Bulk WhatsApp Messaging",
    "SMS API (AWS Pinpoint, IN SMS)",
    "Email Marketing (Amazon SES)",
    "Voice Calls API",
    "Razorpay Payment Integration",
    "AI-Powered Responses",
    "Customer Data Platform",
    "Message Templates",
    "Analytics Dashboard",
    "Contact Management",
    "Webhook Integration"
  ],
  "screenshot": LOGO_URL,
  "softwareVersion": "1.0.0",
  "publisher": {
    "@type": "Organization",
    "name": "WECARE.DIGITAL",
    "url": "https://wecare.digital"
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.8",
    "ratingCount": "150",
    "bestRating": "5",
    "worstRating": "1"
  }
};

// Structured data for the website
const websiteSchema = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Bharat Stack by WECARE.DIGITAL",
  "alternateName": "Bharat Stack",
  "url": "https://stack.wecare.digital",
  "description": "Enterprise WhatsApp Business API platform for multi-channel customer engagement",
  "publisher": {
    "@type": "Organization",
    "name": "WECARE.DIGITAL"
  },
  "potentialAction": {
    "@type": "SearchAction",
    "target": {
      "@type": "EntryPoint",
      "urlTemplate": "https://stack.wecare.digital/contacts?q={search_term_string}"
    },
    "query-input": "required name=search_term_string"
  },
  "inLanguage": "en-IN"
};

// FAQ Schema for AI and search engines
const faqSchema = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is Bharat Stack by WECARE.DIGITAL?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Stack CRM is an enterprise multi-channel messaging platform that integrates WhatsApp Business API, SMS, Email, and Voice communications. It helps businesses engage customers, send bulk messages, collect payments via Razorpay, and automate responses with AI."
      }
    },
    {
      "@type": "Question",
      "name": "How can I send bulk WhatsApp messages?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Stack CRM provides bulk WhatsApp messaging through the official WhatsApp Business API. You can upload contacts, create message templates, and send promotional or transactional messages to thousands of customers at once."
      }
    },
    {
      "@type": "Question",
      "name": "Does Stack CRM support WhatsApp payments?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes, Stack CRM integrates with Razorpay to enable WhatsApp payments. You can send payment requests directly through WhatsApp and track payment status in real-time."
      }
    },
    {
      "@type": "Question",
      "name": "What messaging channels does Stack CRM support?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Stack CRM supports WhatsApp Business API, SMS (via AWS Pinpoint and IN SMS), Email (via Amazon SES), and Voice calls. All channels are unified in a single dashboard."
      }
    }
  ]
};

// Service Schema
const serviceSchema = {
  "@context": "https://schema.org",
  "@type": "Service",
  "serviceType": "WhatsApp Business API Platform",
  "provider": {
    "@type": "Organization",
    "name": "WECARE.DIGITAL"
  },
  "areaServed": {
    "@type": "Country",
    "name": "India"
  },
  "hasOfferCatalog": {
    "@type": "OfferCatalog",
    "name": "Messaging Services",
    "itemListElement": [
      {
        "@type": "Offer",
        "itemOffered": {
          "@type": "Service",
          "name": "WhatsApp Business API"
        }
      },
      {
        "@type": "Offer",
        "itemOffered": {
          "@type": "Service",
          "name": "Bulk SMS"
        }
      },
      {
        "@type": "Offer",
        "itemOffered": {
          "@type": "Service",
          "name": "Email Marketing"
        }
      },
      {
        "@type": "Offer",
        "itemOffered": {
          "@type": "Service",
          "name": "Voice Calls"
        }
      }
    ]
  }
};

// Breadcrumb schema for internal pages
const getBreadcrumbSchema = ( pageName: string, pageUrl: string ) => ( {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Home",
      "item": "https://stack.wecare.digital"
    },
    {
      "@type": "ListItem",
      "position": 2,
      "name": pageName,
      "item": pageUrl
    }
  ]
} );

/**
 * AuthGate — shows Header + Footer around the login form only when unauthenticated.
 * Once authenticated, renders children directly (Layout handles its own Header/Footer).
 */
const AuthGate: React.FC<{ children: React.ReactNode }> = ( { children } ) => {
  const { authStatus } = useAuthenticator( ( ctx ) => [ ctx.authStatus ] );
  const isAuthed = authStatus === 'authenticated';

  if ( isAuthed ) return <>{ children }</>;

  return (
    <>
      <Header />
      <div className="ag-shell">
        <div className="ag-centre">
          { children }
        </div>
        <Footer />
      </div>
      <style jsx>{`
        /* 108px, not the flat 96px this used to inline.
           The public header is position:fixed and 108px tall, dropping to 96px only
           below 768px - so a single 96px value pulled the whole centred block 12px
           up UNDER the header on every desktop, which is exactly where the new brand
           badge above the form sits. Matched to both of the header's heights rather
           than to one of them.
           Moved out of inline styles for that reason: a style attribute cannot carry
           a media query, so the two-height fix is not expressible inline. */
        .ag-shell{display:flex;flex-direction:column;min-height:100vh;padding-top:108px}
        .ag-centre{flex:1;display:flex;align-items:center;justify-content:center}
        @media(max-width:767px){.ag-shell{padding-top:96px}}
      `}</style>
    </>
  );
};

export default function App ( { Component, pageProps }: AppProps ) {
  const router = useRouter();


  // EXACT-MATCH allowlist. A public page missing from this list renders an empty
  // body with HTTP 200 — a 404 that does not look like one — so every new public
  // route has to be added here as well as created under src/pages.
  const isPublic = router.pathname === '/' || router.pathname === '/grahak-os' || router.pathname === '/vayulok' || router.pathname === '/contact-test';
  const showPublicWhatsApp = router.pathname === '/' || router.pathname === '/grahak-os';

  useEffect( () => {

    // Register service worker for PWA + offline — production only.
    //
    // In dev the worker is actively harmful: sw.js serves anything matching
    // \.(js|css)$ cache-first with no revalidation, and Next's dev chunks live
    // under /_next/static/*.js. Once cached, every normal refresh replayed a
    // stale bundle — and because styled-jsx ships its CSS inside those chunks,
    // edits to the page looked like they had not applied. Only Ctrl+Shift+R
    // escaped it, because a hard reload is what bypasses a service worker.
    if ( 'serviceWorker' in navigator )
    {
      if ( process.env.NODE_ENV === 'production' )
      {
        navigator.serviceWorker.register( '/sw.js' ).catch( () => { } );
      }
      else
      {
        // Not merely "don't register": a worker already installed on this
        // origin keeps controlling the page until it is explicitly removed, so
        // skipping registration alone would leave existing dev machines broken.
        navigator.serviceWorker.getRegistrations()
          .then( ( regs ) => Promise.all( regs.map( ( r ) => r.unregister() ) ) )
          .catch( () => { } );
        if ( window.caches )
        {
          caches.keys()
            .then( ( keys ) => Promise.all( keys.map( ( k ) => caches.delete( k ) ) ) )
            .catch( () => { } );
        }
      }
    }
    // Init Capacitor native plugins
    initCapacitor( { push: ( p ) => router.push( p ), back: () => router.back() } );
  }, [] );

  // NO client-mount gate here, deliberately.
  //
  // This used to be `if ( !mounted ) return null;`, which ran BEFORE the branches below
  // and therefore before their <Head>. The cost was total: every statically exported page
  // shipped an empty body AND an empty head - /grahak-os/index.html was 3,299 bytes with
  // no title, no description, no og tags, no canonical and no JSON-LD. Crawlers that do
  // not execute JS saw an untitled blank page, link previews had nothing to read, and any
  // webview where the bundle failed showed white.
  //
  // It guarded nothing specific: `mounted` was set in one effect and read in one place,
  // with no client-only value in the render path. The window.dataLayer and
  // window.fbAsyncInit references below are inside inline <script> strings, so they are
  // never evaluated during render and cannot cause a mismatch.
  //
  // If a hydration warning does surface, fix the element that causes it rather than
  // restoring this. Grammarly injecting attributes into <body> is the known one, and
  // suppressHydrationWarning on that element is the targeted answer - blanking the
  // document is not.

  // Public page
  if ( isPublic )
  {
    return (
      <ErrorBoundary>
        <Head>
          <title>Bharat Stack by WECARE.DIGITAL - WhatsApp Business API Platform | Multi-Channel Messaging CRM India</title>
          <link rel="preconnect" href="https://fonts.googleapis.com" />
          <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
          <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&amp;display=swap" rel="stylesheet" />
          <meta name="description" content="Enterprise WhatsApp Business API platform for India. Send bulk WhatsApp messages, SMS, Email & Voice. AI-powered CRM with Razorpay payments. Connect with 2B+ users. Start free today." />
          <meta name="keywords" content="WhatsApp Business API, WhatsApp CRM, bulk WhatsApp messaging, WhatsApp marketing India, business messaging platform, SMS API India, email marketing, voice calls API, Razorpay WhatsApp payments, customer engagement platform, multi-channel CRM, WhatsApp automation, WhatsApp chatbot, business communication, enterprise messaging, WhatsApp templates, promotional messages, transactional messages, OTP WhatsApp, order notifications, WECARE.DIGITAL, Stack CRM" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <link rel="icon" href={ FAVICON_URL } />
          <link rel="apple-touch-icon" href={ LOGO_URL } />
          <link rel="canonical" href="https://stack.wecare.digital/" />

          {/* Open Graph */ }
          <meta property="og:type" content="website" />
          <meta property="og:url" content="https://stack.wecare.digital/" />
          <meta property="og:title" content="Bharat Stack - WhatsApp Business API Platform | WECARE.DIGITAL" />
          <meta property="og:description" content="Enterprise WhatsApp Business API platform. Send bulk messages, payments & automate customer engagement with AI. Trusted by businesses across India." />
          <meta property="og:image" content={ LOGO_URL } />
          <meta property="og:image:width" content="512" />
          <meta property="og:image:height" content="512" />
          <meta property="og:site_name" content="Bharat Stack by WECARE.DIGITAL" />
          <meta property="og:locale" content="en_IN" />

          {/* Twitter */ }
          <meta name="twitter:card" content="summary_large_image" />
          <meta name="twitter:url" content="https://stack.wecare.digital/" />
          <meta name="twitter:title" content="Bharat Stack - WhatsApp Business API Platform" />
          <meta name="twitter:description" content="Enterprise WhatsApp Business API platform. Multi-channel messaging CRM with AI automation." />
          <meta name="twitter:image" content={ LOGO_URL } />

          {/* SEO */ }
          <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" />
          <meta name="googlebot" content="index, follow" />
          <meta name="author" content="WECARE.DIGITAL" />
          <meta name="publisher" content="WECARE.DIGITAL" />
          <meta name="language" content="English" />
          <meta name="geo.region" content="IN" />
          <meta name="geo.placename" content="India" />
          <meta name="theme-color" content="#000000" />

          {/* PWA / Mobile App */ }
          <meta name="apple-mobile-web-app-capable" content="yes" />
          <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
          <meta name="mobile-web-app-capable" content="yes" />
          <link rel="manifest" href="/manifest.json" />

          {/* Structured Data */ }
          <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( organizationSchema ) } } />
          <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( softwareSchema ) } } />
          <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( websiteSchema ) } } />
          <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( faqSchema ) } } />
          <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( serviceSchema ) } } />
        </Head>
        {/* Google Analytics 4 (G-S3G6REP6Q7) */ }
        <Script src={ `https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}` } strategy="afterInteractive" />
        <Script id="google-analytics-ads" strategy="afterInteractive">
          { `
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', '${GA_MEASUREMENT_ID}', { 'send_page_view': true });
          `}
        </Script>
        {/* Facebook SDK for JavaScript */ }
        <Script id="facebook-sdk-init-public" strategy="afterInteractive">
          { `
            window.fbAsyncInit = function() {
              FB.init({
                appId: '${process.env.NEXT_PUBLIC_FB_APP_ID || ''}',
                cookie: true,
                xfbml: true,
                version: 'v25.0'
              });
              FB.AppEvents.logPageView();
            };
          `}
        </Script>
        <Script src="https://connect.facebook.net/en_US/sdk.js" strategy="afterInteractive" id="facebook-jssdk-public" />
        <Header homeBrand={ router.pathname === '/' } />
        <Component { ...pageProps } />
        <Footer />
        {/*
          Translation + read-aloud, public pages only, and deliberately not on
          the authenticated dashboard: those screens render customer names,
          phone numbers and message bodies, and machine-translating live
          operational data would corrupt what an operator is reading.
        */}
        <LanguageBar />
        { showPublicWhatsApp && (
          <Script
            id="wecare-wa-widget"
            src="https://app.wecare.digital/stream/code/wecare-wa-widget.js"
            strategy="lazyOnload"
          />
        ) }
      </ErrorBoundary>
    );
  }

  // Get page name for breadcrumb
  const pageName = router.pathname.split( '/' ).filter( Boolean ).map( s => s.charAt( 0 ).toUpperCase() + s.slice( 1 ) ).join( ' > ' ) || 'Dashboard';
  const pageUrl = `https://stack.wecare.digital${router.pathname}`;

  // Protected pages
  return (
    <ErrorBoundary>
      <Head>
        <title>Bharat Stack by WECARE.DIGITAL</title>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&amp;display=swap" rel="stylesheet" />
        <meta name="description" content="Stack CRM Dashboard - Multi-channel messaging platform" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href={ FAVICON_URL } />
        <link rel="apple-touch-icon" href={ LOGO_URL } />
        <meta name="robots" content="noindex, nofollow" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="theme-color" content="#1a3a2a" />
        <link rel="manifest" href="/manifest.json" />
        <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( organizationSchema ) } } />
        <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( getBreadcrumbSchema( pageName, pageUrl ) ) } } />
      </Head>
      {/* Google Analytics 4 (G-S3G6REP6Q7) */ }
      <Script src={ `https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}` } strategy="afterInteractive" />
      <Script id="google-analytics-ads" strategy="afterInteractive">
        { `
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', '${GA_MEASUREMENT_ID}', { 'send_page_view': true });
        `}
      </Script>
      {/* Facebook SDK for JavaScript */ }
      <Script id="facebook-sdk-init" strategy="afterInteractive">
        { `
          window.fbAsyncInit = function() {
            FB.init({
              appId: '${process.env.NEXT_PUBLIC_FB_APP_ID || ''}',
              cookie: true,
              xfbml: true,
              version: 'v25.0'
            });
            FB.AppEvents.logPageView();
          };
        `}
      </Script>
      <Script src="https://connect.facebook.net/en_US/sdk.js" strategy="afterInteractive" id="facebook-jssdk" />
      <ThemeProvider theme={ authTheme }>
        <Authenticator.Provider>
          <AuthGate>
            <Authenticator hideSignUp={ true } components={ { Header: AuthBrandHeader } }>
              { ( { signOut, user } ) => {
                if ( typeof window !== 'undefined' && ( window as any ).FB )
                {
                  ( window as any ).FB.AppEvents.logEvent( 'CompletedRegistration' );
                }
                return (
                  <ToastProvider>
                    <ConfirmProvider>
                      <Component { ...pageProps } signOut={ () => { signOut?.(); router.push( '/' ); } } user={ user } />
                      <FloatingAgent />
                    </ConfirmProvider>
                  </ToastProvider>
                );
              } }
            </Authenticator>
          </AuthGate>
        </Authenticator.Provider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

