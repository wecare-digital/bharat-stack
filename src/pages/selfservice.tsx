/**
 * /selfservice - retired, redirects to /contact/.
 *
 * 99 references to this address are still live in the repo, and the important ones are not
 * links on a page: amplify/functions/ai/ai-generate-response/handler.py uses
 * https://wecare.digital/selfservice as the button URL for "Start Now", "Book Slot",
 * "Upload Now", "Get Support" and "Self Service" on outbound WhatsApp messages, and it is
 * also the footer text on those templates. Every one of those already sitting in a
 * customer's chat history points here.
 *
 * /contact/ is the correct destination, not a generic fallback: PUBLIC_PAGE_META describes
 * it as "Submit, amend or track a request, drop documents, or leave a review", which is
 * precisely the set of things the retired self-service page did.
 *
 * See src/components/RetiredUrl.tsx for the redirect mechanics and why this is not a 301.
 */

import RetiredUrl from '../components/RetiredUrl';

export default function SelfService() {
  return <RetiredUrl to="/contact/" was="Self-service" />;
}
