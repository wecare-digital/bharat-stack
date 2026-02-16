/**
 * Contact Import/Export Component
 * CSV import and export functionality
 */

import React, { useState, useRef } from 'react';
import * as api from '../api/client';

interface ContactImportExportProps {
  contacts: api.Contact[];
  onImportComplete?: () => void;
}

type ImportTab = 'csv' | 'manual';

const ContactImportExport: React.FC<ContactImportExportProps> = ({ contacts, onImportComplete }) => {
  const [activeTab, setActiveTab] = useState<ImportTab>('csv');
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<api.ImportResult | null>(null);
  const [previewData, setPreviewData] = useState<Partial<api.Contact>[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Manual entry state
  const [manualName, setManualName] = useState('');
  const [manualPhone, setManualPhone] = useState('');
  const [manualEmail, setManualEmail] = useState('');
  const [manualOptInWA, setManualOptInWA] = useState(true);
  const [manualSaving, setManualSaving] = useState(false);

  // CSV file handling
  const handleFileSelect = async (file: File) => {
    if (!file.name.endsWith('.csv') && !file.name.endsWith('.vcf')) {
      alert('Please select a CSV or VCF file');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      let parsed: Partial<api.Contact>[];
      
      if (file.name.endsWith('.vcf')) {
        parsed = parseVCardContacts(content);
      } else {
        parsed = api.parseContactsCSV(content);
      }
      
      setPreviewData(parsed);
      setImportResult(null);
    };
    reader.readAsText(file);
  };

  // Parse vCard format (exported from Google Contacts)
  const parseVCardContacts = (content: string): Partial<api.Contact>[] => {
    const contacts: Partial<api.Contact>[] = [];
    const vcards = content.split('END:VCARD');
    
    for (const vcard of vcards) {
      if (!vcard.includes('BEGIN:VCARD')) continue;
      
      const contact: Partial<api.Contact> = {};
      
      // Parse name
      const fnMatch = vcard.match(/FN:(.+)/);
      if (fnMatch) contact.name = fnMatch[1].trim();
      
      // Parse phone
      const telMatch = vcard.match(/TEL[^:]*:(.+)/);
      if (telMatch) {
        let phone = telMatch[1].replace(/[^\d+]/g, '');
        if (!phone.startsWith('+')) phone = '+' + phone;
        contact.phone = phone;
      }
      
      // Parse email
      const emailMatch = vcard.match(/EMAIL[^:]*:(.+)/);
      if (emailMatch) contact.email = emailMatch[1].trim();
      
      if (contact.phone || contact.email) {
        contacts.push(contact);
      }
    }
    
    return contacts;
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  const handleImport = async () => {
    if (previewData.length === 0) return;
    
    setImporting(true);
    try {
      const result = await api.importContacts(previewData);
      setImportResult(result);
      if (result.created > 0 || result.updated > 0) {
        onImportComplete?.();
      }
    } catch (err) {
      console.error('Import failed:', err);
    } finally {
      setImporting(false);
    }
  };

  const handleExport = () => {
    const csv = api.exportContactsToCSV(contacts);
    api.downloadFile(csv, `contacts_${new Date().toISOString().split('T')[0]}.csv`, 'text/csv');
  };

  const clearPreview = () => {
    setPreviewData([]);
    setImportResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Manual contact entry
  const handleManualAdd = async () => {
    if (!manualPhone && !manualEmail) {
      alert('Phone or email is required');
      return;
    }
    
    setManualSaving(true);
    try {
      const result = await api.createContact({
        name: manualName,
        phone: manualPhone.startsWith('+') ? manualPhone : `+${manualPhone}`,
        email: manualEmail || undefined,
        optInWhatsApp: manualOptInWA,
      });
      
      if (result) {
        setManualName('');
        setManualPhone('');
        setManualEmail('');
        setManualOptInWA(true);
        onImportComplete?.();
        setImportResult({ total: 1, created: 1, updated: 0, failed: 0, errors: [] });
      }
    } catch (err) {
      console.error('Manual add failed:', err);
    } finally {
      setManualSaving(false);
    }
  };

  // Download CSV template
  const downloadTemplate = () => {
    const template = `name,phone,email
John Doe,+919876543210,john@example.com
Jane Smith,+918765432109,
Rahul Kumar,+917654321098,rahul@gmail.com`;
    
    api.downloadFile(template, 'contacts_template.csv', 'text/csv');
  };

  return (
    <div className="import-export-section">
      <div className="section-header">
        <h3>Add Contacts</h3>
        <button className="export-btn" onClick={handleExport}>
          Export CSV ({contacts.length})
        </button>
      </div>

      {/* Import Method Tabs */}
      <div className="import-tabs">
        <button 
          className={`import-tab ${activeTab === 'manual' ? 'active' : ''}`}
          onClick={() => setActiveTab('manual')}
        >
          Manual
        </button>
        <button 
          className={`import-tab ${activeTab === 'csv' ? 'active' : ''}`}
          onClick={() => setActiveTab('csv')}
        >
          CSV/VCF
        </button>
      </div>

      {/* Manual Entry Tab */}
      {activeTab === 'manual' && (
        <div className="manual-entry">
          <div className="form-row">
            <div className="form-field">
              <label>Name</label>
              <input 
                type="text" 
                value={manualName} 
                onChange={(e) => setManualName(e.target.value)}
                placeholder="Contact name"
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-field">
              <label>Phone *</label>
              <input 
                type="tel" 
                value={manualPhone} 
                onChange={(e) => setManualPhone(e.target.value)}
                placeholder="+91 98765 43210"
              />
            </div>
            <div className="form-field">
              <label>Email</label>
              <input 
                type="email" 
                value={manualEmail} 
                onChange={(e) => setManualEmail(e.target.value)}
                placeholder="email@example.com"
              />
            </div>
          </div>
          <div className="form-row">
            <label className="checkbox-inline">
              <input 
                type="checkbox" 
                checked={manualOptInWA} 
                onChange={(e) => setManualOptInWA(e.target.checked)}
              />
              <span>WhatsApp Opt-In</span>
            </label>
          </div>
          <button 
            className="import-btn"
            onClick={handleManualAdd}
            disabled={(!manualPhone && !manualEmail) || manualSaving}
          >
            {manualSaving ? 'Adding...' : '+ Add Contact'}
          </button>
        </div>
      )}

      {/* CSV/VCF Import Tab */}
      {activeTab === 'csv' && (
        <>
          {/* CSV Format Info */}
          <div className="csv-format-info">
            <div className="format-header">
              <span>CSV Format (Simple)</span>
              <button className="template-download-btn" onClick={downloadTemplate}>
                Download Template
              </button>
            </div>
            <div className="format-table">
              <table>
                <thead>
                  <tr>
                    <th>Column</th>
                    <th>Required</th>
                    <th>Example</th>
                  </tr>
                </thead>
                <tbody>
                  <tr><td>name</td><td>No</td><td>John Doe</td></tr>
                  <tr><td>phone</td><td>Yes</td><td>+919876543210</td></tr>
                  <tr><td>email</td><td>No</td><td>john@example.com</td></tr>
                </tbody>
              </table>
              <div className="format-note">All contacts auto opt-in to WhatsApp by default</div>
            </div>
          </div>

          <div 
            className={`import-zone ${dragOver ? 'dragging' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.vcf"
              style={{ display: 'none' }}
              onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
            />
            <div className="import-zone-icon">CSV</div>
            <div className="import-zone-text">
              Drop CSV or VCF file here or click to browse
            </div>
            <div className="import-zone-hint">
              Supports: CSV (comma-separated) | VCF (vCard)
            </div>
          </div>

          {previewData.length > 0 && (
            <div className="import-preview">
              <div className="preview-header">
                <h4>Preview ({previewData.length} contacts)</h4>
                <button className="clear-btn" onClick={clearPreview}>Clear</button>
              </div>
              
              <div className="preview-table">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Phone</th>
                      <th>Email</th>
                    </tr>
                  </thead>
                  <tbody>
                    {previewData.slice(0, 5).map((contact, i) => (
                      <tr key={i}>
                        <td>{contact.name || '-'}</td>
                        <td>{contact.phone}</td>
                        <td>{contact.email || '-'}</td>
                      </tr>
                    ))}
                    {previewData.length > 5 && (
                      <tr>
                        <td colSpan={3} className="more-rows">
                          ... and {previewData.length - 5} more
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <button 
                className="import-btn"
                onClick={handleImport}
                disabled={importing}
              >
                {importing ? 'Importing...' : `Import ${previewData.length} Contacts`}
              </button>
            </div>
          )}
        </>
      )}

      {/* Import Result */}
      {importResult && (
        <div className={`import-result ${importResult.failed > 0 ? 'has-errors' : 'success'}`}>
          <div className="import-stats">
            <div className="import-stat">
              <div className="import-stat-value">{importResult.created}</div>
              <div className="import-stat-label">Created</div>
            </div>
            <div className="import-stat">
              <div className="import-stat-value">{importResult.updated}</div>
              <div className="import-stat-label">Updated</div>
            </div>
            <div className="import-stat">
              <div className="import-stat-value">{importResult.failed}</div>
              <div className="import-stat-label">Failed</div>
            </div>
          </div>
          {importResult.errors.length > 0 && (
            <div className="import-errors">
              <strong>Errors:</strong>
              <ul>
                {importResult.errors.slice(0, 5).map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <style jsx>{`
        .import-export-section {
          background: #fff;
          border-radius: 12px;
          padding: 20px;
          border: 1px solid #e5e7eb;
          margin-bottom: 20px;
        }
        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }
        .section-header h3 {
          font-size: 16px;
          font-weight: 600;
          margin: 0;
        }
        .export-btn {
          background: #fff;
          border: 1px solid #000;
          padding: 8px 14px;
          border-radius: 13px;
          cursor: pointer;
          font-size: 13px;
          transition: all 0.2s;
        }
        .export-btn:hover {
          background: #f5f5f5;
        }
        
        /* Tabs */
        .import-tabs {
          display: flex;
          gap: 8px;
          margin-bottom: 16px;
        }
        .import-tab {
          flex: 1;
          padding: 10px 16px;
          border: 1px solid #000;
          background: #fff;
          border-radius: 13px;
          cursor: pointer;
          font-size: 13px;
          font-weight: 500;
          color: #000;
          transition: all 0.2s;
        }
        .import-tab:hover {
          background: #f5f5f5;
        }
        .import-tab.active {
          background: #f5f5f5;
          font-weight: 600;
        }
        
        /* Manual Entry */
        .manual-entry {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .form-row {
          display: flex;
          gap: 12px;
        }
        .form-field {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .form-field label {
          font-size: 12px;
          font-weight: 500;
          color: #4a4a4a;
        }
        .form-field input {
          padding: 10px 12px;
          border: 1px solid #000;
          border-radius: 13px;
          font-size: 14px;
        }
        .form-field input:focus {
          outline: none;
          box-shadow: 0 0 0 3px rgba(0,0,0,0.1);
        }
        .checkbox-inline {
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          font-size: 13px;
        }
        .checkbox-inline input {
          width: 16px;
          height: 16px;
        }

        /* CSV Format Info */
        .csv-format-info {
          background: #f5f5f5;
          border: 1px solid #e5e5e5;
          border-radius: 13px;
          padding: 14px;
          margin-bottom: 16px;
        }
        .format-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
          font-size: 13px;
          font-weight: 600;
          color: #000;
        }
        .template-download-btn {
          background: #fff;
          color: #000;
          border: 1px solid #000;
          padding: 6px 12px;
          border-radius: 13px;
          font-size: 12px;
          font-weight: 500;
          cursor: pointer;
          transition: background 0.2s;
        }
        .template-download-btn:hover {
          background: #f5f5f5;
        }
        .format-table {
          overflow-x: auto;
        }
        .format-table table {
          width: 100%;
          border-collapse: collapse;
          font-size: 12px;
        }
        .format-table th {
          text-align: left;
          padding: 6px 8px;
          background: #e5e5e5;
          font-weight: 600;
          color: #000;
        }
        .format-table td {
          padding: 6px 8px;
          border-bottom: 1px solid #e5e5e5;
          color: #4a4a4a;
        }
        .format-table td:first-child {
          font-family: monospace;
          color: #000;
          font-weight: 500;
        }
        .format-note {
          font-size: 11px;
          color: #6b6b6b;
          margin-top: 8px;
          font-style: italic;
        }
        
        /* Import Zone */
        .import-zone {
          border: 2px dashed #e5e5e5;
          border-radius: 13px;
          padding: 32px;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s;
        }
        .import-zone:hover, .import-zone.dragging {
          border-color: #000;
          background: #f5f5f5;
        }
        .import-zone-icon {
          font-size: 32px;
          margin-bottom: 8px;
        }
        .import-zone-text {
          font-size: 14px;
          font-weight: 500;
          color: #000;
          margin-bottom: 4px;
        }
        .import-zone-hint {
          font-size: 12px;
          color: #6b6b6b;
        }
        
        /* Preview */
        .import-preview {
          margin-top: 16px;
        }
        .preview-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        .preview-header h4 {
          font-size: 14px;
          font-weight: 600;
          margin: 0;
        }
        .clear-btn {
          background: none;
          border: none;
          color: #6b6b6b;
          cursor: pointer;
          font-size: 13px;
        }
        .clear-btn:hover {
          color: #059669;
        }
        .preview-table {
          overflow-x: auto;
          margin-bottom: 16px;
        }
        .preview-table table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }
        .preview-table th {
          text-align: left;
          padding: 8px;
          background: #f5f5f5;
          border-bottom: 1px solid #e5e5e5;
          font-weight: 600;
          color: #4a4a4a;
        }
        .preview-table td {
          padding: 8px;
          border-bottom: 1px solid #f5f5f5;
        }
        .more-rows {
          text-align: center;
          color: #6b6b6b;
          font-style: italic;
        }
        
        /* Import Button */
        .import-btn {
          width: 100%;
          padding: 12px;
          background: #fff;
          color: #000;
          border: 1px solid #000;
          border-radius: 13px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.2s;
        }
        .import-btn:hover:not(:disabled) {
          background: #f5f5f5;
        }
        .import-btn:disabled {
          background: #f5f5f5;
          color: #999;
          border-color: #e5e5e5;
          cursor: not-allowed;
        }
        
        /* Import Result */
        .import-result {
          margin-top: 16px;
          padding: 16px;
          border-radius: 13px;
          background: #f5f5f5;
          border: 1px solid #000;
        }
        .import-result.has-errors {
          border-color: #059669;
        }
        .import-stats {
          display: flex;
          gap: 24px;
          justify-content: center;
        }
        .import-stat {
          text-align: center;
        }
        .import-stat-value {
          font-size: 24px;
          font-weight: 600;
          color: #000;
        }
        .import-stat-label {
          font-size: 12px;
          color: #4a4a4a;
        }
        .import-errors {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid #e5e5e5;
          font-size: 13px;
          color: #059669;
        }
        .import-errors ul {
          margin: 8px 0 0 0;
          padding-left: 20px;
        }
        .import-errors li {
          margin-bottom: 4px;
        }

        @media (max-width: 640px) {
          .form-row {
            flex-direction: column;
          }
          .import-stats {
            gap: 16px;
          }
        }
      `}</style>
    </div>
  );
};

export default ContactImportExport;
