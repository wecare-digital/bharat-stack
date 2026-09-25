/**
 * Secure Files — wecare.digital/get/secure
 *
 * One form does three things, because they are one intention: naming a customer,
 * registering a file to them, and creating the login that lets them fetch it.
 * Entering a mobile number here CREATES a Cognito customer if none exists, and
 * that number is the one that will receive the WhatsApp OTP - so a typo does not
 * fail loudly, it silently registers the file to someone who will never ask for it.
 * The form says so next to the field.
 *
 * Upload is three calls, not one: register, PUT to S3, confirm. The confirm step
 * re-checks the object really landed, so an upload that dies half way leaves a
 * `pending` row rather than an `active` file a customer could be charged for and
 * not receive.
 *
 * The S3 key is deliberately absent from this page. Objects are stored as
 * `wecare-digital-<uuid>-<uuid>`, and the readable name lives only in the table,
 * so everything here is keyed on `fileId`.
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import Button from '../../components/ui/Button';
import Spinner from '../../components/ui/Spinner';
import { useToastContext } from '../../contexts/ToastContext';
import * as api from '../../api/client';
import type { SecureFile } from '../../api/client';

interface PageProps { signOut?: () => void; user?: any; }

const MAX_BYTES = 200 * 1024 * 1024;

function formatBytes ( bytes: number ): string {
    if ( !bytes ) return '0 B';
    const units = [ 'B', 'KB', 'MB', 'GB' ];
    const exponent = Math.min( Math.floor( Math.log( bytes ) / Math.log( 1024 ) ), units.length - 1 );
    return `${( bytes / Math.pow( 1024, exponent ) ).toFixed( exponent === 0 ? 0 : 1 )} ${units[ exponent ]}`;
}

function formatRupees ( paise: number ): string {
    return `₹${( ( paise || 0 ) / 100 ).toFixed( 2 )}`;
}

const STATUS_COLOURS: Record<string, { bg: string; fg: string }> = {
    active: { bg: '#dcfce7', fg: '#166534' },
    pending: { bg: '#fef3c7', fg: '#92400e' },
    revoked: { bg: '#fee2e2', fg: '#991b1b' },
};

export default function SecureFilesPage ( { signOut, user }: PageProps ) {
    const toast = useToastContext();

    const [ name, setName ] = useState( '' );
    const [ mobile, setMobile ] = useState( '' );
    const [ displayName, setDisplayName ] = useState( '' );
    const [ file, setFile ] = useState<File | null>( null );
    const [ uploading, setUploading ] = useState( false );
    const [ step, setStep ] = useState( '' );

    const [ files, setFiles ] = useState<SecureFile[]>( [] );
    const [ loading, setLoading ] = useState( true );
    const [ loadError, setLoadError ] = useState( '' );
    const [ filterMobile, setFilterMobile ] = useState( '' );

    /** Refetch and replace the table. Used by the filter button and after an upload. */
    const fetchInto = useCallback( async ( mobileFilter?: string ) => {
        const result = await api.listSecureFiles( mobileFilter || undefined );
        if ( result.ok )
        {
            setFiles( result.data.files || [] );
            setLoadError( '' );
        } else
        {
            // Say why, rather than rendering an empty table that looks like "no files".
            setLoadError( result.failure.message || 'Could not load secure files' );
            setFiles( [] );
        }
        setLoading( false );
    }, [] );

    /** Reload with the spinner, for buttons and post-upload refresh. */
    const load = useCallback( ( mobileFilter?: string ) => {
        setLoading( true );
        return fetchInto( mobileFilter );
    }, [ fetchInto ] );

    useEffect( () => {
        // Subscribe-then-settle: state is updated from the promise callback rather
        // than the effect body, and `cancelled` stops a late response writing to an
        // unmounted component.
        let cancelled = false;
        api.listSecureFiles().then( result => {
            if ( cancelled ) return;
            if ( result.ok )
            {
                setFiles( result.data.files || [] );
                setLoadError( '' );
            } else
            {
                setLoadError( result.failure.message || 'Could not load secure files' );
                setFiles( [] );
            }
            setLoading( false );
        } );
        return () => { cancelled = true; };
    }, [] );

    const resetForm = () => {
        setName( '' );
        setMobile( '' );
        setDisplayName( '' );
        setFile( null );
    };

    const handleUpload = async () => {
        if ( !file ) { toast.error( 'Choose a file first' ); return; }
        if ( !name.trim() ) { toast.error( 'Customer name is required' ); return; }
        if ( !mobile.trim() ) { toast.error( 'Customer mobile number is required' ); return; }
        if ( file.size > MAX_BYTES )
        {
            toast.error( `File is larger than ${formatBytes( MAX_BYTES )}` );
            return;
        }

        setUploading( true );
        try
        {
            setStep( 'Registering customer and file…' );
            const contentType = file.type || 'application/octet-stream';
            const ticket = await api.initSecureUpload( {
                name: name.trim(),
                mobile: mobile.trim(),
                displayName: displayName.trim() || file.name,
                originalFilename: file.name,
                contentType,
                sizeBytes: file.size,
            } );
            if ( !ticket.ok )
            {
                toast.error( ticket.failure.message || 'Could not register the file' );
                return;
            }

            setStep( 'Uploading…' );
            const sent = await api.uploadSecureFileBytes( ticket.data.uploadUrl, file, contentType );
            if ( !sent )
            {
                // The record stays `pending`, so nothing is downloadable or billable.
                toast.error( 'Upload failed. The file was not stored; try again.' );
                return;
            }

            setStep( 'Confirming…' );
            const confirmed = await api.confirmSecureUpload( ticket.data.fileId );
            if ( !confirmed.ok )
            {
                toast.error( confirmed.failure.message || 'Upload could not be confirmed' );
                return;
            }

            toast.success( `${displayName.trim() || file.name} registered to ${name.trim()}` );
            resetForm();
            load( filterMobile || undefined );
        } catch ( err: any )
        {
            toast.error( err?.message || 'Upload failed' );
        } finally
        {
            setUploading( false );
            setStep( '' );
        }
    };

    const handleRevoke = async ( target: SecureFile ) => {
        const ok = window.confirm(
            `Revoke "${target.displayName}"?\n\n`
            + 'The customer will no longer be able to download it. '
            + 'The record is kept so the history of who was charged survives.',
        );
        if ( !ok ) return;

        const result = await api.revokeSecureFile( target.fileId );
        if ( result.ok )
        {
            toast.success( 'File revoked' );
            load( filterMobile || undefined );
        } else
        {
            toast.error( result.failure.message || 'Could not revoke the file' );
        }
    };

    const label: React.CSSProperties = {
        fontSize: 'var(--text-sm)', color: 'var(--text-muted)',
        display: 'block', marginBottom: '6px',
    };
    const input: React.CSSProperties = {
        width: '100%', padding: '10px 12px', borderRadius: '8px',
        border: '1px solid var(--border)', background: 'var(--surface)',
        color: 'var(--text-primary)', fontSize: 'var(--text-md)',
    };
    const cell: React.CSSProperties = {
        padding: '10px 12px', borderBottom: '1px solid var(--border)',
        fontSize: 'var(--text-sm)', textAlign: 'left',
    };

    return (
        <Layout onSignOut={ signOut } user={ user }>
            <SEO title="Secure Files" description="Share files with a verified customer" />

            <div style={ { padding: '24px', maxWidth: '1100px' } }>
                <div style={ { marginBottom: '24px' } }>
                    <h1 style={ { fontSize: 'var(--h2)', fontWeight: 600, margin: 0 } }>Secure Files</h1>
                    <p style={ { color: 'var(--text-secondary)', marginTop: '8px', fontSize: 'var(--text-md)' } }>
                        Files registered to one customer, who verifies over WhatsApp before downloading.
                        Stored under an unguessable name, and never reachable from a public link.
                    </p>
                </div>

                {/* ── upload + register ─────────────────────────────────────── */ }
                <div style={ {
                    border: '1px solid var(--border)', borderRadius: '12px',
                    padding: '24px', marginBottom: '28px', background: 'var(--surface)',
                } }>
                    <h2 style={ { fontSize: 'var(--text-lg)', fontWeight: 600, margin: '0 0 4px' } }>
                        Add a file
                    </h2>
                    <p style={ { color: 'var(--text-muted)', fontSize: 'var(--text-sm)', margin: '0 0 20px' } }>
                        The customer login is created automatically from the mobile number.
                    </p>

                    <div style={ {
                        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                        gap: '16px', marginBottom: '16px',
                    } }>
                        <div>
                            <label style={ label } htmlFor="sf-name">Customer name</label>
                            <input
                                id="sf-name"
                                style={ input }
                                value={ name }
                                onChange={ e => setName( e.target.value ) }
                                placeholder="Ramesh Kumar"
                                disabled={ uploading }
                            />
                        </div>

                        <div>
                            <label style={ label } htmlFor="sf-mobile">Customer mobile</label>
                            <input
                                id="sf-mobile"
                                style={ input }
                                value={ mobile }
                                onChange={ e => setMobile( e.target.value ) }
                                placeholder="8100640044"
                                inputMode="tel"
                                disabled={ uploading }
                            />
                            {/* The consequence of a typo is silent, so say it here. */ }
                            <p style={ { color: 'var(--text-muted)', fontSize: 'var(--text-xs)', margin: '6px 0 0' } }>
                                This number receives the WhatsApp OTP. A 10-digit Indian number
                                gets +91 automatically. Check it — the file is registered to
                                whoever this is.
                            </p>
                        </div>

                        <div>
                            <label style={ label } htmlFor="sf-display">
                                File name shown to the customer
                            </label>
                            <input
                                id="sf-display"
                                style={ input }
                                value={ displayName }
                                onChange={ e => setDisplayName( e.target.value ) }
                                placeholder={ file?.name || 'Trade Licence 2026' }
                                disabled={ uploading }
                            />
                        </div>

                        <div>
                            <label style={ label } htmlFor="sf-file">File</label>
                            <input
                                id="sf-file"
                                style={ { ...input, padding: '8px' } }
                                type="file"
                                onChange={ e => setFile( e.target.files?.[ 0 ] || null ) }
                                disabled={ uploading }
                            />
                            { file && (
                                <p style={ { color: 'var(--text-muted)', fontSize: 'var(--text-xs)', margin: '6px 0 0' } }>
                                    { formatBytes( file.size ) } · { file.type || 'unknown type' }
                                </p>
                            ) }
                        </div>
                    </div>

                    <div style={ { display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' } }>
                        <Button variant="primary" onClick={ handleUpload } disabled={ uploading }>
                            { uploading ? <Spinner /> : 'Register and upload' }
                        </Button>
                        { uploading && step && (
                            <span style={ { color: 'var(--text-muted)', fontSize: 'var(--text-sm)' } }>
                                { step }
                            </span>
                        ) }
                        { !uploading && (
                            <span style={ { color: 'var(--text-muted)', fontSize: 'var(--text-sm)' } }>
                                Customer pays { formatRupees( 4900 ) } per download.
                            </span>
                        ) }
                    </div>
                </div>

                {/* ── registered files ──────────────────────────────────────── */ }
                <div style={ {
                    border: '1px solid var(--border)', borderRadius: '12px',
                    padding: '24px', background: 'var(--surface)',
                } }>
                    <div style={ {
                        display: 'flex', justifyContent: 'space-between',
                        alignItems: 'flex-end', gap: '16px', flexWrap: 'wrap', marginBottom: '16px',
                    } }>
                        <div>
                            <h2 style={ { fontSize: 'var(--text-lg)', fontWeight: 600, margin: 0 } }>
                                Registered files
                            </h2>
                            <p style={ { color: 'var(--text-muted)', fontSize: 'var(--text-sm)', margin: '4px 0 0' } }>
                                { loading ? 'Loading…' : `${files.length} file${files.length === 1 ? '' : 's'}` }
                            </p>
                        </div>
                        <div style={ { display: 'flex', gap: '8px', alignItems: 'flex-end' } }>
                            <div>
                                <label style={ label } htmlFor="sf-filter">Filter by mobile</label>
                                <input
                                    id="sf-filter"
                                    style={ { ...input, width: '190px' } }
                                    value={ filterMobile }
                                    onChange={ e => setFilterMobile( e.target.value ) }
                                    placeholder="8100640044"
                                    inputMode="tel"
                                />
                            </div>
                            <Button variant="ghost" size="sm" onClick={ () => load( filterMobile || undefined ) }>
                                Apply
                            </Button>
                        </div>
                    </div>

                    { loadError && (
                        <div style={ {
                            background: 'var(--danger-light)', border: '1px solid var(--danger)',
                            borderRadius: '8px', padding: '12px 16px', marginBottom: '12px',
                            fontSize: 'var(--text-sm)', color: 'var(--danger)',
                        } }>
                            ⚠️ { loadError }
                        </div>
                    ) }

                    { loading && (
                        <div style={ { display: 'flex', alignItems: 'center', gap: '8px', padding: '16px 0' } }>
                            <Spinner /> <span style={ { color: 'var(--text-muted)' } }>Loading files…</span>
                        </div>
                    ) }

                    { !loading && !loadError && files.length === 0 && (
                        <p style={ { color: 'var(--text-muted)', fontSize: 'var(--text-sm)', padding: '16px 0', margin: 0 } }>
                            No files registered yet.
                        </p>
                    ) }

                    { !loading && files.length > 0 && (
                        <div style={ { overflowX: 'auto' } }>
                            <table style={ { width: '100%', borderCollapse: 'collapse' } }>
                                <thead>
                                    <tr>
                                        { [ 'File', 'Customer', 'Mobile', 'Size', 'Downloads', 'Status', '' ].map( heading => (
                                            <th key={ heading } style={ {
                                                ...cell, color: 'var(--text-muted)',
                                                fontWeight: 500, fontSize: 'var(--text-xs)',
                                                textTransform: 'uppercase', letterSpacing: '0.04em',
                                            } } scope="col">
                                                { heading }
                                            </th>
                                        ) ) }
                                    </tr>
                                </thead>
                                <tbody>
                                    { files.map( row => {
                                        const colour = STATUS_COLOURS[ row.status ] || STATUS_COLOURS.pending;
                                        return (
                                            <tr key={ row.fileId }>
                                                <td style={ cell }>
                                                    <div style={ { fontWeight: 500 } }>{ row.displayName }</div>
                                                    <div style={ { color: 'var(--text-muted)', fontSize: 'var(--text-xs)' } }>
                                                        { row.originalFilename }
                                                    </div>
                                                </td>
                                                <td style={ cell }>{ row.ownerName || '—' }</td>
                                                {/* masked at the API; the full number is never sent here */ }
                                                <td style={ { ...cell, fontFamily: 'var(--font-mono)' } }>
                                                    { row.ownerPhoneMasked || '—' }
                                                </td>
                                                <td style={ cell }>{ formatBytes( row.sizeBytes ) }</td>
                                                <td style={ cell }>{ row.downloadCount ?? 0 }</td>
                                                <td style={ cell }>
                                                    <span style={ {
                                                        fontSize: 'var(--text-xs)', padding: '2px 8px',
                                                        borderRadius: '4px', fontWeight: 500,
                                                        background: colour.bg, color: colour.fg,
                                                    } }>
                                                        { row.status }
                                                    </span>
                                                </td>
                                                <td style={ cell }>
                                                    { row.status !== 'revoked' && (
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={ () => handleRevoke( row ) }
                                                        >
                                                            Revoke
                                                        </Button>
                                                    ) }
                                                </td>
                                            </tr>
                                        );
                                    } ) }
                                </tbody>
                            </table>
                        </div>
                    ) }
                </div>
            </div>
        </Layout>
    );
}
