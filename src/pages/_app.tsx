/**
 * WECARE.DIGITAL
 * Simplified auth - just wrap protected pages with Authenticator
 */

import type { AppProps } from 'next/app';
import Head from 'next/head';
import Script from 'next/script';
import { useRouter } from 'next/router';
import { useState, useEffect } from 'react';
import { Amplify } from 'aws-amplify';
// I18n lives in aws-amplify/utils in v6, not on the root export.
import { I18n } from 'aws-amplify/utils';
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
// Was LanguageBar. Renamed because it no longer only chooses a language: it is the single
// floating widget holding BOTH the WhatsApp contact button and the translate control. The
// external wecare-wa-widget.js that used to inject the WhatsApp button is retired with it.
import SupportWidget from '../components/SupportWidget';
import ErrorBoundary from '../components/ErrorBoundary';
import Header from '../components/Header';
import Footer from '../components/Footer';
import { ToastProvider } from '../contexts/ToastContext';
import { ConfirmProvider } from '../contexts/ConfirmContext';
import { initCapacitor, isNative } from '../lib/capacitor';
import { VERIFICATION } from '../config/analytics';

/**
 * Plain-English labels for the MFA chooser.
 *
 * The user's preferred MFA factor is deliberately UNSET in Cognito, because the
 * API reference says: "If multiple options are activated and no preference is
 * set, a challenge to choose an MFA option will be returned during sign-in."
 * That challenge is what gives a choice of destination at sign-in instead of one
 * hardcoded channel - which matters here because the registered mobile is a
 * WhatsApp Business API number and SMS to it is the least dependable of the
 * three.
 *
 * Amplify renders it as a radio group (SelectMfaType), and its stock labels are
 * "Email Message", "Text Message" and "Authenticator App" - nouns that name a
 * technology rather than saying what is about to happen. These say what happens.
 *
 * They deliberately do NOT include the destination address or number. At this
 * point in the flow the password has been accepted, so it is not a secret from
 * the person typing - but it is rendered pre-authentication, and a masked hint
 * adds nothing a person choosing their own factor does not already know.
 *
 * Overridden through I18n rather than by replacing the component, because
 * getMfaTypeLabelByValue passes every label through translate(); swapping the
 * component would mean owning its form wiring and losing the state machine's
 * submit handling.
 */
I18n.putVocabularies( {
  en: {
    'Select MFA Type': 'How should we send your code?',
    'Email Message': 'Email me a code',
    'Text Message': 'Text me a code (SMS)',
    'Authenticator App': 'Use my authenticator app',
  },
} );

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
          // The apex. This is an OAuth redirect URI, which Cognito validates against a
          // registered allowlist - an unregistered host fails with redirect_mismatch and
          // sign-in stops working - so this fallback must name a REGISTERED URI.
          // https://wecare.digital/ is registered on the stack-wecare-digital-web client
          // as both a callback and a logout URL, verified against the live pool.
          //
          // This used to say stack.wecare.digital, on the reasoning that the apex was
          // only the public marketing host while the app was served from the subdomain.
          // That distinction no longer exists: Amplify maps the apex to this same branch
          // and 301s stack.wecare.digital to it, so the subdomain served nothing of its
          // own and has been retired. A redirecting host is a bad OAuth redirect URI in
          // any case - it works only as long as the 301 preserves the ?code=.
          redirectSignIn: [
            process.env.NEXT_PUBLIC_APP_URL || 'https://wecare.digital/',
          ],
          redirectSignOut: [
            process.env.NEXT_PUBLIC_APP_URL || 'https://wecare.digital/',
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
// Read but deliberately NOT used to inject a tag. GA4 is fired by the GTM container
// (see _document.tsx); a direct gtag.js snippet here double-counts. Kept so the env
// var stays documented and so anything that needs the id for a dataLayer push has it.
export const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || '';

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
  // Stable @id so other nodes - the WebSite, the per-page WebPage, and the
  // product-level SoftwareApplication on /grahak-os - can reference this one entity
  // instead of restating it and risking a conflicting copy.
  "@id": "https://wecare.digital/#organization",
  "name": "WECARE.DIGITAL",
  "alternateName": "WECARE.DIGITAL",
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
    "url": "https://wecare.digital/contact",
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
  "name": "WECARE.DIGITAL",
  "alternateName": "WECARE.DIGITAL",
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
    "SMS API (India DLT templates)",
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
  "@id": "https://wecare.digital/#website",
  "name": "WECARE.DIGITAL",
  "alternateName": "WECARE.DIGITAL",
  "url": "https://wecare.digital",
  "description": "Enterprise WhatsApp Business API platform for multi-channel customer engagement",
  "publisher": {
    "@type": "Organization",
    "name": "WECARE.DIGITAL"
  },
  // SearchAction REMOVED. It declared the sitelinks search box, which Google removed
  // from Search on 2024-11-21 and whose documentation was deleted a month later -
  // Google's own guidance is that the markup does not need removing but will not be
  // used. It was also pointing at https://wecare.digital/contacts?q=, an
  // AUTHENTICATED dashboard route, so it advertised a search endpoint that returns a
  // login wall to anyone not signed in. Wrong on both counts, so it is gone rather
  // than left as inert weight.
  "inLanguage": "en-IN"
};

