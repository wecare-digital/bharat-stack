/**
 * Store Page - WECARE.DIGITAL
 * WhatsApp Catalog & Product Management
 * URL: https://base.wecare.digital/store
 */

import React, { useState } from 'react';
import Layout from '../../components/Layout';
import PageHeader from '../../components/PageHeader';
import SEO from '../../components/SEO';
import { WhatsAppIcon, MessageIcon, PaymentIcon, DocumentIcon } from '../../lib/icons';

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
                  <span className="feature-icon"><WhatsAppIcon size={28} /></span>
                  <h4>Product Catalog</h4>
                  <p>Sync products from Meta Commerce Manager</p>
                </div>
                <div className="feature-card">
                  <span className="feature-icon"><MessageIcon size={28} /></span>
                  <h4>Interactive Messages</h4>
                  <p>Send product lists and single product messages</p>
                </div>
                <div className="feature-card">
                  <span className="feature-icon"><DocumentIcon size={28} /></span>
                  <h4>Cart & Checkout</h4>
                  <p>Customers can add items and checkout via WhatsApp</p>
                </div>
                <div className="feature-card">
                  <span className="feature-icon"><PaymentIcon size={28} /></span>
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
                        <div className="placeholder">—</div>
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
                <span className="empty-icon"><DocumentIcon size={48} /></span>
                <h3>No Orders Yet</h3>
                <p>Orders from WhatsApp catalog will appear here</p>
              </div>
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .store-page { }
        .page-tabs { }
        .tab-btn { }
        .tab-btn:hover { }
        .tab-btn.active { }
        .tab-content { min-height: 400px; }
        .info-banner { }
        .info-banner h3 { }
        .info-banner p { }
        .docs-link { }
        .docs-link:hover { }
        .features-grid { }
        .feature-card { }
        .feature-icon { }
        .feature-card h4 { }
        .feature-card p { }
        .section-header { }
        .section-header h3 { }
        .add-btn { }
        .add-btn:hover { }
        .products-grid { }
        .product-card { }
        .product-image { }
        .product-image img { }
        .placeholder { }
        .product-info { }
        .product-info h4 { }
        .product-info p { }
        .product-meta { }
        .price { }
        .stock { }
        .stock.in { }
        .stock.out { }
        .empty-state { }
        .empty-icon { }
        .empty-state h3 { }
        .empty-state p { }
        @media (max-width: 768px) { }
        @media (max-width: 480px) { }
      `}</style>
    </Layout>
  );
};

export default StorePage;
