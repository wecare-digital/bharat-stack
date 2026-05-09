/**
 * Design Reference — WECARE.DIGITAL
 * Complete inner page design system reference.
 * URL: /dashboard/design-reference
 *
 * Sections:
 * 1. Color Palette
 * 2. Typography
 * 3. Spacing & Layout
 * 4. Buttons
 * 5. Form Inputs
 * 6. Cards & Containers
 * 7. Tables
 * 8. Tabs & Navigation
 * 9. Badges & Pills
 * 10. Toasts & Alerts
 * 11. Empty States
 * 12. Loading States
 * 13. Modals
 * 14. Icons
 * 15. Responsive Breakpoints
 * 16. Accessibility
 * 17. Motion & Transitions
 * 18. Page Templates
 */

import React, { useState } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import Button from '../../components/ui/Button';

interface PageProps { signOut?: () => void; user?: any; }

// ─── Design Tokens ───
const COLORS = {
    primary: { label: 'Primary (Dark Green)', value: '#1a3a2a', text: '#fff' },
    primaryHover: { label: 'Primary Hover', value: '#0f2a1d', text: '#fff' },
    lime: { label: 'Lime Accent', value: '#d1f470', text: '#1a3a2a' },
    limeHover: { label: 'Lime Hover', value: '#c5e866', text: '#1a3a2a' },
    white: { label: 'White', value: '#ffffff', text: '#111827' },
    bgSecondary: { label: 'Background Secondary', value: '#f9fafb', text: '#111827' },
    bgHover: { label: 'Background Hover', value: '#f5f5f5', text: '#111827' },
    text: { label: 'Text Primary', value: '#111827', text: '#fff' },
    textSecondary: { label: 'Text Secondary', value: '#6b7280', text: '#fff' },
    textMuted: { label: 'Text Muted', value: '#9ca3af', text: '#111827' },
    border: { label: 'Border', value: '#e5e7eb', text: '#111827' },
    borderDark: { label: 'Border Dark', value: '#d1d5db', text: '#111827' },
    danger: { label: 'Danger', value: '#dc2626', text: '#fff' },
    dangerLight: { label: 'Danger Light', value: '#fef2f2', text: '#dc2626' },
};

const TYPOGRAPHY = [
    { name: 'Page Title', size: '28px', weight: 700, sample: 'Dashboard Overview' },
    { name: 'Section Title', size: '20px', weight: 600, sample: 'Recent Activity' },
    { name: 'Card Title', size: '16px', weight: 600, sample: 'WhatsApp Messages' },
    { name: 'Body', size: '14px', weight: 400, sample: 'The quick brown fox jumps over the lazy dog.' },
    { name: 'Button', size: '14px', weight: 500, sample: 'Send Message' },
    { name: 'Table Cell', size: '13px', weight: 400, sample: '+91 98765 43210' },
    { name: 'Caption / Label', size: '12px', weight: 600, sample: 'TOTAL MESSAGES' },
    { name: 'Monospace', size: '12px', weight: 400, sample: 'arn:aws:lambda:ap-south-1:123456789' },
];

const SPACING = [
    { token: '--space-1', value: '4px' },
    { token: '--space-2', value: '8px' },
    { token: '--space-3', value: '12px' },
    { token: '--space-4', value: '16px' },
    { token: '--space-5', value: '20px' },
    { token: '--space-6', value: '24px' },
    { token: '--space-8', value: '32px' },
    { token: '--space-10', value: '40px' },
    { token: '--space-12', value: '48px' },
];

const RADII = [
    { token: '--radius-sm', value: '6px', use: 'Small elements, badges' },
    { token: '--radius-md', value: '8px', use: 'Inputs, small cards' },
    { token: '--radius-btn', value: '13px', use: 'All buttons' },
    { token: '--radius-lg', value: '12px', use: 'Cards, sections' },
    { token: '--radius-xl', value: '14px', use: 'Tab containers' },
    { token: '--radius-2xl', value: '16px', use: 'Large cards, modals' },
    { token: '--radius-full', value: '9999px', use: 'Avatars, pills' },
];

const BREAKPOINTS = [
    { name: 'Mobile S', value: '≤ 480px', columns: '1-2', padding: '16px' },
    { name: 'Mobile L', value: '481–768px', columns: '2', padding: '20px' },
    { name: 'Tablet', value: '769–1024px', columns: '2-3', padding: '24px' },
    { name: 'Desktop', value: '1025–1440px', columns: 'auto-fit', padding: '24px' },
    { name: 'Wide', value: '> 1440px', columns: 'auto-fit (max 1400px)', padding: '24px' },
];

const TABS_LIST = [
    { id: 'colors', label: '🎨 Colors' },
    { id: 'typography', label: '🔤 Typography' },
    { id: 'spacing', label: '📐 Spacing' },
    { id: 'buttons', label: '🔘 Buttons' },
    { id: 'inputs', label: '📝 Inputs' },
    { id: 'cards', label: '🃏 Cards' },
    { id: 'tables', label: '📊 Tables' },
    { id: 'tabs', label: '📑 Tabs' },
    { id: 'badges', label: '🏷️ Badges' },
    { id: 'toasts', label: '🔔 Toasts' },
    { id: 'empty', label: '📭 Empty States' },
    { id: 'loading', label: '⏳ Loading' },
    { id: 'modals', label: '💬 Modals' },
    { id: 'icons', label: '🎯 Icons' },
    { id: 'responsive', label: '📱 Responsive' },
    { id: 'a11y', label: '♿ Accessibility' },
    { id: 'motion', label: '✨ Motion' },
    { id: 'templates', label: '📄 Templates' },
];