// FAQ Schema for AI and search engines
const faqSchema = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is WECARE.DIGITAL?",
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
        "text": "Stack CRM supports WhatsApp Business API, SMS (with India DLT templates), Email (via Amazon SES), and Voice calls. All channels are unified in a single dashboard."
      }
    }
  ]
};

// Service Schema
const serviceSchema = {
  "@context": "https://schema.org",
  "@type": "Service",
  "@id": "https://wecare.digital/#service",
  // `name` was missing. It is a required property on Service, and without it the
  // entity describes a serviceType with nothing to call it - a validator reports it and
  // Google has no label to attach.
  "name": "WECARE.DIGITAL customer engagement services",
  "serviceType": "WhatsApp Business API Platform",
  // Reference, not a restatement: the full Organization is declared once with this
  // @id, so repeating its properties here is what creates conflicting copies.
  "provider": { "@id": "https://wecare.digital/#organization" },
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

/**
 * Per-route WebPage + BreadcrumbList for the PUBLIC pages, as a single @graph.
 *
 * Why this exists: every public page was emitting the same five site-level entities
 * and nothing that identified the page itself, so Google had no per-URL description of
 * the site's hierarchy. Breadcrumbs are the supported signal for that.
 *
 * Deliberately NOT a sitelinks search box - see the note on websiteSchema. Google
 * removed that feature in November 2024.
 *
 * /contact uses ContactPage, which is the correct schema.org type for it. The rest are
 * WebPage. Anything not listed falls back to a bare WebPage with no breadcrumb, which
 * is correct for the home page: a breadcrumb whose only entry is the page you are on
 * says nothing.
 */
const PUBLIC_PAGE_META: Record<string, { name: string; type: string; description: string }> = {
  '/grahak-os': { name: 'Grahak OS', type: 'WebPage', description: 'Customer engagement across WhatsApp, SMS, Email and Voice.' },
  '/vayulok': { name: 'VayuLok', type: 'WebPage', description: 'Bharat air and weather intelligence.' },
  '/contact': { name: 'Contact', type: 'ContactPage', description: 'Submit, amend or track a request, drop documents, or leave a review.' },
  '/terms': { name: 'Terms', type: 'WebPage', description: 'Terms of service.' },
  '/privacy': { name: 'Privacy', type: 'WebPage', description: 'How WECARE.DIGITAL handles your data.' },
  '/my-order': { name: 'My Order', type: 'WebPage', description: 'Check the status of an order, delivery, request or booking.' },
  // Bharat Rx does NOT do medicine retail - the owner confirmed that, and the description
  // said "Medicines, consults, reminders and records" until then. Structured data that
  // promises a product the page does not offer is worse than none.
  '/bharat-rx': { name: 'Bharat Rx', type: 'WebPage', description: 'Consults, appointments, reminders and records in one place.' },
  // The seven product pages. Descriptions are shorter than the pages' own meta descriptions
  // on purpose: this feeds WebPage.description in the schema graph, where a sentence is
  // enough, while the <title>/<meta> pair in ProductPage.tsx does the search-result work.
  '/elsewhere': { name: 'Elsewhere', type: 'WebPage', description: 'End-to-end travel: visas, bookings and journeys.' },
  '/expo-week': { name: 'Expo Week', type: 'WebPage', description: 'A virtual travel fair and immersive digital expo.' },
  '/dastavez': { name: 'Dastavez', type: 'WebPage', description: 'Business documentation and registrations in India.' },
  '/clear-closure': { name: 'Clear Closure', type: 'WebPage', description: 'Online dispute resolution, fully online.' },
  '/ritual-guru': { name: 'Ritual Guru', type: 'WebPage', description: 'Curated, temple-grade puja kits.' },
  // Renamed twice: '/swdhya' -> '/open-possibility' -> '/anew'. The route moved with the
  // brand name each time; neither earlier address was ever published, so there is nothing
  // to redirect from.
  '/anew': { name: 'Anew', type: 'WebPage', description: 'Reflection-led conversations that create clarity and action.' },
  '/niji-setu': { name: 'Niji Setu', type: 'WebPage', description: 'A QR code people scan to reach you on a masked call.' },
};

/**
 * RETIRED URLS: now handled at the CDN, not in the code.
 *
 * /selfservice and /product-page/* were previously kept alive by an in-repo client-side
 * redirect (src/components/RetiredUrl.tsx + these RETIRED_ROUTES entries), because a
 * static export cannot emit a server 301 and Amplify Hosting redirects are console-managed.
 *
 * On owner instruction those stubs were REMOVED. The routes no longer exist in the export,
 * so a request for them now 404s at the origin UNLESS a CDN-level 301 is configured in the
 * Amplify Console (Rewrites and redirects: /selfservice -> /contact/ and /product-page/<*>
 * -> /contact/). That console redirect is the owner's responsibility and is the correct,
 * single place for it. NOTE: any /selfservice or /product-page link already delivered in a
 * WhatsApp message will break until that console 301 exists.
 */
const SITE = 'https://wecare.digital';

const getPublicPageSchema = ( pathname: string ) => {
  const meta = PUBLIC_PAGE_META[ pathname ];
  if ( !meta ) {
    return {
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      '@id': `${SITE}/#webpage`,
      url: `${SITE}/`,
      name: 'WECARE.DIGITAL',
      isPartOf: { '@id': `${SITE}/#website` },
      inLanguage: 'en-IN',
    };
  }
  // trailingSlash is set, so the canonical URL carries the slash. Breadcrumb items
  // must match the canonical or they describe a URL that redirects.
  const url = `${SITE}${pathname}/`;
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': meta.type,
        '@id': `${url}#webpage`,
        url,
        name: meta.name,
        description: meta.description,
        isPartOf: { '@id': `${SITE}/#website` },
        inLanguage: 'en-IN',
        breadcrumb: { '@id': `${url}#breadcrumb` },
      },
      {
        '@type': 'BreadcrumbList',
        '@id': `${url}#breadcrumb`,
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: `${SITE}/` },
          { '@type': 'ListItem', position: 2, name: meta.name, item: url },
        ],
      },
    ],
  };
};

