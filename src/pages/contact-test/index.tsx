/**
 * Contact Us Page — WECARE.DIGITAL
 * Clean, balanced inner page layout with contact info, form, and quick links.
 */
import React, { useState } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';

const IcMail = () => ( <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22 6 12 13 2 6" /></svg> );
const IcPhone = () => ( <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z" /></svg> );
const IcMap = () => ( <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" /><circle cx="12" cy="10" r="3" /></svg> );
const IcClock = () => ( <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg> );
const IcWhatsApp = () => ( <svg width="20" height="20" viewBox="0 0 24 24" fill="#1a3a2a"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" /></svg> );
const IcSend = () => ( <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg> );

interface PageProps { signOut?: () => void; user?: any; }

const ContactUsPage: React.FC<PageProps> = ( { signOut, user } ) => {
  const [ name, setName ] = useState( '' );
  const [ email, setEmail ] = useState( '' );
  const [ phone, setPhone ] = useState( '' );
  const [ subject, setSubject ] = useState( '' );
  const [ message, setMessage ] = useState( '' );
  const [ sending, setSending ] = useState( false );
  const [ sent, setSent ] = useState( false );

  const handleSubmit = async ( e: React.FormEvent ) => {
    e.preventDefault();
    if ( !name.trim() || !message.trim() ) return;
    setSending( true );
    // Simulate send — in production this would call an API
    await new Promise( r => setTimeout( r, 1200 ) );
    setSending( false );
    setSent( true );
    setName( '' ); setEmail( '' ); setPhone( '' ); setSubject( '' ); setMessage( '' );
    setTimeout( () => setSent( false ), 5000 );
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 14px', fontSize: 14, color: '#1a1a1a',
    background: '#fff', border: '1.5px solid #e5e7eb', borderRadius: 10,
    outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box',
    transition: 'border-color 0.15s',
  };

  const labelStyle: React.CSSProperties = {
    display: 'block', fontSize: 13, fontWeight: 500, color: '#1a3a2a', marginBottom: 6,
  };

  return (
    <Layout onSignOut={ signOut } user={ user }>
      <SEO title="Contact Us" description="Get in touch with WECARE.DIGITAL" />
      <div className="inner-page-container" style={ { maxWidth: 960, margin: '0 auto', padding: '24px 20px' } }>
        {/* Page Header */ }
        <div style={ { marginBottom: 32 } }>
          <h1 style={ { fontSize: 24, fontWeight: 700, color: '#1a1a1a', margin: '0 0 6px' } }>Contact Us</h1>
          <p style={ { fontSize: 14, color: '#6b7280', margin: 0 } }>We'd love to hear from you. Reach out anytime.</p>
        </div>

        {/* Main Grid: Contact Info + Form */ }
        <div style={ { display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 24, marginBottom: 32 } }>
          {/* Left: Contact Information */ }
          <div style={ { display: 'flex', flexDirection: 'column', gap: 16 } }>
            {/* Company Card */ }
            <div style={ { background: '#fff', border: '1.5px solid #d1f470', borderRadius: 13, padding: 20 } }>
              <div style={ { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 } }>
                <img src="https://app.wecare.digital/stream/media/m/wecaredigital.png" alt="WECARE.DIGITAL" style={ { width: 40, height: 40, borderRadius: 10, objectFit: 'contain' } } />
                <div>
                  <div style={ { fontSize: 16, fontWeight: 700, color: '#1a1a1a' } }>WECARE.DIGITAL</div>
                  <div style={ { fontSize: 12, color: '#6b7280' } }>Unified CRM Platform</div>
                </div>
              </div>

              <div style={ { display: 'flex', flexDirection: 'column', gap: 14 } }>
                <div style={ { display: 'flex', alignItems: 'flex-start', gap: 10 } }>
                  <div style={ { width: 36, height: 36, borderRadius: 10, background: 'rgba(209,244,112,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 } }><IcMap /></div>
                  <div>
                    <div style={ { fontSize: 12, fontWeight: 600, color: '#1a3a2a', marginBottom: 2 } }>Office</div>
                    <div style={ { fontSize: 13, color: '#374151', lineHeight: 1.5 } }>The W.B.S.I.D.C. Building, Unit 1/20,<br />81/2/7, Phears Ln, Kolkata, WB 700012</div>
                  </div>
                </div>

                <div style={ { display: 'flex', alignItems: 'center', gap: 10 } }>
                  <div style={ { width: 36, height: 36, borderRadius: 10, background: 'rgba(209,244,112,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 } }><IcPhone /></div>
                  <div>
                    <div style={ { fontSize: 12, fontWeight: 600, color: '#1a3a2a', marginBottom: 2 } }>Phone</div>
                    <a href="tel:+919330994400" style={ { fontSize: 13, color: '#374151', textDecoration: 'none' } }>+91 93309 94400</a>
                  </div>
                </div>

                <div style={ { display: 'flex', alignItems: 'center', gap: 10 } }>
                  <div style={ { width: 36, height: 36, borderRadius: 10, background: 'rgba(209,244,112,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 } }><IcMail /></div>
                  <div>
                    <div style={ { fontSize: 12, fontWeight: 600, color: '#1a3a2a', marginBottom: 2 } }>Email</div>
                    <a href="mailto:one@wecare.digital" style={ { fontSize: 13, color: '#374151', textDecoration: 'none' } }>one@wecare.digital</a>
                  </div>
                </div>

                <div style={ { display: 'flex', alignItems: 'center', gap: 10 } }>
                  <div style={ { width: 36, height: 36, borderRadius: 10, background: 'rgba(209,244,112,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 } }><IcWhatsApp /></div>
                  <div>
                    <div style={ { fontSize: 12, fontWeight: 600, color: '#1a3a2a', marginBottom: 2 } }>WhatsApp</div>
                    <a href="https://wa.me/919330994400" target="_blank" rel="noopener noreferrer" style={ { fontSize: 13, color: '#374151', textDecoration: 'none' } }>+91 93309 94400</a>
                  </div>
                </div>

                <div style={ { display: 'flex', alignItems: 'center', gap: 10 } }>
                  <div style={ { width: 36, height: 36, borderRadius: 10, background: 'rgba(209,244,112,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 } }><IcClock /></div>
                  <div>
                    <div style={ { fontSize: 12, fontWeight: 600, color: '#1a3a2a', marginBottom: 2 } }>Hours</div>
                    <div style={ { fontSize: 13, color: '#374151' } }>Mon–Sat, 10:00 AM – 7:00 PM IST</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Quick Links */ }
            <div style={ { background: '#fff', border: '1.5px solid #d1f470', borderRadius: 13, padding: 20 } }>
              <div style={ { fontSize: 14, fontWeight: 600, color: '#1a1a1a', marginBottom: 12 } }>Quick Links</div>
              <div style={ { display: 'flex', flexDirection: 'column', gap: 8 } }>
                { [
                  { label: 'Self-Service Portal', href: '/forms/selfservice' },
                  // A second entry labelled 'Selfservice' pointed at
                  // https://www.wecare.digital/selfservice. Removed 2026-09-25: the
                  // marketing /selfservice page was deleted in commit 6bc44a35, so the
                  // link ran 301 (www -> apex) -> 301 (trailing slash) -> 404. It was
                  // also near-duplicate labelling next to the live app route above,
                  // which is the one a reader of this page actually wants.
                  { label: 'Subscribe for Updates', href: '#', note: 'Send "subscribe" on WhatsApp' },
                ].map( ( link, i ) => (
                  <a key={ i } href={ link.href } style={ { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(209,244,112,0.3)', background: '#f9fafb', textDecoration: 'none', fontSize: 13, color: '#1a3a2a', fontWeight: 500, transition: 'background 0.15s' } }>
                    <span>{ link.label }</span>
                    { link.note && <span style={ { fontSize: 10, color: '#9ca3af', fontWeight: 400 } }>{ link.note }</span> }
                    { !link.note && <span style={ { fontSize: 14, color: '#9ca3af' } }>→</span> }
                  </a>
                ) ) }
              </div>
            </div>
          </div>

          {/* Right: Contact Form */ }
          <div style={ { background: '#fff', border: '1.5px solid #d1f470', borderRadius: 13, padding: 24 } }>
            <div style={ { fontSize: 16, fontWeight: 600, color: '#1a1a1a', marginBottom: 4 } }>Send us a message</div>
            <p style={ { fontSize: 13, color: '#6b7280', margin: '0 0 20px' } }>Fill out the form and we'll get back to you within 24 hours.</p>

            { sent && (
              <div style={ { display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 10, marginBottom: 16, fontSize: 13, color: '#166534' } }>
                <span>✅</span> Message sent. We'll be in touch soon.
              </div>
            ) }

            <form onSubmit={ handleSubmit } style={ { display: 'flex', flexDirection: 'column', gap: 14 } }>
              <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 } }>
                <div>
                  <label style={ labelStyle }>Name <span style={ { color: '#dc2626' } }>*</span></label>
                  <input style={ inputStyle } value={ name } onChange={ e => setName( e.target.value ) } placeholder="Your name" required onFocus={ e => e.currentTarget.style.borderColor = '#d1f470' } onBlur={ e => e.currentTarget.style.borderColor = '#e5e7eb' } />
                </div>
                <div>
                  <label style={ labelStyle }>Email</label>
                  <input type="email" style={ inputStyle } value={ email } onChange={ e => setEmail( e.target.value ) } placeholder="you@example.com" onFocus={ e => e.currentTarget.style.borderColor = '#d1f470' } onBlur={ e => e.currentTarget.style.borderColor = '#e5e7eb' } />
                </div>
              </div>

              <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 } }>
                <div>
                  <label style={ labelStyle }>Phone</label>
                  <input type="tel" style={ inputStyle } value={ phone } onChange={ e => setPhone( e.target.value ) } placeholder="+91 XXXXX XXXXX" onFocus={ e => e.currentTarget.style.borderColor = '#d1f470' } onBlur={ e => e.currentTarget.style.borderColor = '#e5e7eb' } />
                </div>
                <div>
                  <label style={ labelStyle }>Subject</label>
                  <input style={ inputStyle } value={ subject } onChange={ e => setSubject( e.target.value ) } placeholder="What's this about?" onFocus={ e => e.currentTarget.style.borderColor = '#d1f470' } onBlur={ e => e.currentTarget.style.borderColor = '#e5e7eb' } />
                </div>
              </div>

              <div>
                <label style={ labelStyle }>Message <span style={ { color: '#dc2626' } }>*</span></label>
                <textarea style={ { ...inputStyle, minHeight: 120, resize: 'vertical' } as any } value={ message } onChange={ e => setMessage( e.target.value ) } placeholder="Tell us how we can help..." required onFocus={ e => ( e.currentTarget as any ).style.borderColor = '#d1f470' } onBlur={ e => ( e.currentTarget as any ).style.borderColor = '#e5e7eb' } />
              </div>

              <button type="submit" disabled={ sending || !name.trim() || !message.trim() } style={ {
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                padding: '12px 24px', background: sending ? '#e5e7eb' : '#d1f470', color: '#1a3a2a',
                border: '1.5px solid #d1f470', borderRadius: 10, fontSize: 14, fontWeight: 600,
                cursor: sending ? 'wait' : 'pointer', fontFamily: 'inherit', transition: 'all 0.15s',
                opacity: ( !name.trim() || !message.trim() ) ? 0.5 : 1,
              } }>
                { sending ? 'Sending...' : <><IcSend /> Send Message</> }
              </button>
            </form>
          </div>
        </div>

        {/* Bottom: GSTIN & Legal */ }
        <div style={ { textAlign: 'center', padding: '16px 0', borderTop: '1px solid #f3f4f6', fontSize: 12, color: '#9ca3af' } }>
          GSTIN: 19AAFFW7196L1Z8 · CIN: U72900WB2024PTC271440 · wecare.digital
        </div>
      </div>
    </Layout>
  );
};

export default ContactUsPage;
