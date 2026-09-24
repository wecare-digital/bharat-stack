/**
 * Commerce module home — phase 7.3.
 *
 * Provider-neutral name and headings; the storefront provider is named only inside the
 * connection table, which is the authorised place for it.
 *
 * BEHIND A FLAG, AND OFF — for a different reason than Growth
 * ----------------------------------------------------------
 * Growth is off because the data is not reachable. Commerce is off because the storefront
 * **is live and in production**. The master prompt is explicit that the existing Wix site
 * must be preserved, so a new surface over a production store opens deliberately rather
 * than by being deployed. With the flag off this page links to the working catalog and
 * order pages instead of shadowing them.
 *
 * NO APPLY, AND NO PAYMENT MUTATION
 * ---------------------------------
 * Storefront APPLY tools are refused in `governance.py`. Payment capture, refund and
 * payment-configuration changes are refused outright by `01-standing-authorization.md` —
 * not gated, refused. Said on the page because an operator deciding what to ask for needs
 * to know which of these is "not yet" and which is "never from here".
 */
import React from 'react';
import Link from 'next/link';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import PageShell, { ShellTab } from '../../components/PageShell';
import IntegrationAccessTable from '../../components/IntegrationAccessTable';
import { featureFlags } from '../../config/featureFlags';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const TABS: ShellTab[] = [
  { id: 'connections', label: 'Connections' },
  { id: 'catalog', label: 'Catalog & orders' },
  { id: 'payments', label: 'Payments' },
];

/** The storefront provider. Growth owns the other seven. */
const COMMERCE_PROVIDERS = [ 'wix' ];

/** The live pages this module gathers rather than replaces. */
const EXISTING = [
  { href: '/store', label: 'Catalog', note: 'Products, brands and offers' },
  { href: '/dm/commerce', label: 'Commerce', note: 'Store operations' },
  { href: '/pay', label: 'Payments overview', note: 'Links, flows and status' },
  { href: '/pay/records', label: 'Invoice records', note: 'The billed/paid/delivered ledger' },
];

const Disabled: React.FC = () => (
  <div style={ {
    padding: 20, border: '1px solid #e5e7eb', borderLeft: '3px solid #b45309',
    borderRadius: 13, background: '#fffbeb', maxWidth: 760,
  } }>
    <div style={ { fontSize: 14, fontWeight: 600, color: '#78350f', marginBottom: 6 } }>
      The Commerce module is switched off
    </div>
    <p style={ { fontSize: 13, color: '#92400e', lineHeight: 1.6, margin: '0 0 10px' } }>
      Not because it is unfinished, but because the storefront is live. A new surface over
      a production store should be opened on purpose, and every capability it would gather
      already works at its own page — so turning this on before then would add a second
      way to do the same things rather than a better one.
    </p>
    <p style={ { fontSize: 13, color: '#92400e', lineHeight: 1.6, margin: 0 } }>
      Set
      <code style={ {
        margin: '0 4px', padding: '1px 6px', borderRadius: 4,
        background: '#fff', fontSize: 12,
      } }>NEXT_PUBLIC_ENABLE_COMMERCE_MODULE=true</code>
      to gather them here.
    </p>
  </div>
);

const CommerceBody: React.FC<PageProps> = ( { signOut, user, embedded } ) => {
  const content = (
    <PageShell
      title="Commerce"
      subtitle="Catalog, orders and payment state"
      tabs={ TABS }
      defaultTab="connections"
    >
      { ( activeTab ) => (
        <div style={ { display: 'flex', flexDirection: 'column', gap: 20 } }>
          { !featureFlags.commerceModule && <Disabled /> }

          { activeTab === 'connections' && (
            <IntegrationAccessTable
              only={ COMMERCE_PROVIDERS }
              caption={
                'The storefront connection. It reads SCOPE_UNVERIFIED because no '
                + 'authorised read has been recorded, not because the store is down — '
                + 'the live site is serving.'
              }
            />
          ) }

          { activeTab === 'catalog' && (
            <div style={ { maxWidth: 760 } }>
              <p style={ { fontSize: 13, color: '#374151', lineHeight: 1.6, marginTop: 0 } }>
                These already work. Listed rather than duplicated:
              </p>
              <div style={ {
                border: '1px solid #e5e7eb', borderRadius: 13, overflow: 'hidden',
                background: '#fff',
              } }>
                { EXISTING.map( ( item, i ) => (
                  <Link key={ item.href } href={ item.href } style={ {
                    display: 'block', padding: '13px 16px', textDecoration: 'none',
                    borderTop: i === 0 ? 'none' : '1px solid #f0f0f0',
                  } }>
                    <span style={ { fontSize: 14, fontWeight: 600, color: '#1a3a2a' } }>
                      { item.label }
                    </span>
                    <span style={ { fontSize: 12, color: '#6b7280', marginLeft: 8 } }>
                      { item.note }
                    </span>
                  </Link>
                ) ) }
              </div>
            </div>
          ) }

          { activeTab === 'payments' && (
            <div style={ { fontSize: 13, color: '#374151', lineHeight: 1.6, maxWidth: 760 } }>
              <p style={ { marginTop: 0 } }>
                Payment state is readable here and at{ ' ' }
                <Link href="/pay/records" style={ { color: '#1a3a2a' } }>Invoice records</Link>,
                which is read-only on purpose: <code>deleteInvoice</code> takes an
                <code> adjustSequence</code> flag, so one mis-click could renumber a
                statutory GST series.
              </p>
              <p style={ { margin: 0 } }>
                Capturing a payment, issuing a refund and changing payment configuration
                are <strong>refused</strong> from any assistant surface — not queued for
                confirmation. That is a standing rule, not a temporary state.
              </p>
            </div>
          ) }
        </div>
      ) }
    </PageShell>
  );

  if ( embedded ) return content;
  return (
    <Layout user={ user } onSignOut={ signOut }>
      <SEO title="Commerce" description="Catalog, orders and payment state in one place. Read-only." noindex />
      { content }
    </Layout>
  );
};

export default CommerceBody;
