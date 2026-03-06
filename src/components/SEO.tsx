/**
 * SEO Component - WECARE.DIGITAL
 * Reusable SEO meta tags for all pages
 */

import Head from 'next/head';

interface SEOProps {
  title: string;
  description: string;
  keywords?: string;
  canonical?: string;
  noindex?: boolean;
  ogImage?: string;
}

const BASE_URL = 'https://stack.wecare.digital';
const DEFAULT_IMAGE = 'https://app.wecare.digital/stream/media/m/wecaredigital.png';
const SITE_NAME = 'Stack CRM by WECARE.DIGITAL';

// Default keywords for all pages
const DEFAULT_KEYWORDS = 'WhatsApp Business API, WhatsApp CRM, bulk messaging, SMS API, email marketing, voice calls, Razorpay payments, customer engagement, multi-channel CRM, WECARE.DIGITAL, Stack CRM';

export default function SEO({ 
  title, 
  description, 
  keywords = '', 
  canonical,
  noindex = false,
  ogImage = DEFAULT_IMAGE 
}: SEOProps) {
  const fullTitle = `${title} | ${SITE_NAME}`;
  const allKeywords = keywords ? `${keywords}, ${DEFAULT_KEYWORDS}` : DEFAULT_KEYWORDS;
  
  return (
    <Head>
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      <meta name="keywords" content={allKeywords} />
      
      {/* Robots */}
      <meta name="robots" content={noindex ? 'noindex, nofollow' : 'index, follow'} />
      
      {/* Canonical */}
      {canonical && <link rel="canonical" href={`${BASE_URL}${canonical}`} />}
      
      {/* Open Graph */}
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:image" content={ogImage} />
      <meta property="og:type" content="website" />
      <meta property="og:site_name" content={SITE_NAME} />
      {canonical && <meta property="og:url" content={`${BASE_URL}${canonical}`} />}
      
      {/* Twitter */}
      <meta name="twitter:card" content="summary" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={ogImage} />
    </Head>
  );
}

// Page-specific SEO configurations
export const PAGE_SEO = {
  dashboard: {
    title: 'Dashboard - Overview & Analytics',
    description: 'View your messaging analytics, contact statistics, payment records, and AWS billing. Monitor WhatsApp, SMS, Email performance in real-time.',
    keywords: 'messaging dashboard, analytics, WhatsApp statistics, SMS reports, email metrics, billing overview'
  },
  contacts: {
    title: 'Contacts - Customer Management',
    description: 'Manage your customer contacts. Import, export, search and organize contacts for WhatsApp, SMS, and Email campaigns.',
    keywords: 'contact management, customer database, import contacts, export contacts, CRM contacts'
  },
  whatsapp: {
    title: 'WhatsApp Messaging - Business API',
    description: 'Send and receive WhatsApp messages using official Business API. Create templates, send bulk messages, and automate responses.',
    keywords: 'WhatsApp messaging, WhatsApp Business API, WhatsApp templates, bulk WhatsApp, WhatsApp automation'
  },
  sms: {
    title: 'SMS Messaging - AWS Pinpoint & Airtel',
    description: 'Send SMS messages via AWS Pinpoint or Airtel. Bulk SMS campaigns, OTP delivery, and transactional messages.',
    keywords: 'SMS API, bulk SMS, AWS Pinpoint SMS, Airtel SMS, OTP SMS, transactional SMS'
  },
  email: {
    title: 'Email Marketing - Amazon SES',
    description: 'Send emails via Amazon SES. Create email campaigns, transactional emails, and marketing newsletters.',
    keywords: 'email marketing, Amazon SES, bulk email, email campaigns, transactional email'
  },
  voice: {
    title: 'Voice Calls - AWS & Airtel',
    description: 'Make voice calls via AWS or Airtel. Automated voice campaigns, IVR, and voice notifications.',
    keywords: 'voice calls API, AWS voice, Airtel voice, IVR, voice campaigns, voice notifications'
  },
  payments: {
    title: 'Payments - Razorpay Integration',
    description: 'Send payment requests via WhatsApp with Razorpay integration. Track payments, generate payment links.',
    keywords: 'WhatsApp payments, Razorpay integration, payment links, payment collection, UPI payments'
  },
  bulk: {
    title: 'Bulk Messaging - Campaigns',
    description: 'Send bulk messages across WhatsApp, SMS, Email, and Voice. Create campaigns, schedule messages, track delivery.',
    keywords: 'bulk messaging, bulk WhatsApp, bulk SMS, bulk email, message campaigns, scheduled messages'
  },
  templates: {
    title: 'WhatsApp Templates - Message Templates',
    description: 'Create and manage WhatsApp message templates. Promotional, transactional, and utility templates for business messaging.',
    keywords: 'WhatsApp templates, message templates, promotional templates, transactional templates, template management'
  },
  billing: {
    title: 'Billing - AWS Cost Management',
    description: 'Track AWS resource usage and costs. Monitor Lambda, DynamoDB, S3, API Gateway, and other service billing.',
    keywords: 'AWS billing, cost management, resource usage, Lambda costs, DynamoDB costs, cloud billing'
  },
  aiConfig: {
    title: 'AI Configuration - Response Automation',
    description: 'Configure AI-powered response automation. Set up Amazon Bedrock agents, knowledge bases, and auto-reply settings.',
    keywords: 'AI automation, Amazon Bedrock, AI responses, chatbot configuration, auto-reply, knowledge base'
  }
};
