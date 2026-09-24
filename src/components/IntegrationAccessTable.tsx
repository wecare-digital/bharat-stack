/**
 * The integration registry, rendered as it actually is.
 *
 * Shared by the Growth and Commerce module homes. Both need the same answer — "can we
 * read from this provider, and if not, what exactly unblocks it" — and the registry is
 * the only place that knows.
 *
 * THREE STATES, NOT A TICK
 * ------------------------
 * `registry.py` is emphatic about this and it is the reason this component does not
 * render a boolean: "a credential existing is not a scope being granted. That has
 * already cost this project once: the Google OAuth client exists and works, and
 * `contacts.readonly` was never added to the consent screen, so the identity import is
 * blocked on a provider setting rather than on code."
 *
 *   CREDENTIAL_ABSENT   nothing stored. Nothing to try.
 *   SCOPE_UNVERIFIED    a credential exists; no authorised read has been recorded.
 *   VERIFIED            a real read succeeded and was recorded.
 *
 * Nothing is VERIFIED today, and this table says so rather than showing seven green
 * ticks for seven providers nobody has read from.
 *
 * FRESHNESS IS SHOWN
 * ------------------
 * The snapshot's `generatedAt` is rendered, because the credential-existence half is
 * frozen at generation time and the registry's own rule is that an age rendered without
 * its timestamp is how a dashboard shows last week as today.
 */
import React from 'react';
import inventory from '../content/integration-registry.json';

/** Colour by state. Amber for "not proven", never the success green. */
const STATE_STYLE: Record<string, { label: string; fg: string; bg: string }> = {
  VERIFIED: { label: 'Connected', fg: '#15803d', bg: '#f0fdf4' },
  SCOPE_UNVERIFIED: { label: 'Not verified', fg: '#b45309', bg: '#fffbeb' },
  CREDENTIAL_ABSENT: { label: 'Not connected', fg: '#6b7280', bg: '#f9fafb' },
};

interface Provider {
  key: string;
  displayName?: string;
  owner?: string;
  access?: string;
  adapterBuilt?: boolean;
  maxAgeSeconds?: number;
  unblock?: string | null;
  notes?: string | null;
}

interface Props {
  /** Show only these registry keys. Omit for all eight. */
  only?: string[];
  caption?: string;
}

const IntegrationAccessTable: React.FC<Props> = ( { only, caption } ) => {
  const all = ( inventory.providers as Provider[] );
  const providers = only ? all.filter( ( p ) => only.includes( p.key ) ) : all;

  if ( providers.length === 0 ) {
    return <p style={ { fontSize: 13, color: '#6b7280' } }>No integrations in scope here.</p>;
  }

  return (
    <div>
      { caption && (
        <p style={ { fontSize: 13, color: '#6b7280', margin: '0 0 10px', lineHeight: 1.5 } }>
          { caption }
        </p>
      ) }

      <div style={ {
        border: '1px solid #e5e7eb', borderRadius: 13, overflow: 'hidden',
        background: '#fff',
      } }>
        { providers.map( ( p, i ) => {
          const state = STATE_STYLE[ p.access ?? '' ] ?? STATE_STYLE.CREDENTIAL_ABSENT;
          return (
            <div key={ p.key } style={ {
              padding: '14px 16px',
              borderTop: i === 0 ? 'none' : '1px solid #f0f0f0',
            } }>
              <div style={ {
                display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
              } }>
                <span style={ { fontSize: 14, fontWeight: 600, color: '#1a1a1a' } }>
                  { p.displayName ?? p.key }
                </span>
                <span style={ {
                  fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
                  color: state.fg, background: state.bg,
                } }>
                  { state.label }
                </span>
                { p.adapterBuilt === false && (
                  <span style={ {
                    fontSize: 11, padding: '2px 8px', borderRadius: 10,
                    color: '#6b7280', background: '#f9fafb',
                  } }>
                    No adapter built
                  </span>
                ) }
              </div>

              { p.owner && (
                <div style={ { fontSize: 12, color: '#6b7280', marginTop: 4 } }>
                  Account: { p.owner }
                </div>
              ) }

              {/* The unblock is the useful half. A state without the next action is a
                  status light nobody can act on. */}
              { p.unblock && (
                <div style={ {
                  fontSize: 12, color: '#374151', marginTop: 6, lineHeight: 1.5,
                  paddingLeft: 10, borderLeft: '3px solid #d1f470',
                } }>
                  { p.unblock }
                </div>
              ) }

              { p.notes && (
                <div style={ { fontSize: 12, color: '#9ca3af', marginTop: 5 } }>
                  { p.notes }
                </div>
              ) }
            </div>
          );
        } ) }
      </div>

      <p style={ { fontSize: 11, color: '#9ca3af', marginTop: 10, lineHeight: 1.5 } }>
        Read state as of { new Date( inventory.generatedAt ).toLocaleString() }.
        Credential presence is checked when this snapshot is generated, so regenerate it
        after changing a credential or a scope. Nothing is marked Connected until a real
        authorised read has been recorded.
      </p>
    </div>
  );
};

export default IntegrationAccessTable;
