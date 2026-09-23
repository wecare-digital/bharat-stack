export interface PublicBlogPost {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  url: string;
  content?: string;
  richContent?: { nodes?: any[] };
  seoTitle?: string;
  metaDescription?: string;
  focusKeyword?: string;
  keywords?: string[];
  jsonLd?: Record<string, any>;
  publishedDate?: string;
  modifiedDate?: string;
  coverImage?: string;
  category?: string;
  tags?: string[];
  hashtags?: string[];
  authorName?: string;
  robots?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital';
const PUBLIC_BLOG_API = `${API_BASE}/seo-tools/blog-public`;

export async function listPublicBlogPosts (): Promise<PublicBlogPost[]> {
  try {
    const response = await fetch( PUBLIC_BLOG_API, {
      headers: { Accept: 'application/json' },
    } );
    if ( !response.ok ) return [];
    const body = await response.json();
    return body?.ok && Array.isArray( body.posts ) ? body.posts : [];
  } catch
  {
    return [];
  }
}

export async function getPublicBlogPost ( slug: string ): Promise<PublicBlogPost | null> {
  try {
    const response = await fetch( `${PUBLIC_BLOG_API}/${encodeURIComponent( slug )}`, {
      headers: { Accept: 'application/json' },
    } );
    if ( !response.ok ) return null;
    const body = await response.json();
    return body?.ok && body.post ? body.post : null;
  } catch
  {
    return null;
  }
}
