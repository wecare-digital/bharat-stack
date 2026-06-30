/**
 * WABA Business Usernames Manager
 * Shows the LIVE business username for each WhatsApp number (from Meta), with its status:
 *   WABA 1 (WECARE.DIGITAL) → @wecare.digital
 *   WABA 2 (Manish Agarwal) → @manishagarwal
 * Uses Meta Graph API via the whatsapp-business-api Lambda.
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import Button from '../../components/ui/Button';
import Spinner from '../../components/ui/Spinner';
import { useToastContext } from '../../contexts/ToastContext';
import * as api from '../../api/client';
import { WHATSAPP_PHONES } from '../../config/constants';

interface PageProps { signOut?: () => void; user?: any; }

interface PhoneUsernameState {
    loading: boolean;
    username?: string;
    status?: string;
    error?: string;
}

// One fixed username per number — the only value that can be claimed.
const PHONES = [
    {
        key: 'primary',
        label: 'WABA 1 — WECARE.DIGITAL',
        phoneId: WHATSAPP_PHONES.primary.metaPhoneId,
        display: WHATSAPP_PHONES.primary.display,
        wabaId: WHATSAPP_PHONES.primary.wabaId,
        fixedUsername: WHATSAPP_PHONES.primary.username, // 'wecaredigital'
    },
    {
        key: 'secondary',
        label: 'WABA 2 — Manish Agarwal',
        phoneId: WHATSAPP_PHONES.secondary.metaPhoneId,
        display: WHATSAPP_PHONES.secondary.display,
        wabaId: WHATSAPP_PHONES.secondary.wabaId,
        fixedUsername: WHATSAPP_PHONES.secondary.username, // 'manish'
    },
];

export default function WABAUsernames ( { signOut, user }: PageProps ) {
    const toast = useToastContext();
    const [ states, setStates ] = useState<Record<string, PhoneUsernameState>>( {} );
    const [ claiming, setClaiming ] = useState<Record<string, boolean>>( {} );

    const fetchUsername = useCallback( async ( phoneId: string ) => {
        setStates( prev => ( {
            ...prev,
            [ phoneId ]: { ...prev[ phoneId ], loading: true, error: undefined },
        } ) );
        try
        {
            const usernameData = await api.getBusinessUsername( phoneId );
            setStates( prev => ( {
                ...prev,
                [ phoneId ]: {
                    loading: false,
                    username: usernameData?.username,
                    status: usernameData?.status,
                    error: undefined,
                },
            } ) );
        } catch ( err: any )
        {
            setStates( prev => ( {
                ...prev,
                [ phoneId ]: { loading: false, error: err.message || 'Failed to fetch username' },
            } ) );
        }
    }, [] );

    useEffect( () => {
        PHONES.forEach( p => fetchUsername( p.phoneId ) );
    }, [ fetchUsername ] );

    // Claim the single fixed username for this number.
    const handleClaim = async ( phoneId: string, username: string ) => {
        setClaiming( prev => ( { ...prev, [ phoneId ]: true } ) );
        try
        {
            const result = await api.claimBusinessUsername( phoneId, username );
            if ( result.success )
            {
                toast.success( `Username @${username} claimed successfully` );
                fetchUsername( phoneId );
            } else
            {
                toast.error( result.error || 'Failed to claim username' );
            }
        } catch ( err: any )
        {
            toast.error( err.message || 'Failed to claim username' );
        } finally
        {
            setClaiming( prev => ( { ...prev, [ phoneId ]: false } ) );
        }
    };

    return (
        <Layout onSignOut={ signOut } user={ user }>
            <SEO title="WABA Usernames" description="Manage WhatsApp Business usernames" />

            <div style={ { padding: '24px', maxWidth: '900px' } }>
                <div style={ { marginBottom: '24px' } }>
                    <h1 style={ { fontSize: 'var(--h2)', fontWeight: 600, margin: 0 } }>
                        WhatsApp Business Usernames
                    </h1>
                    <p style={ { color: 'var(--text-secondary)', marginTop: '8px', fontSize: 'var(--text-md)' } }>
                        Each number has one fixed business username. Customers can find and message your business directly by it.
                    </p>
                </div>

                { PHONES.map( phone => {
                    const state = states[ phone.phoneId ] || { loading: true };
                    const isClaiming = claiming[ phone.phoneId ] || false;
                    const fixed = phone.fixedUsername || '';

                    return (
                        <div key={ phone.key } style={ {
                            border: '1px solid var(--border)',
                            borderRadius: '12px',
                            padding: '24px',
                            marginBottom: '20px',
                            background: 'var(--surface)',
                        } }>
                            {/* Header */ }
                            <div style={ { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' } }>
                                <div>
                                    <h2 style={ { fontSize: 'var(--text-lg)', fontWeight: 600, margin: 0 } }>
                                        { phone.label }
                                    </h2>
                                    <p style={ { color: 'var(--text-muted)', fontSize: 'var(--text-sm)', margin: '4px 0 0' } }>
                                        { phone.display } · Phone ID: { phone.phoneId }
                                    </p>
                                </div>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={ () => fetchUsername( phone.phoneId ) }
                                    disabled={ state.loading }
                                >
                                    { state.loading ? <Spinner /> : '↻ Refresh' }
                                </Button>
                            </div>

                            {/* Loading */ }
                            { state.loading && (
                                <div style={ { display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 0' } }>
                                    <Spinner /> <span style={ { color: 'var(--text-muted)' } }>Fetching username...</span>
                                </div>
                            ) }

                            {/* Error banner */ }
                            { !state.loading && state.error && (
                                <div style={ {
                                    background: 'var(--danger-light)', border: '1px solid var(--danger)',
                                    borderRadius: '8px', padding: '12px 16px', marginBottom: '12px',
                                    fontSize: 'var(--text-sm)', color: 'var(--danger)',
                                } }>
                                    ⚠️ { state.error }
                                </div>
                            ) }

                            {/* Live username + actions */ }
                            { !state.loading && (
                                <div>
                                    <label style={ { fontSize: 'var(--text-sm)', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' } }>
                                        Business Username
                                    </label>
                                    <div style={ { display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' } }>
                                        <span style={ {
                                            fontSize: 'var(--text-xl)', fontWeight: 600,
                                            color: state.username ? 'var(--accent)' : 'var(--text-muted)', fontFamily: 'var(--font-mono)',
                                        } }>
                                            @{ state.username || fixed }
                                        </span>
                                        { state.username && (
                                            <span style={ {
                                                fontSize: 'var(--text-xs)', padding: '2px 8px',
                                                borderRadius: '4px', fontWeight: 500,
                                                background: state.status === 'approved' ? '#dcfce7' : state.status === 'reserved' ? '#fef3c7' : 'var(--bg-secondary)',
                                                color: state.status === 'approved' ? '#166534' : state.status === 'reserved' ? '#92400e' : 'var(--text-muted)',
                                            } }>
                                                { state.status || 'set' }
                                            </span>
                                        ) }
                                        { !state.username && (
                                            <Button
                                                variant="primary"
                                                size="sm"
                                                onClick={ () => handleClaim( phone.phoneId, fixed ) }
                                                disabled={ isClaiming }
                                            >
                                                { isClaiming ? <Spinner /> : `Claim @${fixed}` }
                                            </Button>
                                        ) }
                                    </div>
                                    <p style={ { color: 'var(--text-muted)', fontSize: 'var(--text-xs)', marginTop: '10px' } }>
                                        { state.username
                                            ? 'Live username from Meta. Reserved names become visible to users once Meta enables the feature for everyone.'
                                            : 'No username claimed yet for this number.' }
                                    </p>
                                </div>
                            ) }
                        </div>
                    );
                } ) }
            </div>
        </Layout>
    );
}
