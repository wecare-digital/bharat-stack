/**
 * Design Reference — WECARE.DIGITAL
 * Complete inner page design system — ALL sections visible on one scrollable page.
 * URL: /dashboard/design-reference
 * 
 * Shows EVERYTHING: colors, typography, spacing, buttons, inputs, cards,
 * tables, tabs, badges, toasts, empty states, loading, modals, icons,
 * responsive, accessibility, motion, page templates, shadows, and real screenshots.
 */

import React from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';

interface PageProps { signOut?: () => void; user?: any; }

// ─── All design tokens inline to avoid CSS override issues ───
const C = {
    primary: '#1a3a2a',
    primaryHover: '#0f2a1d',
    lime: '#d1f470',
    limeHover: '#c5e866',
    white: '#ffffff',
    bg2: '#f9fafb',
    bgHover: '#f5f5f5',
    text: '#111827',
    text2: '#6b7280',
    textMuted: '#9ca3af',
    border: '#e5e7eb',
    borderDark: '#d1d5db',
    danger: '#dc2626',
    dangerLight: '#fef2f2',
};

const DesignReferencePage: React.FC<PageProps> = ( { signOut, user } ) => {
    return (
        <Layout user={ user } onSignOut={ signOut }>
            <SEO title="Design Reference | WECARE.DIGITAL" description="Complete design system reference" noindex={ true } />
            <div className="inner-page" style={ { padding: 0, overflow: 'auto', background: '#fff' } }>
                <div style={ { maxWidth: 1400, margin: '0 auto', padding: '32px 24px' } }>

                    {/* ═══════════════════════════════════════════════════════════════
              HEADER
          ═══════════════════════════════════════════════════════════════ */}
                    <div style={ { marginBottom: 48, borderBottom: `3px solid ${C.lime}`, paddingBottom: 24 } }>
                        <h1 style={ { fontSize: 34, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>
                            Design Reference — WECARE.DIGITAL
                        </h1>
                        <p style={ { fontSize: 15, color: C.text2, margin: 0 } }>
                            Complete inner page design system. Lime + Dark Green theme. Every component, token, and pattern documented below.
                        </p>
                        <div style={ { marginTop: 16, display: 'flex', gap: 8, flexWrap: 'wrap' } }>
                            <span style={ { padding: '4px 12px', borderRadius: 20, background: C.lime, color: C.primary, fontSize: 12, fontWeight: 600 } }>v3.0</span>
                            <span style={ { padding: '4px 12px', borderRadius: 20, background: C.bg2, color: C.text2, fontSize: 12, fontWeight: 500 } }>18 Sections</span>
                            <span style={ { padding: '4px 12px', borderRadius: 20, background: C.bg2, color: C.text2, fontSize: 12, fontWeight: 500 } }>WCAG 2.1 AA</span>
                            <span style={ { padding: '4px 12px', borderRadius: 20, background: C.bg2, color: C.text2, fontSize: 12, fontWeight: 500 } }>Mobile-First</span>
                        </div>
                    </div>

                    {/* ═══════════════════════════════════════════════════════════════
              1. COLOR PALETTE
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>1. Color Palette</h2>
                        <p style={ { fontSize: 14, color: C.text2, marginBottom: 20 } }>Lime + Dark Green on white. Minimal, professional, high contrast.</p>

                        <div style={ { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 12 } }>
                            { [
                                { name: 'Primary', hex: '#1a3a2a', fg: '#fff' },
                                { name: 'Primary Hover', hex: '#0f2a1d', fg: '#fff' },
                                { name: 'Lime', hex: '#d1f470', fg: '#1a3a2a' },
                                { name: 'Lime Hover', hex: '#c5e866', fg: '#1a3a2a' },
                                { name: 'White', hex: '#ffffff', fg: '#111827' },
                                { name: 'BG Secondary', hex: '#f9fafb', fg: '#111827' },
                                { name: 'BG Hover', hex: '#f5f5f5', fg: '#111827' },
                                { name: 'Text Primary', hex: '#111827', fg: '#fff' },
                                { name: 'Text Secondary', hex: '#6b7280', fg: '#fff' },
                                { name: 'Text Muted', hex: '#9ca3af', fg: '#111827' },
                                { name: 'Border', hex: '#e5e7eb', fg: '#111827' },
                                { name: 'Border Dark', hex: '#d1d5db', fg: '#111827' },
                                { name: 'Danger', hex: '#dc2626', fg: '#fff' },
                                { name: 'Danger Light', hex: '#fef2f2', fg: '#dc2626' },
                            ].map( ( c, i ) => (
                                <div key={ i } style={ { textAlign: 'center' } }>
                                    <div style={ { width: '100%', height: 72, borderRadius: 12, background: c.hex, display: 'flex', alignItems: 'center', justifyContent: 'center', color: c.fg, fontSize: 11, fontWeight: 600, border: '1px solid #e5e7eb' } }>{ c.hex }</div>
                                    <div style={ { marginTop: 6, fontSize: 12, fontWeight: 600, color: '#111827' } }>{ c.name }</div>
                                </div>
                            ) ) }
                        </div>

                        <div style={ { marginTop: 16, background: C.bg2, border: `1.5px solid ${C.lime}`, borderRadius: 13, padding: '12px 16px', fontSize: 13, color: '#374151' } }>
                            <strong>Rules:</strong> Primary for text/borders/active. Lime for CTAs/active tabs/accent borders. White for backgrounds. Danger only for errors/destructive. Use CSS variables from <code style={ { background: '#e5e7eb', padding: '1px 4px', borderRadius: 3 } }>tokens.css</code>.
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              2. TYPOGRAPHY
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>2. Typography</h2>
                        <p style={ { fontSize: 14, color: C.text2, marginBottom: 20 } }>Font: Inter. System fallback stack. Clean hierarchy.</p>

                        <div style={ { border: `2px solid ${C.lime}`, borderRadius: 16, overflow: 'hidden' } }>
                            <table style={ { width: '100%', borderCollapse: 'collapse', fontSize: 13 } }>
                                <thead>
                                    <tr style={ { background: C.lime } }>
                                        <th style={ { padding: '12px 16px', textAlign: 'left', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', color: C.primary } }>Element</th>
                                        <th style={ { padding: '12px 16px', textAlign: 'left', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', color: C.primary } }>Size</th>
                                        <th style={ { padding: '12px 16px', textAlign: 'left', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', color: C.primary } }>Weight</th>
                                        <th style={ { padding: '12px 16px', textAlign: 'left', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', color: C.primary } }>Preview</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    { [
                                        { el: 'Page Title (h1)', size: '28px', weight: '700', preview: 'Dashboard Overview' },
                                        { el: 'Section Title (h2)', size: '20px', weight: '600', preview: 'Recent Activity' },
                                        { el: 'Card Title (h3)', size: '16px', weight: '600', preview: 'WhatsApp Messages' },
                                        { el: 'Body Text', size: '14px', weight: '400', preview: 'The quick brown fox jumps over the lazy dog.' },
                                        { el: 'Button Label', size: '14px', weight: '500', preview: 'Send Message' },
                                        { el: 'Table Cell', size: '13px', weight: '400', preview: '+91 98765 43210' },
                                        { el: 'Caption / Label', size: '12px', weight: '600', preview: 'TOTAL MESSAGES' },
                                        { el: 'Monospace', size: '12px', weight: '400', preview: 'arn:aws:lambda:ap-south-1:*' },
                                    ].map( ( t, i ) => (
                                        <tr key={ i } style={ { borderBottom: '1px solid #f3f4f6' } }>
                                            <td style={ { padding: '12px 16px', fontWeight: 500 } }>{ t.el }</td>
                                            <td style={ { padding: '12px 16px' } }><code style={ { background: '#f9fafb', padding: '2px 6px', borderRadius: 4, fontSize: 11 } }>{ t.size }</code></td>
                                            <td style={ { padding: '12px 16px' } }>{ t.weight }</td>
                                            <td style={ { padding: '12px 16px', fontSize: t.size, fontWeight: parseInt( t.weight ), fontFamily: t.el.includes( 'Mono' ) ? 'monospace' : 'inherit' } }>{ t.preview }</td>
                                        </tr>
                                    ) ) }
                                </tbody>
                            </table>
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              3. SPACING & LAYOUT
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>3. Spacing & Layout</h2>
                        <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 } }>
                            <div>
                                <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12 } }>Spacing Scale</h3>
                                { [ 4, 8, 12, 16, 20, 24, 32, 40, 48 ].map( ( v, i ) => (
                                    <div key={ i } style={ { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 } }>
                                        <code style={ { fontSize: 11, background: '#f9fafb', padding: '2px 6px', borderRadius: 4, width: 80, display: 'inline-block' } }>--space-{ [ 1, 2, 3, 4, 5, 6, 8, 10, 12 ][ i ] }</code>
                                        <div style={ { width: v, height: 14, background: C.lime, borderRadius: 3, border: `1px solid ${C.primary}` } } />
                                        <span style={ { fontSize: 11, color: C.text2 } }>{ v }px</span>
                                    </div>
                                ) ) }
                            </div>
                            <div>
                                <h3 style={ { fontSize: 16, fontWeight: 600, marginBottom: 12 } }>Border Radius</h3>
                                <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 } }>
                                    { [
                                        { r: 6, label: 'sm (6px)' },
                                        { r: 8, label: 'md (8px)' },
                                        { r: 13, label: 'btn (13px)' },
                                        { r: 12, label: 'lg (12px)' },
                                        { r: 16, label: '2xl (16px)' },
                                        { r: 9999, label: 'full' },
                                    ].map( ( b, i ) => (
                                        <div key={ i } style={ { textAlign: 'center' } }>
                                            <div style={ { width: 56, height: 56, borderRadius: b.r, border: `2px solid ${C.primary}`, background: C.bg2, margin: '0 auto 6px' } } />
                                            <div style={ { fontSize: 11, color: C.text2 } }>{ b.label }</div>
                                        </div>
                                    ) ) }
                                </div>
                                <h3 style={ { fontSize: 16, fontWeight: 600, margin: '24px 0 12px' } }>Layout Dimensions</h3>
                                <div style={ { fontSize: 13, lineHeight: 2 } }>
                                    <div>Max content: <strong>1400px</strong></div>
                                    <div>Sidebar: <strong>240px</strong></div>
                                    <div>Header: <strong>56px</strong></div>
                                    <div>Page padding: <strong>24px</strong></div>
                                    <div>Card padding: <strong>16-20px</strong></div>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              4. BUTTONS — ALL VARIANTS, SIZES, STATES
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>4. Buttons</h2>
                        <p style={ { fontSize: 14, color: C.text2, marginBottom: 20 } }>13px radius, 44px min-height, 1.5px border. All interactive.</p>

                        <h3 style={ { fontSize: 15, fontWeight: 600, marginBottom: 12 } }>4.1 Variants</h3>
                        <div style={ { display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 } }>
                            <button className="btn btn-primary btn-md">Primary CTA</button>
                            <button className="btn btn-secondary btn-md">Secondary</button>
                            <button className="btn btn-ghost btn-md">Ghost</button>
                            <button className="btn btn-danger btn-md">Danger</button>
                            <button className="btn btn-primary btn-md" disabled>Disabled</button>
                        </div>

                        <h3 style={ { fontSize: 15, fontWeight: 600, marginBottom: 12 } }>4.2 Sizes</h3>
                        <div style={ { display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 24 } }>
                            <button className="btn btn-secondary btn-sm">Small 36px</button>
                            <button className="btn btn-secondary btn-md">Medium 44px</button>
                            <button className="btn btn-secondary btn-lg">Large 52px</button>
                        </div>

                        <h3 style={ { fontSize: 15, fontWeight: 600, marginBottom: 12 } }>4.3 Icon Buttons</h3>
                        <div style={ { display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 24 } }>
                            <button className="icon-btn icon-btn-md" aria-label="Refresh">↻</button>
                            <button className="icon-btn icon-btn-md" aria-label="Add">+</button>
                            <button className="icon-btn icon-btn-md" aria-label="Close">✕</button>
                            <button className="icon-btn icon-btn-md icon-btn-danger" aria-label="Delete">🗑</button>
                        </div>

                        <h3 style={ { fontSize: 15, fontWeight: 600, marginBottom: 12 } }>4.4 Button States</h3>
                        <div style={ { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 } }>
                            { [
                                { label: 'Default', bg: '#fff', border: C.primary, color: C.text },
                                { label: 'Hover', bg: C.bg2, border: C.primaryHover, color: C.text },
                                { label: 'Active/Pressed', bg: '#e5e7eb', border: C.primary, color: C.text },
                                { label: 'Focus', bg: '#fff', border: C.primary, color: C.text, shadow: `0 0 0 3px rgba(26,58,42,0.3)` },
                                { label: 'Disabled', bg: '#fff', border: C.primary, color: C.text, opacity: 0.4 },
                                { label: 'Loading', bg: C.lime, border: C.primary, color: C.primary },
                            ].map( ( s, i ) => (
                                <div key={ i } style={ { textAlign: 'center', padding: 12, background: '#f9fafb', borderRadius: 12 } }>
                                    <div style={ { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '10px 18px', minHeight: 44, borderRadius: 13, border: `1.5px solid ${s.border}`, background: s.bg, color: s.color, fontSize: 14, fontWeight: 500, opacity: s.opacity || 1, boxShadow: s.shadow || 'none' } }>
                                        { s.label === 'Loading' ? '⟳ Sending...' : s.label }
                                    </div>
                                    <div style={ { marginTop: 8, fontSize: 11, color: C.text2 } }>{ s.label }</div>
                                </div>
                            ) ) }
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              5. FORM INPUTS
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>5. Form Inputs</h2>
                        <p style={ { fontSize: 14, color: C.text2, marginBottom: 20 } }>44px height, lime border, dark green focus. 16px font on mobile.</p>

                        <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 } }>
                            <div className="form-group">
                                <label style={ { display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 8 } }>Text Input (Default)</label>
                                <input className="search-input" type="text" placeholder="Enter value..." style={ { width: '100%', maxWidth: 'none' } } readOnly />
                            </div>
                            <div className="form-group">
                                <label style={ { display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 8 } }>Search Input</label>
                                <input className="search-input" type="search" placeholder="🔍 Search contacts..." style={ { width: '100%', maxWidth: 'none' } } readOnly />
                            </div>
                            <div className="form-group">
                                <label style={ { display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 8 } }>Select Dropdown</label>
                                <select style={ { width: '100%' } }>
                                    <option>Choose channel...</option>
                                    <option>WhatsApp</option>
                                    <option>SMS</option>
                                    <option>Email</option>
                                    <option>RCS</option>
                                </select>
                            </div>
                            <div className="form-group">
                                <label style={ { display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 8 } }>Error State</label>
                                <input type="text" defaultValue="Invalid phone" className="error" style={ { width: '100%', borderColor: '#dc2626' } } readOnly />
                                <span style={ { fontSize: 12, color: '#dc2626', marginTop: 4, display: 'block' } }>Phone number must start with +91</span>
                            </div>
                            <div className="form-group" style={ { gridColumn: '1 / -1' } }>
                                <label style={ { display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 8 } }>Textarea</label>
                                <textarea placeholder="Type your WhatsApp message here..." style={ { width: '100%', minHeight: 100 } } readOnly />
                            </div>
                            <div className="form-group">
                                <label style={ { display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 8 } }>Disabled Input</label>
                                <input type="text" value="Cannot edit" disabled style={ { width: '100%', opacity: 0.5 } } readOnly />
                            </div>
                            <div className="form-group">
                                <label style={ { display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 8 } }>Checkbox + Radio</label>
                                <div style={ { display: 'flex', gap: 16, alignItems: 'center' } }>
                                    <label style={ { display: 'flex', alignItems: 'center', gap: 6, fontSize: 14 } }><input type="checkbox" defaultChecked style={ { accentColor: C.primary } } /> WhatsApp</label>
                                    <label style={ { display: 'flex', alignItems: 'center', gap: 6, fontSize: 14 } }><input type="checkbox" style={ { accentColor: C.primary } } /> SMS</label>
                                    <label style={ { display: 'flex', alignItems: 'center', gap: 6, fontSize: 14 } }><input type="radio" name="ch" defaultChecked style={ { accentColor: C.primary } } /> Active</label>
                                    <label style={ { display: 'flex', alignItems: 'center', gap: 6, fontSize: 14 } }><input type="radio" name="ch" style={ { accentColor: C.primary } } /> Inactive</label>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              6. CARDS & CONTAINERS
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>6. Cards & Containers</h2>

                        <h3 style={ { fontSize: 15, fontWeight: 600, margin: '16px 0 12px' } }>6.1 Stat Cards</h3>
                        <div className="stats-grid" style={ { gridTemplateColumns: 'repeat(4, 1fr)' } }>
                            <div className="stat-card"><div className="stat-value">1,247</div><div className="stat-label">Messages Sent</div></div>
                            <div className="stat-card accent"><div className="stat-value">98.5%</div><div className="stat-label">Delivery Rate</div></div>
                            <div className="stat-card"><div className="stat-value">342</div><div className="stat-label">Contacts</div></div>
                            <div className="stat-card"><div className="stat-value">₹12.4K</div><div className="stat-label">Revenue</div></div>
                        </div>

                        <h3 style={ { fontSize: 15, fontWeight: 600, margin: '24px 0 12px' } }>6.2 Action Cards</h3>
                        <div style={ { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 } }>
                            { [
                                { icon: '📱', title: 'WhatsApp', desc: 'Send via WA Business API' },
                                { icon: '💬', title: 'SMS', desc: 'AWS Pinpoint / IN SMS' },
                                { icon: '📧', title: 'Email', desc: 'Amazon SES integration' },
                                { icon: '📞', title: 'Voice', desc: 'Outbound voice calls' },
                                { icon: '🔔', title: 'Push', desc: 'FCM push notifications' },
                                { icon: '💳', title: 'Pay', desc: 'Razorpay payment links' },
                            ].map( ( c, i ) => (
                                <div key={ i } className="inner-card" style={ { cursor: 'pointer', transition: 'all 0.15s ease' } }>
                                    <div style={ { fontSize: 28, marginBottom: 8 } }>{ c.icon }</div>
                                    <div style={ { fontSize: 15, fontWeight: 600, color: C.text, marginBottom: 4 } }>{ c.title }</div>
                                    <div style={ { fontSize: 13, color: C.text2 } }>{ c.desc }</div>
                                </div>
                            ) ) }
                        </div>

                        <h3 style={ { fontSize: 15, fontWeight: 600, margin: '24px 0 12px' } }>6.3 Info Banner</h3>
                        <div className="info-banner">
                            <span>ℹ️</span>
                            <span>WhatsApp Business API requires approved message templates for outbound marketing messages. <a href="#" style={ { color: C.primary, fontWeight: 500 } }>Learn more →</a></span>
                        </div>

                        <h3 style={ { fontSize: 15, fontWeight: 600, margin: '24px 0 12px' } }>6.4 Section Card (Content Container)</h3>
                        <div className="inner-card">
                            <h4 style={ { margin: '0 0 12px', fontSize: 16, fontWeight: 600 } }>Recent Messages</h4>
                            <p style={ { margin: 0, fontSize: 14, color: C.text2 } }>This is a section card used to group related content. It has 1.5px lime border, 16px border-radius, and 20px padding.</p>
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              7. TABLES
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>7. Tables</h2>
                        <p style={ { fontSize: 14, color: C.text2, marginBottom: 20 } }>2px lime border, lime header, hover rows, monospace for data.</p>

                        <div className="table-container">
                            <table className="inner-table">
                                <thead>
                                    <tr>
                                        <th>Contact</th>
                                        <th>Phone</th>
                                        <th>Channel</th>
                                        <th>Status</th>
                                        <th>Last Message</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td><strong>Rahul Sharma</strong></td>
                                        <td style={ { fontFamily: 'monospace' } }>+91 98765 43210</td>
                                        <td>WhatsApp</td>
                                        <td><span style={ { padding: '3px 10px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: C.lime, color: C.primary } }>Active</span></td>
                                        <td>2 min ago</td>
                                        <td><button className="btn btn-secondary btn-sm">View</button></td>
                                    </tr>
                                    <tr>
                                        <td><strong>Priya Patel</strong></td>
                                        <td style={ { fontFamily: 'monospace' } }>+91 87654 32109</td>
                                        <td>SMS</td>
                                        <td><span style={ { padding: '3px 10px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: C.dangerLight, color: C.danger } }>Failed</span></td>
                                        <td>1 hour ago</td>
                                        <td><button className="btn btn-secondary btn-sm">Retry</button></td>
                                    </tr>
                                    <tr>
                                        <td><strong>Amit Kumar</strong></td>
                                        <td style={ { fontFamily: 'monospace' } }>+91 76543 21098</td>
                                        <td>RCS</td>
                                        <td><span style={ { padding: '3px 10px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: C.bg2, color: C.primary } }>Delivered</span></td>
                                        <td>5 min ago</td>
                                        <td><button className="btn btn-secondary btn-sm">View</button></td>
                                    </tr>
                                    <tr>
                                        <td><strong>Neha Singh</strong></td>
                                        <td style={ { fontFamily: 'monospace' } }>+91 65432 10987</td>
                                        <td>Email</td>
                                        <td><span style={ { padding: '3px 10px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: '#e5e7eb', color: '#374151' } }>Pending</span></td>
                                        <td>10 min ago</td>
                                        <td><button className="btn btn-secondary btn-sm">View</button></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              8. TABS & NAVIGATION
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>8. Tabs & Navigation</h2>

                        <h3 style={ { fontSize: 15, fontWeight: 600, margin: '16px 0 12px' } }>8.1 Main Tabs (Lime Container)</h3>
                        <div className="tabs">
                            <button className="tab-btn active">Overview</button>
                            <button className="tab-btn">Messages</button>
                            <button className="tab-btn">Pay</button>
                            <button className="tab-btn">Billing</button>
                            <button className="tab-btn">Health</button>
                            <button className="tab-btn">AI</button>
                        </div>

                        <h3 style={ { fontSize: 15, fontWeight: 600, margin: '24px 0 12px' } }>8.2 Sub-Tabs</h3>
                        <div className="tabs tabs-sub">
                            <button className="tab-btn active">All</button>
                            <button className="tab-btn">Sent</button>
                            <button className="tab-btn">Received</button>
                            <button className="tab-btn">Failed</button>
                            <button className="tab-btn">Queued</button>
                        </div>

                        <h3 style={ { fontSize: 15, fontWeight: 600, margin: '24px 0 12px' } }>8.3 Sidebar Navigation (Dark)</h3>
                        <div style={ { background: C.primary, borderRadius: 16, padding: 16, maxWidth: 260 } }>
                            { [
                                { label: 'Dashboard', active: true },
                                { label: 'Messages', active: false },
                                { label: 'Pay', active: false },
                                { label: 'Contacts', active: false },
                                { label: 'Store', active: false },
                                { label: 'SEO', active: false },
                            ].map( ( item, i ) => (
                                <div key={ i } style={ { padding: '10px 14px', borderRadius: 8, background: item.active ? 'rgba(209,244,112,0.3)' : 'transparent', borderLeft: item.active ? `3px solid ${C.lime}` : '3px solid transparent', color: item.active ? '#fff' : 'rgba(255,255,255,0.6)', fontSize: 14, fontWeight: item.active ? 500 : 400, marginBottom: 2, cursor: 'pointer' } }>{ item.label }</div>
                            ) ) }
                        </div>

                        <h3 style={ { fontSize: 15, fontWeight: 600, margin: '24px 0 12px' } }>8.4 Breadcrumbs</h3>
                        <div className="breadcrumbs">
                            <ol className="breadcrumbs-list">
                                <li className="breadcrumbs-item"><a className="breadcrumbs-link" href="#">Home</a><span className="breadcrumbs-separator">›</span></li>
                                <li className="breadcrumbs-item"><a className="breadcrumbs-link" href="#">Dashboard</a><span className="breadcrumbs-separator">›</span></li>
                                <li className="breadcrumbs-item"><span className="breadcrumbs-current">Design Reference</span></li>
                            </ol>
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              9. BADGES & PILLS
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>9. Badges & Status Pills</h2>
                        <div style={ { display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 } }>
                            { [
                                { label: 'Active', bg: C.lime, color: C.primary },
                                { label: 'Delivered', bg: C.bg2, color: C.primary },
                                { label: 'Sent', bg: '#e5e7eb', color: '#374151' },
                                { label: 'Pending', bg: '#fff', color: C.text2 },
                                { label: 'Failed', bg: C.dangerLight, color: C.danger },
                                { label: 'Error', bg: C.primary, color: '#fff' },
                                { label: 'New', bg: C.lime, color: C.primary },
                                { label: 'Draft', bg: '#f9fafb', color: '#9ca3af' },
                                { label: 'Published', bg: C.lime, color: C.primary },
                                { label: 'Archived', bg: '#e5e7eb', color: '#6b7280' },
                                { label: 'Online', bg: '#d1f470', color: '#1a3a2a' },
                                { label: 'Offline', bg: '#fef2f2', color: '#dc2626' },
                            ].map( ( b, i ) => (
                                <span key={ i } style={ { display: 'inline-block', padding: '4px 12px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: b.bg, color: b.color, border: '1px solid ' + ( b.bg === '#fff' ? '#e5e7eb' : 'transparent' ) } }>{ b.label }</span>
                            ) ) }
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              10. TOASTS & ALERTS
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>10. Toasts & Alerts</h2>
                        <div style={ { display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 420 } }>
                            <div className="toast toast-success" style={ { position: 'static', animation: 'none' } }>
                                <div className="toast-icon">✓</div>
                                <span className="toast-message">Message sent successfully to +91 98765 43210</span>
                                <button className="toast-close">✕</button>
                            </div>
                            <div className="toast toast-error" style={ { position: 'static', animation: 'none', borderColor: '#dc2626' } }>
                                <div className="toast-icon" style={ { background: C.dangerLight, color: C.danger } }>!</div>
                                <span className="toast-message">Failed to deliver — recipient blocked</span>
                                <button className="toast-close">✕</button>
                            </div>
                            <div className="toast toast-warning" style={ { position: 'static', animation: 'none' } }>
                                <div className="toast-icon">⚠</div>
                                <span className="toast-message">Rate limit: 45/50 messages used this minute</span>
                                <button className="toast-close">✕</button>
                            </div>
                            <div className="toast toast-info" style={ { position: 'static', animation: 'none' } }>
                                <div className="toast-icon">ℹ</div>
                                <span className="toast-message">New template approved by Meta</span>
                                <button className="toast-close">✕</button>
                            </div>
                        </div>
                        <div style={ { marginTop: 16, background: C.bg2, border: `1.5px solid ${C.lime}`, borderRadius: 13, padding: '12px 16px', fontSize: 13 } }>
                            <strong>Rules:</strong> Top-right position. Auto-dismiss: 5s success, 8s error. Max 3 visible. Slide-in from right. Always include close button.
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              11. EMPTY STATES
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>11. Empty States</h2>
                        <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 } }>
                            <div className="inner-card">
                                <div className="empty-state">
                                    <div className="empty-state-icon">📭</div>
                                    <h3 className="empty-state-title">No messages yet</h3>
                                    <p className="empty-state-description">Send your first WhatsApp message to get started with customer engagement.</p>
                                    <button className="btn btn-primary btn-md">Send First Message</button>
                                </div>
                            </div>
                            <div className="inner-card">
                                <div className="empty-state">
                                    <div className="empty-state-icon">🔍</div>
                                    <h3 className="empty-state-title">No results found</h3>
                                    <p className="empty-state-description">Try adjusting your search or filter criteria to find what you need.</p>
                                    <button className="btn btn-secondary btn-md">Clear Filters</button>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              12. LOADING STATES
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>12. Loading States</h2>
                        <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20 } }>
                            {/* Skeleton */ }
                            <div className="inner-card">
                                <h4 style={ { fontSize: 14, fontWeight: 600, marginBottom: 12 } }>Skeleton Loading</h4>
                                <div style={ { height: 14, width: '60%', background: '#f5f5f5', borderRadius: 4, marginBottom: 10 } } className="skeleton" />
                                <div style={ { height: 28, width: '40%', background: '#f5f5f5', borderRadius: 4, marginBottom: 10 } } className="skeleton" />
                                <div style={ { height: 12, width: '80%', background: '#f5f5f5', borderRadius: 4 } } className="skeleton" />
                            </div>
                            {/* Spinner */ }
                            <div className="inner-card" style={ { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 140 } }>
                                <h4 style={ { fontSize: 14, fontWeight: 600, marginBottom: 12 } }>Spinner</h4>
                                <div className="spinner" style={ { width: 32, height: 32, border: '3px solid #f3f4f6', borderTop: `3px solid ${C.primary}`, borderRadius: '50%' } } />
                                <span style={ { marginTop: 8, fontSize: 13, color: C.text2 } }>Loading data...</span>
                            </div>
                            {/* Button Loading */ }
                            <div className="inner-card" style={ { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 140 } }>
                                <h4 style={ { fontSize: 14, fontWeight: 600, marginBottom: 12 } }>Button Loading</h4>
                                <button className="btn btn-primary btn-md btn-loading" disabled>
                                    <span className="spinner" style={ { width: 16, height: 16, border: '2px solid rgba(26,58,42,0.3)', borderTop: `2px solid ${C.primary}`, borderRadius: '50%', display: 'inline-block' } } />
                                    <span className="btn-text-loading">Sending...</span>
                                </button>
                            </div>
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              13. MODALS & DIALOGS
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>13. Modals & Dialogs</h2>
                        <div style={ { background: 'rgba(0,0,0,0.25)', borderRadius: 16, padding: 40, display: 'flex', alignItems: 'center', justifyContent: 'center' } }>
                            <div style={ { background: '#fff', borderRadius: 16, padding: 24, maxWidth: 420, width: '100%', boxShadow: '0 20px 40px rgba(0,0,0,0.2)' } }>
                                <div style={ { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 } }>
                                    <h3 style={ { margin: 0, fontSize: 18, fontWeight: 600 } }>Delete Contact?</h3>
                                    <button className="icon-btn icon-btn-sm icon-btn-ghost" aria-label="Close">✕</button>
                                </div>
                                <p style={ { fontSize: 14, color: C.text2, margin: '0 0 24px' } }>
                                    Are you sure you want to delete <strong>Rahul Sharma</strong>? This will remove all message history and cannot be undone.
                                </p>
                                <div style={ { display: 'flex', gap: 12, justifyContent: 'flex-end' } }>
                                    <button className="btn btn-secondary btn-md">Cancel</button>
                                    <button className="btn btn-danger btn-md">Delete Contact</button>
                                </div>
                            </div>
                        </div>
                        <div style={ { marginTop: 16, background: C.bg2, border: `1.5px solid ${C.lime}`, borderRadius: 13, padding: '12px 16px', fontSize: 13 } }>
                            <strong>Modal Rules:</strong> Max-width 480px. Radius 16px. Overlay rgba(0,0,0,0.5). Focus trap. ESC to close. Animate: fade + slide-up (250ms). Always include close button.
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              14. ICONS
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>14. Icons</h2>
                        <p style={ { fontSize: 14, color: C.text2, marginBottom: 20 } }>Stroke-based SVGs. 1.5px stroke. Sizes: 14/16/18/20px. Color inherits from parent.</p>
                        <div style={ { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(90px, 1fr))', gap: 12 } }>
                            { [
                                '↻ Refresh', '+ Add', '✕ Close', '🔍 Search', '✏️ Edit', '🗑️ Delete',
                                '📱 WhatsApp', '💬 SMS', '📧 Email', '📞 Voice', '🔔 Push', '💳 Pay',
                                '👤 Contact', '📊 Chart', '⚙️ Settings', '🔗 Link', '📋 Copy', '↗️ Export',
                                '📥 Import', '🔄 Sync', '📄 Document', '🏷️ Tag', '⭐ Star', '🔒 Lock',
                            ].map( ( icon, i ) => (
                                <div key={ i } style={ { textAlign: 'center', padding: 10, background: '#f9fafb', borderRadius: 10, border: '1px solid #e5e7eb' } }>
                                    <div style={ { fontSize: 20, marginBottom: 4 } }>{ icon.split( ' ' )[ 0 ] }</div>
                                    <div style={ { fontSize: 10, color: C.text2 } }>{ icon.split( ' ' ).slice( 1 ).join( ' ' ) }</div>
                                </div>
                            ) ) }
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              15. SHADOWS
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>15. Shadows</h2>
                        <div style={ { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20 } }>
                            { [
                                { name: 'sm', shadow: '0 1px 2px rgba(0,0,0,0.04)' },
                                { name: 'md', shadow: '0 2px 8px rgba(0,0,0,0.06)' },
                                { name: 'lg', shadow: '0 4px 12px rgba(0,0,0,0.08)' },
                                { name: 'xl', shadow: '0 8px 24px rgba(0,0,0,0.12)' },
                            ].map( ( s, i ) => (
                                <div key={ i } style={ { textAlign: 'center' } }>
                                    <div style={ { width: '100%', height: 80, background: '#fff', borderRadius: 12, boxShadow: s.shadow, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: C.text2 } }>shadow-{ s.name }</div>
                                    <code style={ { fontSize: 10, color: C.text2, marginTop: 8, display: 'block' } }>{ s.shadow }</code>
                                </div>
                            ) ) }
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              16. RESPONSIVE BREAKPOINTS
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>16. Responsive Breakpoints</h2>
                        <div className="table-container">
                            <table className="inner-table">
                                <thead>
                                    <tr>
                                        <th>Breakpoint</th>
                                        <th>Width</th>
                                        <th>Grid</th>
                                        <th>Sidebar</th>
                                        <th>Padding</th>
                                        <th>Notes</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr><td><strong>Mobile S</strong></td><td>≤ 480px</td><td>1 col</td><td>Hidden</td><td>16px</td><td>Stack everything, full-width CTAs</td></tr>
                                    <tr><td><strong>Mobile L</strong></td><td>481–768px</td><td>2 col</td><td>Overlay</td><td>20px</td><td>Hamburger menu, collapsible</td></tr>
                                    <tr><td><strong>Tablet</strong></td><td>769–1024px</td><td>2-3 col</td><td>Collapsed</td><td>24px</td><td>Icons-only sidebar</td></tr>
                                    <tr><td><strong>Desktop</strong></td><td>1025–1440px</td><td>auto-fit</td><td>Full 240px</td><td>24px</td><td>Full layout</td></tr>
                                    <tr><td><strong>Wide</strong></td><td>&gt; 1440px</td><td>auto-fit</td><td>Full 240px</td><td>24px</td><td>Max-width 1400px centered</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              17. ACCESSIBILITY
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>17. Accessibility (WCAG 2.1 AA)</h2>
                        <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 } }>
                            <div className="inner-card">
                                <h3 style={ { fontSize: 15, fontWeight: 600, marginBottom: 12, color: C.primary } }>✅ Implemented</h3>
                                <ul style={ { margin: 0, padding: '0 0 0 18px', fontSize: 13, lineHeight: 2.2, color: '#374151' } }>
                                    <li>Min 44px touch targets on all buttons/links</li>
                                    <li>Focus-visible ring: 3px rgba(26,58,42,0.3)</li>
                                    <li>Color contrast: #1a3a2a on #fff = 12.6:1 ✓</li>
                                    <li>Color contrast: #6b7280 on #fff = 5.0:1 ✓</li>
                                    <li>Semantic HTML headings (h1→h4)</li>
                                    <li>Keyboard navigation (Tab, Enter, Escape)</li>
                                    <li>aria-label on icon-only buttons</li>
                                    <li>prefers-reduced-motion: disable animations</li>
                                    <li>16px input font (prevents iOS zoom)</li>
                                    <li>Safe area insets for notch devices</li>
                                    <li>touch-action: manipulation (no double-tap zoom)</li>
                                </ul>
                            </div>
                            <div className="inner-card">
                                <h3 style={ { fontSize: 15, fontWeight: 600, marginBottom: 12, color: C.danger } }>⚠️ Improvements Needed</h3>
                                <ul style={ { margin: 0, padding: '0 0 0 18px', fontSize: 13, lineHeight: 2.2, color: '#374151' } }>
                                    <li>Change lang="en" → lang="en-IN"</li>
                                    <li>Add skip-to-content link</li>
                                    <li>Add aria-live="polite" on toast container</li>
                                    <li>Add role="alert" on error messages</li>
                                    <li>Complete modal focus trap</li>
                                    <li>Add aria-expanded on sidebar items</li>
                                    <li>Add aria-current="page" on active nav</li>
                                    <li>Add aria-describedby on form errors</li>
                                    <li>Test with NVDA + VoiceOver</li>
                                    <li>Add high-contrast mode support</li>
                                </ul>
                            </div>
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              18. MOTION & TRANSITIONS
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>18. Motion & Transitions</h2>
                        <div className="table-container">
                            <table className="inner-table">
                                <thead>
                                    <tr>
                                        <th>Token</th>
                                        <th>Duration</th>
                                        <th>Easing</th>
                                        <th>Use Case</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr><td>--transition-fast</td><td>100ms</td><td>ease</td><td>Button press, toggle</td></tr>
                                    <tr><td>--transition-normal</td><td>150ms</td><td>ease</td><td>Hover states, border changes</td></tr>
                                    <tr><td>--transition-slow</td><td>250ms</td><td>cubic-bezier(0.16,1,0.3,1)</td><td>Modal open, sidebar expand</td></tr>
                                    <tr><td>Toast enter</td><td>200ms</td><td>ease</td><td>Slide in from right</td></tr>
                                    <tr><td>Toast exit</td><td>200ms</td><td>ease</td><td>Slide out to right</td></tr>
                                    <tr><td>Skeleton pulse</td><td>1500ms</td><td>ease-in-out (infinite)</td><td>Loading placeholder</td></tr>
                                    <tr><td>Spinner</td><td>800ms</td><td>linear (infinite)</td><td>Loading rotation</td></tr>
                                    <tr><td>Button active</td><td>instant</td><td>—</td><td>scale(0.98)</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              19. PAGE TEMPLATES
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>19. Page Templates</h2>
                        <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 } }>
                            { [
                                { title: '📊 Dashboard Page', desc: 'Stats + Tabs + Content', code: '<Layout>\n  <SEO />\n  <PageHeader />\n  <StatsGrid 4-col />\n  <Tabs>\n    <TabContent />\n  </Tabs>\n</Layout>' },
                                { title: '📝 Form Page', desc: 'Input form + Preview', code: '<Layout>\n  <SEO />\n  <PageHeader />\n  <Grid 2-col>\n    <FormSection />\n    <PreviewCard />\n  </Grid>\n</Layout>' },
                                { title: '💬 Messaging Page', desc: 'Split: Contacts + Chat', code: '<Layout>\n  <SEO />\n  <SplitView>\n    <ContactsSidebar />\n    <ChatArea>\n      <MessageList />\n      <ComposeBar />\n    </ChatArea>\n  </SplitView>\n</Layout>' },
                                { title: '📋 List/Table Page', desc: 'Filters + Table + Pagination', code: '<Layout>\n  <SEO />\n  <PageHeader + CreateBtn />\n  <FilterBar />\n  <Table />\n  <Pagination />\n</Layout>' },
                            ].map( ( t, i ) => (
                                <div key={ i } className="inner-card">
                                    <h4 style={ { margin: '0 0 4px', fontSize: 16, fontWeight: 600 } }>{ t.title }</h4>
                                    <p style={ { margin: '0 0 12px', fontSize: 13, color: C.text2 } }>{ t.desc }</p>
                                    <pre style={ { background: '#f9fafb', borderRadius: 8, padding: 12, fontSize: 11, fontFamily: 'monospace', color: '#374151', margin: 0, whiteSpace: 'pre-wrap', border: '1px solid #e5e7eb' } }>{ t.code }</pre>
                                </div>
                            ) ) }
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              20. COMPLETE FILE REFERENCE
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { marginBottom: 56 } }>
                        <h2 style={ { fontSize: 22, fontWeight: 700, color: C.primary, margin: '0 0 8px' } }>20. File Reference</h2>
                        <div className="table-container">
                            <table className="inner-table">
                                <thead>
                                    <tr>
                                        <th>File</th>
                                        <th>Purpose</th>
                                        <th>Priority</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr><td><code>src/styles/tokens.css</code></td><td>CSS variables — colors, spacing, typography, shadows</td><td>Core</td></tr>
                                    <tr><td><code>src/styles/inner-ux.css</code></td><td>Component styles — buttons, tabs, tables, toasts, forms</td><td>Core</td></tr>
                                    <tr><td><code>src/styles/inner-pages.css</code></td><td>Page-level overrides — sidebar, cards, responsive</td><td>Core</td></tr>
                                    <tr><td><code>src/styles/Dashboard.css</code></td><td>Dashboard-specific — stats, billing, messages</td><td>Page</td></tr>
                                    <tr><td><code>src/styles/Layout.css</code></td><td>Layout structure — sidebar, header, content area</td><td>Core</td></tr>
                                    <tr><td><code>src/styles/button.css</code></td><td>Button system — variants, sizes, states</td><td>Component</td></tr>
                                    <tr><td><code>src/components/ui/Button.tsx</code></td><td>Button React component with icons</td><td>Component</td></tr>
                                    <tr><td><code>src/components/ui/Tabs.tsx</code></td><td>Tabs React component</td><td>Component</td></tr>
                                    <tr><td><code>src/components/ui/Table.tsx</code></td><td>Table React component</td><td>Component</td></tr>
                                    <tr><td><code>src/components/ui/Modal.tsx</code></td><td>Modal React component</td><td>Component</td></tr>
                                    <tr><td><code>src/components/ui/Spinner.tsx</code></td><td>Loading spinner</td><td>Component</td></tr>
                                    <tr><td><code>src/components/ui/EmptyState.tsx</code></td><td>Empty state pattern</td><td>Component</td></tr>
                                    <tr><td><code>src/components/ui/Pagination.tsx</code></td><td>Pagination component</td><td>Component</td></tr>
                                    <tr><td><code>src/config/navigation.ts</code></td><td>Sidebar navigation tree</td><td>Config</td></tr>
                                    <tr><td><code>src/components/Layout.tsx</code></td><td>Main layout wrapper</td><td>Core</td></tr>
                                    <tr><td><code>src/components/SEO.tsx</code></td><td>SEO meta tags component</td><td>Core</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </section>

                    {/* ═══════════════════════════════════════════════════════════════
              FOOTER SUMMARY
          ═══════════════════════════════════════════════════════════════ */}
                    <section style={ { background: C.bg2, border: `2px solid ${C.lime}`, borderRadius: 16, padding: 24 } }>
                        <h2 style={ { fontSize: 18, fontWeight: 700, color: C.primary, margin: '0 0 16px' } }>📋 Quick Reference Summary</h2>
                        <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 20 } }>
                            <div>
                                <strong style={ { fontSize: 13, display: 'block', marginBottom: 8 } }>Colors</strong>
                                <div style={ { fontSize: 12, lineHeight: 2, color: '#374151' } }>
                                    Primary: #1a3a2a<br />
                                    Lime: #d1f470<br />
                                    Danger: #dc2626<br />
                                    BG: #fff / #f9fafb
                                </div>
                            </div>
                            <div>
                                <strong style={ { fontSize: 13, display: 'block', marginBottom: 8 } }>Dimensions</strong>
                                <div style={ { fontSize: 12, lineHeight: 2, color: '#374151' } }>
                                    Button radius: 13px<br />
                                    Touch target: 44px<br />
                                    Border: 1.5px<br />
                                    Max width: 1400px
                                </div>
                            </div>
                            <div>
                                <strong style={ { fontSize: 13, display: 'block', marginBottom: 8 } }>Typography</strong>
                                <div style={ { fontSize: 12, lineHeight: 2, color: '#374151' } }>
                                    Font: Inter<br />
                                    H1: 28px / 700<br />
                                    Body: 14px / 400<br />
                                    Caption: 12px / 600
                                </div>
                            </div>
                            <div>
                                <strong style={ { fontSize: 13, display: 'block', marginBottom: 8 } }>Key Rules</strong>
                                <div style={ { fontSize: 12, lineHeight: 2, color: '#374151' } }>
                                    1 primary CTA/section<br />
                                    Confirm destructive<br />
                                    Skeleton for loading<br />
                                    16px input on mobile
                                </div>
                            </div>
                        </div>
                    </section>

                </div>
            </div>
        </Layout>
    );
};

export default DesignReferencePage;
