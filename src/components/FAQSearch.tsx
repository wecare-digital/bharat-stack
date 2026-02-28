/**
 * FAQ Search Component
 * 
 * Interactive FAQ search with keyword-based matching
 * Works offline, no API calls needed
 */

import React, { useState, useEffect } from 'react';
import { searchFAQs, getAllFAQs, formatSearchResponse, getCategoryName, type FAQSearchResult } from '../utils/faqSearch';

interface FAQSearchProps {
  defaultCategory?: string;
  maxResults?: number;
  showShortAnswers?: boolean;
  placeholder?: string;
  className?: string;
}

export default function FAQSearch({
  defaultCategory,
  maxResults = 3,
  showShortAnswers = false,
  placeholder = 'Ask a question...',
  className = ''
}: FAQSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<FAQSearchResult[]>([]);
  const [selectedCategory, setSelectedCategory] = useState(defaultCategory || '');
  const [showAllFAQs, setShowAllFAQs] = useState(false);
  
  // Search on query change
  useEffect(() => {
    if (query.trim()) {
      const searchResults = searchFAQs(query, {
        maxResults,
        shortAnswer: showShortAnswers,
        category: selectedCategory || undefined
      });
      setResults(searchResults);
      setShowAllFAQs(false);
    } else {
      setResults([]);
    }
  }, [query, selectedCategory, maxResults, showShortAnswers]);
  
  const handleShowAll = () => {
    setShowAllFAQs(true);
    setQuery('');
    setResults([]);
  };
  
  const allFAQs = getAllFAQs(showShortAnswers);
  
  return (
    <div className={`faq-search ${className}`}>
      <style>{`
        .faq-search {
          max-width: 800px;
          margin: 0 auto;
          padding: 20px;
        }
        
        .faq-search-header {
          margin-bottom: 24px;
        }
        
        .faq-search-title {
          font-size: 24px;
          font-weight: 600;
          margin-bottom: 8px;
          color: #1a1a1a;
        }
        
        .faq-search-subtitle {
          font-size: 14px;
          color: #666;
        }
        
        .faq-search-input-wrapper {
          position: relative;
          margin-bottom: 16px;
        }
        
        .faq-search-input {
          width: 100%;
          padding: 12px 16px;
          font-size: 16px;
          border: 2px solid #e0e0e0;
          border-radius: 8px;
          outline: none;
          transition: border-color 0.2s;
        }
        
        .faq-search-input:focus {
          border-color: #4CAF50;
        }
        
        .faq-category-filter {
          display: flex;
          gap: 8px;
          margin-bottom: 16px;
          flex-wrap: wrap;
        }
        
        .faq-category-btn {
          padding: 8px 16px;
          border: 1px solid #e0e0e0;
          border-radius: 20px;
          background: white;
          cursor: pointer;
          font-size: 14px;
          transition: all 0.2s;
        }
        
        .faq-category-btn:hover {
          background: #f5f5f5;
        }
        
        .faq-category-btn.active {
          background: #4CAF50;
          color: white;
          border-color: #4CAF50;
        }
        
        .faq-results {
          margin-top: 24px;
        }
        
        .faq-result-item {
          background: white;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 12px;
          transition: box-shadow 0.2s;
        }
        
        .faq-result-item:hover {
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .faq-result-question {
          font-size: 16px;
          font-weight: 600;
          color: #1a1a1a;
          margin-bottom: 8px;
        }
        
        .faq-result-answer {
          font-size: 14px;
          color: #444;
          line-height: 1.6;
          white-space: pre-line;
        }
        
        .faq-result-meta {
          display: flex;
          gap: 12px;
          margin-top: 8px;
          font-size: 12px;
          color: #999;
        }
        
        .faq-category-badge {
          background: #f0f0f0;
          padding: 2px 8px;
          border-radius: 4px;
        }
        
        .faq-no-results {
          text-align: center;
          padding: 40px 20px;
          color: #666;
        }
        
        .faq-show-all-btn {
          width: 100%;
          padding: 12px;
          background: #f5f5f5;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
          cursor: pointer;
          font-size: 14px;
          color: #666;
          transition: all 0.2s;
        }
        
        .faq-show-all-btn:hover {
          background: #e0e0e0;
        }
        
        .faq-all-categories {
          margin-top: 24px;
        }
        
        .faq-category-section {
          margin-bottom: 32px;
        }
        
        .faq-category-title {
          font-size: 18px;
          font-weight: 600;
          color: #1a1a1a;
          margin-bottom: 16px;
          padding-bottom: 8px;
          border-bottom: 2px solid #4CAF50;
        }
      `}</style>
      
      <div className="faq-search-header">
        <h2 className="faq-search-title">Frequently Asked Questions</h2>
        <p className="faq-search-subtitle">Search for answers or browse by category</p>
      </div>
      
      <div className="faq-search-input-wrapper">
        <input
          type="text"
          className="faq-search-input"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      
      <div className="faq-category-filter">
        <button
          className={`faq-category-btn ${!selectedCategory ? 'active' : ''}`}
          onClick={() => setSelectedCategory('')}
        >
          All
        </button>
        <button
          className={`faq-category-btn ${selectedCategory === 'general' ? 'active' : ''}`}
          onClick={() => setSelectedCategory('general')}
        >
          General
        </button>
        <button
          className={`faq-category-btn ${selectedCategory === 'orders' ? 'active' : ''}`}
          onClick={() => setSelectedCategory('orders')}
        >
          Orders & Delivery
        </button>
        <button
          className={`faq-category-btn ${selectedCategory === 'payments' ? 'active' : ''}`}
          onClick={() => setSelectedCategory('payments')}
        >
          Payments
        </button>
      </div>
      
      {query && results.length > 0 && (
        <div className="faq-results">
          {results.map((result) => (
            <div key={result.id} className="faq-result-item">
              <div className="faq-result-question">{result.question}</div>
              <div className="faq-result-answer">{result.answer}</div>
              <div className="faq-result-meta">
                <span className="faq-category-badge">{getCategoryName(result.category)}</span>
                <span>Match score: {result.score}</span>
              </div>
            </div>
          ))}
        </div>
      )}
      
      {query && results.length === 0 && (
        <div className="faq-no-results">
          <p>No matching FAQs found.</p>
          <p style={{ marginTop: '8px', fontSize: '14px' }}>
            Try different keywords or contact us at +91 9330994400
          </p>
        </div>
      )}
      
      {!query && !showAllFAQs && (
        <button className="faq-show-all-btn" onClick={handleShowAll}>
          Browse All FAQs
        </button>
      )}
      
      {showAllFAQs && (
        <div className="faq-all-categories">
          {Object.entries(allFAQs).map(([category, faqs]) => (
            <div key={category} className="faq-category-section">
              <h3 className="faq-category-title">{getCategoryName(category)}</h3>
              {faqs.map((faq) => (
                <div key={faq.id} className="faq-result-item">
                  <div className="faq-result-question">{faq.question}</div>
                  <div className="faq-result-answer">
                    {showShortAnswers ? faq.shortAnswer : faq.answer}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
