/**
 * Service Operations Hub — WECARE.DIGITAL
 *
 * One PageShell hub for the WhatsApp-Flow-driven service cluster (all /wa-business/*):
 * Orders (orchestrator) + Service Requests + Bookings + Drop Docs + Enterprise + Reviews + FAQ.
 * Mirrors the WhatsApp Settings hub pattern. Each tab embeds an existing page
 * (via its `embedded` prop) so those routes still work standalone too.
 */
import React, { Suspense } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import PageShell, { ShellTab } from '../../../components/PageShell';

import OrdersPage from '../orders';
import AppointmentsPage from '../appointments';
import RxSlotsPage from '../rx-slots';
import DocumentsPage from '../documents';
import EnterprisePage from '../enterprise';
import ReviewsPage from '../reviews';
import FaqPage from '../faq';
import SubmitRequestPage from '../../service/submit-request';
import TrackRequestPage from '../../service/track-request';
import AmendRequestPage from '../../service/amend-request';

interface PageProps { signOut?: () => void; user?: any; }

const TABS: ShellTab[] = [
    { id: 'orders', label: 'Orders' },
    { id: 'submit', label: 'Submit Request', divider: true },
    { id: 'track', label: 'Track Request' },
    { id: 'amend', label: 'Amend Request' },
    { id: 'appointments', label: 'Appointments', divider: true },
    { id: 'rx-slots', label: 'RX Slots' },
    { id: 'documents', label: 'Drop Docs', divider: true },
    { id: 'enterprise', label: 'Enterprise' },
    { id: 'reviews', label: 'Reviews' },
    { id: 'faq', label: 'FAQ' },
];

const ServiceOpsPage: React.FC<PageProps> = ( { signOut, user } ) => (
    <Layout user={ user } onSignOut={ signOut }>
        <SEO title="Service Operations | WECARE.DIGITAL" description="Orders, service requests, bookings, documents, enterprise, reviews & FAQ" noindex={ true } />
        <PageShell
            title="Service Operations"
            subtitle="Orders, requests, bookings, documents & support — all WhatsApp-Flow driven"
            tabs={ TABS }
            defaultTab="orders"
        >
            { ( activeTab ) => (
                <Suspense fallback={ <div style={ { padding: 40, textAlign: 'center' } }>Loading…</div> }>
                    { activeTab === 'orders' && <OrdersPage signOut={ signOut } user={ user } embedded /> }
                    { activeTab === 'submit' && <SubmitRequestPage signOut={ signOut } user={ user } embedded /> }
                    { activeTab === 'track' && <TrackRequestPage signOut={ signOut } user={ user } embedded /> }
                    { activeTab === 'amend' && <AmendRequestPage signOut={ signOut } user={ user } embedded /> }
                    { activeTab === 'appointments' && <AppointmentsPage signOut={ signOut } user={ user } embedded /> }
                    { activeTab === 'rx-slots' && <RxSlotsPage signOut={ signOut } user={ user } embedded /> }
                    { activeTab === 'documents' && <DocumentsPage signOut={ signOut } user={ user } embedded /> }
                    { activeTab === 'enterprise' && <EnterprisePage signOut={ signOut } user={ user } embedded /> }
                    { activeTab === 'reviews' && <ReviewsPage signOut={ signOut } user={ user } embedded /> }
                    { activeTab === 'faq' && <FaqPage signOut={ signOut } user={ user } embedded /> }
                </Suspense>
            ) }
        </PageShell>
    </Layout>
);

export default ServiceOpsPage;
