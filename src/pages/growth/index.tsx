/**
 * Growth module home — phase 7.3.
 *
 * Provider-neutral by name and by heading, per the master prompt: "Use provider-neutral
 * page names and confine exact provider labels/IDs to authorized connection details."
 * So the page is "Growth", its sections are "Search presence" and "Advertising", and the
 * provider names appear only inside the connection table, which is the authorised place
 * for them.
 *
 * BEHIND A FLAG, AND OFF
 * ----------------------
 * `featureFlags.growthModule` is false unless an env var says otherwise. With it off this
 * route renders a short, honest explanation instead of a shell of empty panels — because
 * the empty panels are the failure mode this project keeps finding. The old Tasks page
 * promised six features with nothing behind five of them; a Growth page showing zeroed
 * ad metrics would be the same lie with a different subject.
 *
 * WHAT IS REAL HERE TODAY
 * -----------------------
 * The connection state is real: it comes from `lambda_utils/integrations/registry.py` via
 * a generated snapshot, and it reports that **7 of 8 providers are SCOPE_UNVERIFIED and
 * one has no credential at all**. That is the useful content at this stage — not a
 * dashboard of numbers we cannot fetch, but a precise list of what is not connected and
 * the exact unblock for each. Every one of those unblocks is an owner action; none is
 * code.
 *
 * AI MAY READ AND PLAN, NOT APPLY
 * -------------------------------
 * Stated on the page, because an operator reading it needs to know. All growth APPLY
 * tools are refused in `governance.py` and no value on this page can change that.
 */
import React from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import PageShell, { ShellTab } from '../../components/PageShell';
import IntegrationAccessTable from '../../components/IntegrationAccessTable';
import { featureFlags } from '../../config/featureFlags';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const TABS: ShellTab[] = [
  { id: 'connections', label: 'Connections' },
  { id: 'search', label: 'Search presence' },
  { id: 'advertising', label: 'Advertising' },
];

/** Providers that belong to Growth. Commerce gets Wix; these are the rest. */
const GROWTH_PROVIDERS = [
  'search_console', 'business_profile', 'ga4', 'bing_webmaster',
  'google_ads', 'meta_ads', 'play_reporting',
];

const Disabled: React.FC = () => (
  <div style={ {
    padding: 20, border: '1px solid #e5e7eb', borderLeft: '3px solid #b45309',
    borderRadius: 13, background: '#fffbeb', maxWidth: 760,
  } }>
    <div style={ { fontSize: 14, fontWeight: 600, color: '#78350f', marginBottom: 6 } }>
      The Growth module is switched off
    </div>
    <p style={ { fontSize: 13, color: '#92400e', lineHeight: 1.6, margin: '0 0 10px' } }>
      It stays off until provider access is granted. Seven of the eight data providers
      have a stored credential but no recorded authorised read, and one has no credential
      at all — so with the module on you would be looking at panels that cannot fetch
      anything. An empty chart is indistinguishable from a chart showing zero, and that
      ambiguity is worse than an absence stated plainly.
    </p>
    <p style={ { fontSize: 13, color: '#92400e', lineHeight: 1.6, margin: 0 } }>
      The connection state below is real and worth reading now: it lists exactly what is
      unconnected and the precise unblock for each. Set
      <code style={ {
        margin: '0 4px', padding: '1px 6px', borderRadius: 4,
        background: '#fff', fontSize: 12,
      } }>NEXT_PUBLIC_ENABLE_GROWTH_MODULE=true</code>
      once a provider reports Connected.
    </p>
  </div>
);

const GrowthBody: React.FC<PageProps> = ( { signOut, user, embedded } ) => {
  const content = (
    <PageShell
      title="Growth"
      subtitle="Search presence, advertising and attribution — read-only"
      tabs={ TABS }
      defaultTab="connections"
    >
      { ( activeTab ) => (
        <div style={ { display: 'flex', flexDirection: 'column', gap: 20 } }>
          { !featureFlags.growthModule && <Disabled /> }

          { activeTab === 'connections' && (
            <IntegrationAccessTable
              only={ GROWTH_PROVIDERS }
              caption={
                'Whether we can read from each provider, in three states. A stored '
                + 'credential is not a granted scope — that distinction has already cost '
                + 'this project a blocked contacts import, where the OAuth client worked '
                + 'and the scope was never added to the consent screen.'
              }
            />
          ) }

          { activeTab === 'search' && (
            <div style={ { fontSize: 13, color: '#374151', lineHeight: 1.6, maxWidth: 760 } }>
              <p style={ { marginTop: 0 } }>
                Search presence work lives under the gear today: pages, schema, sitemaps,
                issues and tracking are all built and in use. This tab exists to bring
                the read-only <em>reporting</em> side of it here once a search provider
                reports Connected.
              </p>
              <p style={ { margin: 0 } }>
                Nothing is duplicated in the meantime. Pointing you at the working pages
                is more useful than a second copy of them with no data behind it.
              </p>
            </div>
          ) }

          { activeTab === 'advertising' && (
            <div style={ { fontSize: 13, color: '#374151', lineHeight: 1.6, maxWidth: 760 } }>
              <p style={ { marginTop: 0 } }>
                Advertising is <strong>read and plan only</strong>. The assistant may
                summarise performance and draft a change; it cannot apply one. Activating
                spend, changing a budget or a bid, and publishing an ad are all refused
                outright rather than gated behind a confirmation.
              </p>
              <p style={ { margin: 0 } }>
                That is a deliberate refusal, not a missing feature. It stays that way
                while the plan/approve/apply path is new.
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
      <SEO title="Growth" description="Search presence, advertising and attribution read state. Read-only." noindex />
      { content }
    </Layout>
  );
};

export default GrowthBody;