// ─── Styles ───
const S = {
    page: { padding: '24px', maxWidth: 1400, margin: '0 auto' } as React.CSSProperties,
    header: { marginBottom: 32 } as React.CSSProperties,
    title: { fontSize: 28, fontWeight: 700, color: '#1a3a2a', margin: '0 0 8px' } as React.CSSProperties,
    subtitle: { fontSize: 14, color: '#6b7280', margin: 0 } as React.CSSProperties,
    tabs: { display: 'flex', gap: 8, flexWrap: 'wrap' as const, marginBottom: 32, padding: '12px 16px', background: '#f9fafb', borderRadius: 14, border: '2px solid #d1f470' } as React.CSSProperties,
    tab: ( active: boolean ): React.CSSProperties => ( { padding: '10px 16px', borderRadius: 10, border: '1.5px solid transparent', background: active ? '#d1f470' : 'transparent', color: active ? '#1a3a2a' : '#6b7280', fontWeight: active ? 600 : 500, fontSize: 13, cursor: 'pointer', transition: 'all 0.15s ease', whiteSpace: 'nowrap' } ),
    section: { marginBottom: 40 } as React.CSSProperties,
    sectionTitle: { fontSize: 20, fontWeight: 600, color: '#1a3a2a', margin: '0 0 16px', paddingBottom: 12, borderBottom: '1px solid #e5e7eb' } as React.CSSProperties,
    grid: ( cols: string ): React.CSSProperties => ( { display: 'grid', gridTemplateColumns: cols, gap: 16 } ),
    card: { background: '#fff', border: '1.5px solid #d1f470', borderRadius: 16, padding: 20 } as React.CSSProperties,
    code: { fontFamily: 'monospace', fontSize: 12, background: '#f9fafb', padding: '2px 6px', borderRadius: 4 } as React.CSSProperties,
    swatch: ( bg: string, text: string ): React.CSSProperties => ( { width: '100%', height: 80, borderRadius: 12, background: bg, display: 'flex', alignItems: 'center', justifyContent: 'center', color: text, fontWeight: 600, fontSize: 12, border: '1px solid #e5e7eb' } ),
    row: { display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' as const } as React.CSSProperties,
    table: { width: '100%', borderCollapse: 'collapse' as const, fontSize: 13, border: '2px solid #d1f470', borderRadius: 16, overflow: 'hidden' } as React.CSSProperties,
    th: { background: '#d1f470', color: '#1a3a2a', padding: '12px 16px', textAlign: 'left' as const, fontWeight: 600, fontSize: 11, textTransform: 'uppercase' as const, letterSpacing: '0.5px' } as React.CSSProperties,
    td: { padding: '12px 16px', borderBottom: '1px solid #f3f4f6' } as React.CSSProperties,
    badge: ( bg: string, color: string ): React.CSSProperties => ( { display: 'inline-block', padding: '3px 10px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: bg, color } ),
    note: { background: '#f9fafb', border: '1.5px solid #d1f470', borderRadius: 13, padding: '12px 16px', fontSize: 13, color: '#374151', marginTop: 12 } as React.CSSProperties,
    demoBtn: ( variant: string ): React.CSSProperties => {
        const base: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '10px 18px', minHeight: 44, fontSize: 14, fontWeight: 500, borderRadius: 13, cursor: 'pointer', transition: 'all 0.15s ease', border: '1.5px solid #1a3a2a' };
        if ( variant === 'primary' ) return { ...base, background: '#d1f470', color: '#1a3a2a' };
        if ( variant === 'secondary' ) return { ...base, background: '#fff', color: '#111827' };
        if ( variant === 'ghost' ) return { ...base, background: 'transparent', color: '#6b7280', border: '1.5px solid #1a3a2a' };
        if ( variant === 'danger' ) return { ...base, background: '#fff', color: '#dc2626', border: '1.5px solid #dc2626' };
        if ( variant === 'danger-filled' ) return { ...base, background: '#dc2626', color: '#fff', border: '1.5px solid #dc2626' };
        if ( variant === 'disabled' ) return { ...base, background: '#fff', color: '#111827', opacity: 0.4, cursor: 'not-allowed' };
        return base;
    },
};

// ─── Section Components ───

const ColorsSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>1. Color Palette</h2>
        <p style={ { fontSize: 14, color: '#6b7280', marginBottom: 20 } }>
            Lime + Dark Green theme. White backgrounds, lime accents, dark green for text and active states.
        </p>
        <div style={ S.grid( 'repeat(auto-fill, minmax(160px, 1fr))' ) }>
            { Object.entries( COLORS ).map( ( [ key, c ] ) => (
                <div key={ key } style={ { textAlign: 'center' } }>
                    <div style={ S.swatch( c.value, c.text ) }>{ c.value }</div>
                    <div style={ { marginTop: 8, fontSize: 12, fontWeight: 600, color: '#111827' } }>{ c.label }</div>
                    <div style={ { fontSize: 11, color: '#9ca3af' } }>{ key }</div>
                </div>
            ) ) }
        </div>
        <div style={ S.note }>
            <strong>Usage Rules:</strong> Primary (#1a3a2a) for text, borders, active states. Lime (#d1f470) for CTA buttons, active tabs, accent borders. White for backgrounds. Never use raw colors — use CSS variables from tokens.css.
        </div>
    </div>
);

const TypographySection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>2. Typography</h2>
        <p style={ { fontSize: 14, color: '#6b7280', marginBottom: 20 } }>
            Font: Inter (system fallback). Clean, readable hierarchy.
        </p>
        <div style={ { overflow: 'auto' } }>
            <table style={ S.table }>
                <thead>
                    <tr>
                        <th style={ S.th }>Element</th>
                        <th style={ S.th }>Size</th>
                        <th style={ S.th }>Weight</th>
                        <th style={ S.th }>Sample</th>
                    </tr>
                </thead>
                <tbody>
                    { TYPOGRAPHY.map( ( t, i ) => (
                        <tr key={ i }>
                            <td style={ S.td }><strong>{ t.name }</strong></td>
                            <td style={ S.td }><code style={ S.code }>{ t.size }</code></td>
                            <td style={ S.td }>{ t.weight }</td>
                            <td style={ { ...S.td, fontSize: t.size, fontWeight: t.weight, fontFamily: t.name === 'Monospace' ? 'monospace' : 'inherit' } }>{ t.sample }</td>
                        </tr>
                    ) ) }
                </tbody>
            </table>
        </div>
        <div style={ S.note }>
            <strong>Best Practice:</strong> Use semantic heading levels (h1-h4). Page title = h1, section = h2, card title = h3. Never skip heading levels for accessibility.
        </div>
    </div>
);

const SpacingSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>3. Spacing & Layout</h2>
        <div style={ S.grid( '1fr 1fr' ) }>
            <div>
                <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12 } }>Spacing Scale</h3>
                { SPACING.map( ( s, i ) => (
                    <div key={ i } style={ { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 } }>
                        <code style={ { ...S.code, width: 100 } }>{ s.token }</code>
                        <div style={ { width: parseInt( s.value ), height: 16, background: '#d1f470', borderRadius: 4, border: '1px solid #1a3a2a' } } />
                        <span style={ { fontSize: 12, color: '#6b7280' } }>{ s.value }</span>
                    </div>
                ) ) }
            </div>
            <div>
                <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12 } }>Border Radius</h3>
                <table style={ S.table }>
                    <thead>
                        <tr>
                            <th style={ S.th }>Token</th>
                            <th style={ S.th }>Value</th>
                            <th style={ S.th }>Use</th>
                        </tr>
                    </thead>
                    <tbody>
                        { RADII.map( ( r, i ) => (
                            <tr key={ i }>
                                <td style={ S.td }><code style={ S.code }>{ r.token }</code></td>
                                <td style={ S.td }>{ r.value }</td>
                                <td style={ S.td }>{ r.use }</td>
                            </tr>
                        ) ) }
                    </tbody>
                </table>
            </div>
        </div>
        <div style={ S.note }>
            <strong>Layout:</strong> Max content width = 1400px. Sidebar = 240px. Page padding = 24px. Cards use 16px internal padding minimum.
        </div>
    </div>
);

const ButtonsSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>4. Buttons</h2>
        <p style={ { fontSize: 14, color: '#6b7280', marginBottom: 20 } }>
            All buttons: 13px border-radius, 44px min-height (touch target), 1.5px border.
        </p>

        <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12 } }>Variants</h3>
        <div style={ { ...S.row, marginBottom: 24 } }>
            <button style={ S.demoBtn( 'primary' ) }>Primary</button>
            <button style={ S.demoBtn( 'secondary' ) }>Secondary</button>
            <button style={ S.demoBtn( 'ghost' ) }>Ghost</button>
            <button style={ S.demoBtn( 'danger' ) }>Danger</button>
            <button style={ S.demoBtn( 'danger-filled' ) }>Danger Filled</button>
            <button style={ S.demoBtn( 'disabled' ) }>Disabled</button>
        </div>

        <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12 } }>Sizes</h3>
        <div style={ { ...S.row, marginBottom: 24 } }>
            <button style={ { ...S.demoBtn( 'secondary' ), height: 36, padding: '0 12px', fontSize: 12 } }>Small (36px)</button>
            <button style={ { ...S.demoBtn( 'secondary' ), height: 44, padding: '0 16px' } }>Medium (44px)</button>
            <button style={ { ...S.demoBtn( 'secondary' ), height: 52, padding: '0 24px', fontSize: 16 } }>Large (52px)</button>
        </div>

        <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12 } }>Icon Buttons</h3>
        <div style={ { ...S.row, marginBottom: 24 } }>
            <button style={ { ...S.demoBtn( 'secondary' ), width: 44, height: 44, padding: 0 } }>↻</button>
            <button style={ { ...S.demoBtn( 'secondary' ), width: 44, height: 44, padding: 0 } }>+</button>
            <button style={ { ...S.demoBtn( 'secondary' ), width: 44, height: 44, padding: 0 } }>✕</button>
            <button style={ { ...S.demoBtn( 'secondary' ), width: 44, height: 44, padding: 0 } }>🔍</button>
        </div>

        <div style={ { overflow: 'auto' } }>
            <table style={ S.table }>
                <thead>
                    <tr>
                        <th style={ S.th }>Variant</th>
                        <th style={ S.th }>Background</th>
                        <th style={ S.th }>Border</th>
                        <th style={ S.th }>Text</th>
                        <th style={ S.th }>Use Case</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td style={ S.td }>Primary</td><td style={ S.td }>#d1f470</td><td style={ S.td }>#1a3a2a</td><td style={ S.td }>#1a3a2a</td><td style={ S.td }>Main CTA (Send, Save, Create)</td></tr>
                    <tr><td style={ S.td }>Secondary</td><td style={ S.td }>#ffffff</td><td style={ S.td }>#1a3a2a</td><td style={ S.td }>#111827</td><td style={ S.td }>Secondary actions (Cancel, Edit)</td></tr>
                    <tr><td style={ S.td }>Ghost</td><td style={ S.td }>transparent</td><td style={ S.td }>#1a3a2a</td><td style={ S.td }>#6b7280</td><td style={ S.td }>Minimal actions (Close, Dismiss)</td></tr>
                    <tr><td style={ S.td }>Danger</td><td style={ S.td }>#ffffff</td><td style={ S.td }>#dc2626</td><td style={ S.td }>#dc2626</td><td style={ S.td }>Destructive (Delete, Remove)</td></tr>
                    <tr><td style={ S.td }>Danger Filled</td><td style={ S.td }>#dc2626</td><td style={ S.td }>#dc2626</td><td style={ S.td }>#ffffff</td><td style={ S.td }>Confirm delete</td></tr>
                </tbody>
            </table>
        </div>

        <div style={ S.note }>
            <strong>UX Rules:</strong> One primary button per section. Destructive actions require confirmation modal. All buttons must have min 44px touch target. Use loading spinner for async actions.
        </div>
    </div>
);

const InputsSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>5. Form Inputs</h2>
        <p style={ { fontSize: 14, color: '#6b7280', marginBottom: 20 } }>
            All inputs: 44px height, 13px radius, lime border, dark green focus ring.
        </p>
        <div style={ S.grid( '1fr 1fr' ) }>
            <div>
                <label style={ { display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 8 } }>Text Input</label>
                <input type="text" placeholder="Enter value..." style={ { width: '100%', height: 44, padding: '10px 12px', border: '1.5px solid #d1f470', borderRadius: 13, fontSize: 14, outline: 'none' } } readOnly />
            </div>
            <div>
                <label style={ { display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 8 } }>Search Input</label>
                <input type="search" placeholder="Search contacts..." style={ { width: '100%', height: 44, padding: '10px 12px', border: '1.5px solid #d1f470', borderRadius: 13, fontSize: 14, outline: 'none' } } readOnly />
            </div>
            <div>
                <label style={ { display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 8 } }>Select</label>
                <select style={ { width: '100%', height: 44, padding: '10px 12px', border: '1.5px solid #d1f470', borderRadius: 13, fontSize: 14, outline: 'none', background: '#fff' } }>
                    <option>Choose option...</option>
                    <option>WhatsApp</option>
                    <option>SMS</option>
                </select>
            </div>
            <div>
                <label style={ { display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 8 } }>Error State</label>
                <input type="text" value="Invalid input" style={ { width: '100%', height: 44, padding: '10px 12px', border: '1.5px solid #dc2626', borderRadius: 13, fontSize: 14, outline: 'none' } } readOnly />
                <span style={ { fontSize: 12, color: '#dc2626', marginTop: 4, display: 'block' } }>This field is required</span>
            </div>
            <div style={ { gridColumn: '1 / -1' } }>
                <label style={ { display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 8 } }>Textarea</label>
                <textarea placeholder="Type your message..." style={ { width: '100%', minHeight: 88, padding: '10px 12px', border: '1.5px solid #d1f470', borderRadius: 13, fontSize: 14, outline: 'none', resize: 'vertical' } } readOnly />
            </div>
        </div>
        <div style={ S.note }>
            <strong>States:</strong> Default (lime border) → Hover (dark green border) → Focus (dark green border + lime shadow ring) → Error (red border) → Disabled (50% opacity). Always use 16px font on mobile to prevent iOS zoom.
        </div>
    </div>
);

const CardsSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>6. Cards & Containers</h2>
        <div style={ S.grid( '1fr 1fr 1fr' ) }>
            {/* Stat Card */ }
            <div style={ { ...S.card, textAlign: 'center' } }>
                <div style={ { fontSize: 32, fontWeight: 700, color: '#111827' } }>1,247</div>
                <div style={ { fontSize: 12, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.5px', marginTop: 4 } }>Total Messages</div>
            </div>
            {/* Stat Card with accent */ }
            <div style={ { ...S.card, textAlign: 'center', borderLeft: '4px solid #d1f470' } }>
                <div style={ { fontSize: 32, fontWeight: 700, color: '#1a3a2a' } }>98.5%</div>
                <div style={ { fontSize: 12, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.5px', marginTop: 4 } }>Delivery Rate</div>
            </div>
            {/* Action Card */ }
            <div style={ { ...S.card, cursor: 'pointer' } }>
                <div style={ { fontSize: 24, marginBottom: 12 } }>📱</div>
                <div style={ { fontSize: 16, fontWeight: 600, color: '#111827', marginBottom: 4 } }>WhatsApp</div>
                <div style={ { fontSize: 13, color: '#6b7280' } }>Send messages via WhatsApp Business API</div>
            </div>
        </div>

        <h3 style={ { fontSize: 16, fontWeight: 600, margin: '24px 0 12px' } }>Card Variants</h3>
        <div style={ { overflow: 'auto' } }>
            <table style={ S.table }>
                <thead>
                    <tr>
                        <th style={ S.th }>Type</th>
                        <th style={ S.th }>Border</th>
                        <th style={ S.th }>Radius</th>
                        <th style={ S.th }>Hover</th>
                        <th style={ S.th }>Use</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td style={ S.td }>Stat Card</td><td style={ S.td }>1.5px #d1f470</td><td style={ S.td }>12px</td><td style={ S.td }>border → #1a3a2a</td><td style={ S.td }>KPI metrics</td></tr>
                    <tr><td style={ S.td }>Section Card</td><td style={ S.td }>1.5px #d1f470</td><td style={ S.td }>16px</td><td style={ S.td }>—</td><td style={ S.td }>Content sections</td></tr>
                    <tr><td style={ S.td }>Action Card</td><td style={ S.td }>1.5px #d1f470</td><td style={ S.td }>13px</td><td style={ S.td }>border → #1a3a2a, bg → #f9fafb</td><td style={ S.td }>Clickable navigation</td></tr>
                    <tr><td style={ S.td }>Feature Card</td><td style={ S.td }>1.5px #d1f470</td><td style={ S.td }>16px</td><td style={ S.td }>border → #1a3a2a, shadow</td><td style={ S.td }>Feature showcase</td></tr>
                    <tr><td style={ S.td }>Info Banner</td><td style={ S.td }>1.5px #d1f470</td><td style={ S.td }>13px</td><td style={ S.td }>—</td><td style={ S.td }>Informational notices</td></tr>
                </tbody>
            </table>
        </div>
    </div>
);

const TablesSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>7. Tables</h2>
        <p style={ { fontSize: 14, color: '#6b7280', marginBottom: 20 } }>
            Tables: 2px lime border, lime header background, hover rows.
        </p>
        <div style={ { overflow: 'auto', border: '2px solid #d1f470', borderRadius: 16 } }>
            <table style={ { ...S.table, border: 'none' } }>
                <thead>
                    <tr>
                        <th style={ S.th }>Contact</th>
                        <th style={ S.th }>Phone</th>
                        <th style={ S.th }>Channel</th>
                        <th style={ S.th }>Status</th>
                        <th style={ S.th }>Last Message</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style={ S.td }><strong>Rahul Sharma</strong></td>
                        <td style={ { ...S.td, fontFamily: 'monospace' } }>+91 98765 43210</td>
                        <td style={ S.td }>WhatsApp</td>
                        <td style={ S.td }><span style={ S.badge( '#f9fafb', '#1a3a2a' ) }>Active</span></td>
                        <td style={ S.td }>2 min ago</td>
                    </tr>
                    <tr>
                        <td style={ S.td }><strong>Priya Patel</strong></td>
                        <td style={ { ...S.td, fontFamily: 'monospace' } }>+91 87654 32109</td>
                        <td style={ S.td }>SMS</td>
                        <td style={ S.td }><span style={ S.badge( '#fef2f2', '#dc2626' ) }>Failed</span></td>
                        <td style={ S.td }>1 hour ago</td>
                    </tr>
                    <tr>
                        <td style={ S.td }><strong>Amit Kumar</strong></td>
                        <td style={ { ...S.td, fontFamily: 'monospace' } }>+91 76543 21098</td>
                        <td style={ S.td }>RCS</td>
                        <td style={ S.td }><span style={ S.badge( '#d1f470', '#1a3a2a' ) }>Delivered</span></td>
                        <td style={ S.td }>5 min ago</td>
                    </tr>
                </tbody>
            </table>
        </div>
        <div style={ S.note }>
            <strong>Table Rules:</strong> Always wrap in overflow-x container for mobile. Min-width 600px. Header: lime bg, uppercase, 12px. Rows: hover #f9fafb. Use monospace for phone numbers, IDs, ARNs.
        </div>
    </div>
);

const TabsSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>8. Tabs & Navigation</h2>
        <p style={ { fontSize: 14, color: '#6b7280', marginBottom: 20 } }>
            Tabs: Contained in lime-bordered pill container. Active = lime fill.
        </p>

        <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12 } }>Main Tabs</h3>
        <div style={ { display: 'flex', gap: 8, padding: '12px 16px', background: '#f9fafb', borderRadius: 14, border: '2px solid #d1f470', marginBottom: 24, overflowX: 'auto' } }>
            <button style={ { padding: '10px 18px', borderRadius: 10, border: '1.5px solid transparent', background: '#d1f470', color: '#1a3a2a', fontWeight: 600, fontSize: 14, cursor: 'pointer' } }>Overview</button>
            <button style={ { padding: '10px 18px', borderRadius: 10, border: '1.5px solid transparent', background: 'transparent', color: '#6b7280', fontWeight: 500, fontSize: 14, cursor: 'pointer' } }>Messages</button>
            <button style={ { padding: '10px 18px', borderRadius: 10, border: '1.5px solid transparent', background: 'transparent', color: '#6b7280', fontWeight: 500, fontSize: 14, cursor: 'pointer' } }>Pay</button>
            <button style={ { padding: '10px 18px', borderRadius: 10, border: '1.5px solid transparent', background: 'transparent', color: '#6b7280', fontWeight: 500, fontSize: 14, cursor: 'pointer' } }>Billing</button>
        </div>

        <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12 } }>Sub-Tabs</h3>
        <div style={ { display: 'flex', gap: 8, padding: '4px', background: '#f9fafb', borderRadius: 14, marginBottom: 24 } }>
            <button style={ { padding: '8px 14px', borderRadius: 10, border: '1.5px solid transparent', background: '#d1f470', color: '#1a3a2a', fontWeight: 600, fontSize: 13, cursor: 'pointer' } }>All</button>
            <button style={ { padding: '8px 14px', borderRadius: 10, border: '1.5px solid transparent', background: 'transparent', color: '#6b7280', fontWeight: 500, fontSize: 13, cursor: 'pointer' } }>Sent</button>
            <button style={ { padding: '8px 14px', borderRadius: 10, border: '1.5px solid transparent', background: 'transparent', color: '#6b7280', fontWeight: 500, fontSize: 13, cursor: 'pointer' } }>Received</button>
            <button style={ { padding: '8px 14px', borderRadius: 10, border: '1.5px solid transparent', background: 'transparent', color: '#6b7280', fontWeight: 500, fontSize: 13, cursor: 'pointer' } }>Failed</button>
        </div>

        <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12 } }>Sidebar Navigation</h3>
        <div style={ { background: '#1a3a2a', borderRadius: 16, padding: 16, maxWidth: 260 } }>
            <div style={ { padding: '10px 14px', borderRadius: 8, background: 'rgba(209,244,112,0.3)', borderLeft: '3px solid #d1f470', color: '#fff', fontSize: 14, fontWeight: 500, marginBottom: 4 } }>Dashboard</div>
            <div style={ { padding: '10px 14px', borderRadius: 8, color: 'rgba(255,255,255,0.7)', fontSize: 14, fontWeight: 400, marginBottom: 4 } }>Messages</div>
            <div style={ { padding: '10px 14px', borderRadius: 8, color: 'rgba(255,255,255,0.7)', fontSize: 14, fontWeight: 400, marginBottom: 4 } }>Pay</div>
            <div style={ { padding: '10px 14px', borderRadius: 8, color: 'rgba(255,255,255,0.7)', fontSize: 14, fontWeight: 400 } }>Contacts</div>
        </div>
    </div>
);

const BadgesSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>9. Badges & Pills</h2>
        <div style={ { ...S.row, marginBottom: 24 } }>
            <span style={ S.badge( '#d1f470', '#1a3a2a' ) }>Active</span>
            <span style={ S.badge( '#f9fafb', '#1a3a2a' ) }>Delivered</span>
            <span style={ S.badge( '#fef2f2', '#dc2626' ) }>Failed</span>
            <span style={ S.badge( '#1a3a2a', '#ffffff' ) }>Error</span>
            <span style={ S.badge( '#e5e7eb', '#374151' ) }>Pending</span>
            <span style={ S.badge( '#fff', '#6b7280' ) }>Draft</span>
        </div>
        <div style={ { overflow: 'auto' } }>
            <table style={ S.table }>
                <thead>
                    <tr>
                        <th style={ S.th }>Badge</th>
                        <th style={ S.th }>Background</th>
                        <th style={ S.th }>Text</th>
                        <th style={ S.th }>Use Case</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td style={ S.td }>Success/Active</td><td style={ S.td }>#d1f470</td><td style={ S.td }>#1a3a2a</td><td style={ S.td }>Active, delivered, online</td></tr>
                    <tr><td style={ S.td }>Neutral</td><td style={ S.td }>#f9fafb</td><td style={ S.td }>#1a3a2a</td><td style={ S.td }>Info, read, completed</td></tr>
                    <tr><td style={ S.td }>Danger</td><td style={ S.td }>#fef2f2</td><td style={ S.td }>#dc2626</td><td style={ S.td }>Failed, error, rejected</td></tr>
                    <tr><td style={ S.td }>Dark</td><td style={ S.td }>#1a3a2a</td><td style={ S.td }>#ffffff</td><td style={ S.td }>Critical error badge</td></tr>
                    <tr><td style={ S.td }>Muted</td><td style={ S.td }>#e5e7eb</td><td style={ S.td }>#374151</td><td style={ S.td }>Pending, queued</td></tr>
                </tbody>
            </table>
        </div>
        <div style={ S.note }>
            <strong>Badge Rules:</strong> Padding 3px 10px, border-radius 10px, font-size 11px, font-weight 600. Always uppercase for status badges.
        </div>
    </div>
);

const ToastsSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>10. Toasts & Alerts</h2>
        <div style={ { display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 400 } }>
            {/* Success Toast */ }
            <div style={ { display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: '#fff', borderRadius: 13, border: '1.5px solid #d1f470', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' } }>
                <div style={ { width: 24, height: 24, borderRadius: '50%', background: '#d1f470', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#1a3a2a' } }>✓</div>
                <span style={ { flex: 1, fontSize: 14, color: '#111827' } }>Message sent successfully</span>
                <button style={ { background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: 16 } }>✕</button>
            </div>
            {/* Error Toast */ }
            <div style={ { display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: '#fff', borderRadius: 13, border: '1.5px solid #dc2626', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' } }>
                <div style={ { width: 24, height: 24, borderRadius: '50%', background: '#fef2f2', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#dc2626' } }>!</div>
                <span style={ { flex: 1, fontSize: 14, color: '#111827' } }>Failed to send message</span>
                <button style={ { background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: 16 } }>✕</button>
            </div>
            {/* Warning Toast */ }
            <div style={ { display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: '#fff', borderRadius: 13, border: '1.5px solid #d1f470', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' } }>
                <div style={ { width: 24, height: 24, borderRadius: '50%', background: '#f9fafb', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#1a3a2a' } }>⚠</div>
                <span style={ { flex: 1, fontSize: 14, color: '#111827' } }>Rate limit approaching</span>
                <button style={ { background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: 16 } }>✕</button>
            </div>
        </div>
        <div style={ S.note }>
            <strong>Toast Rules:</strong> Position: top-right. Auto-dismiss: 5s for success, 8s for error. Animation: slide-in from right. Max 3 visible at once. Always include close button.
        </div>
    </div>
);

const EmptyStatesSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>11. Empty States</h2>
        <div style={ S.grid( '1fr 1fr' ) }>
            <div style={ { ...S.card, textAlign: 'center', padding: '48px 24px' } }>
                <div style={ { width: 80, height: 80, margin: '0 auto 16px', background: '#f9fafb', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 32 } }>📭</div>
                <h3 style={ { margin: '0 0 8px', fontSize: 18, fontWeight: 600, color: '#111827' } }>No messages yet</h3>
                <p style={ { margin: '0 0 20px', fontSize: 14, color: '#6b7280' } }>Send your first WhatsApp message to get started.</p>
                <button style={ S.demoBtn( 'primary' ) }>Send Message</button>
            </div>
            <div style={ { ...S.card, textAlign: 'center', padding: '48px 24px' } }>
                <div style={ { width: 80, height: 80, margin: '0 auto 16px', background: '#f9fafb', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 32 } }>🔍</div>
                <h3 style={ { margin: '0 0 8px', fontSize: 18, fontWeight: 600, color: '#111827' } }>No results found</h3>
                <p style={ { margin: '0 0 20px', fontSize: 14, color: '#6b7280' } }>Try adjusting your search or filter criteria.</p>
                <button style={ S.demoBtn( 'secondary' ) }>Clear Filters</button>
            </div>
        </div>
        <div style={ S.note }>
            <strong>Empty State Rules:</strong> Always include: icon (80px circle), title, description, and a CTA button. Center-aligned. Padding 48px top/bottom.
        </div>
    </div>
);

const LoadingSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>12. Loading States</h2>
        <div style={ S.grid( '1fr 1fr 1fr' ) }>
            {/* Skeleton Card */ }
            <div style={ S.card }>
                <div style={ { height: 16, width: '60%', background: '#f5f5f5', borderRadius: 4, marginBottom: 12, animation: 'pulse 1.5s ease-in-out infinite' } } />
                <div style={ { height: 32, width: '40%', background: '#f5f5f5', borderRadius: 4, marginBottom: 8 } } />
                <div style={ { height: 12, width: '80%', background: '#f5f5f5', borderRadius: 4 } } />
            </div>
            {/* Spinner */ }
            <div style={ { ...S.card, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 } }>
                <div style={ { width: 32, height: 32, border: '3px solid #f3f4f6', borderTop: '3px solid #1a3a2a', borderRadius: '50%', animation: 'spin 0.8s linear infinite' } } />
                <span style={ { fontSize: 13, color: '#6b7280' } }>Loading...</span>
            </div>
            {/* Button Loading */ }
            <div style={ { ...S.card, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 } }>
                <button style={ { ...S.demoBtn( 'primary' ), opacity: 0.7 } }>
                    <span style={ { width: 16, height: 16, border: '2px solid rgba(26,58,42,0.3)', borderTop: '2px solid #1a3a2a', borderRadius: '50%', display: 'inline-block' } } />
                    Sending...
                </button>
            </div>
        </div>
        <div style={ S.note }>
            <strong>Loading Rules:</strong> Use skeleton screens for initial page load. Use spinner for data refresh. Use button loading state for form submissions. Always show loading within 100ms of action.
        </div>
    </div>
);

const ModalsSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>13. Modals</h2>
        <div style={ { background: 'rgba(0,0,0,0.3)', borderRadius: 16, padding: 40, display: 'flex', alignItems: 'center', justifyContent: 'center' } }>
            <div style={ { background: '#fff', borderRadius: 16, padding: 24, maxWidth: 400, width: '100%', boxShadow: '0 20px 40px rgba(0,0,0,0.2)' } }>
                <div style={ { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 } }>
                    <h3 style={ { margin: 0, fontSize: 18, fontWeight: 600 } }>Confirm Delete</h3>
                    <button style={ { background: 'none', border: 'none', fontSize: 20, color: '#6b7280', cursor: 'pointer' } }>✕</button>
                </div>
                <p style={ { fontSize: 14, color: '#6b7280', margin: '0 0 24px' } }>Are you sure you want to delete this contact? This action cannot be undone.</p>
                <div style={ { display: 'flex', gap: 12, justifyContent: 'flex-end' } }>
                    <button style={ S.demoBtn( 'secondary' ) }>Cancel</button>
                    <button style={ S.demoBtn( 'danger-filled' ) }>Delete</button>
                </div>
            </div>
        </div>
        <div style={ S.note }>
            <strong>Modal Rules:</strong> Max-width 480px. Border-radius 16px. Overlay: rgba(0,0,0,0.5). Always include close button. Trap focus inside modal. ESC key to close. Animate: fade + slide-up.
        </div>
    </div>
);

const IconsSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>14. Icons</h2>
        <p style={ { fontSize: 14, color: '#6b7280', marginBottom: 20 } }>
            Stroke-based SVG icons. 1.5px stroke width. Sizes: 14px (sm), 16px (md), 18px (lg), 20px (xl).
        </p>
        <div style={ S.grid( 'repeat(auto-fill, minmax(100px, 1fr))' ) }>
            { [ '↻ Refresh', '+ Create', '✕ Close', '🔍 Search', '✏️ Edit', '🗑️ Delete', '▶ Play', '⏸ Pause', '📱 WhatsApp', '💬 SMS', '📧 Email', '🔔 Push', '💳 Pay', '👤 Contact', '📊 Chart', '⚙️ Settings' ].map( ( icon, i ) => (
                <div key={ i } style={ { textAlign: 'center', padding: 12, background: '#f9fafb', borderRadius: 12, border: '1px solid #e5e7eb' } }>
                    <div style={ { fontSize: 20, marginBottom: 4 } }>{ icon.split( ' ' )[ 0 ] }</div>
                    <div style={ { fontSize: 11, color: '#6b7280' } }>{ icon.split( ' ' )[ 1 ] }</div>
                </div>
            ) ) }
        </div>
        <div style={ S.note }>
            <strong>Icon Rules:</strong> Use stroke-based SVGs (not filled). Color inherits from parent. Always pair with aria-label for accessibility. Icon-only buttons need explicit aria-label and title attributes.
        </div>
    </div>
);

const ResponsiveSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>15. Responsive Breakpoints</h2>
        <div style={ { overflow: 'auto' } }>
            <table style={ S.table }>
                <thead>
                    <tr>
                        <th style={ S.th }>Breakpoint</th>
                        <th style={ S.th }>Width</th>
                        <th style={ S.th }>Grid Columns</th>
                        <th style={ S.th }>Page Padding</th>
                        <th style={ S.th }>Notes</th>
                    </tr>
                </thead>
                <tbody>
                    { BREAKPOINTS.map( ( bp, i ) => (
                        <tr key={ i }>
                            <td style={ S.td }><strong>{ bp.name }</strong></td>
                            <td style={ S.td }><code style={ S.code }>{ bp.value }</code></td>
                            <td style={ S.td }>{ bp.columns }</td>
                            <td style={ S.td }>{ bp.padding }</td>
                            <td style={ S.td }>{ i === 0 ? 'Stack everything, full-width buttons' : i === 1 ? '2-col grid, collapsible sidebar' : i === 2 ? 'Sidebar overlay' : i === 3 ? 'Full layout' : 'Centered max-width 1400px' }</td>
                        </tr>
                    ) ) }
                </tbody>
            </table>
        </div>
        <div style={ S.note }>
            <strong>Mobile Rules:</strong> Min touch target 44px. Font-size 16px on inputs (prevent iOS zoom). Stack grids to 1 column. Full-width CTAs. Hide sidebar behind hamburger. Safe area insets for notch devices.
        </div>
    </div>
);

const AccessibilitySection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>16. Accessibility (WCAG 2.1 AA)</h2>
        <div style={ S.grid( '1fr 1fr' ) }>
            <div style={ S.card }>
                <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12 } }>✅ Requirements Met</h3>
                <ul style={ { margin: 0, padding: '0 0 0 20px', fontSize: 13, color: '#374151', lineHeight: 2 } }>
                    <li>Min 44px touch targets on all interactive elements</li>
                    <li>Focus-visible ring (3px rgba(26,58,42,0.3)) on all focusable elements</li>
                    <li>Semantic HTML (headings, landmarks, lists)</li>
                    <li>Color contrast: #1a3a2a on #fff = 12.6:1 ✓</li>
                    <li>Color contrast: #6b7280 on #fff = 5.0:1 ✓</li>
                    <li>Keyboard navigation support (Tab, Enter, Escape)</li>
                    <li>aria-label on icon-only buttons</li>
                    <li>prefers-reduced-motion support</li>
                    <li>lang="en" on document</li>
                </ul>
            </div>
            <div style={ S.card }>
                <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12 } }>⚠️ Improvements Needed</h3>
                <ul style={ { margin: 0, padding: '0 0 0 20px', fontSize: 13, color: '#374151', lineHeight: 2 } }>
                    <li>Change lang="en" → lang="en-IN" for locale targeting</li>
                    <li>Add skip-to-content link</li>
                    <li>Add aria-live regions for toast notifications</li>
                    <li>Add role="alert" on error messages</li>
                    <li>Ensure modal focus trap (currently partial)</li>
                    <li>Add aria-expanded on collapsible sidebar items</li>
                    <li>Add aria-current="page" on active nav items</li>
                    <li>Test with screen readers (NVDA, VoiceOver)</li>
                </ul>
            </div>
        </div>
        <div style={ S.note }>
            <strong>Note:</strong> Full WCAG compliance requires manual testing with assistive technologies and expert accessibility review.
        </div>
    </div>
);

const MotionSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>17. Motion & Transitions</h2>
        <div style={ { overflow: 'auto' } }>
            <table style={ S.table }>
                <thead>
                    <tr>
                        <th style={ S.th }>Token</th>
                        <th style={ S.th }>Duration</th>
                        <th style={ S.th }>Easing</th>
                        <th style={ S.th }>Use Case</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td style={ S.td }>--transition-fast</td><td style={ S.td }>100ms</td><td style={ S.td }>ease</td><td style={ S.td }>Button press, checkbox toggle</td></tr>
                    <tr><td style={ S.td }>--transition-normal</td><td style={ S.td }>150ms</td><td style={ S.td }>ease</td><td style={ S.td }>Hover states, border color changes</td></tr>
                    <tr><td style={ S.td }>--transition-slow</td><td style={ S.td }>250ms</td><td style={ S.td }>cubic-bezier(0.16, 1, 0.3, 1)</td><td style={ S.td }>Modal open, sidebar expand</td></tr>
                    <tr><td style={ S.td }>Toast enter</td><td style={ S.td }>200ms</td><td style={ S.td }>ease</td><td style={ S.td }>Slide in from right</td></tr>
                    <tr><td style={ S.td }>Toast exit</td><td style={ S.td }>200ms</td><td style={ S.td }>ease</td><td style={ S.td }>Slide out to right</td></tr>
                    <tr><td style={ S.td }>Skeleton pulse</td><td style={ S.td }>1500ms</td><td style={ S.td }>ease-in-out (infinite)</td><td style={ S.td }>Loading skeleton animation</td></tr>
                    <tr><td style={ S.td }>Spinner</td><td style={ S.td }>800ms</td><td style={ S.td }>linear (infinite)</td><td style={ S.td }>Loading spinner rotation</td></tr>
                </tbody>
            </table>
        </div>
        <div style={ S.note }>
            <strong>Motion Rules:</strong> Respect prefers-reduced-motion. No animation longer than 300ms for UI feedback. Use transform for performance (not top/left). Button active: scale(0.98).
        </div>
    </div>
);

