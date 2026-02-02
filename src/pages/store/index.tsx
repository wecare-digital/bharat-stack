/**
 * Store Page - WECARE.DIGITAL
 * WhatsApp Catalog & Product Management
 * URL: https://base.wecare.digital/store
 */

import React, { useState } from 'react';
import Layout from '../../components/Layout';
import PageHeader from '../../components/PageHeader';
import SEO from '../../components/SEO';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

type TabType = 'catalog' | 'products' | 'orders';

interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  currency: string;
  imageUrl?: string;
  category: string;
  inStock: boolean;
}

const StorePage: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<TabType>('catalog');
  const [products] = useState<Product[]>([
    { id: '1', name: 'Sample Product', description: 'Product description', price: 999, currency: 'INR', category: 'General', inStock: true },
  ]);

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Store | WECARE.DIGITAL" description="WhatsApp Catalog & Product Management" />
      <div className="store-page">
        <PageHeader 
          title="Store" 
          subtitle="WhatsApp Catalog & Product Management"
          icon="store"
        />

        <div className="page-tabs">
          <button className={`tab-btn ${activeTab === 'catalog' ? 'active' : ''}`} onClick={() => setActiveTab('catalog')}>
            Catalog
          </button>
          <button className={`tab-btn ${activeTab === 'products' ? 'active' : ''}`} onClick={() => setActiveTab('products')}>
            Products
          </button>
          <button className={`tab-btn ${activeTab === 'orders' ? 'active' : ''}`} onClick={() => setActiveTab('orders')}>
            Orders
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'catalog' && (
            <div className="catalog-section">
              <div className="info-banner">
                <h3>WhatsApp Business Catalog</h3>
                <p>Connect your product catalog to WhatsApp Business API for seamless shopping experiences.</p>
                <a href="https://developers.facebook.com/docs/whatsapp/cloud-api/guides/sell-products-and-services" target="_blank" rel="noopener noreferrer" className="docs-link">
                  View Documentation →
                </a>
              </div>
              
              <div className="features-grid">
                <div className="feature-card">
                  <span className="feature-icon">🛒</span>
                  <h4>Product Catalog</h4>
                  <p>Sync products from Meta Commerce Manager</p>
                </div>
                <div className="feature-card">
                  <span className="feature-icon">💬</span>
                  <h4>Interactive Messages</h4>
                  <p>Send product lists and single product messages</p>
                </div>
                <div className="feature-card">
                  <span className="feature-icon">📱</span>
                  <h4>Cart & Checkout</h4>
                  <p>Customers can add items and checkout via WhatsApp</p>
                </div>
                <div className="feature-card">
                  <span className="feature-icon">💳</span>
                  <h4>Payment Integration</h4>
                  <p>Razorpay UPI payments for Indian customers</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'products' && (
            <div className="products-section">
              <div className="section-header">
                <h3>Products ({products.length})</h3>
                <button className="add-btn">+ Add Product</button>
              </div>
              
              <div className="products-grid">
                {products.map(product => (
                  <div key={product.id} className="product-card">
                    <div className="product-image">
                      {product.imageUrl ? (
                        <img src={product.imageUrl} alt={product.name} />
                      ) : (
                        <div className="placeholder">📦</div>
                      )}
                    </div>
                    <div className="product-info">
                      <h4>{product.name}</h4>
                      <p>{product.description}</p>
                      <div className="product-meta">
                        <span className="price">₹{product.price}</span>
                        <span className={`stock ${product.inStock ? 'in' : 'out'}`}>
                          {product.inStock ? 'In Stock' : 'Out of Stock'}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'orders' && (
            <div className="orders-section">
              <div className="empty-state">
                <span className="empty-icon">📋</span>
                <h3>No Orders Yet</h3>
                <p>Orders from WhatsApp catalog will appear here</p>
              </div>
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .store-page { padding: 20px; max-width: 1200px; margin: 0 auto; }
        .page-tabs { 
          display: flex; 
          gap: 8px; 
          margin-bottom: 20px;
          padding: 0;
          overflow-x: auto;
        }
        .tab-btn { 
          padding: 8px 16px; 
          border: none; 
          border-radius: 6px; 
          background: transparent; 
          cursor: pointer; 
          font-size: 14px; 
          font-weight: 500;
          color: var(--color-muted, #6b7280);
          white-space: nowrap;
          transition: all 0.15s ease;
        }
        .tab-btn:hover { background: var(--color-bg, #f3f4f6); color: var(--color-text, #111827); }
        .tab-btn.active { 
          background: var(--color-primary, #10b981); 
          color: white; 
        }
        .tab-content { min-height: 400px; }
        
        .info-banner { background: #f5f5f5; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e5e5e5; }
        .info-banner h3 { margin: 0 0 8px 0; font-size: 18px; }
        .info-banner p { margin: 0 0 12px 0; color: #666; }
        .docs-link { color: #000; font-weight: 500; text-decoration: none; }
        .docs-link:hover { text-decoration: underline; }
        
        .features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
        .feature-card { background: white; padding: 20px; border-radius: 12px; border: 1px solid #e5e5e5; }
        .feature-icon { font-size: 28px; display: block; margin-bottom: 12px; }
        .feature-card h4 { margin: 0 0 8px 0; font-size: 16px; }
        .feature-card p { margin: 0; color: #666; font-size: 13px; }
        
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .section-header h3 { margin: 0; }
        .add-btn { padding: 10px 20px; background: #000; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; }
        .add-btn:hover { background: #333; }
        
        .products-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
        .product-card { background: white; border-radius: 12px; border: 1px solid #e5e5e5; overflow: hidden; }
        .product-image { height: 160px; background: #f5f5f5; display: flex; align-items: center; justify-content: center; }
        .product-image img { width: 100%; height: 100%; object-fit: cover; }
        .placeholder { font-size: 48px; opacity: 0.3; }
        .product-info { padding: 16px; }
        .product-info h4 { margin: 0 0 8px 0; font-size: 16px; }
        .product-info p { margin: 0 0 12px 0; color: #666; font-size: 13px; }
        .product-meta { display: flex; justify-content: space-between; align-items: center; }
        .price { font-size: 18px; font-weight: 600; }
        .stock { font-size: 12px; padding: 4px 8px; border-radius: 4px; }
        .stock.in { background: #d1fae5; color: #065f46; }
        .stock.out { background: #fef2f2; color: #dc2626; }
        
        .empty-state { text-align: center; padding: 60px 20px; color: #666; }
        .empty-icon { font-size: 48px; display: block; margin-bottom: 16px; opacity: 0.5; }
        .empty-state h3 { margin: 0 0 8px 0; color: #333; }
        .empty-state p { margin: 0; }
      `}</style>
    </Layout>
  );
};

export default StorePage;
