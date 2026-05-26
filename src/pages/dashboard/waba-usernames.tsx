/**
 * WABA Business Usernames Manager
 * Fetch, claim, and manage WhatsApp Business usernames for WABA 1 & WABA 2.
 * Uses Meta Graph API via whatsapp-business-api Lambda.
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
    suggestions: string[];
    error?: string;
}

const PHONES = [
    {
        key: 'primary',
        label: 'WABA 1 — WECARE.DIGITAL',
        phoneId: WHATSAPP_PHONES.primary.metaPhoneId,
        display: WHATSAPP_PHONES.primary.display,
        name: WHATSAPP_PHONES.primary.name,
        wabaId: WHATSAPP_PHONES.primary.wabaId,
    },
    {
        key: 'secondary',
        label: 'WABA 2 — Manish Agarwal',
        phoneId: WHATSAPP_PHONES.secondary.metaPhoneId,
        display: WHATSAPP_PHONES.secondary.display,
        name: WHATSAPP_PHONES.secondary.name,
        wabaId: WHATSAPP_PHONES.secondary.wabaId,
    },
];

// Username validation per Meta docs
function validateUsername ( value: string ): string | null {
    if ( !value ) return 'Username is required';
    if ( value.length < 3 || value.length > 35 ) return 'Must be 3–35 characters';
    if ( !/[a-zA-Z]/.test( value ) ) return 'Must contain at least one letter (a-z)';
    if ( !/^[a-zA-Z0-9._]+$/.test( value ) ) return 'Only letters, digits, period (.) and underscore (_) allowed';
    if ( value.startsWith( '.' ) || value.endsWith( '.' ) ) return 'Cannot start or end with a period';
    if ( /\.\./.test( value ) ) return 'Cannot have consecutive periods';
    if ( value.toLowerCase().startsWith( 'www' ) ) return 'Cannot start with www';
    const domainEndings = [ '.com', '.org', '.net', '.int', '.edu', '.gov', '.mil', '.us', '.in', '.html' ];
    for ( const ending of domainEndings )
    {
        if ( value.toLowerCase().endsWith( ending ) ) return `Cannot end with ${ending}`;
    }
    return null;
}

export default function WABAUsernames ( { signOut, user }: PageProps ) {
    const toast = useToastContext();
    const [ states, setStates ] = useState<Record<string, PhoneUsernameState>>( {} );
    const [ claimInputs, setClaimInputs ] = useState<Record<string, string>>( {} );
    const [ claiming, setClaiming ] = useState<Record<string, boolean>>( {} );
    const [ deleting, setDeleting ] = useState<Record<string, boolean>>( {} );
    const [ validationErrors, setValidationErrors ] = useState<Record<string, string | null>>( {} );

    const fetchUsername = useCallback( async ( phoneId: string ) => {
        setStates( prev => ( {
            ...prev,
            [ phoneId ]: { ...prev[ phoneId ], loading: true, error: undefined },
        } ) );

        try
        {
            const [ usernameData, suggestionsData ] = await Promise.all( [
                api.getBusinessUsername( phoneId ),
                api.getBusinessUsernameSuggestions( phoneId ),
            ] );

            setStates( prev => ( {
                ...prev,
                [ phoneId ]: {
                    loading: false,
                    username: usernameData?.username,
                    status: usernameData?.status,
                    suggestions: suggestionsData?.suggestions || [],
                    error: undefined,
                },
            } ) );
        } catch ( err: any )
        {
            setStates( prev => ( {
                ...prev,
                [ phoneId ]: {
                    loading: false,
                    suggestions: [],
                    error: err.message || 'Failed to fetch username',
                },
            } ) );
        }
    }, [] );

    useEffect( () => {
        PHONES.forEach( p => fetchUsername( p.phoneId ) );
    }, [ fetchUsername ] );

    const handleClaim = async ( phoneId: string ) => {
        const username = ( claimInputs[ phoneId ] || '' ).trim();
        const validationError = validateUsername( username );
        if ( validationError )
        {
            setValidationErrors( prev => ( { ...prev, [ phoneId ]: validationError } ) );
            return;
        }
        setValidationErrors( prev => ( { ...prev, [ phoneId ]: null } ) );
        setClaiming( prev => ( { ...prev, [ phoneId ]: true } ) );

        try
        {
            const result = await api.claimBusinessUsername( phoneId, username );
            if ( result.success )
            {
                toast.success( `Username @${username} claimed successfully` );
                setClaimInputs( prev => ( { ...prev, [ phoneId ]: '' } ) );
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

    const handleDelete = async ( phoneId: string ) => {
        if ( !confirm( 'Are you sure you want to delete this business username?' ) ) return;
        setDeleting( prev => ( { ...prev, [ phoneId ]: true } ) );

        try
        {
            const result = await api.deleteBusinessUsername( phoneId );
            if ( result.success )
            {
                toast.success( 'Username deleted' );
                fetchUsername( phoneId );
            } else
            {
                toast.error( result.error || 'Failed to delete username' );
            }
        } catch ( err: any )
        {
            toast.error( err.message || 'Failed to delete username' );
        } finally
        {
            setDeleting( prev => ( { ...prev, [ phoneId ]: false } ) );
        }
    };

    const handleInputChange = ( phoneId: string, value: string ) => {
        // Strip @ prefix if user types it
        const clean = value.startsWith( '@' ) ? value.slice( 1 ) : value;
        setClaimInputs( prev => ( { ...prev, [ phoneId ]: clean } ) );
        if ( clean )
        {
            setValidationErrors( prev => ( { ...prev, [ phoneId ]: validateUsername( clean ) } ) );
        } else
        {
            setValidationErrors( prev => ( { ...prev, [ phoneId ]: null } ) );
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
                        Manage business usernames for your WhatsApp numbers. Usernames let customers find and message your business directly.
                    </p>
                    <p style={ {
                        color: 'var(--text-muted)', marginTop: '4px', fontSize: 'var(--text-sm)',
                        background: 'var(--bg-secondary)', padding: '8px 12px', borderRadius: '6px', display: 'inline-block'
                    } }>
                        ℹ️ This feature is rolling out later in 2026. The API may not be available in all regions yet.
                    </p>
                </div>

                { PHONES.map( phone => {
                    const state = states[ phone.phoneId ] || { loading: true, suggestions: [] };
                    const input = claimInputs[ phone.phoneId ] || '';
                    const isClaiming = claiming[ phone.phoneId ] || false;
                    const isDeleting = deleting[ phone.phoneId ] || false;
                    const validationError = validationErrors[ phone.phoneId ];

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

                            {/* Error */ }
                            { !state.loading && state.error && (
                                <div style={ {
                                    background: 'var(--danger-light)', border: '1px solid var(--danger)',
                                    borderRadius: '8px', padding: '12px 16px', marginBottom: '12px',
                                    fontSize: 'var(--text-sm)', color: 'var(--danger)',
                                } }>
                                    ⚠️ { state.error }
                                </div>
                            ) }

                            {/* Current Username */ }
                            { !state.loading && !state.error && (
                                <div style={ { marginBottom: '16px' } }>
                                    <label style={ { fontSize: 'var(--text-sm)', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' } }>
                                        Current Username
                                    </label>
                                    { state.username ? (
                                        <div style={ { display: 'flex', alignItems: 'center', gap: '12px' } }>
                                            <span style={ {
                                                fontSize: 'var(--text-xl)', fontWeight: 600,
                                                color: 'var(--accent)', fontFamily: 'var(--font-mono)',
                                            } }>
                                                @{ state.username }
                                            </span>
                                            <span style={ {
                                                fontSize: 'var(--text-xs)', padding: '2px 8px',
                                                borderRadius: '4px', fontWeight: 500,
                                                background: state.status === 'approved' ? '#dcfce7' : state.status === 'reserved' ? '#fef3c7' : 'var(--bg-secondary)',
                                                color: state.status === 'approved' ? '#166534' : state.status === 'reserved' ? '#92400e' : 'var(--text-muted)',
                                            } }>
                                                { state.status || 'unknown' }
                                            </span>
                                            <Button
                                                variant="danger"
                                                size="sm"
                                                onClick={ () => handleDelete( phone.phoneId ) }
                                                disabled={ isDeleting }
                                            >
                                                { isDeleting ? <Spinner /> : 'Delete' }
                                            </Button>
                                        </div>
                                    ) : (
                                        <span style={ { color: 'var(--text-muted)', fontSize: 'var(--text-md)' } }>
                                            No username set
                                        </span>
                                    ) }
                                </div>
                            ) }

                            {/* Reserved Suggestions */ }
                            { !state.loading && state.suggestions.length > 0 && (
                                <div style={ { marginBottom: '16px' } }>
                                    <label style={ { fontSize: 'var(--text-sm)', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' } }>
                                        Reserved Suggestions (click to use)
                                    </label>
                                    <div style={ { display: 'flex', flexWrap: 'wrap', gap: '8px' } }>
                                        { state.suggestions.map( s => (
                                            <button
                                                key={ s }
                                                onClick={ () => setClaimInputs( prev => ( { ...prev, [ phone.phoneId ]: s } ) ) }
                                                style={ {
                                                    padding: '4px 12px', borderRadius: '6px', border: '1px solid var(--border)',
                                                    background: 'var(--bg-secondary)', cursor: 'pointer', fontSize: 'var(--text-sm)',
                                                    fontFamily: 'var(--font-mono)', transition: 'all 0.15s',
                                                } }
                                                onMouseOver={ e => { ( e.target as HTMLElement ).style.borderColor = 'var(--accent)'; } }
                                                onMouseOut={ e => { ( e.target as HTMLElement ).style.borderColor = 'var(--border)'; } }
                                            >
                                                @{ s }
                                            </button>
                                        ) ) }
                                    </div>
                                </div>
                            ) }

                            {/* Claim / Change Username */ }
                            { !state.loading && (
                                <div style={ { borderTop: '1px solid var(--border-light)', paddingTop: '16px' } }>
                                    <label style={ { fontSize: 'var(--text-sm)', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' } }>
                                        { state.username ? 'Change Username' : 'Claim Username' }
                                    </label>
                                    <div style={ { display: 'flex', gap: '8px', alignItems: 'flex-start' } }>
                                        <div style={ { flex: 1 } }>
                                            <div style={ { position: 'relative' } }>
                                                <span style={ {
                                                    position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)',
                                                    color: 'var(--text-muted)', fontSize: 'var(--text-md)', fontFamily: 'var(--font-mono)',
                                                } }>@</span>
                                                <input
                                                    type="text"
                                                    value={ input }
                                                    onChange={ e => handleInputChange( phone.phoneId, e.target.value ) }
                                                    onKeyDown={ e => { if ( e.key === 'Enter' && input ) handleClaim( phone.phoneId ); } }
                                                    placeholder="desired_username"
                                                    style={ {
                                                        width: '100%', padding: '8px 12px 8px 28px',
                                                        border: `1px solid ${validationError ? 'var(--danger)' : 'var(--border)'}`,
                                                        borderRadius: '8px', fontSize: 'var(--text-md)',
                                                        fontFamily: 'var(--font-mono)', outline: 'none',
                                                        transition: 'border-color 0.15s',
                                                    } }
                                                    onFocus={ e => { if ( !validationError ) e.target.style.borderColor = 'var(--accent)'; } }
                                                    onBlur={ e => { if ( !validationError ) e.target.style.borderColor = 'var(--border)'; } }
                                                />
                                            </div>
                                            { validationError && (
                                                <p style={ { color: 'var(--danger)', fontSize: 'var(--text-xs)', margin: '4px 0 0' } }>
                                                    { validationError }
                                                </p>
                                            ) }
                                        </div>
                                        <Button
                                            variant="primary"
                                            size="md"
                                            onClick={ () => handleClaim( phone.phoneId ) }
                                            disabled={ isClaiming || !input || !!validationError }
                                        >
                                            { isClaiming ? <Spinner /> : ( state.username ? 'Change' : 'Claim' ) }
                                        </Button>
                                    </div>
                                    <p style={ { color: 'var(--text-muted)', fontSize: 'var(--text-xs)', marginTop: '8px' } }>
                                        Rules: 3–35 chars, letters + digits + period + underscore only, must contain a letter, no consecutive periods, cannot start/end with period.
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
