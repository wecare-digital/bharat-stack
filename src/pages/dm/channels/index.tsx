/**
 * Channels — unified home for every messaging channel + cross-channel tools.
 *
 * A clean launcher (not nested mega-tabs): one card per channel with status + quick
 * links into that channel's own tools, plus a "cross-channel" row for the capabilities
 * that span all channels (Unified Inbox, Delivery Report, Broadcast, Contacts…).
 */
import React from 'react';
import Link from 'next/link';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import SEO from '../../../components/SEO';
import { colors } from '../../../lib/design-tokens';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

interface ChannelCard {
    key: string;
    label: string;
    desc: string;
    fg: string;
    bg: string;
    links: { label: string; href: string }[];
}

const CHANNELS: ChannelCard[] = [
    {
        key: 'whatsapp', label: 'WhatsApp', desc: 'Conversations, templates, flows, calling', fg: '#15803d', bg: '#f0fdf4',
        links: [ { label: 'Inbox', href: '/dm/whatsapp' }, { label: 'Settings', href: '/dm/whatsapp/settings' }, { label: 'Service Ops', href: '/dm/service-ops' } ],
    },
    {
        key: 'sms', label: 'SMS', desc: 'AWS Pinpoint + Airtel IQ', fg: '#1d4ed8', bg: '#eff6ff',
        links: [ { label: 'Open', href: '/dm/sms' }, { label: 'Logs', href: '/dm/logs' } ],
    },
    {
        key: 'rcs', label: 'RCS', desc: 'Rich cards & carousels (Sinch)', fg: '#0f766e', bg: '#f0fdfa',
        links: [ { label: 'Open', href: '/dm/rcs' }, { label: 'Send', href: '/dm/rcs/send' } ],
    },
    {
        key: 'email', label: 'Email', desc: 'Transactional & campaigns (SES)', fg: '#b45309', bg: '#fffbeb',
        links: [ { label: 'Open', href: '/dm/ses' }, { label: 'Inbox', href: '/dm/ses/inbox' } ],
    },
    {
        key: 'voice', label: 'Voice', desc: 'Calls, OBD, C2C, CDR', fg: '#6d28d9', bg: '#f5f3ff',
        links: [ { label: 'Outbound', href: '/dm/voice' }, { label: 'Voice In', href: '/dm/voice-in' } ],
    },
    {
        key: 'push', label: 'Push', desc: 'Web & mobile push notifications', fg: '#be185d', bg: '#fdf2f8',
        links: [ { label: 'Open', href: '/dm/push' } ],
    },
];

const CROSS: { label: string; desc: string; href: string }[] = [
    { label: 'Unified Inbox', desc: 'All conversations, one thread per contact', href: '/dm/inbox' },
    { label: 'Broadcast', desc: 'Send a campaign across any channel', href: '/dm/broadcast' },
    { label: 'Content Library', desc: 'Templates & content across channels', href: '/dm/content' },
    { label: 'Calls', desc: 'Unified call log — AWS, Airtel, WhatsApp', href: '/dm/calls' },
    { label: 'Contact 360', desc: 'Everything about a contact in one feed', href: '/dm/contact-360' },
    { label: 'Scheduled', desc: 'Upcoming scheduled sends', href: '/dm/scheduled' },
    { label: 'Analytics', desc: 'Cross-channel volume & delivery', href: '/dm/analytics' },
    { label: 'Automation', desc: 'Cross-channel auto-reply rules', href: '/dm/automation' },
    { label: 'Cost & Usage', desc: 'Estimated per-channel spend', href: '/dm/cost' },
    { label: 'Channel Settings', desc: 'Consent, sender identities, config', href: '/dm/settings' },
    { label: 'Delivery Report', desc: 'Cross-channel logs, status & failures', href: '/dm/logs' },
    { label: 'Contacts', desc: 'One contact book across all channels', href: '/contacts' },
    { label: 'Service Operations', desc: 'WhatsApp-Flow orders, bookings, docs', href: '/dm/service-ops' },
];

const ChannelsHub: React.FC<PageProps> = ( { signOut, user, embedded } ) => {
    const content = (
        <>
            <div className="ch-wrap">
                <PageHeader title="Channels" subtitle="Every messaging channel + the tools that span them" icon="message" />

                <div className="ch-section-label">Channels</div>
                <div className="ch-grid">
                    { CHANNELS.map( c => (
                        <div key={ c.key } className="ch-card">
                            <div className="ch-card-head">
                                <span className="ch-pill" style={ { color: c.fg, background: c.bg } }>{ c.label }</span>
                            </div>
                            <p className="ch-desc">{ c.desc }</p>
                            <div className="ch-links">
                                { c.links.map( l => (
                                    <Link key={ l.href + l.label } href={ l.href } className="ch-link">{ l.label } →</Link>
                                ) ) }
                            </div>
                        </div>
                    ) ) }
                </div>

                <div className="ch-section-label">Cross-channel</div>
                <div className="ch-grid">
                    { CROSS.map( x => (
                        <Link key={ x.href } href={ x.href } className="ch-card ch-card-link">
                            <span className="ch-x-label">{ x.label }</span>
                            <p className="ch-desc">{ x.desc }</p>
                        </Link>
                    ) ) }
                </div>
            </div>

            <style jsx>{ `
                .ch-wrap { padding: 20px; max-width: 1100px; margin: 0 auto; }
                .ch-section-label { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: ${colors.textMuted}; margin: 22px 0 10px; }
                .ch-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }
                .ch-card { border: 1px solid ${colors.border}; border-radius: 14px; padding: 16px; background: #fff; display: flex; flex-direction: column; gap: 8px; }
                .ch-card-link { text-decoration: none; transition: box-shadow .15s ease, border-color .15s ease; }
                .ch-card-link:hover { border-color: ${colors.primary}; box-shadow: ${'0 4px 12px rgba(0,0,0,0.08)'}; }
                .ch-pill { font-size: 12px; font-weight: 700; padding: 4px 11px; border-radius: 9999px; }
                .ch-x-label { font-size: 15px; font-weight: 700; color: ${colors.text}; }
                .ch-desc { font-size: 13px; color: ${colors.textSecondary}; margin: 0; }
                .ch-links { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 4px; }
                .ch-link { font-size: 13px; font-weight: 600; color: ${colors.primary}; text-decoration: none; }
                .ch-link:hover { color: ${colors.primaryHover}; text-decoration: underline; }
            ` }</style>
        </>
    );

    if ( embedded ) return content;
    return (
        <Layout user={ user } onSignOut={ signOut }>
            <SEO title="Channels | WECARE.DIGITAL" description="Unified home for all messaging channels" noindex={ true } />
            { content }
        </Layout>
    );
};

export default ChannelsHub;
