/**
 * Privacy Policy — section content.
 *
 * PORTED VERBATIM from the published document at
 * https://wecaredigitalbw.wixsite.com/website-1/privacy
 * by parsing that page, not by retyping it, so no clause was altered in transit.
 *
 * WHAT WAS CHANGED, and it is only ever structure:
 *   - Wix pads its layout with U+200B zero-width spaces; those are stripped.
 *   - Numbered headings became section objects with slugs, so the page can render a
 *     table of contents and support deep links. A 39-section document with no
 *     navigation is unreadable on a phone, which is where most of these get opened.
 *   - Links to the old Wix paths now point at /terms/ and /privacy/.
 *
 * WHAT WAS NOT CHANGED: the wording of any clause. Editing the substance of a contract
 * or a privacy representation is a legal act, not a copy task - if a clause should read
 * differently, that change belongs to whoever owns the legal risk, and it should be
 * made here and on the source document together so the two cannot diverge.
 *
 * THE SOURCE IS STILL THE WIX PAGE. Until it is retired, a change made there will not
 * appear here. Re-run the extractor rather than hand-patching, or the two drift.
 */

export interface LegalSection {
  /** "14" or "14.11" - preserved so cross-references in the text still resolve. */
  number: string;
  heading: string;
  /** URL-safe anchor, e.g. "s14-11". */
  id: string;
  paragraphs: string[];
}

export const PRIVACY_UPDATED = '2026-09-23';
export const PRIVACY_SOURCE = 'https://wecaredigitalbw.wixsite.com/website-1/privacy';

export const PRIVACY_INTRO: string[] = [
  "This Privacy Policy explains how WECARE.DIGITAL, operated under the business name WECARE.DIGITAL BHARATWORKS (\"WECARE.DIGITAL\", \"we\", \"us\" or \"our\"), collects, uses, stores, shares and protects personal data in connection with our websites, applications, digital platforms, products and Services.",
  "Read it together with our Terms of Service at /terms/ and any privacy information or Service-Specific Terms shown for a particular Service.",
  "Using WECARE.DIGITAL is not unrestricted consent to every possible use of personal data. Where applicable law requires consent or another specific authorisation, we will use an appropriate mechanism."
];

