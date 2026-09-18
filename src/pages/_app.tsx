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
        borderColor: { value: '#d1f470' },
        _focus: {
          borderColor: { value: '#1a3a2a' },
          boxShadow: { value: '0 0 0 3px rgba(209, 244, 112, 0.3)' },
        },
      },
      tabs: {
        item: {
          color: { value: '#6b7280' },
          _active: {
            color: { value: '#1a3a2a' },
            borderColor: { value: '#d1f470' },
          },
          _hover: {
            color: { value: '#0f2a1d' },
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
      <div style={ { display: 'flex', flexDirection: 'column', minHeight: '100vh', paddingTop: 96 } }>
        <div style={ { flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' } }>
          { children }
        </div>
        <Footer />
      </div>
    </>
  );
};

export default function App ( { Component, pageProps }: AppProps ) {
  const router = useRouter();
  const [ mounted, setMounted ] = useState( false );

  const isPublic = router.pathname === '/' || router.pathname === '/grahak-os' || router.pathname === '/contact-test' || router.pathname === '/faq' || router.pathname === '/partners';
  const showPublicWhatsApp = router.pathname === '/' || router.pathname === '/grahak-os';

  useEffect( () => {
    setMounted( true );
    // Register service worker for PWA + offline
    if ( 'serviceWorker' in navigator )
    {
      navigator.serviceWorker.register( '/sw.js' ).catch( () => { } );
    }
    // Init Capacitor native plugins
    initCapacitor( { push: ( p ) => router.push( p ), back: () => router.back() } );
  }, [] );

  // Wait for client-side mount
  if ( !mounted )
  {
    return null;
  }

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
            <Authenticator hideSignUp={ true }>
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

