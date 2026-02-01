/**
 * Rich Text Editor Component
 * WhatsApp-style editor with templates, variables, and AI suggestions
 * Fetches real templates from WhatsApp API
 */

import React, { useState, useRef, useEffect } from 'react';
import styles from '../styles/RichTextEditor.module.css';
import * as api from '../api/client';
import { generateReferenceId } from '../lib/formatters';
import { PAYMENT_CONFIG, DEFAULT_GSTIN } from '../config/constants';

// Payment dialog state
interface PaymentDialogState {
  itemName: string;
  amount: string;
  quantity: string;
  referenceId: string;
  promo: string;      // Discount/Promo
  express: string;    // Delivery/Express
  gstRate: string;    // GST rate (0, 3, 5, 12, 18, 28)
  gstin: string;      // GSTIN number
}

interface RichTextEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  maxLength?: number;
  showCharCount?: boolean;
  showAISuggestions?: boolean;
  channel?: 'whatsapp' | 'sms' | 'email' | 'rcs' | 'voice';
  onSend?: () => void;
  contactContext?: string;
  onTemplateSelect?: (template: api.WhatsAppTemplate) => void;
  selectedContactId?: string;
  phoneNumberId?: string;
  onAttachClick?: () => void;
}

// Variable placeholders for templates
const VARIABLES = [
  { key: '{{1}}', label: 'Variable 1', icon: '①' },
  { key: '{{2}}', label: 'Variable 2', icon: '②' },
  { key: '{{3}}', label: 'Variable 3', icon: '③' },
  { key: '{{4}}', label: 'Variable 4', icon: '④' },
];

