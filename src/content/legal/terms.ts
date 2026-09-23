/**
 * Terms of Service — section content.
 *
 * PORTED VERBATIM from the published document at
 * https://wecaredigitalbw.wixsite.com/website-1/legal-stuff
 * by parsing that page, not by retyping it, so no clause was altered in transit.
 *
 * WHAT WAS CHANGED, and it is only ever structure:
 *   - Wix pads its layout with U+200B zero-width spaces; those are stripped.
 *   - Numbered headings became section objects with slugs, so the page can render a
 *     table of contents and support deep links. A 57-section document with no
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

export const TERMS_UPDATED = '2026-09-23';
export const TERMS_SOURCE = 'https://wecaredigitalbw.wixsite.com/website-1/legal-stuff';

export const TERMS_INTRO: string[] = [
  "These Terms of Service (\"Terms\") govern your access to and use of the websites, applications, digital platforms, products, services, features and other offerings made available under the WECARE.DIGITAL brand.",
  "WECARE.DIGITAL is a brand operated under the business name WECARE.DIGITAL BHARATWORKS (\"WECARE.DIGITAL\", \"Operator\", \"we\", \"us\" or \"our\").",
  "By accessing or using the Services you agree to these Terms. If you do not agree, do not use the Services."
];

export const TERMS_SECTIONS: LegalSection[] = [
  {
    "number": "1",
    "heading": "Definitions",
    "id": "s1",
    "paragraphs": [
      "For these Terms:",
      "\" WECARE.DIGITAL \" means the brand and trade identity through which the Services are offered.",
      "\" WECARE.DIGITAL BHARATWORKS \" means the business operating the WECARE.DIGITAL brand.",
      "\" Platform \" means any website, application, portal, digital interface, software, tool or other technology operated under or in connection with WECARE.DIGITAL.",
      "\" Services \" means all present and future products, services, facilities, functions and offerings made available through or in connection with WECARE.DIGITAL.",
      "Services may include physical products; customized or made-to-order products; marketplace services; professional and expert services; consultations and assistance services; documentation and processing services; bookings and appointments; travel and experience-related services; events and programs; dispute-resolution and facilitation services; digital products and content; memberships and subscriptions; self-service tools; technology-enabled workflows; payment and fulfilment facilitation; partner and referral programs; gift cards, credits and promotions; and other Services introduced from time to time.",
      "\" User \", \"you\" or \"your\" means any individual, organization or other person accessing or using the Services.",
      "\" Seller \" means any seller, vendor, merchant, manufacturer or other person offering goods through or in connection with the Platform.",
      "\" Service Provider \" means any professional, expert, consultant, practitioner, institution, organization, agency or other person providing services through or in connection with the Platform.",
      "\"Third-Party Provider\" means a Seller, Service Provider or another independent third party whose products or services may be accessed through WECARE.DIGITAL.",
      "\" User Content \" means reviews, ratings, photographs, text, documents, comments, messages, files or other material submitted by a User.",
      "\" Service-Specific Terms \" means additional conditions, policies, engagement terms, order terms, booking terms, cancellation conditions or other rules applying to a particular Service."
    ]
  },
  {
    "number": "2",
    "heading": "Scope of These Terms",
    "id": "s2",
    "paragraphs": [
      "These Terms apply to all Services currently offered through WECARE.DIGITAL and, unless otherwise stated, to Services introduced in the future.",
      "We may introduce, modify, expand, reorganize, replace or discontinue Services from time to time.",
      "Certain Services may be governed by additional Service-Specific Terms. These may include terms relating to professional or regulated services, Partner Up or other partner programs, referral or affiliate programs, gift cards, subscriptions, travel or experiences, digital products, events, enterprise services, customized products, documentation or processing services, or other specialized offerings.",
      "Where Service-Specific Terms apply, they form part of your agreement for that particular Service.",
      "If Service-Specific Terms conflict with these Terms, the Service-Specific Terms will apply to the relevant Service to the extent of the conflict, subject always to applicable law."
    ]
  },
  {
    "number": "3",
    "heading": "Eligibility",
    "id": "s3",
    "paragraphs": [
      "Unless a particular Service expressly states otherwise, you must be legally capable of entering into the relevant transaction.",
      "A person who is not legally capable of independently entering into a binding transaction may use an eligible Service only where permitted by law and with appropriate involvement, authorization or consent from a parent, legal guardian or other authorized person.",
      "We may request reasonable age, identity, authority or legal-capacity verification where necessary.",
      "You must not misrepresent your age, identity, authority or legal capacity."
    ]
  },
  {
    "number": "4",
    "heading": "Organizations and Business Users",
    "id": "s4",
    "paragraphs": [
      "If you access or use the Services on behalf of a company, institution, school, organization, employer, association or another entity, you represent that you are authorized to act on its behalf.",
      "Organizational or enterprise Services may be governed by a separate proposal, memorandum of understanding, order form, engagement letter, service agreement, master services agreement or other written agreement.",
      "Where such an agreement has been entered into, it will prevail over these Terms for matters specifically addressed by that agreement."
    ]
  },
  {
    "number": "5",
    "heading": "Nature of WECARE.DIGITAL Services",
    "id": "s5",
    "paragraphs": [
      "WECARE.DIGITAL operates a multi-service digital ecosystem.",
      "Our role may differ depending on the particular product, Service or transaction.",
      "Depending on the circumstances, WECARE.DIGITAL may act as a direct seller of goods; a direct provider of Services; a marketplace; a digital or technology platform; an intermediary or facilitator; a booking or appointment facilitator; a payment or transaction facilitator; a workflow or communication facilitator; a reseller or distributor; a fulfilment or administrative coordinator; or another role expressly identified for a particular Service.",
      "Where WECARE.DIGITAL is identified as the direct seller or provider, the relevant product or Service is supplied by or on behalf of the Operator.",
      "Where an independent Third-Party Provider is identified as the Seller or Service Provider, the underlying goods or services may be supplied by that Third-Party Provider.",
      "The relevant listing, checkout, booking flow, confirmation or Service-Specific Terms may identify the party supplying the product or Service and WECARE.DIGITAL's role in the transaction.",
      "Nothing in this section excludes or limits any responsibility WECARE.DIGITAL is required to assume under applicable law."
    ]
  },
  {
    "number": "6",
    "heading": "Third-Party Sellers and Service Providers",
    "id": "s6",
    "paragraphs": [
      "Third-Party Providers are responsible for the information they provide regarding their products, services, qualifications, licences, registrations, availability, prices, specifications and other relevant details.",
      "Third-Party Providers must comply with applicable laws and with the terms governing their relationship with WECARE.DIGITAL.",
      "Third-Party Providers must not provide materially false or misleading information; misrepresent qualifications or affiliations; offer unlawful or counterfeit goods; provide prohibited Services; manipulate ratings or reviews; infringe intellectual-property rights; engage in fraudulent conduct; or engage in unfair trade practices.",
      "WECARE.DIGITAL may request identity, qualification, registration, licence, business or other verification from a Third-Party Provider.",
      "We may restrict, suspend or remove a provider or listing where reasonably necessary for legal compliance, fraud prevention, Platform integrity, User safety, consumer protection or enforcement of applicable terms.",
      "Any verification undertaken by WECARE.DIGITAL does not constitute a guarantee of a provider's future conduct, quality, suitability or outcome."
    ]
  },
  {
    "number": "7",
    "heading": "Marketplace and Transaction Information",
    "id": "s7",
    "paragraphs": [
      "Where WECARE.DIGITAL operates as a marketplace or facilitator, information required for an informed purchasing decision will be displayed or made available as appropriate for the transaction and as required by applicable law.",
      "Depending on the transaction, this may include Seller or Service Provider identity and contact information; material product or Service characteristics; price and compulsory charges; payment methods; delivery or fulfilment information; cancellation, return, replacement and refund conditions; warranty or guarantee information; and grievance-redressal information.",
      "Where required by applicable law, relevant Seller or Service Provider information may also be supplied to a User after a transaction for effective grievance or dispute resolution.",
      "Where imported goods or services require importer or other origin-related disclosures, applicable information will be provided as required by law."
    ]
  },
  {
    "number": "8",
    "heading": "User Accounts",
    "id": "s8",
    "paragraphs": [
      "Certain Services may require a User account.",
      "You agree to provide accurate, current and complete information; keep your information reasonably updated; protect your account credentials; keep passwords and authentication information confidential; use your account lawfully; and inform us if you reasonably believe your account has been accessed without authorization.",
      "You may not sell, transfer, rent or knowingly permit unauthorized use of your account.",
      "We may request reasonable identity, payment, age, contact or business verification where necessary for security, compliance, fraud prevention or provision of a Service."
    ]
  },
  {
    "number": "9",
    "heading": "Orders, Bookings and Service Requests",
    "id": "s9",
    "paragraphs": [
      "All products and Services are subject to availability and the conditions displayed for the relevant offering.",
      "When you place an order, make a booking or submit a paid Service request, you are generally making an offer to purchase the relevant product or Service.",
      "An automated acknowledgment that your request has been received does not necessarily constitute final acceptance.",
      "A transaction may become confirmed when WECARE.DIGITAL or the relevant provider accepts it, a confirmation is issued, payment is successfully confirmed, or performance of the Service begins, depending on the nature of the transaction.",
      "We may decline, suspend or cancel a transaction where reasonably necessary because of unavailability, payment failure, suspected fraud, incomplete or materially inaccurate information, a material pricing or listing error, legal or regulatory restrictions, safety concerns or another legitimate reason.",
      "Where we cancel a paid transaction and a refund is legally or contractually due, the applicable refund will be processed."
    ]
  },
  {
    "number": "10",
    "heading": "Affirmative Purchase Consent",
    "id": "s10",
    "paragraphs": [
      "Paid products, Services, subscriptions or optional charges will not be treated as purchased merely because of User inactivity, a pre-selected paid option or a pre-ticked checkbox.",
      "A purchase, booking or subscription must result from an affirmative action by the User.",
      "Material mandatory charges applicable to the transaction will be disclosed before final purchase confirmation."
    ]
  },
  {
    "number": "11",
    "heading": "Prices, Taxes and Charges",
    "id": "s11",
    "paragraphs": [
      "Prices displayed through WECARE.DIGITAL may vary according to the Service.",
      "Depending on the transaction, the total amount payable may include the product price, Service fee, applicable taxes, delivery charges, booking charges, platform or facilitation charges, customization charges, processing charges or another disclosed charge.",
      "Applicable compulsory charges will be disclosed before final confirmation of the transaction.",
      "Prices and fees for future transactions may be changed from time to time.",
      "A price change will not ordinarily alter the price of an already accepted transaction unless required by law, expressly agreed by you or necessary to correct an obvious material error before performance."
    ]
  },
  {
    "number": "12",
    "heading": "Payments",
    "id": "s12",
    "paragraphs": [
      "Supported payment methods may include, where available, UPI, credit cards, debit cards, internet banking, payment gateways, approved wallets, bank transfers and other authorized payment methods.",
      "Payment transactions may be processed by independent banks, gateways or payment service providers and may also be subject to their applicable terms.",
      "WECARE.DIGITAL does not become a bank, payment bank or financial institution merely because it enables or facilitates payment for a transaction.",
      "You may use only payment methods that you are legally authorized to use.",
      "Where a payment fails, is reversed, disputed, charged back or appears potentially fraudulent, we may suspend the related transaction while the matter is investigated or resolved."
    ]
  },
  {
    "number": "13",
    "heading": "Subscriptions, Memberships and Recurring Services",
    "id": "s13",
    "paragraphs": [
      "Certain current or future Services may be provided through a subscription, membership or recurring-payment arrangement.",
      "Before enrolling, applicable information concerning price, billing interval, material features, renewal, recurring-payment arrangements and cancellation will be disclosed.",
      "Where recurring-payment authorization is required, authorization will be obtained through an applicable payment mechanism.",
      "Unless otherwise stated or required by law, cancelling a recurring Service prevents future renewals but does not automatically entitle the User to a refund for a completed or already commenced billing period.",
      "Free trials, introductory offers and promotional subscriptions may be subject to additional conditions disclosed at enrollment."
    ]
  },
  {
    "number": "14",
    "heading": "Cancellation, Service Changes, Credits and Refunds",
    "id": "s14",
    "paragraphs": [
      "Cancellation, return, replacement, rescheduling, Service-change and refund eligibility depends on the type of product or Service, the reason for the request, the stage of fulfilment, amounts already incurred and the conditions disclosed for the relevant transaction.",
      "Different conditions may apply to physical products, customized products, professional Services, consultations, appointments, documentation and processing Services, bookings, events, travel and experiences, subscriptions, digital products and other specialized Services.",
      "Applicable conditions may be displayed on the relevant Service page, order or booking form, checkout page, confirmation, invoice or applicable Service-Specific Terms.",
      "Nothing in this section limits a refund, replacement, cancellation or other remedy that must be provided under applicable law."
    ]
  },
  {
    "number": "14.1",
    "heading": "Available Resolution Options",
    "id": "s14-1",
    "paragraphs": [
      "Depending on the relevant transaction and where permitted by applicable law, an eligible cancellation or Service issue may be resolved through one or more of the following: Refund to the original payment method; WECARE.DIGITAL Gift Card or account credit; Replacement of a product; Rescheduling of a Service; Change to another available Service; Replacement booking; Adjustment against another WECARE.DIGITAL Service; or Another mutually agreed resolution.",
      "Where applicable law requires a monetary refund, a Gift Card, account credit or replacement Service will not be imposed as a substitute for that monetary refund unless the User voluntarily agrees or applicable law otherwise permits."
    ]
  },
  {
    "number": "14.2",
    "heading": "Gift Card or Account-Credit Refunds",
    "id": "s14-2",
    "paragraphs": [
      "For certain eligible cancellations, promotional transactions or Services, a refund may be made available in the form of a WECARE.DIGITAL Gift Card or account credit where this option was disclosed for the relevant transaction or is voluntarily accepted by the User.",
      "A Gift Card or account credit may be used toward eligible WECARE.DIGITAL products or Services; may be subject to Service, product or promotional restrictions disclosed when issued; may be non-transferable where stated; and may be adjusted if the original transaction is later reversed, disputed or found to involve fraud.",
      "Gift Cards and account credits are not ordinarily redeemable for cash unless expressly stated or required by applicable law.",
      "Where a transaction is expressly identified before purchase as eligible for Gift Card or account-credit refund only, that condition may apply to voluntary cancellations or changes only to the extent permitted by applicable law.",
      "It will not remove any right to another form of refund or remedy that applicable law requires."
    ]
  },
  {
    "number": "14.3",
    "heading": "Service Changes, Rescheduling and Adjustments",
    "id": "s14-3",
    "paragraphs": [
      "Where a User does not wish to continue with the originally selected Service, WECARE.DIGITAL or the relevant Service Provider may, where available, permit a change to another Service; change of appointment; rescheduling; change of Service Provider; adjustment of the amount paid toward another eligible Service; or issuance of Gift Card or account credit.",
      "If the replacement Service costs more than the original Service, the User may be required to pay the difference.",
      "If the replacement Service costs less, the difference may, depending on the applicable Service-Specific Terms and applicable law, be refunded, issued as Gift Card or account credit, adjusted against another eligible Service or otherwise resolved by agreement.",
      "Once a User voluntarily accepts and uses a replacement Service or agreed Service change, the original cancellation request may be treated as resolved to the extent appropriate."
    ]
  },
  {
    "number": "14.4",
    "heading": "Non-Refundable Charges",
    "id": "s14-4",
    "paragraphs": [
      "Certain amounts may be non-refundable where permitted by applicable law and where the relevant condition has been appropriately disclosed before or in connection with the transaction.",
      "Depending on the transaction, these may include: Work or professional time already performed; Consultation fees for a consultation already provided or commenced; Documentation, research, drafting or processing work already completed; Customization or personalization work already commenced; Government, statutory or filing fees already paid; Non-recoverable third-party charges already incurred; Confirmed booking or reservation charges that cannot be recovered from the relevant provider; Lawfully non-refundable payment-processing or transaction charges actually incurred; Delivery or logistics charges already incurred; Expedited or priority-processing charges after priority work has commenced; Activated, downloaded or consumed digital products or Services; Event, travel or experience costs already committed to a Third-Party Provider; and Another charge expressly identified as non-refundable before the relevant transaction. A fee will not be treated as non-refundable merely by labelling it as such where applicable law requires that amount to be refunded."
    ]
  },
  {
    "number": "14.5",
    "heading": "Standard Products",
    "id": "s14-5",
    "paragraphs": [
      "Return, replacement or refund eligibility for standard products will depend on the conditions disclosed for the particular product and applicable law."
    ]
  },
  {
    "number": "14.6",
    "heading": "Customized and Made-to-Order Products",
    "id": "s14-6",
    "paragraphs": [
      "Customized, personalized or made-to-order goods may become non-cancellable or non-returnable for change-of-mind reasons after production, procurement or customization has commenced where this condition was disclosed before purchase.",
      "This restriction does not eliminate rights available under applicable law relating to defective, damaged, spurious, materially misdescribed or otherwise non-conforming products."
    ]
  },
  {
    "number": "14.7",
    "heading": "Services Already Commenced",
    "id": "s14-7",
    "paragraphs": [
      "Where a Service involves professional time, research, documentation, filing, processing, administration, procurement, booking, customization or other work that has already commenced, refund eligibility may depend on the stage of completion, work already performed, third-party costs already incurred and applicable Service-Specific Terms.",
      "The refundable amount may be reduced by amounts reasonably and lawfully incurred for work already performed, non-recoverable third-party costs, statutory or government fees already paid and other disclosed costs attributable to the requested Service.",
      "Any such restriction remains subject to applicable law."
    ]
  },
  {
    "number": "14.8",
    "heading": "Defective, Deficient, Damaged or Misdescribed Goods and Services",
    "id": "s14-8",
    "paragraphs": [
      "Nothing in these Terms restricts rights available under applicable law where goods are defective, damaged or spurious; Services are deficient; products or Services materially differ from their description; material agreed specifications are not met; the relevant product or Service cannot be supplied as agreed; or another legally recognized ground for refund, replacement, return or other remedy exists."
    ]
  },
  {
    "number": "14.9",
    "heading": "Cancellation by WECARE.DIGITAL or a Provider",
    "id": "s14-9",
    "paragraphs": [
      "If an accepted transaction cannot be fulfilled and is cancelled by WECARE.DIGITAL or the relevant provider, we may, depending on the circumstances and applicable law, reschedule the Service, provide a replacement, offer an alternative Service, issue Gift Card or account credit, or process an applicable monetary refund.",
      "Where applicable law entitles the User to a monetary refund, an alternative Service, Gift Card or account credit will not replace that entitlement unless voluntarily accepted by the User or otherwise permitted by law.",
      "Where cancellation charges are imposed on a User for cancelling a confirmed transaction, WECARE.DIGITAL will comply with any corresponding obligations applicable when cancellation is initiated by WECARE.DIGITAL."
    ]
  },
  {
    "number": "14.10",
    "heading": "Refund Method",
    "id": "s14-10",
    "paragraphs": [
      "Where an eligible monetary refund is approved, it will ordinarily be processed to the original payment method unless another method is agreed with the User, the applicable Service was expressly subject to a lawful Gift Card or credit-refund condition, the original payment method cannot reasonably receive the refund, or another method is required or permitted by applicable law.",
      "Store credit, Gift Card or account credit may be offered as an option where appropriate but will not replace a monetary refund where applicable law requires a monetary refund."
    ]
  },
  {
    "number": "14.11",
    "heading": "Refund Processing and Banking Time",
    "id": "s14-11",
    "paragraphs": [
      "Once an approved monetary refund has been processed by WECARE.DIGITAL, the time required for the amount to appear in the User's bank, card, wallet or other payment account may depend on the relevant bank, card issuer, payment gateway or payment provider.",
      "Depending on the payment provider, an approved refund may take up to 30 days or one applicable billing cycle to appear after processing, unless a shorter period is required by applicable law or the relevant payment provider.",
      "This external processing period does not change the time at which WECARE.DIGITAL initiated the approved refund."
    ]
  },
  {
    "number": "14.12",
    "heading": "Chargebacks and Payment Disputes",
    "id": "s14-12",
    "paragraphs": [
      "If a User initiates a chargeback, payment dispute or reversal while a refund, Service change or other resolution is being processed, WECARE.DIGITAL may temporarily pause duplicate refund processing until the payment dispute is resolved.",
      "A User must not knowingly obtain both a refund and a successful chargeback for the same amount."
    ]
  },
  {
    "number": "15",
    "heading": "Shipping, Delivery and Fulfilment",
    "id": "s15",
    "paragraphs": [
      "Where a transaction involves physical products, delivery availability, charges and estimated timelines may vary according to the product, Seller, manufacturing or customization requirements, destination, stock availability and logistics provider.",
      "Applicable delivery information will be displayed or communicated in connection with the relevant transaction.",
      "Delivery dates are estimates unless expressly stated to be guaranteed.",
      "You are responsible for supplying a complete and accurate delivery address and reasonable information required to complete delivery.",
      "Where international shipping is offered, customs duties, import duties, taxes or other destination-specific charges may apply as disclosed for the transaction or under applicable law.",
      "If an order is lost, materially delayed, damaged in transit or otherwise not fulfilled as agreed, the matter will be dealt with under the applicable Service-Specific policy and applicable law."
    ]
  },
  {
    "number": "16",
    "heading": "Appointments, Consultations and Scheduled Services",
    "id": "s16",
    "paragraphs": [
      "Certain Services may involve appointments, consultations, sessions, events or scheduled engagements.",
      "Availability may change until the booking has been confirmed.",
      "Users are responsible for attending at the agreed time, supplying information reasonably required to provide the Service and complying with disclosed booking requirements.",
      "Late arrival, missed appointments, rescheduling and cancellation may be subject to Service-Specific Terms.",
      "If a provider cancels a scheduled Service, an appropriate rescheduling option, alternative arrangement or applicable refund may be offered.",
      "Where the identity of a particular professional is material to a booking, a different professional will not automatically be treated as an equivalent substitute without appropriate disclosure or agreement."
    ]
  },
  {
    "number": "17",
    "heading": "Professional and Regulated Services",
    "id": "s17",
    "paragraphs": [
      "Certain WECARE.DIGITAL Services may provide access to independent professionals, experts, consultants, practitioners, institutions or other specialized Service Providers.",
      "Unless expressly stated otherwise for a particular Service, making an independent provider accessible through the Platform does not mean that WECARE.DIGITAL itself performs that provider's regulated professional duties.",
      "The relevant provider remains responsible for its professional judgment, advice, qualifications, registrations, licences and professional obligations.",
      "General information available through the Platform is provided for general informational purposes and should not automatically be treated as individualized legal, medical, financial, psychological, mental-health or other regulated professional advice.",
      "No particular professional, commercial, legal, medical, personal or other outcome is guaranteed merely because a Service or professional is accessible through WECARE.DIGITAL.",
      "Where a particular Service requires additional professional disclosures, engagement conditions or Service-Specific Terms, those provisions will apply.",
      "WECARE.DIGITAL is not an emergency-response service.",
      "If you require urgent medical, safety or other emergency assistance, contact the appropriate emergency service."
    ]
  },
  {
    "number": "18",
    "heading": "Travel, Experience and Third-Party Fulfilment Services",
    "id": "s18",
    "paragraphs": [
      "Certain Services may involve travel, accommodation, transportation, experiences, attractions, appointments or other activities fulfilled partly or entirely by Third-Party Providers.",
      "Availability, cancellation requirements, identification requirements, timing, eligibility, entry conditions and other restrictions may be determined by the relevant provider.",
      "You are responsible for reviewing applicable Service-Specific information before booking.",
      "WECARE.DIGITAL does not guarantee governmental approvals, visas, admission, transportation schedules, weather conditions or outcomes controlled by independent third parties or public authorities.",
      "Nothing in this section limits rights available under applicable law."
    ]
  },
  {
    "number": "19",
    "heading": "Documentation, Processing and Assistance Services",
    "id": "s19",
    "paragraphs": [
      "Certain Services may assist Users with documentation, applications, submissions, administrative processes, research or coordination.",
      "Unless expressly stated otherwise, these Services constitute assistance and do not guarantee approval, issuance, acceptance, adjudication, governmental action, regulatory action or any other third-party decision.",
      "Users are responsible for providing accurate, complete and authentic information and documentation.",
      "A User must not knowingly ask WECARE.DIGITAL or a provider to submit false, fraudulent, misleading or fabricated information."
    ]
  },
  {
    "number": "20",
    "heading": "Digital Products and Digital Services",
    "id": "s20",
    "paragraphs": [
      "Certain Services may include downloadable content, online content, virtual Services, digital materials, software-enabled features, online programs or other electronically delivered products.",
      "Purchase of access does not transfer ownership of the underlying intellectual property unless expressly stated.",
      "You may not reproduce, redistribute, resell, commercially exploit or publicly distribute digital materials except where expressly authorized.",
      "Cancellation or refund eligibility may differ once digital access, download, activation or performance begins, subject to applicable law and any Service-Specific Terms disclosed before purchase."
    ]
  },
  {
    "number": "21",
    "heading": "Gift Cards, Credits and Stored Promotional Value",
    "id": "s21",
    "paragraphs": [
      "WECARE.DIGITAL may offer or issue gift cards, vouchers, account credits, promotional balances, refund credits or similar facilities.",
      "A Gift Card or credit may be purchased by a User; issued as part of a promotion; issued following an eligible cancellation; issued as an agreed alternative to a monetary refund; issued following a Service change or adjustment; or provided through another WECARE.DIGITAL program.",
      "Separate Gift Card or Credit Terms may govern purchase, activation, eligible Services, redemption, restrictions, transferability, refunds, cancellation and other conditions.",
      "Gift Cards, credits and promotional balances are not ordinarily redeemable for cash unless expressly stated or required under applicable law.",
      "Where a Gift Card or credit is issued instead of a monetary refund, its issuance does not remove any mandatory consumer right that cannot lawfully be waived."
    ]
  },
  {
    "number": "22",
    "heading": "Partner, Referral and Affiliate Programs",
    "id": "s22",
    "paragraphs": [
      "WECARE.DIGITAL may operate partner, referral, affiliate or commission-based programs, including programs such as Partner Up.",
      "Participation may require acceptance of separate Partner or Program Terms.",
      "Such terms may govern eligibility, activation, qualifying transactions, referral attribution, commissions, reversals, cancellations, payout thresholds, payout schedules, applicable taxes, use of WECARE.DIGITAL branding, advertising and representations, prohibited referral practices, fraud prevention, confidentiality, suspension and termination.",
      "Participation in a partner or referral program does not by itself create an employer-employee, partnership, franchise or agency relationship with WECARE.DIGITAL."
    ]
  },
  {
    "number": "23",
    "heading": "Promotions, Coupons and Offers",
    "id": "s23",
    "paragraphs": [
      "WECARE.DIGITAL may offer discounts, coupons, promotional codes, referral benefits, credits or limited-time offers.",
      "Promotions may be subject to eligibility requirements, validity periods, minimum transaction amounts, usage limits, product restrictions and additional terms.",
      "Promotional benefits may not be exchanged for cash unless expressly stated or legally required.",
      "We may cancel a promotional benefit obtained through fraud, manipulation, automated abuse, duplicate-account misuse or another material violation of promotional conditions."
    ]
  },
  {
    "number": "24",
    "heading": "Reviews, Ratings and User Content",
    "id": "s24",
    "paragraphs": [
      "You retain ownership of User Content that you lawfully own.",
      "By submitting User Content to WECARE.DIGITAL, you grant WECARE.DIGITAL BHARATWORKS a non-exclusive, worldwide, royalty-free licence to host, store, reproduce, format, display and communicate that User Content to the extent reasonably necessary to provide the relevant Service, operate the Platform, display content you intentionally submit for publication, process transactions or requests, maintain Platform security, investigate disputes or complaints and comply with applicable law.",
      "This licence does not transfer ownership of your User Content to WECARE.DIGITAL.",
      "Where identifiable User Content is proposed to be used for advertising or promotional purposes beyond the context in which it was submitted, additional authorization will be obtained where required.",
      "The licence will ordinarily end when the relevant User Content is permanently deleted, except to the extent continued retention is reasonably required for backups, record-keeping, legal obligations, dispute resolution, fraud prevention or another lawful purpose.",
      "You represent that you have the rights necessary to submit User Content.",
      "Reviews and ratings must reflect genuine experiences.",
      "You must not submit fake reviews, manipulated reviews, undisclosed paid reviews, unlawful material, defamatory content, infringing content or content under a deliberately false identity.",
      "We may moderate, restrict or remove User Content where reasonably necessary to comply with law or enforce these Terms."
    ]
  },
  {
    "number": "25",
    "heading": "Intellectual Property",
    "id": "s25",
    "paragraphs": [
      "The Platform and its original software, workflows, design, text, graphics, logos, interfaces, photographs, videos, databases and other content are owned by or licensed to WECARE.DIGITAL BHARATWORKS or the applicable rights holder.",
      "Such materials are protected by applicable intellectual-property laws.",
      "The WECARE.DIGITAL name, brand identity, logos and associated marks may not be copied, imitated or used without appropriate authorization.",
      "Your use of WECARE.DIGITAL gives you a limited, non-exclusive, non-transferable and revocable right to use the Platform for its intended purpose.",
      "No intellectual-property ownership is transferred to you merely because you access or purchase a Service.",
      "If you believe material available through WECARE.DIGITAL infringes your intellectual-property rights, contact one@wecare.digital and provide sufficient information for us to reasonably identify and review the complaint."
    ]
  },
  {
    "number": "26",
    "heading": "Acceptable Use",
    "id": "s26",
    "paragraphs": [
      "You may use WECARE.DIGITAL only for lawful purposes.",
      "You must not commit or facilitate fraud; impersonate another person; intentionally misrepresent your affiliation; threaten, harass or abuse another person; infringe intellectual-property or privacy rights; introduce malware or harmful software; interfere with Platform security; attempt unauthorized system or account access; circumvent technical restrictions; harvest personal information without authorization; send unlawful spam or unsolicited communications; manipulate reviews or ratings; exploit promotions fraudulently; materially disrupt Platform functionality; use automated systems in an abusive manner; list or request unlawful goods or Services; or otherwise use the Platform in violation of applicable law.",
      "We may investigate suspected violations and take proportionate action where necessary."
    ]
  },
  {
    "number": "27",
    "heading": "Third-Party Websites, Tools and Integrations",
    "id": "s27",
    "paragraphs": [
      "The Services may contain links to or rely upon independent third-party websites, payment processors, logistics providers, authentication systems, maps, communication platforms, cloud infrastructure, software or other services.",
      "Third-party services may be governed by their own terms and privacy policies.",
      "We do not control independent third-party systems and cannot guarantee their uninterrupted availability.",
      "Nothing in this section excludes liability that WECARE.DIGITAL is required to assume under applicable law."
    ]
  },
  {
    "number": "28",
    "heading": "Privacy and Personal Data",
    "id": "s28",
    "paragraphs": [
      "Personal data collected through WECARE.DIGITAL will be handled in accordance with our Privacy Policy at: /privacy/ and applicable data-protection law.",
      "The Privacy Policy forms a separate legal document and should be read together with these Terms.",
      "Use of the Platform does not constitute unrestricted or blanket consent to every possible form of personal-data processing.",
      "Where consent or another specific authorization is legally required for particular processing, an appropriate mechanism will be used.",
      "Depending on the Service, personal information may be processed for purposes including account creation and administration, order fulfilment, booking management, payment processing, communication, customer support, identity verification, fraud prevention, Platform security, grievance resolution, legal compliance and provision of requested Services."
    ]
  },
  {
    "number": "29",
    "heading": "Electronic and Service Communications",
    "id": "s29",
    "paragraphs": [
      "By using the Services, you acknowledge that transactional and operational communications may be provided electronically where permitted.",
      "These may include account notices, order confirmations, payment confirmations, booking confirmations, appointment reminders, delivery updates, security alerts, grievance correspondence, policy notices and other Service-related communications.",
      "Such communications may be provided through email, SMS, telephone, messaging services, Platform notifications or other contact methods supplied by you.",
      "Marketing communications will be managed separately and will include consent or opt-out mechanisms where required by applicable law."
    ]
  },
  {
    "number": "30",
    "heading": "Availability and Modification of Services",
    "id": "s30",
    "paragraphs": [
      "We may maintain, update, improve, modify, replace, suspend or discontinue functionality from time to time.",
      "Temporary interruptions may occur due to maintenance, technical failures, network disruption, third-party infrastructure, cybersecurity incidents, regulatory requirements, logistics failures or circumstances beyond reasonable control.",
      "Where a paid Service is materially discontinued before it has been supplied, we will provide any remedy required under applicable law or applicable Service-Specific Terms."
    ]
  },
  {
    "number": "31",
    "heading": "Disclaimer of Warranties",
    "id": "s31",
    "paragraphs": [
      "To the maximum extent permitted by applicable law, the Platform is provided on an \"as available\" basis.",
      "We do not guarantee that every feature or Service will always be uninterrupted, continuously available, completely error-free or suitable for every User's individual purpose.",
      "We do not guarantee a particular business, professional, legal, medical, personal, travel, financial or other outcome merely because a product, Service or provider is accessible through WECARE.DIGITAL.",
      "Nothing in these Terms excludes a statutory warranty, obligation, consumer right or remedy that cannot lawfully be excluded."
    ]
  },
  {
    "number": "32",
    "heading": "Limitation of Liability",
    "id": "s32",
    "paragraphs": [
      "Nothing in these Terms excludes or limits liability where exclusion or limitation is prohibited by applicable law.",
      "Subject to that principle and to the maximum extent permitted by law, neither party will ordinarily be responsible to the other for indirect, incidental, special or consequential losses that were not reasonably foreseeable.",
      "Where WECARE.DIGITAL's contractual liability may lawfully be limited, its aggregate contractual liability arising directly from a particular paid transaction will ordinarily not exceed the amount paid to WECARE.DIGITAL for the product or Service giving rise to the claim.",
      "This limitation does not apply where liability cannot legally be restricted, including liability arising from fraud, wilful misconduct or another matter for which applicable law prohibits limitation.",
      "Nothing in this section restricts mandatory consumer rights."
    ]
  },
  {
    "number": "33",
    "heading": "User Responsibility and Indemnity",
    "id": "s33",
    "paragraphs": [
      "To the extent permitted by applicable law, you are responsible for losses, claims or reasonable costs directly arising from your unlawful use of the Services, your material breach of these Terms, your infringement of another person's rights or unlawful User Content submitted by you.",
      "This section does not require a consumer to indemnify WECARE.DIGITAL for losses caused by WECARE.DIGITAL's own unlawful conduct or for liability that cannot lawfully be transferred."
    ]
  },
  {
    "number": "34",
    "heading": "Fraud Prevention and Platform Security",
    "id": "s34",
    "paragraphs": [
      "We may use reasonable technical, operational and manual measures to identify and prevent unauthorized transactions, account takeover, fraudulent payments, promotion abuse, identity misuse, suspicious activity and other security risks.",
      "Where reasonably necessary, a transaction or account may be temporarily restricted while verification is completed.",
      "We may cooperate with banks, payment providers, regulators, law-enforcement authorities or other competent authorities where permitted or required by law."
    ]
  },
  {
    "number": "35",
    "heading": "Suspension and Termination",
    "id": "s35",
    "paragraphs": [
      "You may stop using the Services at any time.",
      "Where available, you may request account closure through the applicable account or customer-support process.",
      "We may restrict, suspend or terminate access where reasonably necessary due to suspected fraud, security risk, unlawful activity, material violation of these Terms, abuse of Users or providers, repeated payment failure, misuse of the Platform or another legitimate reason.",
      "Where appropriate and legally required, we may provide notice or an opportunity to address the relevant issue.",
      "Termination does not eliminate rights or obligations that arose before termination, including refund rights, payment obligations, dispute rights, confidentiality obligations, intellectual-property provisions or provisions intended by their nature to survive termination."
    ]
  },
  {
    "number": "36",
    "heading": "Force Majeure",
    "id": "s36",
    "paragraphs": [
      "Neither party will be responsible for a failure or delay caused by circumstances beyond its reasonable control to the extent such circumstances prevent performance.",
      "Examples may include natural disasters, severe weather, epidemic or public-health restrictions, war, civil disturbance, government action, widespread utility or telecommunications failures, labour disruption, transportation interruption, large-scale cyber incidents or similar circumstances outside reasonable control.",
      "Nothing in this section removes a cancellation, refund or other right that applicable law requires to remain available."
    ]
  },
  {
    "number": "37",
    "heading": "Customer Care and Grievance Redressal",
    "id": "s37",
    "paragraphs": [
      "Users may contact WECARE.DIGITAL regarding products, orders, bookings, payments, refunds, Sellers, Service Providers, account concerns, Platform concerns, privacy concerns or other grievances.",
      "Customer Care & Grievance Contact",
      "WECARE.DIGITAL Customer Grievance Desk",
      "Business: WECARE.DIGITAL BHARATWORKS",
      "Email: one@wecare.digital",
      "Phone: +91 9330994400",
      "Address: The W.B.S.I.D.C. Building, Unit 1/20 81/2/7, Phears Ln Kolkata, West Bengal 700012, India",
      "Formal complaints submitted through the designated grievance channel will be recorded and, where applicable, assigned a ticket or reference number for tracking.",
      "Where applicable law prescribes a particular grievance process, acknowledgement period, resolution period or escalation process, WECARE.DIGITAL will handle the grievance in accordance with those requirements.",
      "Nothing in this grievance procedure prevents a User from exercising any right available before an appropriate Consumer Commission, regulator, statutory authority, court or other lawful dispute-resolution forum."
    ]
  },
  {
    "number": "38",
    "heading": "Changes to These Terms",
    "id": "s38",
    "paragraphs": [
      "We may update these Terms where reasonably necessary to reflect changes in Services, business operations, technology, Platform functionality, security practices, applicable laws or regulatory requirements.",
      "Where required by applicable law or where a change materially affects User rights, appropriate notice will be provided.",
      "Changes will ordinarily operate prospectively.",
      "Continued use of affected Services after revised Terms become applicable may constitute acceptance only to the extent permitted by applicable law.",
      "Where fresh affirmative acceptance is legally required, we may request it.",
      "A new or materially different Service may also be subject to Service-Specific Terms."
    ]
  },
  {
    "number": "39",
    "heading": "Governing Law and Dispute Resolution",
    "id": "s39",
    "paragraphs": [
      "These Terms are governed by the laws of India.",
      "Users are encouraged to first contact WECARE.DIGITAL Customer Care or the WECARE.DIGITAL Customer Grievance Desk to allow the concern to be reviewed and, where possible, resolved.",
      "Nothing in these Terms restricts a consumer from approaching a Consumer Commission, regulator, statutory authority, court or another forum available under applicable law.",
      "For disputes that are not subject to a mandatory statutory or consumer forum, the courts of competent jurisdiction in Kolkata, West Bengal will have jurisdiction, subject to applicable law."
    ]
  },
  {
    "number": "40",
    "heading": "Severability",
    "id": "s40",
    "paragraphs": [
      "If a provision of these Terms is held to be invalid, unlawful or unenforceable, that provision will be interpreted or limited to the minimum extent necessary.",
      "The remaining provisions will continue to remain effective."
    ]
  },
  {
    "number": "41",
    "heading": "No Waiver",
    "id": "s41",
    "paragraphs": [
      "A failure or delay by WECARE.DIGITAL in enforcing any provision or exercising any right does not constitute a waiver of that provision or right.",
      "A waiver applies only to the specific circumstances for which it is given."
    ]
  },
  {
    "number": "42",
    "heading": "Assignment",
    "id": "s42",
    "paragraphs": [
      "You may not transfer your account or contractual rights under these Terms in a manner that materially affects the Services without our prior consent.",
      "WECARE.DIGITAL BHARATWORKS may transfer its rights or obligations in connection with a genuine business restructuring, merger, acquisition, sale, reorganization or transfer of the WECARE.DIGITAL operations, subject to applicable law and without reducing mandatory User or consumer rights."
    ]
  },
  {
    "number": "43",
    "heading": "Relationship of the Parties",
    "id": "s43",
    "paragraphs": [
      "Nothing in these Terms creates an employment relationship, partnership, franchise, fiduciary relationship or joint venture between a User and WECARE.DIGITAL BHARATWORKS.",
      "A Third-Party Provider does not become an employee of WECARE.DIGITAL merely because its products or Services are accessible through the Platform.",
      "Separate contractual arrangements may govern relationships between WECARE.DIGITAL and individual Sellers, Service Providers, partners or affiliates."
    ]
  },
  {
    "number": "44",
    "heading": "Entire Agreement",
    "id": "s44",
    "paragraphs": [
      "These Terms, together with the Privacy Policy at /privacy/, applicable Service-Specific Terms, order or booking information, applicable cancellation or refund conditions, applicable delivery conditions and any other policy expressly incorporated into a particular transaction form the agreement applicable to your use of the relevant Services.",
      "Where a separately signed agreement, memorandum of understanding, engagement agreement, enterprise agreement or order form covers the same subject matter, that agreement will prevail for matters specifically addressed by it."
    ]
  },
  {
    "number": "45",
    "heading": "Contact Information",
    "id": "s45",
    "paragraphs": [
      "Brand: WECARE.DIGITAL",
      "Operated under the business name:",
      "WECARE.DIGITAL BHARATWORKS",
      "Business Address: The W.B.S.I.D.C. Building, Unit 1/20 81/2/7, Phears Ln Kolkata, West Bengal 700012, India",
      "Customer Care:",
      "Phone: +91 9330994400",
      "Email: one@wecare.digital",
      "For questions, complaints or concerns regarding these Terms or the Services, please contact us using the details above.",
      "Privacy Policy",
      "terms, refunds, shipping, and policies for WECARE.DIGITAL services.",
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
