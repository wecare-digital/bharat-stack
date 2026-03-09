/**
 * Interactive Message Composer
 * Compose and send WhatsApp interactive messages:
 * - List messages (up to 10 sections with rows)
 * - Reply buttons (up to 3 buttons)
 * - Location request
 * - CTA URL button (call-to-action with link)
 */

import React, { useState } from 'react';
import * as api from '../api/client';

interface InteractiveMessageComposerProps {
  contactId: string;
  phoneNumberId: string;
  onClose: () => void;
  onSent: () => void;
  onError: (msg: string) => void;
}

interface ListRow {
  id: string;
  title: string;
  description: string;
}

interface ListSection {
  title: string;
  rows: ListRow[];
}

interface Button {
  id: string;
  title: string;
}

type InteractiveType = 'list' | 'button' | 'location_request' | 'cta_url' | 'flow';

const InteractiveMessageComposer: React.FC<InteractiveMessageComposerProps> = ({
  contactId,
  phoneNumberId,
  onClose,
  onSent,
  onError,
}) => {
  const [sending, setSending] = useState(false);
  const [messageType, setMessageType] = useState<InteractiveType>('button');
  
  // Common fields
  const [header, setHeader] = useState('');
  const [body, setBody] = useState('');
  const [footer, setFooter] = useState('');

  // Button message fields
  const [buttons, setButtons] = useState<Button[]>([
    { id: 'btn_1', title: '' },
  ]);

  // List message fields
  const [buttonText, setButtonText] = useState('View Options');
  const [sections, setSections] = useState<ListSection[]>([
    { title: 'Options', rows: [{ id: 'row_1', title: '', description: '' }] },
  ]);

  // CTA URL fields
  const [ctaButtonText, setCtaButtonText] = useState('Visit');
  const [ctaUrl, setCtaUrl] = useState('');

  // Flow fields
  const [flowId, setFlowId] = useState('');
  const [flowButtonText, setFlowButtonText] = useState('Open Form');
  const [flowScreen, setFlowScreen] = useState('');

  const addButton = () => {
    if (buttons.length >= 3) return;
    setButtons([...buttons, { id: `btn_${buttons.length + 1}`, title: '' }]);
  };

  const removeButton = (index: number) => {
    if (buttons.length <= 1) return;
    setButtons(buttons.filter((_, i) => i !== index));
  };

  const updateButton = (index: number, title: string) => {
    const updated = [...buttons];
    updated[index] = { ...updated[index], title };
    setButtons(updated);
  };

  const addSection = () => {
    if (sections.length >= 10) return;
    setSections([...sections, { title: `Section ${sections.length + 1}`, rows: [{ id: `row_${Date.now()}`, title: '', description: '' }] }]);
  };

  const removeSection = (index: number) => {
    if (sections.length <= 1) return;
    setSections(sections.filter((_, i) => i !== index));
  };

  const updateSectionTitle = (index: number, title: string) => {
    const updated = [...sections];
    updated[index] = { ...updated[index], title };
    setSections(updated);
  };

  const addRow = (sectionIndex: number) => {
    const totalRows = sections.reduce((sum, s) => sum + s.rows.length, 0);
    if (totalRows >= 10) return;
    const updated = [...sections];
    updated[sectionIndex].rows.push({ id: `row_${Date.now()}`, title: '', description: '' });
    setSections(updated);
  };

  const removeRow = (sectionIndex: number, rowIndex: number) => {
    if (sections[sectionIndex].rows.length <= 1) return;
    const updated = [...sections];
    updated[sectionIndex].rows = updated[sectionIndex].rows.filter((_, i) => i !== rowIndex);
    setSections(updated);
  };

  const updateRow = (sectionIndex: number, rowIndex: number, field: 'title' | 'description', value: string) => {
    const updated = [...sections];
    updated[sectionIndex].rows[rowIndex] = { ...updated[sectionIndex].rows[rowIndex], [field]: value };
    setSections(updated);
  };

  const handleSend = async () => {
    if (!body.trim()) {
      onError('Body text is required');
      return;
    }

    if (messageType === 'button' && buttons.every(b => !b.title.trim())) {
      onError('At least one button is required');
      return;
    }

    if (messageType === 'list' && sections.every(s => s.rows.every(r => !r.title.trim()))) {
      onError('At least one list item is required');
      return;
    }

    if (messageType === 'cta_url' && !ctaUrl.trim()) {
      onError('URL is required for CTA button');
      return;
    }

    if (messageType === 'cta_url' && !ctaUrl.startsWith('http')) {
      onError('URL must start with http:// or https://');
      return;
    }

    if (messageType === 'flow' && !flowId.trim()) {
      onError('Flow ID is required');
      return;
    }

    setSending(true);
    try {
      const interactiveData: api.SendInteractiveRequest['interactiveData'] = {
        body,
        header: header || undefined,
        footer: footer || undefined,
      };

      if (messageType === 'button') {
        interactiveData.buttons = buttons.filter(b => b.title.trim()).map(b => ({
          id: b.id,
          title: b.title.trim().substring(0, 20),
        }));
      } else if (messageType === 'list') {
        interactiveData.buttonText = buttonText || 'View Options';
        interactiveData.sections = sections.map(s => ({
          title: s.title,
          rows: s.rows.filter(r => r.title.trim()).map(r => ({
            id: r.id,
            title: r.title.trim().substring(0, 24),
            description: r.description.trim().substring(0, 72),
          })),
        })).filter(s => s.rows.length > 0);
      } else if (messageType === 'cta_url') {
        interactiveData.buttonText = ctaButtonText.trim().substring(0, 20) || 'Visit';
        interactiveData.url = ctaUrl.trim();
      } else if (messageType === 'flow') {
        interactiveData.flowId = flowId.trim();
        interactiveData.buttonText = flowButtonText.trim().substring(0, 20) || 'Open Form';
        if (flowScreen.trim()) {
          interactiveData.flowScreen = flowScreen.trim();
        }
      }

      const result = await api.sendWhatsAppInteractive({
        contactId,
        phoneNumberId,
        interactiveType: messageType,
        interactiveData,
      });

      if (result) {
        onSent();
        onClose();
      } else {
        onError('Failed to send interactive message');
      }
    } catch (err: any) {
      onError(err.message || 'Send failed');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="interactive-composer">
      <div className="composer-header">
        <h3>Interactive Message</h3>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>

      <div className="composer-body">
        {/* Message Type Selector */}
        <div className="type-selector">
          <button
            className={`type-btn ${messageType === 'button' ? 'active' : ''}`}
            onClick={() => setMessageType('button')}
          >
            Buttons
          </button>
          <button
            className={`type-btn ${messageType === 'list' ? 'active' : ''}`}
            onClick={() => setMessageType('list')}
          >
            List
          </button>
          <button
            className={`type-btn ${messageType === 'cta_url' ? 'active' : ''}`}
            onClick={() => setMessageType('cta_url')}
          >
            CTA URL
          </button>
          <button
            className={`type-btn ${messageType === 'flow' ? 'active' : ''}`}
            onClick={() => setMessageType('flow')}
          >
            Flow
          </button>
          <button
            className={`type-btn ${messageType === 'location_request' ? 'active' : ''}`}
            onClick={() => setMessageType('location_request')}
          >
            Location
          </button>
        </div>

        {/* Common Fields */}
        <div className="form-group">
          <label>Header (optional)</label>
          <input
            type="text"
            value={header}
            onChange={(e) => setHeader(e.target.value)}
            placeholder="Header text..."
            maxLength={60}
          />
        </div>

        <div className="form-group">
          <label>Body *</label>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder={messageType === 'location_request' ? 'Please share your location' : 
                        messageType === 'cta_url' ? 'Click the button below to visit our website' :
                        messageType === 'flow' ? 'Please fill out the form below' :
                        'Message body...'}
            rows={3}
            maxLength={1024}
          />
        </div>

        <div className="form-group">
          <label>Footer (optional)</label>
          <input
            type="text"
            value={footer}
            onChange={(e) => setFooter(e.target.value)}
            placeholder="Footer text..."
            maxLength={60}
          />
        </div>

        {/* Button Message Fields */}
        {messageType === 'button' && (
          <div className="buttons-section">
            <label>Reply Buttons ({buttons.length}/3)</label>
            {buttons.map((btn, idx) => (
              <div key={btn.id} className="button-row">
                <input
                  type="text"
                  value={btn.title}
                  onChange={(e) => updateButton(idx, e.target.value)}
                  placeholder={`Button ${idx + 1}`}
                  maxLength={20}
                />
                {buttons.length > 1 && (
                  <button className="remove-btn" onClick={() => removeButton(idx)}>×</button>
                )}
              </div>
            ))}
            {buttons.length < 3 && (
              <button className="add-btn" onClick={addButton}>+ Add Button</button>
            )}
          </div>
        )}

        {/* List Message Fields */}
        {messageType === 'list' && (
          <div className="list-section">
            <div className="form-group">
              <label>Menu Button Text</label>
              <input
                type="text"
                value={buttonText}
                onChange={(e) => setButtonText(e.target.value)}
                placeholder="View Options"
                maxLength={20}
              />
            </div>

            <label>Sections & Items (max 10 items total)</label>
            {sections.map((section, sIdx) => (
              <div key={sIdx} className="section-block">
                <div className="section-header">
                  <input
                    type="text"
                    value={section.title}
                    onChange={(e) => updateSectionTitle(sIdx, e.target.value)}
                    placeholder="Section title"
                    maxLength={24}
                  />
                  {sections.length > 1 && (
                    <button className="remove-btn" onClick={() => removeSection(sIdx)}>×</button>
                  )}
                </div>
                {section.rows.map((row, rIdx) => (
                  <div key={row.id} className="row-block">
                    <input
                      type="text"
                      value={row.title}
                      onChange={(e) => updateRow(sIdx, rIdx, 'title', e.target.value)}
                      placeholder="Item title"
                      maxLength={24}
                    />
                    <input
                      type="text"
                      value={row.description}
                      onChange={(e) => updateRow(sIdx, rIdx, 'description', e.target.value)}
                      placeholder="Description (optional)"
                      maxLength={72}
                    />
                    {section.rows.length > 1 && (
                      <button className="remove-btn small" onClick={() => removeRow(sIdx, rIdx)}>×</button>
                    )}
                  </div>
                ))}
                <button className="add-btn small" onClick={() => addRow(sIdx)}>+ Add Item</button>
              </div>
            ))}
            {sections.length < 10 && (
              <button className="add-btn" onClick={addSection}>+ Add Section</button>
            )}
          </div>
        )}

        {/* CTA URL Fields */}
        {messageType === 'cta_url' && (
          <div className="cta-section">
            <div className="form-group">
              <label>Button Text *</label>
              <input
                type="text"
                value={ctaButtonText}
                onChange={(e) => setCtaButtonText(e.target.value)}
                placeholder="Visit Website"
                maxLength={20}
              />
            </div>
            <div className="form-group">
              <label>URL *</label>
              <input
                type="url"
                value={ctaUrl}
                onChange={(e) => setCtaUrl(e.target.value)}
                placeholder="https://example.com"
              />
            </div>
            <div className="info-box">
              <span className="info-icon">Info:</span>
              <span>CTA URL buttons let you share a clickable link without showing the raw URL in the message.</span>
            </div>
          </div>
        )}

        {/* Flow Fields */}
        {messageType === 'flow' && (
          <div className="flow-section">
            <div className="form-group">
              <label>Flow ID *</label>
              <input
                type="text"
                value={flowId}
                onChange={(e) => setFlowId(e.target.value)}
                placeholder="Enter your WhatsApp Flow ID"
              />
              <small>Get this from Meta Business Suite → WhatsApp → Flows</small>
            </div>
            <div className="form-group">
              <label>Button Text</label>
              <input
                type="text"
                value={flowButtonText}
                onChange={(e) => setFlowButtonText(e.target.value)}
                placeholder="Open Form"
                maxLength={20}
              />
            </div>
            <div className="form-group">
              <label>Initial Screen (optional)</label>
              <input
                type="text"
                value={flowScreen}
                onChange={(e) => setFlowScreen(e.target.value)}
                placeholder="SCREEN_NAME"
              />
              <small>Leave empty to start from the first screen</small>
            </div>
            <div className="info-box">
              <span className="info-icon">Note:</span>
              <span>WhatsApp Flows let you create interactive forms and surveys. Create flows in Meta Business Suite first.</span>
            </div>
          </div>
        )}

        {/* Location Request Info */}
        {messageType === 'location_request' && (
          <div className="info-box">
            <span className="info-icon">Info:</span>
            <span>This will ask the user to share their current location.</span>
          </div>
        )}
      </div>

      <div className="composer-footer">
        <button className="cancel-btn" onClick={onClose}>Cancel</button>
        <button className="send-btn" onClick={handleSend} disabled={sending}>
          {sending ? 'Sending...' : 'Send Message'}
        </button>
      </div>

      <style jsx>{`
        .interactive-composer {
          position: fixed;
          bottom: 80px;
          right: 20px;
          width: 400px;
          max-height: 80vh;
          background: white;
          border-radius: 12px;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
          display: flex;
          flex-direction: column;
          z-index: 1000;
        }
        .composer-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 16px;
          border-bottom: 1px solid #eee;
        }
        .composer-header h3 {
          margin: 0;
          font-size: 16px;
        }
        .close-btn {
          background: none;
          border: none;
          font-size: 24px;
          cursor: pointer;
          color: #666;
        }
        .composer-body {
          flex: 1;
          overflow-y: auto;
          padding: 16px;
        }
        .type-selector {
          display: flex;
          gap: 6px;
          margin-bottom: 16px;
          flex-wrap: wrap;
        }
        .type-btn {
          flex: 1;
          min-width: 80px;
          padding: 10px 6px;
          border: 1px solid #ddd;
          background: #f9f9f9;
          border-radius: 8px;
          cursor: pointer;
          font-size: 11px;
          transition: all 0.2s;
        }
        .type-btn:hover {
          background: #f0f0f0;
        }
        .type-btn.active {
          background: #f5f5f5;
          color: #000;
          border-color: #000;
          font-weight: 600;
        }
        .form-group {
          margin-bottom: 12px;
        }
        .form-group label {
          display: block;
          font-size: 13px;
          font-weight: 500;
          margin-bottom: 4px;
          color: #333;
        }
        .form-group input,
        .form-group textarea {
          width: 100%;
          padding: 8px 12px;
          border: 1px solid #ddd;
          border-radius: 6px;
          font-size: 14px;
        }
        .form-group input:focus,
        .form-group textarea:focus {
          outline: none;
          border-color: #000;
        }
        .buttons-section,
        .list-section,
        .cta-section,
        .flow-section {
          margin-top: 16px;
        }
        .buttons-section > label,
        .list-section > label {
          display: block;
          font-size: 13px;
          font-weight: 500;
          margin-bottom: 8px;
          color: #333;
        }
        .button-row {
          display: flex;
          gap: 8px;
          margin-bottom: 8px;
        }
        .button-row input {
          flex: 1;
          padding: 8px 12px;
          border: 1px solid #ddd;
          border-radius: 6px;
          font-size: 14px;
        }
        .remove-btn {
          width: 32px;
          height: 32px;
          border: none;
          background: #f9fafb;
          color: #1a3a2a;
          border-radius: 6px;
          cursor: pointer;
          font-size: 16px;
        }
        .remove-btn:hover {
          background: #f3f4f6;
        }
        .remove-btn.small {
          width: 24px;
          height: 24px;
          font-size: 14px;
        }
        .add-btn {
          width: 100%;
          padding: 8px;
          border: 1px dashed #ddd;
          background: none;
          border-radius: 6px;
          cursor: pointer;
          color: #666;
          font-size: 13px;
        }
        .add-btn:hover {
          border-color: #000;
          color: #000;
        }
        .add-btn.small {
          padding: 6px;
          font-size: 12px;
          margin-top: 4px;
        }
        .section-block {
          background: #f9f9f9;
          border-radius: 8px;
          padding: 12px;
          margin-bottom: 12px;
        }
        .section-header {
          display: flex;
          gap: 8px;
          margin-bottom: 8px;
        }
        .section-header input {
          flex: 1;
          padding: 8px 12px;
          border: 1px solid #ddd;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
        }
        .row-block {
          display: flex;
          gap: 6px;
          margin-bottom: 6px;
        }
        .row-block input {
          flex: 1;
          padding: 6px 10px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 13px;
        }
        .row-block input:first-child {
          flex: 0.8;
        }
        .info-box {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px;
          background: #f9fafb;
          border-radius: 8px;
          font-size: 13px;
          color: #0f2a1d;
          margin-top: 16px;
        }
        .info-icon {
          font-size: 16px;
        }
        .composer-footer {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
          padding: 12px 16px;
          border-top: 1px solid #eee;
        }
        .cancel-btn {
          padding: 8px 16px;
          border: 1px solid #ddd;
          background: white;
          border-radius: 6px;
          cursor: pointer;
          font-size: 14px;
        }
        .cancel-btn:hover {
          background: #f5f5f5;
        }
        .send-btn {
          padding: 8px 20px;
          border: 1px solid #000;
          background: #fff;
          color: #000;
          border-radius: 13px;
          cursor: pointer;
          font-size: 14px;
          font-weight: 500;
        }
        .send-btn:hover:not(:disabled) {
          background: #f5f5f5;
        }
        .send-btn:disabled {
          background: #9ca3af;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
};

export default InteractiveMessageComposer;
