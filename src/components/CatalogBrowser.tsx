/**
 * Catalog Browser
 * Browse WhatsApp Commerce catalogs and send product messages.
 * Fetches products from CatalogCache DynamoDB table (synced by catalog-management Lambda).
 * Per WhatsApp Cloud API: Product and product_list interactive messages.
 */
import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../api/client';

interface CatalogBrowserProps {
  phoneNumberId?: string;
  wabaId?: string;
  contactId?: string;
  onSendProduct?: (product: Product) => void;
  onClose?: () => void;
}

interface Product {
  id: string;
  retailerId: string;
  name: string;
  description: string;
  price: string;
  currency: string;
  imageUrl: string;
  availability: string;
  catalogId: string;
}

const CatalogBrowser: React.FC<CatalogBrowserProps> = ({
  phoneNumberId, wabaId, contactId, onSendProduct, onClose,
}) => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getCatalogProducts({ wabaId, phoneNumberId });
      setProducts(res?.products || []);
    } catch (e: any) {
      setError(e?.message || 'Failed to load catalog');
    } finally {
      setLoading(false);
    }
  }, [wabaId, phoneNumberId]);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const filtered = products.filter(p =>
    p.name?.toLowerCase().includes(search.toLowerCase()) ||
    p.retailerId?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-4 border rounded-lg bg-white shadow-sm">
      <div className="flex justify-between items-center mb-3">
        <h3 className="font-medium text-sm">WhatsApp Catalog</h3>
        {onClose && (
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg" aria-label="Close">&times;</button>
        )}
      </div>
      <input placeholder="Search products..." value={search} onChange={e => setSearch(e.target.value)}
        className="border rounded px-2 py-1.5 text-sm w-full mb-3" />
      {loading && <p className="text-sm text-gray-500">Loading catalog...</p>}
      {error && <p className="text-sm text-red-500">{error}</p>}
      {!loading && filtered.length === 0 && <p className="text-sm text-gray-500">No products found.</p>}
      <div className="grid grid-cols-2 gap-2 max-h-80 overflow-y-auto">
        {filtered.map(product => (
          <div key={product.id} className="border rounded p-2 text-xs">
            {product.imageUrl && (
              <img src={product.imageUrl} alt={product.name} className="w-full h-20 object-cover rounded mb-1" />
            )}
            <p className="font-medium truncate">{product.name}</p>
            <p className="text-gray-500">{product.currency} {product.price}</p>
            <p className="text-gray-400 truncate">{product.availability}</p>
            {onSendProduct && contactId && (
              <button onClick={() => onSendProduct(product)}
                className="mt-1 w-full bg-green-600 text-white rounded py-1 text-xs hover:bg-green-700">
                Send
              </button>
            )}
          </div>
        ))}
      </div>
      <button onClick={fetchProducts} className="mt-2 text-xs text-blue-600 hover:underline">
        🔄 Refresh
      </button>
    </div>
  );
};

export default CatalogBrowser;