// Breadcrumb schema for internal (authenticated) pages
const getBreadcrumbSchema = ( pageName: string, pageUrl: string ) => ( {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Home",
      // The apex, matching the public canonicals. This previously named the subdomain on
      // the basis that authenticated pages were served from it; they are not - the apex
      // serves them and the subdomain only 301'd here, so this breadcrumb was pointing
      // at a redirect from a page already served on the apex.
      "item": "https://wecare.digital"
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
 * AuthGate — the public chrome around the sign-in card.
 *
 * This is the THIRD place chrome is mounted, and it is easy to forget because it is not
 * a route: any visitor who opens a staff URL without a session lands here, including
 * every mistyped path that does not match the allowlist. So it is a page the public
 * genuinely sees, and it gets the same three pieces as a public page - Header, Footer and
 * SupportWidget.
 *
 * SupportWidget was missing here until now, and the gap mattered in exactly the situation
 * this screen exists for: someone who cannot get in had no way to reach us from the screen
 * telling them they cannot get in. It is mounted below, outside .ag-shell, because the
 * widget is position:fixed and does not belong in a flex column.
 *
 * Once authenticated this returns children directly. Header and Footer are deliberately
 * NOT carried into the dashboard: Layout.tsx has its own top bar and sidebar and no footer
 * at all, and adding a second fixed header would collide with both.
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
      <SupportWidget />
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
      {/* GLOBAL, deliberately: this styles the Amplify Authenticator's own card,
          which is rendered inside a composite component that styled-jsx cannot
          scope into. Targeted via data-amplify-router, a documented Amplify data
          attribute, rather than the amplify-* class names, which are internal.
          Scoped under .ag-shell so it can only ever apply to the unauthenticated
          sign-in chrome and not to anything in the dashboard.

          A 4px lime TOP EDGE, not a lime outline on all four sides. The owner asked
          for a lime border, and a full lime outline is the one thing that should not
          go here: the contract reserves lime for interactive state and #e5e7eb for
          static edges, and a lime ring around a resting card is precisely what made
          the input fields read as permanently focused - the defect fixed one commit
          ago. A single heavy top edge reads as brand, cannot be mistaken for focus,
          and still uses full-strength #d1f470, which is correct here because this
          card IS one of our own surfaces. The other three sides take the static
          hairline. */}
      <style jsx global>{`
        .ag-shell [data-amplify-router]{
          border:1px solid #e5e7eb;
          border-top:4px solid #d1f470;
          border-radius:16px;
          overflow:hidden;
        }

        /* ===== The MFA chooser =====
           Appears because the user's preferred factor is unset, so Cognito
           returns a selection challenge. Amplify renders it as a radio group
           inside [data-amplify-authenticator-select-mfa-type] - a documented
           data attribute, unlike the amplify-* class names, which are internal
           and would be a private API to depend on.

           Unstyled, the options are bare radios with no hit area, which on a
           phone means three small circles and no obvious way to pick. Each one
           becomes a card the whole row of which is tappable.

           Values are the public contract's: 2px #e5e7eb because each row HAS a
           hover, swapping to lime; rgba(0,0,0,.898) label; #1a3a2a on the
           checked mark, which is the palette's active-state green. */
        .ag-shell [data-amplify-authenticator-select-mfa-type] fieldset{
          gap:10px;
        }
        .ag-shell [data-amplify-authenticator-select-mfa-type] .amplify-radio{
          display:flex;
          align-items:center;
          gap:12px;
          padding:14px 18px;
          border:2px solid #e5e7eb;
          border-radius:13px;
          background:#fff;
          cursor:pointer;
          transition:all .25s;
        }
        .ag-shell [data-amplify-authenticator-select-mfa-type] .amplify-radio:hover{
          border-color:#d1f470;
        }
        /* :focus-within, not :focus - the focus lands on the input inside the
           label, so a rule on the row itself would never match. */
        .ag-shell [data-amplify-authenticator-select-mfa-type] .amplify-radio:focus-within{
          border-color:#d1f470;
          box-shadow:0 0 0 3px rgba(26,58,42,.3);
        }
        .ag-shell [data-amplify-authenticator-select-mfa-type] .amplify-radio__label{
          font-size:17px;
          font-weight:500;
          line-height:1.4;
          letter-spacing:-.125px;
          color:rgba(0,0,0,.898);
          cursor:pointer;
        }
        .ag-shell [data-amplify-authenticator-select-mfa-type] .amplify-radio__button{
          --amplify-components-radio-button-color:#1a3a2a;
          --amplify-components-radio-button-border-color:#e5e7eb;
        }
        @media(prefers-reduced-motion:reduce){
          .ag-shell [data-amplify-authenticator-select-mfa-type] .amplify-radio{
            transition:none;
          }
        }
      `}</style>
    </>
  );
};

