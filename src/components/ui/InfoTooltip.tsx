/**
 * InfoTooltip — themed, accessible tooltip/popover.
 *
 * Replaces native `title=""` tooltips which (a) aren't themed, (b) don't wrap,
 * and (c) never appear on touch devices. This:
 *  - opens on hover/focus (desktop) AND tap (mobile)
 *  - renders into a portal (document.body) so it's never clipped by scroll/overflow
 *  - wraps long text, flips above/below based on available space
 *  - closes on outside tap / Escape
 *  - matches the design tokens (white surface, lime border, soft shadow)
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { colors, radius, shadow, zIndex } from '../../lib/design-tokens';

interface InfoTooltipProps {
    content: React.ReactNode;
    children?: React.ReactNode;   // trigger content (defaults to ⓘ)
    label?: string;               // accessible label
    width?: number;               // popover width (px)
}

const InfoTooltip: React.FC<InfoTooltipProps> = ( { content, children, label = 'More information', width = 280 } ) => {
    const [ open, setOpen ] = useState( false );
    const [ mounted, setMounted ] = useState( false );
    const [ pos, setPos ] = useState<{ top: number; left: number; placement: 'top' | 'bottom' }>( { top: 0, left: 0, placement: 'top' } );
    const triggerRef = useRef<HTMLButtonElement>( null );
    const popRef = useRef<HTMLDivElement>( null );

    useEffect( () => setMounted( true ), [] );

    const reposition = useCallback( () => {
        const t = triggerRef.current;
        if ( !t ) return;
        const r = t.getBoundingClientRect();
        const margin = 8;
        const left = Math.min(
            Math.max( margin, r.left + r.width / 2 - width / 2 ),
            window.innerWidth - width - margin
        );
        const placement: 'top' | 'bottom' = r.top > 150 ? 'top' : 'bottom';
        setPos( { top: placement === 'top' ? r.top : r.bottom, left, placement } );
    }, [ width ] );

    useEffect( () => {
        if ( !open ) return;
        reposition();
        const onScroll = () => reposition();
        const onKey = ( e: KeyboardEvent ) => { if ( e.key === 'Escape' ) setOpen( false ); };
        const onDown = ( e: MouseEvent | TouchEvent ) => {
            const tgt = e.target as Node;
            if ( popRef.current?.contains( tgt ) || triggerRef.current?.contains( tgt ) ) return;
            setOpen( false );
        };
        window.addEventListener( 'scroll', onScroll, true );
        window.addEventListener( 'resize', reposition );
        window.addEventListener( 'keydown', onKey );
        document.addEventListener( 'mousedown', onDown );
        document.addEventListener( 'touchstart', onDown );
        return () => {
            window.removeEventListener( 'scroll', onScroll, true );
            window.removeEventListener( 'resize', reposition );
            window.removeEventListener( 'keydown', onKey );
            document.removeEventListener( 'mousedown', onDown );
            document.removeEventListener( 'touchstart', onDown );
        };
    }, [ open, reposition ] );

    return (
        <>
            <button
                ref={ triggerRef }
                type="button"
                aria-label={ label }
                aria-expanded={ open }
                onClick={ ( e ) => { e.stopPropagation(); setOpen( o => !o ); } }
                onMouseEnter={ () => setOpen( true ) }
                onMouseLeave={ () => setOpen( false ) }
                onFocus={ () => setOpen( true ) }
                onBlur={ () => setOpen( false ) }
                style={ {
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    background: 'none', border: 'none', padding: 0, margin: 0,
                    cursor: 'pointer', font: 'inherit', color: 'inherit', lineHeight: 1,
                } }
            >
                { children ?? <span aria-hidden style={ { fontSize: '0.95em', opacity: 0.85 } }>ⓘ</span> }
            </button>

            { mounted && open && createPortal(
                <div
                    ref={ popRef }
                    role="tooltip"
                    onClick={ ( e ) => e.stopPropagation() }
                    style={ {
                        position: 'fixed',
                        top: pos.top,
                        left: pos.left,
                        width,
                        maxWidth: 'calc(100vw - 16px)',
                        transform: pos.placement === 'top' ? 'translateY(-100%) translateY(-8px)' : 'translateY(8px)',
                        background: colors.white,
                        color: colors.text,
                        border: `1.5px solid ${colors.lime}`,
                        borderRadius: radius.lg,
                        boxShadow: shadow.xl,
                        padding: '10px 12px',
                        fontSize: 12.5,
                        lineHeight: 1.5,
                        whiteSpace: 'normal',
                        wordBreak: 'break-word',
                        zIndex: zIndex.tooltip,
                        textAlign: 'left',
                    } }
                >
                    { content }
                </div>,
                document.body
            ) }
        </>
    );
};

export default InfoTooltip;
