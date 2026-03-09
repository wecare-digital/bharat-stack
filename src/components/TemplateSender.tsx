/**
 * Template Sender Component
 * Send template messages (including carousel) to contacts
 * Used when 24-hour window is closed or for marketing campaigns
 */

import React, { useState, useEffect } from 'react';
import * as api from '../api/client';

interface TemplateSenderProps {
  contactId: string;
  contactName: string;
  phoneNumberId: string;
  onClose: () => void;
  onSent: () => void;
  onError: (msg: string) => void;
}

interface TemplateVariable {
  index: number;
  value: string;
  placeholder: string;
}

const TemplateSender: React.FC<TemplateSenderProps> = ({
  contactId,
  contactName,
  phoneNumberId,
  onClose,
  onSent,
  onError,
}) => {
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [templates, setTemplates] = useState<api.WhatsAppTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<api.WhatsAppTemplate | null>(null);
  const [variables, setVariables] = useState<TemplateVariable[]>([]);
  const [cardVariables, setCardVariables] = useState<TemplateVariable[][]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [scheduleMode, setScheduleMode] = useState(false);
  const [scheduledDate, setScheduledDate] = useState('');
  const [scheduledTime, setScheduledTime] = useState('');

  // Load templates on mount
  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const data = await api.listTemplates();
      // Only show approved templates
      setTemplates(data.filter(t => t.status === 'APPROVED'));
    } catch (err) {
      console.error('Failed to load templates:', err);
    } finally {
      setLoading(false);
    }
  };

  // Extract variables from template when selected
  useEffect(() => {
    if (!selectedTemplate) {
      setVariables([]);
      setCardVariables([]);
      return;
    }

    const vars: TemplateVariable[] = [];
    const cardVars: TemplateVariable[][] = [];

    // Check if it's a carousel template
    const carouselComponent = selectedTemplate.components?.find(c => c.type === 'CAROUSEL');
    
    if (carouselComponent) {
      // Extract body variables
      const bodyComponent = selectedTemplate.components?.find(c => c.type === 'BODY');
      if (bodyComponent?.text) {
        const matches = bodyComponent.text.match(/\{\{(\d+)\}\}/g) || [];
        matches.forEach((match, idx) => {
          const num = parseInt(match.replace(/[{}]/g, ''));
          vars.push({
            index: num,
            value: '',
            placeholder: `Variable ${num}`,
          });
        });
      }

      // Extract card variables (simplified - each card may have body variables)
      const cards = (carouselComponent as any).cards || [];
      cards.forEach((card: any, cardIdx: number) => {
        const cardBodyVars: TemplateVariable[] = [];
        const cardBody = card.components?.find((c: any) => c.type === 'BODY');
        if (cardBody?.text) {
          const matches = cardBody.text.match(/\{\{(\d+)\}\}/g) || [];
          matches.forEach((match: string) => {
            const num = parseInt(match.replace(/[{}]/g, ''));
            cardBodyVars.push({
              index: num,
              value: '',
              placeholder: `Card ${cardIdx + 1} - Variable ${num}`,
            });
          });
        }
        cardVars.push(cardBodyVars);
      });
    } else {
      // Standard template - extract all variables
      selectedTemplate.components?.forEach(comp => {
        if (comp.text) {
          const matches = comp.text.match(/\{\{(\d+)\}\}/g) || [];
          matches.forEach(match => {
            const num = parseInt(match.replace(/[{}]/g, ''));
            if (!vars.find(v => v.index === num)) {
              vars.push({
                index: num,
                value: '',
                placeholder: `Variable ${num}`,
              });
            }
          });
        }
      });
    }

    // Sort by index
    vars.sort((a, b) => a.index - b.index);
    
    // Pre-fill first variable with contact name if available
    if (vars.length > 0 && contactName) {
      vars[0].value = contactName;
    }

    setVariables(vars);
    setCardVariables(cardVars);
  }, [selectedTemplate, contactName]);

  const updateVariable = (index: number, value: string) => {
    setVariables(vars => vars.map((v, i) => i === index ? { ...v, value } : v));
  };

  const updateCardVariable = (cardIdx: number, varIdx: number, value: string) => {
    setCardVariables(cards => cards.map((card, ci) => 
      ci === cardIdx 
        ? card.map((v, vi) => vi === varIdx ? { ...v, value } : v)
        : card
    ));
  };

  const handleSend = async () => {
    if (!selectedTemplate) {
      onError('Please select a template');
      return;
    }

    // Validate required variables
    const emptyVars = variables.filter(v => !v.value.trim());
    if (emptyVars.length > 0) {
      onError(`Please fill in all variables (${emptyVars.length} empty)`);
      return;
    }

    setSending(true);
    try {
      // Check if scheduling
      if (scheduleMode && scheduledDate && scheduledTime) {
        const scheduledAt = new Date(`${scheduledDate}T${scheduledTime}`).toISOString();
        const result = await api.scheduleTemplateMessage({
          contactId,
          templateName: selectedTemplate.name,
          templateParams: variables.map(v => v.value),
          phoneNumberId,
          scheduledAt,
        });

        if (result) {
          onSent();
          onClose();
        } else {
          onError('Failed to schedule message');
        }
      } else {
        // Send immediately
        const isCarousel = selectedTemplate.components?.some(c => c.type === 'CAROUSEL');
        
        let result;
        if (isCarousel) {
          result = await api.sendCarouselTemplateMessage({
            contactId,
            templateName: selectedTemplate.name,
            language: selectedTemplate.language,
            phoneNumberId,
            bodyParams: variables.map(v => v.value),
            cardParams: cardVariables.map(card => card.map(v => v.value)),
          });
        } else {
          result = await api.sendWhatsAppTemplateMessage({
            contactId,
            templateName: selectedTemplate.name,
            language: selectedTemplate.language,
            templateParams: variables.map(v => v.value),
            phoneNumberId,
          });
        }

        if (result) {
          onSent();
          onClose();
        } else {
          onError('Failed to send template message');
        }
      }
    } catch (err: any) {
      onError(err.message || 'Send failed');
    } finally {
      setSending(false);
    }
  };

  // Filter templates
  const filteredTemplates = templates.filter(t => {
    const matchesSearch = t.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = filterCategory === 'all' || t.category === filterCategory;
    return matchesSearch && matchesCategory;
  });

  // Get preview text with variables filled in
  const getPreviewText = () => {
    if (!selectedTemplate) return '';
    
    let preview = '';
    selectedTemplate.components?.forEach(comp => {
      if (comp.type === 'HEADER' && comp.text) {
        preview += `*${comp.text}*\n\n`;
      } else if (comp.type === 'BODY' && comp.text) {
        let bodyText = comp.text;
        variables.forEach(v => {
          bodyText = bodyText.replace(`{{${v.index}}}`, v.value || `[${v.placeholder}]`);
        });
        preview += bodyText + '\n';
      } else if (comp.type === 'FOOTER' && comp.text) {
        preview += `\n_${comp.text}_`;
      }
    });
    return preview;
  };

  // Check if template is carousel
  const isCarouselTemplate = selectedTemplate?.components?.some(c => c.type === 'CAROUSEL');

  return (
    <div className="template-sender">
      <div className="sender-header">
        <h3>Send Template Message</h3>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>

      <div className="sender-body">
        {/* Template Selection */}
        {!selectedTemplate ? (
          <div className="template-selection">
            <div className="search-filters">
              <input
                type="text"
                placeholder="Search templates..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="search-input"
              />
              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                className="category-filter"
              >
                <option value="all">All Categories</option>
                <option value="UTILITY">Utility</option>
                <option value="MARKETING">Marketing</option>
                <option value="AUTHENTICATION">Authentication</option>
              </select>
            </div>

            {loading ? (
              <div className="loading">Loading templates...</div>
            ) : filteredTemplates.length === 0 ? (
              <div className="empty">No approved templates found</div>
            ) : (
              <div className="template-list">
                {filteredTemplates.map(template => (
                  <div
                    key={template.id}
                    className="template-item"
                    onClick={() => setSelectedTemplate(template)}
                  >
                    <div className="template-info">
                      <span className="template-name">{template.name}</span>
                      <span className={`category-badge ${template.category.toLowerCase()}`}>
                        {template.category}
                      </span>
                      {template.components?.some(c => c.type === 'CAROUSEL') && (
                        <span className="carousel-badge">Carousel</span>
                      )}
                    </div>
                    <div className="template-preview">
                      {template.components?.find(c => c.type === 'BODY')?.text?.substring(0, 80) || 'No preview'}...
                    </div>
                    <div className="template-lang">{template.language}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="template-config">
            <button className="back-btn" onClick={() => setSelectedTemplate(null)}>
              ← Back to templates
            </button>

            <div className="selected-template">
              <div className="template-header-info">
                <span className="template-name">{selectedTemplate.name}</span>
                <span className={`category-badge ${selectedTemplate.category.toLowerCase()}`}>
                  {selectedTemplate.category}
                </span>
                {isCarouselTemplate && <span className="carousel-badge">Carousel</span>}
              </div>
            </div>

            {/* Variables Input */}
            {variables.length > 0 && (
              <div className="variables-section">
                <label>Template Variables</label>
                {variables.map((v, idx) => (
                  <div key={idx} className="variable-row">
                    <span className="var-label">{`{{${v.index}}}`}</span>
                    <input
                      type="text"
                      value={v.value}
                      onChange={(e) => updateVariable(idx, e.target.value)}
                      placeholder={v.placeholder}
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Card Variables for Carousel */}
            {isCarouselTemplate && cardVariables.length > 0 && (
              <div className="card-variables-section">
                <label>Card Variables</label>
                {cardVariables.map((card, cardIdx) => (
                  card.length > 0 && (
                    <div key={cardIdx} className="card-vars">
                      <span className="card-label">Card {cardIdx + 1}</span>
                      {card.map((v, varIdx) => (
                        <div key={varIdx} className="variable-row">
                          <span className="var-label">{`{{${v.index}}}`}</span>
                          <input
                            type="text"
                            value={v.value}
                            onChange={(e) => updateCardVariable(cardIdx, varIdx, e.target.value)}
                            placeholder={v.placeholder}
                          />
                        </div>
                      ))}
                    </div>
                  )
                ))}
              </div>
            )}

            {/* Preview */}
            <div className="preview-section">
              <label>Preview</label>
              <div className="preview-box">
                <div className="preview-recipient">To: {contactName}</div>
                <div className="preview-content">{getPreviewText()}</div>
                {isCarouselTemplate && (
                  <div className="carousel-indicator">
                    + {cardVariables.length} carousel cards
                  </div>
                )}
              </div>
            </div>

            {/* Schedule Option */}
            <div className="schedule-section">
              <label className="schedule-toggle">
                <input
                  type="checkbox"
                  checked={scheduleMode}
                  onChange={(e) => setScheduleMode(e.target.checked)}
                />
                <span>Schedule for later</span>
              </label>
              
              {scheduleMode && (
                <div className="schedule-inputs">
                  <input
                    type="date"
                    value={scheduledDate}
                    onChange={(e) => setScheduledDate(e.target.value)}
                    min={new Date().toISOString().split('T')[0]}
                  />
                  <input
                    type="time"
                    value={scheduledTime}
                    onChange={(e) => setScheduledTime(e.target.value)}
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="sender-footer">
        <button className="cancel-btn" onClick={onClose}>Cancel</button>
        <button
          className="send-btn"
          onClick={handleSend}
          disabled={!selectedTemplate || sending}
        >
          {sending ? 'Sending...' : scheduleMode ? 'Schedule' : 'Send Now'}
        </button>
      </div>

      <style jsx>{`
        .template-sender {
          position: fixed;
          bottom: 80px;
          right: 20px;
          width: 450px;
          max-height: 85vh;
          background: white;
          border-radius: 12px;
          box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
          display: flex;
          flex-direction: column;
          z-index: 1000;
        }
        .sender-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 14px 18px;
          border-bottom: 1px solid #eee;
        }
        .sender-header h3 {
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
        .sender-body {
          flex: 1;
          overflow-y: auto;
          padding: 16px;
        }
        .search-filters {
          display: flex;
          gap: 8px;
          margin-bottom: 12px;
        }
        .search-input {
          flex: 1;
          padding: 10px 12px;
          border: 1px solid #ddd;
          border-radius: 8px;
          font-size: 14px;
        }
        .category-filter {
          padding: 10px 12px;
          border: 1px solid #ddd;
          border-radius: 8px;
          font-size: 14px;
          min-width: 120px;
        }
        .loading, .empty {
          text-align: center;
          padding: 40px 20px;
          color: #666;
        }
        .template-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 400px;
          overflow-y: auto;
        }
        .template-item {
          padding: 12px;
          border: 1px solid #eee;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s;
        }
        .template-item:hover {
          border-color: #000;
          background: #f5f5f5;
        }
        .template-info {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 6px;
        }
        .template-name {
          font-weight: 500;
          font-size: 14px;
        }
        .category-badge {
          font-size: 10px;
          padding: 2px 8px;
          border-radius: 10px;
          color: white;
        }
        .category-badge.utility { background: #1a3a2a; }
        .category-badge.marketing { background: #1a3a2a; }
        .category-badge.authentication { background: #0f2a1d; }
        .carousel-badge {
          font-size: 10px;
          padding: 2px 8px;
          background: #f9fafb;
          color: #0f2a1d;
          border-radius: 10px;
        }
        .template-preview {
          font-size: 12px;
          color: #666;
          line-height: 1.4;
        }
        .template-lang {
          font-size: 11px;
          color: #999;
          margin-top: 4px;
        }
        .back-btn {
          background: none;
          border: none;
          color: #1a3a2a;
          cursor: pointer;
          font-size: 13px;
          padding: 0;
          margin-bottom: 12px;
        }
        .back-btn:hover {
          text-decoration: underline;
        }
        .selected-template {
          padding: 12px;
          background: #f9f9f9;
          border-radius: 8px;
          margin-bottom: 16px;
        }
        .template-header-info {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .variables-section, .card-variables-section {
          margin-bottom: 16px;
        }
        .variables-section > label, .card-variables-section > label {
          display: block;
          font-size: 13px;
          font-weight: 500;
          margin-bottom: 8px;
          color: #333;
        }
        .variable-row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;
        }
        .var-label {
          font-size: 12px;
          color: #666;
          min-width: 50px;
          font-family: monospace;
        }
        .variable-row input {
          flex: 1;
          padding: 8px 12px;
          border: 1px solid #ddd;
          border-radius: 6px;
          font-size: 14px;
        }
        .variable-row input:focus {
          outline: none;
          border-color: #000;
        }
        .card-vars {
          background: #f5f5f5;
          padding: 10px;
          border-radius: 6px;
          margin-bottom: 8px;
        }
        .card-label {
          display: block;
          font-size: 12px;
          font-weight: 500;
          color: #666;
          margin-bottom: 8px;
        }
        .preview-section {
          margin-bottom: 16px;
        }
        .preview-section > label {
          display: block;
          font-size: 13px;
          font-weight: 500;
          margin-bottom: 8px;
          color: #333;
        }
        .preview-box {
          background: #e5ddd5;
          padding: 12px;
          border-radius: 8px;
        }
        .preview-recipient {
          font-size: 11px;
          color: #666;
          margin-bottom: 8px;
        }
        .preview-content {
          background: #dcf8c6;
          padding: 10px 12px;
          border-radius: 8px;
          font-size: 14px;
          line-height: 1.5;
          white-space: pre-wrap;
        }
        .carousel-indicator {
          margin-top: 8px;
          font-size: 12px;
          color: #0f2a1d;
          background: #f9fafb;
          padding: 6px 10px;
          border-radius: 6px;
          text-align: center;
        }
        .schedule-section {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid #eee;
        }
        .schedule-toggle {
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          font-size: 14px;
        }
        .schedule-toggle input {
          width: 18px;
          height: 18px;
        }
        .schedule-inputs {
          display: flex;
          gap: 8px;
          margin-top: 12px;
        }
        .schedule-inputs input {
          flex: 1;
          padding: 10px 12px;
          border: 1px solid #ddd;
          border-radius: 6px;
          font-size: 14px;
        }
        .sender-footer {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
          padding: 14px 18px;
          border-top: 1px solid #eee;
        }
        .cancel-btn {
          padding: 10px 18px;
          border: 1px solid #ddd;
          background: white;
          border-radius: 8px;
          cursor: pointer;
          font-size: 14px;
        }
        .cancel-btn:hover {
          background: #f5f5f5;
        }
        .send-btn {
          padding: 10px 24px;
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
        @media (max-width: 500px) {
          .template-sender {
            width: calc(100vw - 40px);
            right: 20px;
            left: 20px;
          }
        }
      `}</style>
    </div>
  );
};

export default TemplateSender;