const TemplatesSection = () => (
    <div style={ S.section }>
        <h2 style={ S.sectionTitle }>18. Page Templates</h2>
        <p style={ { fontSize: 14, color: '#6b7280', marginBottom: 20 } }>
            Standard page layouts used across the platform.
        </p>
        <div style={ S.grid( '1fr 1fr' ) }>
            <div style={ S.card }>
                <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 8 } }>📊 Dashboard Page</h3>
                <p style={ { fontSize: 13, color: '#6b7280', marginBottom: 12 } }>Stats grid + tabbed content</p>
                <div style={ { background: '#f9fafb', borderRadius: 8, padding: 12, fontSize: 11, fontFamily: 'monospace', color: '#374151' } }>
                    { '<Layout>' }<br />
                    { '  <SEO />' }<br />
                    { '  <PageHeader title + actions />' }<br />
                    { '  <StatsGrid 4-col />' }<br />
                    { '  <Tabs>' }<br />
                    { '    <TabContent />' }<br />
                    { '  </Tabs>' }<br />
                    { '</Layout>' }
                </div>
            </div>
            <div style={ S.card }>
                <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 8 } }>📝 Form Page</h3>
                <p style={ { fontSize: 13, color: '#6b7280', marginBottom: 12 } }>Input form + preview</p>
                <div style={ { background: '#f9fafb', borderRadius: 8, padding: 12, fontSize: 11, fontFamily: 'monospace', color: '#374151' } }>
                    { '<Layout>' }<br />
                    { '  <SEO />' }<br />
                    { '  <PageHeader title />' }<br />
                    { '  <Grid 2-col>' }<br />
                    { '    <FormSection inputs />' }<br />
                    { '    <PreviewCard />' }<br />
                    { '  </Grid>' }<br />
                    { '</Layout>' }
                </div>
            </div>
            <div style={ S.card }>
                <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 8 } }>💬 Messaging Page</h3>
                <p style={ { fontSize: 13, color: '#6b7280', marginBottom: 12 } }>Split view: contacts + chat</p>
                <div style={ { background: '#f9fafb', borderRadius: 8, padding: 12, fontSize: 11, fontFamily: 'monospace', color: '#374151' } }>
                    { '<Layout>' }<br />
                    { '  <SEO />' }<br />
                    { '  <SplitView>' }<br />
                    { '    <ContactsSidebar />' }<br />
                    { '    <ChatArea>' }<br />
                    { '      <MessageList />' }<br />
                    { '      <ComposeBar />' }<br />
                    { '    </ChatArea>' }<br />
                    { '  </SplitView>' }<br />
                    { '</Layout>' }
                </div>
            </div>
            <div style={ S.card }>
                <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 8 } }>📋 List/Table Page</h3>
                <p style={ { fontSize: 13, color: '#6b7280', marginBottom: 12 } }>Filters + data table + pagination</p>
                <div style={ { background: '#f9fafb', borderRadius: 8, padding: 12, fontSize: 11, fontFamily: 'monospace', color: '#374151' } }>
                    { '<Layout>' }<br />
                    { '  <SEO />' }<br />
                    { '  <PageHeader title + create btn />' }<br />
                    { '  <FilterBar search + selects />' }<br />
                    { '  <Table data />' }<br />
                    { '  <Pagination />' }<br />
                    { '</Layout>' }
                </div>
            </div>
        </div>
        <div style={ S.note }>
            <strong>Template Rules:</strong> Every page must use Layout wrapper. Every page must include SEO component. Use consistent page header pattern. Stats grid for KPI pages. Tabbed layout for multi-section pages.
        </div>
    </div>
);