const RichTextEditor: React.FC<RichTextEditorProps> = ({
  value,
  onChange,
  placeholder = 'Type a message...',
  disabled = false,
  maxLength,
  showCharCount = false,
  showAISuggestions = true,
  channel = 'whatsapp',
  onSend,
  contactContext,
  onTemplateSelect,
  selectedContactId,
  phoneNumberId,
  onAttachClick,
}) => {
  const [showTemplates, setShowTemplates] = useState(false);
  const [showVariables, setShowVariables] = useState(false);
  const [showFormatting, setShowFormatting] = useState(false);
  const [templates, setTemplates] = useState<api.WhatsAppTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState<string[]>([]);
  const [loadingAI, setLoadingAI] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [sendingTemplate, setSendingTemplate] = useState(false);
  const [templateMessage, setTemplateMessage] = useState<string | null>(null);
  const [templateVariableDialog, setTemplateVariableDialog] = useState<{
    template: api.WhatsAppTemplate;
    variables: string[];
    variableCount: number;
  } | null>(null);
  const [showPaymentDialog, setShowPaymentDialog] = useState(false);
  const [paymentForm, setPaymentForm] = useState<PaymentDialogState>({
    itemName: '',
    amount: '',
    quantity: '1',
    referenceId: '',
    promo: '0',
    express: '0',
    gstRate: '0',
    gstin: DEFAULT_GSTIN,
  });
  const [sendingPayment, setSendingPayment] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Load templates from API
  useEffect(() => {
    if (channel === 'whatsapp') {
      loadTemplates();
    }
  }, [channel]);

  const loadTemplates = async () => {
    setTemplatesLoading(true);
    try {
      const data = await api.listWhatsAppTemplates();
      setTemplates(data);
    } catch (error) {
      console.error('Failed to load templates:', error);
    } finally {
      setTemplatesLoading(false);
    }
  };

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowTemplates(false);
        setShowVariables(false);
        setShowFormatting(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px';
    }
  }, [value]);

  const insertAtCursor = (text: string) => {
    const textarea = textareaRef.current;
    if (textarea) {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const newValue = value.substring(0, start) + text + value.substring(end);
      onChange(newValue);
      setTimeout(() => {
        textarea.selectionStart = textarea.selectionEnd = start + text.length;
        textarea.focus();
      }, 0);
    } else {
      onChange(value + text);
    }
  };

  const wrapSelection = (prefix: string, suffix: string) => {
    const textarea = textareaRef.current;
    if (textarea) {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const selected = value.substring(start, end);
      const newValue = value.substring(0, start) + prefix + selected + suffix + value.substring(end);
      onChange(newValue);
      setTimeout(() => {
        textarea.selectionStart = start + prefix.length;
        textarea.selectionEnd = end + prefix.length;
        textarea.focus();
      }, 0);
    }
    setShowFormatting(false);
  };

  // Count variables in template body ({{1}}, {{2}}, etc.)
  const countTemplateVariables = (template: api.WhatsAppTemplate): number => {
    const bodyComponent = template.components.find(c => c.type === 'BODY');
    if (!bodyComponent?.text) return 0;
    const matches = bodyComponent.text.match(/\{\{\d+\}\}/g);
    return matches ? matches.length : 0;
  };

  const applyTemplate = async (template: api.WhatsAppTemplate) => {
    // Check if template has variables
    const varCount = countTemplateVariables(template);
    
    if (varCount > 0 && selectedContactId && phoneNumberId) {
      // Show variable input dialog
      setTemplateVariableDialog({
        template,
        variables: Array(varCount).fill(''),
        variableCount: varCount,
      });
      setShowTemplates(false);
      return;
    }
    
    // If we have contact and phone number, send the template directly
    if (selectedContactId && phoneNumberId) {
      await sendTemplateMessage(template, []);
    } else {
      // Fallback: put template body text in editor for manual editing
      const bodyComponent = template.components.find(c => c.type === 'BODY');
      const bodyText = bodyComponent?.text || `[Template: ${template.name}]`;
      onChange(bodyText);
      setShowTemplates(false);
      if (onTemplateSelect) {
        onTemplateSelect(template);
      }
    }
    textareaRef.current?.focus();
  };

  // Send template with variables
  const sendTemplateMessage = async (template: api.WhatsAppTemplate, variables: string[]) => {
    if (!selectedContactId || !phoneNumberId) return;
    
    setSendingTemplate(true);
    setTemplateMessage(`Sending template: ${template.name}...`);
    setTemplateVariableDialog(null);
    
    try {
      const result = await api.sendWhatsAppTemplateMessage({
        contactId: selectedContactId,
        templateName: template.name,
        language: template.language,
        phoneNumberId: phoneNumberId,
        templateParams: variables.filter(v => v.trim() !== ''),
      });
      
      if (result) {
        setTemplateMessage(`✓ Template "${template.name}" sent!`);
        setTimeout(() => setTemplateMessage(null), 3000);
      } else {
        setTemplateMessage(`× Failed to send template`);
        setTimeout(() => setTemplateMessage(null), 3000);
      }
    } catch (error: any) {
      console.error('Template send error:', error);
      setTemplateMessage(`× Error: ${error.message || 'Failed to send'}`);
      setTimeout(() => setTemplateMessage(null), 3000);
    } finally {
      setSendingTemplate(false);
      setShowTemplates(false);
    }
  };

  // Update variable value in dialog
  const updateVariableValue = (index: number, value: string) => {
    if (!templateVariableDialog) return;
    const newVars = [...templateVariableDialog.variables];
    newVars[index] = value;
    setTemplateVariableDialog({ ...templateVariableDialog, variables: newVars });
  };

  const insertVariable = (variable: typeof VARIABLES[0]) => {
    insertAtCursor(variable.key);
    setShowVariables(false);
  };

  const fetchAISuggestions = async () => {
    if (!value.trim() || value.length < 3) {
      setAiError('Type at least 3 characters');
      setTimeout(() => setAiError(null), 2000);
      return;
    }
    
    setLoadingAI(true);
    setAiError(null);
    setShowSuggestions(false);
    
    try {
      console.log('Fetching AI suggestion for:', value.substring(0, 50));
      
      // Use the AI generate API with external context for inbox
      const result = await api.generateAIResponse(value, {
        contactName: contactContext,
        channel: channel,
      });
      
      console.log('AI response:', result);
      
      if (result && result.response && result.response.trim()) {
        setAiSuggestions([result.response]);
        setShowSuggestions(true);
        setAiError(null);
      } else {
        // Show fallback if no response
        setAiSuggestions([
          'Thank you for reaching out! How can I assist you today?',
          'I understand. Let me help you with that.',
        ]);
        setShowSuggestions(true);
      }
    } catch (error: any) {
      console.error('AI suggestions error:', error);
      setAiError('AI service error');
      setTimeout(() => setAiError(null), 3000);
      
      // Show fallback suggestions even on error
      setAiSuggestions([
        'Thank you for your message. How can I help you?',
        'Is there anything else you need assistance with?',
      ]);
      setShowSuggestions(true);
    } finally {
      setLoadingAI(false);
    }
  };

  // Send payment message - ALWAYS use interactive mode from inbox
  // Interactive payments MUST go from WECARE.DIGITAL number (configured in constants)
  
  const sendPaymentMessage = async () => {
    if (!selectedContactId) return;
    if (!paymentForm.itemName || !paymentForm.amount || !paymentForm.referenceId) return;

    setSendingPayment(true);
    setTemplateMessage('Sending interactive payment request...');

    try {
      const amountInPaise = Math.round(parseFloat(paymentForm.amount) * 100);
      const promoInPaise = Math.round(parseFloat(paymentForm.promo || '0') * 100);
      const expressInPaise = Math.round(parseFloat(paymentForm.express || '0') * 100);
      const gstRate = parseInt(paymentForm.gstRate) || 0;
      // Calculate tax based on GST rate
      const taxInPaise = Math.round(amountInPaise * gstRate / 100);

      console.log('Sending payment from RichTextEditor:', {
        contactId: selectedContactId,
        itemName: paymentForm.itemName,
        amount: amountInPaise,
        quantity: paymentForm.quantity,
        discount: promoInPaise,
        shipping: expressInPaise,
        gstRate,
        tax: taxInPaise,
        gstin: paymentForm.gstin,
      });

      const result = await api.sendWhatsAppPaymentMessage({
        contactId: selectedContactId,
        // Interactive payments MUST go from WECARE.DIGITAL (has Razorpay)
        phoneNumberId: PAYMENT_CONFIG.phoneNumberId,
        referenceId: paymentForm.referenceId,
        items: [{
          name: paymentForm.itemName,
          amount: amountInPaise,
          quantity: parseInt(paymentForm.quantity) || 1,
        }],
        discount: promoInPaise,
        delivery: expressInPaise,
        tax: taxInPaise,
        gstRate: gstRate,
        gstin: paymentForm.gstin || DEFAULT_GSTIN,
        useInteractive: true, // ALWAYS use interactive mode from inbox
      });

      console.log('Payment result:', result);

      if (result) {
        setTemplateMessage(`✓ Payment request sent! Ref: ${paymentForm.referenceId}`);
        setShowPaymentDialog(false);
        setPaymentForm({ itemName: '', amount: '', quantity: '1', referenceId: '', promo: '0', express: '0', gstRate: '0', gstin: DEFAULT_GSTIN });
      } else {
        const connStatus = api.getConnectionStatus();
        setTemplateMessage(`× Failed: ${connStatus.lastError || 'Unknown error'}`);
      }
    } catch (error: any) {
      console.error('Payment send error:', error);
      setTemplateMessage(`× Error: ${error.message || 'Failed to send'}`);
    } finally {
      setSendingPayment(false);
      setTimeout(() => setTemplateMessage(null), 5000);
    }
  };

  const applySuggestion = (suggestion: string) => {
    onChange(suggestion);
    setShowSuggestions(false);
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && onSend) {
      e.preventDefault();
      onSend();
    }
  };

  const charCount = value.length;
  const isOverLimit = maxLength ? charCount > maxLength : false;
  const hasVariables = value.includes('{{');

  // Get template status badge
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED': return { text: '✓', class: 'approved' };
      case 'PENDING': return { text: '○', class: 'pending' };
      case 'REJECTED': return { text: '×', class: 'rejected' };
      default: return { text: '?', class: '' };
    }
  };

  return (
    <div className={styles['rich-text-editor']} ref={dropdownRef}>
      {/* Template Send Status */}
      {templateMessage && (
        <div className={styles['template-message']}>
          {templateMessage}
        </div>
      )}

      {/* AI Suggestions Panel */}
      {showAISuggestions && showSuggestions && aiSuggestions.length > 0 && (
        <div className={styles['ai-suggestions-panel']}>
          <div className={styles['ai-suggestions-header']}>
            <span>◇ AI Suggestion</span>
            <button onClick={() => setShowSuggestions(false)}>×</button>
          </div>
          <div className={styles['ai-suggestions-list']}>
            {aiSuggestions.map((suggestion, i) => (
              <button key={i} className={styles['ai-suggestion-item']} onClick={() => applySuggestion(suggestion)}>
                {suggestion.length > 100 ? suggestion.substring(0, 100) + '...' : suggestion}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Templates Dropdown */}
      {showTemplates && (
        <div className={styles['dropdown-panel']}>
          <div className={styles['dropdown-header']}>
            <span>▤ WhatsApp Templates</span>
            <button onClick={() => setShowTemplates(false)}>×</button>
          </div>
          <div className={styles['dropdown-list']}>
            {templatesLoading ? (
              <div className={styles['dropdown-loading']}>Loading templates...</div>
            ) : templates.length > 0 ? (
              templates.map((template) => {
                const badge = getStatusBadge(template.status);
                const bodyComponent = template.components.find(c => c.type === 'BODY');
                const preview = bodyComponent?.text?.substring(0, 50) || '';
                const varCount = countTemplateVariables(template);
                return (
                  <button 
                    key={template.id} 
                    className={styles['dropdown-item']} 
                    onClick={() => applyTemplate(template)}
                    disabled={template.status !== 'APPROVED' || sendingTemplate}
                  >
                    <span className={`${styles['template-status']} ${styles[badge.class]}`}>{badge.text}</span>
                    <div className={styles['template-info']}>
                      <span className={styles['template-name']}>{template.name}</span>
                      {preview && <span className={styles['template-preview']}>{preview}...</span>}
                    </div>
                    <span className={styles['template-category']}>
                      {template.category}
                      {varCount > 0 && <span className={styles['var-count']}> ({varCount} var)</span>}
                    </span>
                  </button>
                );
              })
            ) : (
              <div className={styles['dropdown-empty']}>
                <p>No templates found</p>
                <p className={styles['dropdown-hint-text']}>Templates are managed in AWS Console or Meta Business Suite</p>
              </div>
            )}
          </div>
          <div className={styles['dropdown-hint']}>
            {selectedContactId ? 'Click to send template directly' : 'Select a contact first to send templates'}
          </div>
        </div>
      )}

      {/* Template Variable Input Dialog */}
      {templateVariableDialog && (
        <div className={styles['variable-dialog']}>
          <div className={styles['variable-dialog-header']}>
            <span>▤ {templateVariableDialog.template.name}</span>
            <button onClick={() => setTemplateVariableDialog(null)}>×</button>
          </div>
          <div className={styles['variable-dialog-preview']}>
            {templateVariableDialog.template.components.find(c => c.type === 'BODY')?.text || ''}
          </div>
          <div className={styles['variable-dialog-inputs']}>
            {templateVariableDialog.variables.map((val, i) => (
              <div key={i} className={styles['variable-input-row']}>
                <label>{`{{${i + 1}}}`}</label>
                <input
                  type="text"
                  value={val}
                  onChange={(e) => updateVariableValue(i, e.target.value)}
                  placeholder={`Enter value for variable ${i + 1}`}
                  autoFocus={i === 0}
                />
              </div>
            ))}
          </div>
          <div className={styles['variable-dialog-actions']}>
            <button 
              className={styles['cancel-btn']}
              onClick={() => setTemplateVariableDialog(null)}
            >
              Cancel
            </button>
            <button 
              className={styles['send-template-btn']}
              onClick={() => sendTemplateMessage(templateVariableDialog.template, templateVariableDialog.variables)}
              disabled={sendingTemplate || templateVariableDialog.variables.some(v => !v.trim())}
            >
              {sendingTemplate ? 'Sending...' : 'Send Template'}
            </button>
          </div>
        </div>
      )}

      {/* Payment Dialog */}
      {showPaymentDialog && (
        <div className={`${styles['variable-dialog']} ${styles['payment-dialog']}`}>
          <div className={styles['variable-dialog-header']}>
            <span>Payment Request</span>
            <button onClick={() => setShowPaymentDialog(false)}>×</button>
          </div>
          <div className={styles['variable-dialog-preview']}>
            Razorpay UPI | +91 93309 94400
          </div>
          <div className={styles['variable-dialog-inputs']}>
            <div className={styles['payment-grid']}>
              <div className={`${styles['variable-input-row']} ${styles['full-width']}`}>
                <label>Ref ID</label>
                <input
                  type="text"
                  value={paymentForm.referenceId}
                  onChange={(e) => setPaymentForm({...paymentForm, referenceId: e.target.value})}
                  placeholder="WDSRXXXXXXXX"
                  readOnly
                />
              </div>
              <div className={`${styles['variable-input-row']} ${styles['full-width']}`}>
                <label>Item Name *</label>
                <input
                  type="text"
                  value={paymentForm.itemName}
                  onChange={(e) => setPaymentForm({...paymentForm, itemName: e.target.value})}
                  placeholder="Service Fee"
                  autoFocus
                />
              </div>
              <div className={styles['variable-input-row']}>
                <label>Amount (₹) *</label>
                <input
                  type="number"
                  value={paymentForm.amount}
                  onChange={(e) => setPaymentForm({...paymentForm, amount: e.target.value})}
                  placeholder="100"
                  step="0.01"
                  min="1"
                />
              </div>
              <div className={styles['variable-input-row']}>
                <label>Qty *</label>
                <input
                  type="number"
                  value={paymentForm.quantity}
                  onChange={(e) => setPaymentForm({...paymentForm, quantity: e.target.value})}
                  placeholder="1"
                  min="1"
                />
              </div>
              <div className={styles['variable-input-row']}>
                <label>Promo (₹)</label>
                <input
                  type="number"
                  value={paymentForm.promo}
                  onChange={(e) => setPaymentForm({...paymentForm, promo: e.target.value})}
                  placeholder="0"
                  step="0.01"
                  min="0"
                />
              </div>
              <div className={styles['variable-input-row']}>
                <label>Express (₹)</label>
                <input
                  type="number"
                  value={paymentForm.express}
                  onChange={(e) => setPaymentForm({...paymentForm, express: e.target.value})}
                  placeholder="0"
                  step="0.01"
                  min="0"
                />
              </div>
              <div className={styles['variable-input-row']}>
                <label>Tax Rate</label>
                <select
                  value={paymentForm.gstRate}
                  onChange={(e) => setPaymentForm({...paymentForm, gstRate: e.target.value})}
                >
                  <option value="0">0%</option>
                  <option value="3">3%</option>
                  <option value="5">5%</option>
                  <option value="12">12%</option>
                  <option value="18">18%</option>
                  <option value="28">28%</option>
                </select>
              </div>
              <div className={styles['variable-input-row']}>
                <label>GSTIN</label>
                <input
                  type="text"
                  value={paymentForm.gstin}
                  onChange={(e) => setPaymentForm({...paymentForm, gstin: e.target.value})}
                  placeholder={DEFAULT_GSTIN}
                />
              </div>
            </div>
          </div>
          <div className={styles['variable-dialog-actions']}>
            <button className={styles['cancel-btn']} onClick={() => setShowPaymentDialog(false)}>
              Cancel
            </button>
            <button
              className={styles['send-template-btn']}
              onClick={sendPaymentMessage}
              disabled={sendingPayment || !paymentForm.itemName || !paymentForm.amount || !paymentForm.referenceId}
            >
              {sendingPayment ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      )}

      {/* Variables Dropdown */}
      {showVariables && (
        <div className={styles['dropdown-panel']}>
          <div className={styles['dropdown-header']}>
            <span>⊕ Variables</span>
            <button onClick={() => setShowVariables(false)}>×</button>
          </div>
          <div className={styles['dropdown-list']}>
            {VARIABLES.map((variable) => (
              <button key={variable.key} className={styles['dropdown-item']} onClick={() => insertVariable(variable)}>
                <span className={styles['variable-icon']}>{variable.icon}</span>
                <span>{variable.key}</span>
                <span className={styles['variable-label']}>{variable.label}</span>
              </button>
            ))}
          </div>
          <div className={styles['dropdown-hint']}>
            Variables are replaced when sending templates
          </div>
        </div>
      )}

      {/* Formatting Dropdown */}
      {showFormatting && channel === 'whatsapp' && (
        <div className={styles['dropdown-panel']}>
          <div className={styles['dropdown-header']}>
            <span>◈ Formatting</span>
            <button onClick={() => setShowFormatting(false)}>×</button>
          </div>
          <div className={styles['dropdown-list']}>
            <button className={styles['dropdown-item']} onClick={() => wrapSelection('*', '*')}>
              <span className={styles['format-icon']}><strong>B</strong></span>
              <span>Bold</span>
              <span className={styles['format-hint']}>*text*</span>
            </button>
            <button className={styles['dropdown-item']} onClick={() => wrapSelection('_', '_')}>
              <span className={styles['format-icon']}><em>I</em></span>
              <span>Italic</span>
              <span className={styles['format-hint']}>_text_</span>
            </button>
            <button className={styles['dropdown-item']} onClick={() => wrapSelection('~', '~')}>
              <span className={styles['format-icon']}><s>S</s></span>
              <span>Strikethrough</span>
              <span className={styles['format-hint']}>~text~</span>
            </button>
            <button className={styles['dropdown-item']} onClick={() => wrapSelection('```', '```')}>
              <span className={styles['format-icon']}>{'<>'}</span>
              <span>Monospace</span>
              <span className={styles['format-hint']}>```text```</span>
            </button>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className={styles['editor-toolbar']}>
        {/* Templates Button (WhatsApp only) */}
        {channel === 'whatsapp' && (
          <button
            type="button"
            className={`${styles['toolbar-btn']} ${showTemplates ? styles['active'] : ''}`}
            onClick={() => { setShowTemplates(!showTemplates); setShowVariables(false); setShowFormatting(false); setShowPaymentDialog(false); }}
            title="Templates (can send outside 24h window)"
          >
            <svg width="16" height="16" xmlns="http://www.w3.org/2000/svg" fill="#10B981" viewBox="0 0 16 16"><path d="M3 4.5h10a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2m0 1a1 1 0 0 0-1 1v3a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-3a1 1 0 0 0-1-1zM1 2a.5.5 0 0 1 .5-.5h13a.5.5 0 0 1 0 1h-13A.5.5 0 0 1 1 2m0 12a.5.5 0 0 1 .5-.5h13a.5.5 0 0 1 0 1h-13A.5.5 0 0 1 1 14"/></svg>
          </button>
        )}

        {/* Payment Button (WhatsApp only) */}
        {channel === 'whatsapp' && selectedContactId && (
          <button
            type="button"
            className={`${styles['toolbar-btn']} ${showPaymentDialog ? styles['active'] : ''}`}
            onClick={() => { 
              if (!showPaymentDialog) {
                // Auto-generate reference ID when opening (using formatter)
                setPaymentForm(prev => ({...prev, referenceId: generateReferenceId()}));
              }
              setShowPaymentDialog(!showPaymentDialog); 
              setShowTemplates(false); 
              setShowVariables(false); 
              setShowFormatting(false); 
            }}
            title="Send Payment Request (UPI)"
          >
            <svg width="16" height="16" xmlns="http://www.w3.org/2000/svg" fill="#10B981" viewBox="0 0 16 16"><path d="M11 5.5a.5.5 0 0 1 .5-.5h2a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1-.5-.5z"/><path d="M2 2a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zm13 2v5H1V4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1m-1 9H2a1 1 0 0 1-1-1v-1h14v1a1 1 0 0 1-1 1"/></svg>
          </button>
        )}

        {/* Variables Button */}
        <button
          type="button"
          className={`${styles['toolbar-btn']} ${showVariables ? styles['active'] : ''} ${hasVariables ? styles['has-vars'] : ''}`}
          onClick={() => { setShowVariables(!showVariables); setShowTemplates(false); setShowFormatting(false); setShowPaymentDialog(false); }}
          title="Insert Variable"
        >
          <svg width="16" height="16" xmlns="http://www.w3.org/2000/svg" fill="#10B981" viewBox="0 0 16 16"><path d="m13.498.795.149-.149a1.207 1.207 0 1 1 1.707 1.708l-.149.148a1.5 1.5 0 0 1-.059 2.059L4.854 14.854a.5.5 0 0 1-.233.131l-4 1a.5.5 0 0 1-.606-.606l1-4a.5.5 0 0 1 .131-.232l9.642-9.642a.5.5 0 0 0-.642.056L6.854 4.854a.5.5 0 1 1-.708-.708L9.44.854A1.5 1.5 0 0 1 11.5.796a1.5 1.5 0 0 1 1.998-.001"/></svg>
        </button>

        {/* Formatting Button (WhatsApp only) */}
        {channel === 'whatsapp' && (
          <button
            type="button"
            className={`${styles['toolbar-btn']} ${showFormatting ? styles['active'] : ''}`}
            onClick={() => { setShowFormatting(!showFormatting); setShowTemplates(false); setShowVariables(false); setShowPaymentDialog(false); }}
            title="Formatting"
          >
            <svg width="16" height="16" xmlns="http://www.w3.org/2000/svg" fill="#10B981" viewBox="0 0 16 16"><path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325"/></svg>
          </button>
        )}

        {/* Attachment Button */}
        {channel === 'whatsapp' && (
          <button
            type="button"
            className={styles['toolbar-btn']}
            onClick={() => {
              if (onAttachClick) {
                // Use parent's file input
                onAttachClick();
              } else {
                // Fallback: create temporary file input
                const input = document.createElement('input');
                input.type = 'file';
                input.accept = 'image/*,video/*,audio/*,.pdf,.doc,.docx';
                input.onchange = (e) => {
                  const file = (e.target as HTMLInputElement).files?.[0];
                  if (file) {
                    insertAtCursor(`[Attachment: ${file.name}]`);
                  }
                };
                input.click();
              }
            }}
            title="Attach File"
          >
            <svg width="16" height="16" xmlns="http://www.w3.org/2000/svg" fill="#10B981" viewBox="0 0 16 16"><path fillRule="evenodd" d="M3 8a.5.5 0 0 1 .5-.5h6.793L8.146 5.354a.5.5 0 1 1 .708-.708l3 3a.5.5 0 0 1 0 .708l-3 3a.5.5 0 0 1-.708-.708L10.293 8.5H3.5A.5.5 0 0 1 3 8"/><path fillRule="evenodd" d="M12.5 4a.5.5 0 0 1 .5.5v7a.5.5 0 0 1-1 0v-7a.5.5 0 0 1 .5-.5"/></svg>
          </button>
        )}

        {/* AI Button */}
        {showAISuggestions && (
          <button
            type="button"
            className={`${styles['toolbar-btn']} ${styles['ai-btn']} ${aiError ? styles['error'] : ''}`}
            onClick={fetchAISuggestions}
            disabled={loadingAI}
            title={aiError || "Get AI Suggestion (Bedrock)"}
          >
            {loadingAI ? '...' : <svg width="16" height="16" xmlns="http://www.w3.org/2000/svg" fill="#10B981" viewBox="0 0 16 16"><path d="M6 12.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5M3 8.062C3 6.76 4.235 5.765 5.53 5.886a26.6 26.6 0 0 0 4.94 0C11.765 5.765 13 6.76 13 8.062v1.157a.93.93 0 0 1-.765.935c-.845.147-2.34.346-4.235.346s-3.39-.2-4.235-.346A.93.93 0 0 1 3 9.219zm4.542-.827a.25.25 0 0 0-.217.068l-.92.9a25 25 0 0 1-1.871-.183.25.25 0 0 0-.068.495c.55.076 1.232.149 2.02.193a.25.25 0 0 0 .189-.071l.754-.736.847 1.71a.25.25 0 0 0 .404.062l.932-.97a25 25 0 0 0 1.922-.188.25.25 0 0 0-.068-.495c-.538.074-1.207.145-1.98.189a.25.25 0 0 0-.166.076l-.754.785-.842-1.7a.25.25 0 0 0-.182-.135"/><path d="M8.5 1.866a1 1 0 1 0-1 0V3h-2A4.5 4.5 0 0 0 1 7.5V8a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1v-.5A4.5 4.5 0 0 0 10.5 3h-2zM14 7.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V7.5A3.5 3.5 0 0 1 5.5 4h5A3.5 3.5 0 0 1 14 7.5"/></svg>}
          </button>
        )}

        <div className={styles['toolbar-spacer']} />

        {/* Character Count */}
        {showCharCount && (
          <span className={`${styles['char-counter']} ${isOverLimit ? styles['over-limit'] : ''}`}>
            {charCount}{maxLength ? `/${maxLength}` : ''}
          </span>
        )}

        {/* Variable indicator */}
        {hasVariables && (
          <span className={styles['var-indicator']} title="Contains variables">
            ⊕ {(value.match(/\{\{\d+\}\}/g) || []).length}
          </span>
        )}
      </div>

      {/* Text Input */}
      <div className={styles['editor-input-wrapper']}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          className={`${styles['editor-textarea']} ${isOverLimit ? styles['over-limit'] : ''}`}
          rows={1}
        />
        
        {onSend && (
          <button
            type="button"
            className={styles['send-btn']}
            onClick={onSend}
            disabled={disabled || !value.trim() || isOverLimit}
            title="Send (Enter)"
          >
            →
          </button>
        )}
      </div>

      {/* Help hint */}
      <div className={styles['editor-hint']}>
        {channel === 'whatsapp' && (
          <span>Enter to send · Shift+Enter for new line · *bold* _italic_ ~strike~</span>
        )}
        {channel === 'sms' && (
          <span>SMS: 160 chars = 1 segment · Enter to send</span>
        )}
        {channel === 'email' && (
          <span>Enter to send · Shift+Enter for new line</span>
        )}
      </div>
    </div>
  );
};

export default RichTextEditor;