export default function App ( { Component, pageProps }: AppProps ) {
  const router = useRouter();


  // EXACT-MATCH allowlist. A public page missing from this list renders an empty
  // body with HTTP 200 — a 404 that does not look like one — so every new public
  // route has to be added here as well as created under src/pages.
  // Blog and post pages own their own <head> via SEO.tsx, so the sitewide Head below is
  // suppressed for them - that is stack's arrangement and it is kept.
  const isContentPublic = router.pathname === '/blog' || router.pathname === '/post/[slug]';
  // /faq and /partners are deliberately ABSENT. stack still lists them because this
  // branch's removal has not landed there yet; both pages were deleted on owner
  // instruction and re-adding the routes here would render blank 200s for them.
  // PUBLIC_PAGE_META is the single list of public marketing routes now. The seven new product
  // pages made the old inline chain of ORs unreadable and, worse, made it possible to add a
  // page to the menu and the sitemap while forgetting this one - which renders an empty body
  // with HTTP 200 and is invisible until someone loads the route. Deriving the allowlist from
  // the metadata map means a product cannot exist for structured data but not for rendering.
  // /get is public but NOT marketing, so it is listed here rather than added to
  // PUBLIC_PAGE_META: it must render without a staff sign-in, but it should not
  // acquire WebPage/BreadcrumbList structured data or appear in the sitemap. It is
  // the customer file-collection page - a visitor verifies their own number over
  // WhatsApp against the customer pool, which has nothing to do with the staff
  // Authenticator this branch would otherwise wrap it in.
  //
  // Without this line the page renders the staff sign-in screen at HTTP 200, which
  // is precisely the "404 that does not look like one" the comment above warns
  // about. Found exactly that way on the live site when this page was at /files.
  // '/contact-test' WAS LISTED HERE AND HAD TO COME OFF. It was the only route that was
  // both in this allowlist AND wrapped in the authenticated <Layout> by its own page file,
  // and the combination leaked the dashboard into public HTML: because the export is
  // prerendered with no session, Layout rendered in full, so
  // https://wecare.digital/contact-test/ returned HTTP 200 carrying the entire staff
  // sidebar - Inbox, Contacts, Broadcast, Payments, Service Ops, Store, Forms, Tasks - the
  // page search box and the BottomNav, to anyone who asked. Verified live before removal;
  // /dm/inbox/ and /store/ were clean, so this page was the whole of the exposure.
  //
  // It was also a duplicate: /contact is the real public contact page, and this one's form
  // resolved a setTimeout and threw the message away. De-listed rather than deleted so the
  // removal is one reversible line; PublicRouteRegistration.test.ts now fails any public
  // route that imports Layout, so this shape cannot return.
  const isPublic = router.pathname === '/'
    || router.pathname === '/get'
    || Object.prototype.hasOwnProperty.call( PUBLIC_PAGE_META, router.pathname )
    || isContentPublic;

  // trailingSlash is set in next.config.js, so the canonical form of every route except
  // the root carries a trailing slash. A canonical pointing at the slashless URL names
  // a location that 308-redirects, which is a contradictory signal.
  const canonicalUrl = router.pathname === '/'
    ? `${SITE}/`
    : `${SITE}${router.pathname}/`;
  // NO showPublicWhatsApp FLAG ANY MORE. It gated a <Script> tag that injected the
  // external wecare-wa-widget.js, and that script is retired: the WhatsApp button is now
  // the left half of the SupportWidget component, which this file renders in the public branch
  // below - so the branch itself is the gate and a separate boolean would be a second
  // source of truth for the same question. A new public page picks the widget up by
  // being public, exactly as it picks up the header and footer.

  /**
   * A MISTYPED ADDRESS LANDS ON THE HOME PAGE, and the address bar says so.
   *
   * Amplify's last custom rule is `/<*>` -> `/index.html` with status `404-200`. Despite
   * the name that is NOT "rewrite to 200" — the CDK enum calls it `NOT_FOUND_REWRITE`,
   * "Not found rewrite (404)". Measured on the live site: an unknown path returns HTTP
   * 404 with a body byte-identical to `/index.html`.
   *
   * Because the exported `index.html` carries `"page":"/"`, Next hydrates it as the home
   * route, so `router.pathname` is already `/` and the real home page renders. The only
   * thing left wrong is the address bar, which still shows whatever was typed. This
   * corrects it.
   *
   * WHY NOT DO IT AT THE CDN. A `200`/`301`/`302` rule on `/<*>` matches unconditionally
   * rather than only after the file lookup misses, so it would shadow all ~123 exported
   * pages and serve the home page for the whole site. Only the 404-family statuses are
   * conditional. The status therefore stays 404, which is also the honest answer: a URL
   * that was never published should not report 200, or anyone can mint unlimited
   * indexable addresses on the domain and Google records it as a soft 404.
   *
   * replaceState, not router.replace: this is a cosmetic correction of an address that
   * was never a route, so it must not add a history entry (Back would re-enter the typo)
   * and must not re-run the router. Guarded on the PATH ONLY, so `/?utm_source=x` and
   * `/#pricing` on the real home page are left alone.
   */
  useEffect( () => {
    if ( router.pathname !== '/' ) return;
    const typedPath = router.asPath.split( '?' )[ 0 ].split( '#' )[ 0 ];
    if ( typedPath === '/' || typedPath === '' ) return;
    const suffix = router.asPath.slice( typedPath.length );
    window.history.replaceState( window.history.state, '', '/' + suffix );
  }, [ router.pathname, router.asPath ] );

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
        { !isContentPublic && (
          <Head>
          {/* PRODUCT-NEUTRAL SITEWIDE TITLE. This read "WECARE.DIGITAL - WhatsApp Business
              API Platform | Multi-Channel Messaging CRM India" - 86 characters, of which
              Google shows about 60, and every word after the brand described a single
              product. It was the <title> for all 15 public routes, so the company home page
              was titled as a WhatsApp CRM. Kept short enough to survive truncation and
              worded to match the og/twitter/description copy below. */}
          <title>Everyday AI, built for Bharat | WECARE.DIGITAL</title>
          <link rel="preconnect" href="https://fonts.googleapis.com" />
          <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
          <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&amp;display=swap" rel="stylesheet" />
          {/* SITEWIDE FALLBACK, AND IT MUST STAY PRODUCT-NEUTRAL.
              This block is inherited by every public route that does not declare its own, so
              whatever it says becomes the identity of 15 pages. It used to read "Enterprise
              WhatsApp Business API platform for India..." with 22 WhatsApp keywords - copy
              written for ONE product - so the company home page was indexed as a WhatsApp
              product page and competed with /grahak-os/ for the same terms.
              /grahak-os/ is unaffected by this change: it already declares its own title,
              description, keywords and OG tags, so its WhatsApp positioning is stated where it
              belongs rather than leaking sitewide. Any page wanting product-specific terms
              should do the same.
              NOTE ON KEYWORDS: Google has ignored meta keywords since 2009 and Bing gives it no
              weight either, so this tag earns nothing for ranking. It is kept only so the page
              does not describe a product it is not about; deleting it outright would be equally
              valid. Do not invest in tuning it. */}
          <meta name="description" content="WECARE.DIGITAL builds everyday AI for consumers, enterprises, climate tech and frontier tech, with transparent pricing and one place to track everything." />
          <meta name="keywords" content="WECARE.DIGITAL, everyday AI, AI services India, transparent pricing, consumer services, enterprise services, climate tech, frontier tech" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <link rel="icon" href={ FAVICON_URL } />
          <link rel="apple-touch-icon" href={ LOGO_URL } />
          {/* CANONICAL AND og:url ARE COMPUTED, and carry a key.
              Both were hardcoded to the site root, on every page. The result was that
              /contact/, /terms/, /privacy/, /grahak-os/ and /vayulok/ each shipped TWO
              canonical tags - this root one first, then the page's own correct one -
              which is ambiguous, and the most likely reading is that every page is a
              duplicate of the homepage. That alone would keep those URLs from ranking,
              and sitelinks with them.
              key="canonical" is what makes this safe to keep here: next/head dedupes by
              key and a page's Head is processed after _app's, so a page that sets its
              own canonical overrides this one instead of adding a second. Routes that
              set none now inherit a correct value rather than pointing at the root. */}
          <link rel="canonical" key="canonical" href={ canonicalUrl } />

          {/* Search Console / Bing Webmaster ownership.
              Rendered only when the env value is set. An empty content="" tag is worse
              than no tag: verification fails either way, but an empty one looks
              configured and stops anyone looking for the cause.
              Note the Bing property is registered as https://www.wecare.digital/, which
              301s to the apex this site now serves from, so the property may need
              re-pointing at https://wecare.digital/. */}
          { VERIFICATION.google && (
            <meta name="google-site-verification" content={ VERIFICATION.google } />
          ) }
          { VERIFICATION.bing && (
            <meta name="msvalidate.01" content={ VERIFICATION.bing } />
          ) }

          {/* Open Graph.
              EVERY og: TAG CARRIES A key, AND THAT IS LOAD-BEARING - not tidiness.
              next/head only de-duplicates meta by `name`, `httpEquiv`, `charSet` and
              `itemProp`. `property` is NOT in that list, so two og:title tags coexist
              happily where two twitter:title tags collapse to one. Measured on the built
              export, /grahak-os/index.html shipped TWO of every single og tag - type, url,
              title, description, image, site_name, locale - because that page declares its
              own set and nothing merged them. A link preview then reads whichever it meets
              first, which was this sitewide block, so the product page previewed with the
              sitewide copy.
              An explicit key is the documented escape hatch, but it only works when BOTH
              sides use the SAME key: og:url already had key="og:url" here and still
              duplicated, because /grahak-os/ declared its og:url without one. The keys
              below are therefore mirrored in src/pages/grahak-os/index.tsx, and any future
              page that declares og tags must use these same keys or it will double them
              again. Verify with:
                grep -o '"og:title"' out/grahak-os/index.html | wc -l   # must be 1 */}
          <meta property="og:type" key="og:type" content="website" />
          <meta property="og:url" key="og:url" content={ canonicalUrl } />
          {/* PRODUCT-NEUTRAL, for the same reason the description above is.
              These read "WECARE.DIGITAL - WhatsApp Business API Platform | WECARE.DIGITAL"
              and "Enterprise WhatsApp Business API platform. Send bulk messages, payments &
              automate customer engagement with AI." That is one product's copy, and because
              this block is inherited by every public route it was the share preview for all
              15 of them - including the company home page, which is not a WhatsApp product
              page. It also printed the brand name TWICE in a single og:title.
              The wording now mirrors the neutral description already agreed above, so the
              title, description, og and twitter tags finally describe the same company.
              /grahak-os/ keeps its WhatsApp positioning in its own Head, which is where a
              product claim belongs. */}
          <meta property="og:title" key="og:title" content="Everyday AI, built for Bharat | WECARE.DIGITAL" />
          <meta property="og:description" key="og:description" content="WECARE.DIGITAL builds everyday AI for consumers, enterprises, climate tech and frontier tech, with transparent pricing and one place to track everything." />
          <meta property="og:image" key="og:image" content={ LOGO_URL } />
          <meta property="og:image:width" key="og:image:width" content="512" />
          <meta property="og:image:height" key="og:image:height" content="512" />
          <meta property="og:site_name" key="og:site_name" content="WECARE.DIGITAL" />
          <meta property="og:locale" key="og:locale" content="en_IN" />

          {/* Twitter. These need no key - next/head dedupes on `name`, which is why only
              the og: block above was doubling. twitter:url was hardcoded to the site root
              on every page, the same defect already fixed on canonical and og:url; it is
              computed now so a shared link resolves to the page that was shared. */ }
          <meta name="twitter:card" content="summary_large_image" />
          <meta name="twitter:url" content={ canonicalUrl } />
          <meta name="twitter:title" content="Everyday AI, built for Bharat | WECARE.DIGITAL" />
          <meta name="twitter:description" content="WECARE.DIGITAL builds everyday AI for consumers, enterprises, climate tech and frontier tech, with transparent pricing and one place to track everything." />
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

          {/* Structured Data.
              SITE-LEVEL ENTITIES ONLY, emitted once. Google's structured data
              guidelines require the markup to represent the page's actual content, and
              a page must not carry two conflicting copies of the same entity.

              faqSchema is GONE from here. Two reasons, either of which is sufficient:
              Google stopped showing FAQ rich results on 2026-05-07 and is dropping the
              search appearance and Rich Results Test support, so it earns nothing; and
              it was emitted on EVERY public page, including /terms, /privacy, /contact
              and /vayulok, none of which contain an FAQ. Marking up content that is not
              on the page is a guidelines violation, not merely useless.

              A per-route BreadcrumbList and WebPage are added below instead. Those are
              still supported, and breadcrumbs are the part of this that actually helps
              Google understand site hierarchy. */}
          <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( organizationSchema ) } } />
          {/* The PLATFORM-level SoftwareApplication is emitted everywhere EXCEPT
              /grahak-os, which declares its own product-level one. Both together put
              two SoftwareApplication entities on a single page, which leaves Google to
              guess which application the page is actually about. The product page wins
              there because it is the more specific claim; every other page keeps the
              platform entity. */}
          { router.pathname !== '/grahak-os' && (
            <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( softwareSchema ) } } />
          ) }
          <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( websiteSchema ) } } />
          {/* serviceSchema IS SCOPED TO /grahak-os, the mirror image of the
              softwareSchema gate just above. It declares serviceType "WhatsApp Business
              API Platform" and a hasOfferCatalog of WhatsApp / Bulk SMS / Email Marketing
              / Voice Calls - one product's offering - and it was being emitted on all 15
              public routes, so /terms, /privacy, /contact, /my-order and the company home
              page each told Google they offer a WhatsApp messaging catalog.
              That is the same leak already fixed on description, keywords, title and the
              og block, and here it is also a guidelines problem rather than just wasted
              markup: Google requires structured data to represent the page's actual
              content, which a messaging offer catalog does not do on a privacy policy.
              On /grahak-os the entity is accurate, so the value needs no rewording - only
              the scope was wrong. */}
          { router.pathname === '/grahak-os' && (
            <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( serviceSchema ) } } />
          ) }
          <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( getPublicPageSchema( router.pathname ) ) } } />
        </Head>
        ) }
        {/* NO DIRECT gtag.js HERE - BY POLICY, and it was being violated.
            _document.tsx states that all Google tracking on this property is delivered
            exclusively through the GTM container, which itself fires GA4
            (G-GNRPFFBXMF) and Google Ads (AW-18396505964), and that adding a direct
            snippet alongside it double-counts every pageview and conversion.
            This file was doing exactly that. Measured in a browser, the home page
            requested gtag/js FOUR times: G-S3G6REP6Q7 bare from the snippet that used
            to be here, plus AW-18396505964, G-GNRPFFBXMF and G-S3G6REP6Q7 again from
            the container. So G-S3G6REP6Q7 was loaded twice on every page view.
            The snippet is injected client-side by next/script, so it never appeared in
            the static HTML and could not be found by grepping the export - only a
            request log shows it. tagcheck.js now asserts the container loads once and
            no direct gtag.js accompanies it. */}
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
        <Header />
        <Component { ...pageProps } />
        <Footer />
        {/* WhatsApp contact + page translation. This comment used to read "translation +
            read-aloud, public pages only, and deliberately not on the authenticated
            dashboard" and both halves are now wrong, which is why it is rewritten rather
            than trimmed: read-aloud was removed (Amazon Polly has no voice for Tamil,
            Telugu, Bengali or most other Indic languages, so the button was hidden for
            nearly every language this serves), and the widget IS on the dashboard now -
            see the mount in the authenticated branch below for the one attribute that
            makes that safe. Three mounts total, all in this file: here, AuthGate, and the
            authenticated branch. PublicWidgets.test.tsx counts them. */}
        <SupportWidget />
      </ErrorBoundary>
    );
  }

  // Get page name for breadcrumb
  const pageName = router.pathname.split( '/' ).filter( Boolean ).map( s => s.charAt( 0 ).toUpperCase() + s.slice( 1 ) ).join( ' > ' ) || 'Dashboard';
  // The apex serves these routes; the old subdomain only 301'd here.
  const pageUrl = `https://wecare.digital${router.pathname}`;

  // Protected pages
  return (
    <ErrorBoundary>
      <Head>
        <title>WECARE.DIGITAL</title>
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
        {/* NO DIRECT gtag.js HERE - BY POLICY, and it was being violated.
            _document.tsx states that all Google tracking on this property is delivered
            exclusively through the GTM container, which itself fires GA4
            (G-GNRPFFBXMF) and Google Ads (AW-18396505964), and that adding a direct
            snippet alongside it double-counts every pageview and conversion.
            This file was doing exactly that. Measured in a browser, the home page
            requested gtag/js FOUR times: G-S3G6REP6Q7 bare from the snippet that used
            to be here, plus AW-18396505964, G-GNRPFFBXMF and G-S3G6REP6Q7 again from
            the container. So G-S3G6REP6Q7 was loaded twice on every page view.
            The snippet is injected client-side by next/script, so it never appeared in
            the static HTML and could not be found by grepping the export - only a
            request log shows it. tagcheck.js now asserts the container loads once and
            no direct gtag.js accompanies it. */}
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
                      {/* THE SAME COMBINED WIDGET AS THE PUBLIC PAGES, so contact and
                          language are in one place on every route in the product rather
                          than only on the marketing side.
                          IT IS SAFE HERE BECAUSE OF ONE ATTRIBUTE. SupportWidget starts
                          its translation walk at `.layout`, and Layout.tsx marks
                          `.main-content` with data-wc-no-translate - so the sidebar's
                          navigation translates while every page's CONTENT (customer
                          names, numbers, message bodies) is exempt. Without that
                          attribute this mount would let an operator machine-translate
                          live customer data, which is why it was previously excluded.
                          FloatingAgent above is a different thing and stays: it is the
                          internal AI task assistant, not customer contact. */}
                      <SupportWidget />
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