// ─── Main Page Component ───
const DesignReferencePage: React.FC<PageProps> = ( { signOut, user } ) => {
    const [ activeTab, setActiveTab ] = useState( 'colors' );

    const renderSection = () => {
        switch ( activeTab )
        {
            case 'colors': return <ColorsSection />;
            case 'typography': return <TypographySection />;
            case 'spacing': return <SpacingSection />;
            case 'buttons': return <ButtonsSection />;
            case 'inputs': return <InputsSection />;
            case 'cards': return <CardsSection />;
            case 'tables': return <TablesSection />;
            case 'tabs': return <TabsSection />;
            case 'badges': return <BadgesSection />;
            case 'toasts': return <ToastsSection />;
            case 'empty': return <EmptyStatesSection />;
            case 'loading': return <LoadingSection />;
            case 'modals': return <ModalsSection />;
            case 'icons': return <IconsSection />;
            case 'responsive': return <ResponsiveSection />;
            case 'a11y': return <AccessibilitySection />;
            case 'motion': return <MotionSection />;
            case 'templates': return <TemplatesSection />;
            default: return <ColorsSection />;
        }
    };

    return (
        <Layout user={ user } onSignOut={ signOut }>
            <SEO
                title="Design Reference | WECARE.DIGITAL"
                description="Complete inner page design system reference — colors, typography, components, patterns, and UX best practices."
                noindex={ true }
            />
            <div style={ S.page }>
                {/* Header */ }
                <div style={ S.header }>
                    <h1 style={ S.title }>Design Reference</h1>
                    <p style={ S.subtitle }>
                        Complete inner page design system — Lime + Dark Green theme. 18 sections covering every UI pattern.
                    </p>
                </div>

                {/* Tab Navigation */ }
                <div style={ S.tabs }>
                    { TABS_LIST.map( tab => (
                        <button
                            key={ tab.id }
                            onClick={ () => setActiveTab( tab.id ) }
                            style={ S.tab( activeTab === tab.id ) }
                        >
                            { tab.label }
                        </button>
                    ) ) }
                </div>

                {/* Active Section */ }
                { renderSection() }

                {/* Footer Summary */ }
                <div style={ { ...S.card, marginTop: 40, background: '#f9fafb' } }>
                    <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12, color: '#1a3a2a' } }>📋 Design System Summary</h3>
                    <div style={ S.grid( '1fr 1fr 1fr' ) }>
                        <div>
                            <strong style={ { fontSize: 13 } }>Colors</strong>
                            <ul style={ { margin: '4px 0 0', padding: '0 0 0 16px', fontSize: 12, color: '#6b7280', lineHeight: 1.8 } }>
                                <li>Primary: #1a3a2a</li>
                                <li>Accent: #d1f470</li>
                                <li>Danger: #dc2626</li>
                                <li>Background: #ffffff / #f9fafb</li>
                            </ul>
                        </div>
                        <div>
                            <strong style={ { fontSize: 13 } }>Key Dimensions</strong>
                            <ul style={ { margin: '4px 0 0', padding: '0 0 0 16px', fontSize: 12, color: '#6b7280', lineHeight: 1.8 } }>
                                <li>Button radius: 13px</li>
                                <li>Min touch target: 44px</li>
                                <li>Border width: 1.5px</li>
                                <li>Max content: 1400px</li>
                            </ul>
                        </div>
                        <div>
                            <strong style={ { fontSize: 13 } }>Files</strong>
                            <ul style={ { margin: '4px 0 0', padding: '0 0 0 16px', fontSize: 12, color: '#6b7280', lineHeight: 1.8 } }>
                                <li>tokens.css — Variables</li>
                                <li>inner-ux.css — Components</li>
                                <li>inner-pages.css — Overrides</li>
                                <li>Dashboard.css — Dashboard</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            {/* Inline keyframes for demo */ }
            <style>{ `
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
        </Layout>
    );
};

export default DesignReferencePage;