export const PRIVACY_SECTIONS: LegalSection[] = [
  {
    "number": "1",
    "heading": "Scope",
    "id": "s1",
    "paragraphs": [
      "This Privacy Policy applies to personal data processed by WECARE.DIGITAL in connection with our websites and applications; User accounts; products, orders and deliveries; appointments and bookings; professional or expert Services; documentation and processing Services; travel or experience Services; digital products; subscriptions and memberships; partner or referral programs; gift cards and promotions; customer support and grievances; enterprise or institutional Services; and other Services offered under the WECARE.DIGITAL brand.",
      "Independent Sellers, Service Providers, payment processors or other third parties may process personal data for their own purposes. Their own privacy terms may apply where they independently determine how personal data is processed."
    ]
  },
  {
    "number": "2",
    "heading": "What Personal Data Means",
    "id": "s2",
    "paragraphs": [
      "For this Privacy Policy, \"Personal Data\" means information relating to an individual who is identifiable by or in relation to that information, or another meaning given to the term under applicable data-protection law.",
      "Depending on the Service and circumstances, Personal Data may include information provided directly by you, information generated through your use of the Platform and information received from authorized or lawful third-party sources."
    ]
  },
  {
    "number": "3",
    "heading": "Personal Data We May Collect",
    "id": "s3",
    "paragraphs": [
      "The information we collect depends on the Service you use and the information reasonably required to provide it."
    ]
  },
  {
    "number": "3.1",
    "heading": "Account and Contact Information",
    "id": "s3-1",
    "paragraphs": [
      "We may collect your name, email address, telephone number, username or account identifiers, authentication information, communication preferences and profile information you choose to provide or that is required for a specific Service."
    ]
  },
  {
    "number": "3.2",
    "heading": "Transaction Information",
    "id": "s3-2",
    "paragraphs": [
      "When you purchase, book or request a Service, we may process order or booking details; products or Services requested; billing or delivery information; transaction amount; payment status; refunds or cancellations; invoice information; Gift Card or account-credit information; and transaction history.",
      "Payments may be processed through independent banks, gateways or payment providers.",
      "Depending on the payment method, WECARE.DIGITAL may receive transaction identifiers, status information or limited payment-related details from the processor.",
      "Where payment credentials are collected directly by an independent payment provider, that provider's privacy and security practices may apply to those credentials."
    ]
  },
  {
    "number": "3.3",
    "heading": "Service Information",
    "id": "s3-3",
    "paragraphs": [
      "Depending on the Service, you may provide documents, photographs, forms, application information, appointment details, instructions, preferences, identity or eligibility information, professional-service information, travel-related information, information necessary for customization or other information necessary to fulfil your request.",
      "Some Services may involve information that is particularly sensitive in context, such as health-related, financial, identity, professional, legal or consultation information.",
      "Such information will be handled according to the relevant purpose, applicable law and any additional Service-Specific privacy information."
    ]
  },
  {
    "number": "3.4",
    "heading": "Communications",
    "id": "s3-4",
    "paragraphs": [
      "We may process communications you send through email, telephone, messaging services, Platform chat, web forms, support requests, social media or other communication channels.",
      "Where a call, consultation or interaction is recorded, appropriate notice or authorization will be provided where required."
    ]
  },
  {
    "number": "3.5",
    "heading": "Device and Usage Information",
    "id": "s3-5",
    "paragraphs": [
      "When you use the Platform, certain technical information may be collected automatically, including IP address, browser type, device type, operating system, device or session identifiers, referring and exit pages, pages or features used, timestamps, diagnostic information, security logs and general usage information."
    ]
  },
  {
    "number": "3.6",
    "heading": "Location Information",
    "id": "s3-6",
    "paragraphs": [
      "A Service may process approximate or precise location information where relevant, such as for delivery, local availability, navigation or location-enabled functionality.",
      "Where device permission, consent or another authorization is required, we will request it through an appropriate mechanism. You can normally control location permissions through your device or browser settings."
    ]
  },
  {
    "number": "3.7",
    "heading": "Cookies and Similar Technologies",
    "id": "s3-7",
    "paragraphs": [
      "We may use cookies, pixels, local storage or similar technologies to keep the Platform operational; maintain sessions; remember preferences; protect accounts; measure performance; understand how Services are used; prevent fraud; and support analytics, communications or advertising where applicable.",
      "Where consent is legally required for a particular category of technology, an appropriate choice mechanism will be provided. Disabling certain technologies may affect Platform functionality."
    ]
  },
  {
    "number": "3.8",
    "heading": "Information From Third Parties",
    "id": "s3-8",
    "paragraphs": [
      "We may receive Personal Data from Sellers and Service Providers; payment providers; logistics partners; authentication providers; organizations arranging access to a Service; authorized representatives; referral partners; public sources; and public authorities or other persons where permitted by law."
    ]
  },
  {
    "number": "4",
    "heading": "How We Collect Personal Data",
    "id": "s4",
    "paragraphs": [
      "We may collect Personal Data when you create or use an account; access the Platform; purchase, book or use a Service; submit documents or forms; communicate with us; participate in a program, promotion or event; interact with a Seller or Service Provider through WECARE.DIGITAL; use a payment or delivery flow; submit a review or other User Content; use cookies or similar technologies; or otherwise interact with WECARE.DIGITAL.",
      "We may also receive information from authorized third parties where reasonably necessary for a requested Service, security, fraud prevention, verification or another lawful purpose."
    ]
  },
  {
    "number": "5",
    "heading": "Why We Process Personal Data",
    "id": "s5",
    "paragraphs": [
      "Depending on the circumstances, Personal Data may be processed to: Create and administer accounts;",
      "Provide requested Services; Process orders and bookings; Coordinate Sellers and Service Providers; Process and verify payments; Deliver products; Manage appointments; Process documents and requests; Personalize relevant functionality; Communicate about transactions; Provide customer support; Administer subscriptions and memberships; Operate partner or referral programs; Manage promotions, credits and gift cards; Verify identity, authority or eligibility; Protect Users and the Platform; Prevent fraud and abuse; Detect and investigate security incidents; Maintain service quality; Analyze and improve Services; Manage complaints and disputes; Establish, exercise or defend legal claims; Comply with legal obligations; and Carry out other purposes clearly disclosed when information is collected.",
      "We will not use Personal Data for a materially unrelated purpose where applicable law requires additional notice, consent or another lawful basis."
    ]
  },
  {
    "number": "6",
    "heading": "Consent and Other Permitted Processing",
    "id": "s6",
    "paragraphs": [
      "Where processing depends on your consent, we will seek consent using an appropriate affirmative mechanism and provide information reasonably necessary for an informed choice.",
      "Where required by applicable law, you may withdraw consent using the mechanism provided for the relevant Service or by contacting us.",
      "Withdrawal of consent does not invalidate processing lawfully carried out before withdrawal.",
      "If Personal Data is necessary to provide a requested Service, withdrawal, deletion or refusal to provide necessary information may mean that the Service cannot be provided or continued.",
      "Personal Data may also be processed without consent where applicable law permits or requires such processing."
    ]
  },
  {
    "number": "7",
    "heading": "Children and Minors",
    "id": "s7",
    "paragraphs": [
      "Services intended for independent purchase or contracting are generally designed for persons legally capable of entering into the relevant transaction.",
      "Where a Service is made available to a child or minor and applicable law requires parental or guardian authorization, WECARE.DIGITAL will use appropriate measures to obtain or verify that authorization.",
      "Where prohibited by applicable law, we will not knowingly undertake tracking, behavioural monitoring or targeted advertising directed at children.",
      "If you believe Personal Data relating to a child has been processed without required authorization, contact one@wecare.digital ."
    ]
  },
  {
    "number": "8",
    "heading": "Professional, Expert and Consultation Information",
    "id": "s8",
    "paragraphs": [
      "Some WECARE.DIGITAL Services may involve professionals, experts, consultants, practitioners or institutions.",
      "Information provided in connection with such Services remains Personal Data where it relates to an identifiable individual.",
      "Access to consultation or professional-service information will be limited according to the purpose of the Service, applicable professional obligations, operational necessity and applicable law.",
      "We do not treat consultation information as outside the scope of privacy protection merely because it was supplied during a professional interaction.",
      "Information may be disclosed where required by law; where necessary to address a serious and legally recognized safety concern; where you authorize disclosure; where sharing is necessary to provide the Service you requested; or where another lawful basis applies.",
      "Additional professional confidentiality requirements may apply to a particular Service Provider."
    ]
  },
  {
    "number": "9",
    "heading": "Enterprise, Employer and Institutional Services",
    "id": "s9",
    "paragraphs": [
      "A Service may be provided, arranged or funded through an employer, educational institution, organization or another sponsoring entity.",
      "In such cases, the organization may provide information necessary to confirm eligibility or administer access.",
      "What information may be made available to the organization will depend on the applicable arrangement, Service-Specific Terms and law.",
      "Where appropriate, reporting may use aggregated or de-identified information.",
      "Personal consultation content will not be disclosed merely because an employer or institution funded access, except where you authorize it, disclosure is necessary for the Service as disclosed to you, or disclosure is otherwise lawfully permitted or required."
    ]
  },
  {
    "number": "10",
    "heading": "How We Share Personal Data",
    "id": "s10",
    "paragraphs": [
      "Personal Data may be shared only as reasonably necessary for legitimate Service, operational, security, transactional or legal purposes and subject to applicable law."
    ]
  },
  {
    "number": "10.1",
    "heading": "Sellers and Service Providers",
    "id": "s10-1",
    "paragraphs": [
      "Where you request a product or Service supplied by an independent Seller or Service Provider, information reasonably necessary to fulfil, administer or support the transaction may be shared with that provider.",
      "The provider may have independent legal and professional responsibilities concerning that information."
    ]
  },
  {
    "number": "10.2",
    "heading": "Service Vendors and Data Processors",
    "id": "s10-2",
    "paragraphs": [
      "We may use third parties that provide cloud hosting, communications, authentication, customer support, analytics, cybersecurity, payment processing, logistics, document processing, appointment systems, software infrastructure or other operational support.",
      "Such providers should receive only information reasonably necessary for the relevant function and, where appropriate, be subject to contractual, confidentiality and security requirements."
    ]
  },
  {
    "number": "10.3",
    "heading": "Payment Providers",
    "id": "s10-3",
    "paragraphs": [
      "Information necessary to complete a payment, refund, chargeback or payment investigation may be transmitted directly to or received from payment gateways, banks, card networks or other payment providers.",
      "Those providers may process information under their own privacy terms and regulatory obligations."
    ]
  },
  {
    "number": "10.4",
    "heading": "Logistics and Fulfilment Partners",
    "id": "s10-4",
    "paragraphs": [
      "Delivery names, addresses, telephone numbers and other necessary fulfilment information may be shared with couriers, Sellers, warehouses or other fulfilment partners."
    ]
  },
  {
    "number": "10.5",
    "heading": "Business Customers or Sponsoring Organizations",
    "id": "s10-5",
    "paragraphs": [
      "Where an organization arranges or funds access to a Service, information reasonably necessary to administer eligibility, billing, participation or the relevant arrangement may be shared as disclosed for that Service and as permitted by law."
    ]
  },
  {
    "number": "10.6",
    "heading": "Legal and Regulatory Disclosures",
    "id": "s10-6",
    "paragraphs": [
      "We may disclose information where reasonably necessary or legally required to comply with law or lawful process; respond to competent authorities; protect rights or safety; investigate fraud; prevent cybersecurity incidents; enforce applicable agreements; or establish, exercise or defend legal claims."
    ]
  },
  {
    "number": "10.7",
    "heading": "Business Reorganization",
    "id": "s10-7",
    "paragraphs": [
      "If WECARE.DIGITAL or its operations undergo a genuine restructuring, acquisition, merger, sale, financing or transfer, Personal Data may be transferred as part of that transaction subject to applicable law and appropriate safeguards."
    ]
  },
  {
    "number": "11",
    "heading": "Public Information and User Content",
    "id": "s11",
    "paragraphs": [
      "Information you intentionally submit for public display, such as certain reviews, ratings, public comments or profile content, may become visible to others.",
      "Please avoid publishing information that you do not want to make public.",
      "Our rights concerning User Content are described separately in the Terms of Service at:",
      "/terms/",
      "Submission of Personal Data for one purpose does not automatically authorize unrestricted promotional use.",
      "Where additional authorization is legally required for advertising or promotional use of identifiable content, it will be obtained."
    ]
  },
  {
    "number": "12",
    "heading": "Analytics, Advertising and Marketing",
    "id": "s12",
    "paragraphs": [
      "We may use aggregated or appropriately de-identified information to understand Platform performance, usage patterns and Service demand.",
      "Where marketing communications are sent, applicable consent, unsubscribe or opt-out mechanisms will be used.",
      "Transactional communications necessary for an account, order, booking, payment, security event, grievance or requested Service may continue even where you opt out of marketing.",
      "Where personalized advertising involves Personal Data and requires consent or another specific choice under applicable law, the appropriate mechanism will be provided."
    ]
  },
  {
    "number": "13",
    "heading": "Automated Tools and Service Improvement",
    "id": "s13",
    "paragraphs": [
      "WECARE.DIGITAL may use software, automated systems or technology-assisted workflows to operate, secure, organize, route or improve Services.",
      "Where an automated process materially affects a User in a manner for which applicable law requires additional disclosure, consent, review or another safeguard, an appropriate mechanism will be used.",
      "Automated tools may also be used for fraud detection, security monitoring, spam prevention, service routing, analytics or operational support."
    ]
  },
  {
    "number": "14",
    "heading": "International Processing and Transfers",
    "id": "s14",
    "paragraphs": [
      "Some technology, cloud, communications, payment, analytics or service providers may process information outside the location from which you use WECARE.DIGITAL.",
      "Where Personal Data is transferred or processed across borders, we will do so subject to applicable restrictions, lawful requirements and safeguards.",
      "We may alter, restrict or discontinue a transfer arrangement where required by applicable law or governmental direction."
    ]
  },
  {
    "number": "15",
    "heading": "Data Retention",
    "id": "s15",
    "paragraphs": [
      "We retain Personal Data only for as long as reasonably necessary for the purpose for which it was processed, legitimate operational requirements or applicable legal obligations.",
      "Different categories of information may therefore have different retention periods.",
      "Information may be retained where reasonably necessary for an active transaction or ongoing Service; account administration; financial, tax or accounting records; statutory record-keeping; transaction security; fraud prevention; complaint or dispute resolution; backups; legal claims; enforcement of agreements; or compliance with another applicable requirement.",
      "Certain transaction, security, financial and processing records may need to be retained after account closure or a deletion request where required or permitted by law.",
      "When Personal Data is no longer required, it may be deleted, anonymized, de-identified or otherwise handled in accordance with applicable law and our retention processes."
    ]
  },
  {
    "number": "16",
    "heading": "Security",
    "id": "s16",
    "paragraphs": [
      "We use reasonable technical and organizational measures appropriate to the nature of the information and risks involved.",
      "Measures may include, where appropriate, access controls, authentication measures, encryption or masking, monitoring and logging, backups, security testing, vendor controls, incident-response procedures and internal confidentiality restrictions.",
      "No online or electronic system can guarantee absolute security.",
      "Users are responsible for taking reasonable steps to protect account credentials and devices."
    ]
  },
  {
    "number": "17",
    "heading": "Personal Data Breaches",
    "id": "s17",
    "paragraphs": [
      "If we become aware of a Personal Data breach, we will assess the incident and take reasonable steps to contain, investigate and remediate it.",
      "Affected individuals, competent authorities or other persons will be notified where and in the manner required by applicable law.",
      "Such communications may include information concerning the nature of the incident, relevant risks, measures taken and steps Users can consider to protect themselves."
    ]
  },
  {
    "number": "18",
    "heading": "Your Privacy Rights",
    "id": "s18",
    "paragraphs": [
      "Subject to applicable law and any lawful exceptions, you may have rights concerning Personal Data processed by WECARE.DIGITAL.",
      "Depending on the law and circumstances, these may include the ability to: Obtain information about Personal Data being processed; Request correction of inaccurate information; Request completion or updating of information; Request erasure where legally available; Withdraw consent where processing is based on consent; Raise a privacy grievance; Nominate another eligible individual where such a right is provided by law; and Exercise other rights provided by applicable law.",
      "Requests may be sent to one@wecare.digital .",
      "We may request reasonable information to verify identity, authority or the scope of a request before acting on it.",
      "A deletion request will not require deletion of information that we must lawfully retain or that remains reasonably necessary for another lawful purpose."
    ]
  },
  {
    "number": "19",
    "heading": "Account Closure",
    "id": "s19",
    "paragraphs": [
      "Where account closure functionality is available, you may request closure through the applicable Platform or customer-support process.",
      "Closing an account does not necessarily result in immediate deletion of every record.",
      "Information may continue to be retained where required or permitted for completed transactions, legal obligations, fraud prevention, security, dispute resolution, backups or another lawful purpose."
    ]
  },
  {
    "number": "20",
    "heading": "Communications Preferences",
    "id": "s20",
    "paragraphs": [
      "You may be able to manage certain communication preferences through the Platform, an unsubscribe link, device settings or by contacting us.",
      "Marketing preferences do not necessarily affect operational or transactional messages that are reasonably necessary for an account, transaction, booking, security matter, grievance or requested Service."
    ]
  },
  {
    "number": "21",
    "heading": "Third-Party Websites and Services",
    "id": "s21",
    "paragraphs": [
      "The Platform may contain links to independent websites, applications or services.",
      "WECARE.DIGITAL does not control the privacy practices of independent third parties.",
      "When you leave our Platform or interact directly with an independent provider, review that provider's privacy information and applicable terms."
    ]
  },
  {
    "number": "22",
    "heading": "Changes to This Privacy Policy",
    "id": "s22",
    "paragraphs": [
      "We may update this Privacy Policy where reasonably necessary to reflect changes in our Services, technology, practices, security requirements, business operations or applicable law.",
      "Where a change materially affects how Personal Data is handled or where applicable law requires notice, an appropriate notice will be provided.",
      "We will not treat silence, inactivity or continued use as fresh consent where applicable law requires a separate affirmative consent mechanism."
    ]
  },
  {
    "number": "23",
    "heading": "Privacy Questions and Grievances",
    "id": "s23",
    "paragraphs": [
      "For questions, requests or complaints concerning Personal Data, privacy or the handling of information, contact:",
      "Privacy & Grievance Contact",
      "WECARE.DIGITAL Privacy & Grievance Desk",
      "Business: WECARE.DIGITAL BHARATWORKS",
      "Email: one@wecare.digital",
      "Phone: +91 9330994400",
      "Address: The W.B.S.I.D.C. Building, Unit 1/20 81/2/7, Phears Ln Kolkata, West Bengal 700012, India",
      "We may request reasonable information to verify the identity or authority of a person making a privacy request.",
      "Privacy requests and grievances will be handled in accordance with applicable law.",
      "Where applicable law provides a right to approach a competent data-protection authority, board, regulator, court or other lawful forum, that right remains available."
    ]
  },
  {
    "number": "24",
    "heading": "Contact Information",
    "id": "s24",
    "paragraphs": [
      "Brand: WECARE.DIGITAL",
      "Operated under the business name:",
      "WECARE.DIGITAL BHARATWORKS",
      "Business Address: The W.B.S.I.D.C. Building, Unit 1/20 81/2/7, Phears Ln Kolkata, West Bengal 700012, India",
      "Customer Care / Privacy Contact:",
      "Phone: +91 9330994400",
      "Email: one@wecare.digital",
      "For questions, requests, complaints or concerns regarding this Privacy Policy or the handling of Personal Data, please contact us using the details above.",
      "how WECARE.DIGITAL collects, uses, and protects personal data.",
      "A passionate team of solvers coming together in unexpected ways to solve the challenges and unmet needs of consumers today and tomorrow",
      "BUY GIFT CARD",
      "Any amount. Message included.",
      "THE FUTURE IS ENGAGED",
      "FOR MICROSERVICES DONE RIGHT, WECARE.DIGITAL IS YOUR GUIDING LIGHT. FAST, SECURE, AND ALWAYS SMART, WE'RE THE TECH YOU NEED TO START!",
      "INFO",
      "LEGAL STUFF",
      "CONTACT",
      "INVITE",
      "APP",
      "BHARAT STACK",
      "DECARBONIZING",
      "OPERATIONS",
      "bottom of page"
    ]
  }
];
