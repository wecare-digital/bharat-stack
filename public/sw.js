/**
 * Service Worker - WECARE.DIGITAL Stack CRM
 * Offline caching with network-first strategy for API,
 * cache-first for static assets.
 */

// Bumped v2 -> v3 deliberately. The `activate` handler below deletes every cache
// key it does not recognise, so renaming these is what evicts the stale v2
// entries — including the cache-first .js/.css copies that were pinning browsers
// to an old bundle until a hard reload.
const CACHE_NAME = 'stack-crm-v3';
const STATIC_CACHE = 'stack-static-v3';

// Static assets to pre-cache on install
const PRECACHE_URLS = [
  '/',
  '/manifest.json',
  '/offline.html',
];

// Install: pre-cache shell
self.addEventListener( 'install', ( event ) =>
{
  event.waitUntil(
    caches.open( STATIC_CACHE ).then( ( cache ) =>
    {
      return cache.addAll( PRECACHE_URLS );
    } )
  );
  self.skipWaiting();
} );

// Activate: clean old caches
self.addEventListener( 'activate', ( event ) =>
{
  event.waitUntil(
    caches.keys().then( ( keys ) =>
      Promise.all(
        keys
          .filter( ( k ) => k !== CACHE_NAME && k !== STATIC_CACHE )
          .map( ( k ) => caches.delete( k ) )
      )
    )
  );
  self.clients.claim();
} );

// Fetch: network-first for API, cache-first for static
self.addEventListener( 'fetch', ( event ) =>
{
  const { request } = event;
  const url = new URL( request.url );

  // Skip non-GET
  if ( request.method !== 'GET' ) return;

  // Skip chrome-extension, etc.
  if ( !url.protocol.startsWith( 'http' ) ) return;

  // Stay out of the way on a dev server. Falling through without calling
  // respondWith lets the request go straight to the network, so an already
  // installed worker cannot keep serving a stale /_next/static chunk. _app.tsx
  // no longer registers outside production, but this makes the worker safe even
  // where one is still installed.
  if ( url.hostname === 'localhost' || url.hostname === '127.0.0.1' ) return;

  // API calls: network-first with cache fallback.
  //
  // `api.` IS THE IMPORTANT ONE AND IT WAS MISSING. This branch matched only `/api/` paths
  // and `execute-api` hostnames, and the app's API is neither - it is
  // https://api.wecare.digital. So every API call in the product fell through to the
  // network-first HTML handler at the bottom of this function, whose failure path returns
  // `/offline.html`. A caller doing `response.json()` on an offline HTML page does not get a
  // network error, it gets a JSON parse error, which is a much harder thing to diagnose from
  // a bug report - and the widget's language catalogue is one of those callers.
  //
  // Matching on the `api.` prefix rather than the full host so a staging or regional API
  // subdomain is covered without another edit.
  if (
    url.pathname.startsWith( '/api/' )
    || url.hostname.startsWith( 'api.' )
    || url.hostname.includes( 'execute-api' )
  )
  {
    event.respondWith(
      fetch( request )
        .then( ( response ) =>
        {
          if ( response.ok )
          {
            const clone = response.clone();
            caches.open( CACHE_NAME ).then( ( cache ) => cache.put( request, clone ) );
          }
          return response;
        } )
        .catch( () => caches.match( request ) )
    );
    return;
  }

  // Static assets: cache-first
  if (
    url.pathname.match( /\.(js|css|png|jpg|jpeg|svg|ico|woff2?|ttf|eot)$/ ) ||
    url.hostname === 'fonts.googleapis.com' ||
    url.hostname === 'fonts.gstatic.com'
  )
  {
    event.respondWith(
      caches.match( request ).then( ( cached ) =>
      {
        if ( cached ) return cached;
        return fetch( request ).then( ( response ) =>
        {
          if ( response.ok )
          {
            const clone = response.clone();
            caches.open( STATIC_CACHE ).then( ( cache ) => cache.put( request, clone ) );
          }
          return response;
        } );
      } )
    );
    return;
  }

  // HTML pages: network-first, fallback to offline page
  event.respondWith(
    fetch( request )
      .then( ( response ) =>
      {
        if ( response.ok )
        {
          const clone = response.clone();
          caches.open( CACHE_NAME ).then( ( cache ) => cache.put( request, clone ) );
        }
        return response;
      } )
      .catch( () =>
        caches.match( request ).then( ( cached ) => cached || caches.match( '/offline.html' ) )
      )
  );
} );

// Push notification handler
self.addEventListener( 'push', ( event ) =>
{
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'Stack CRM';
  const options = {
    body: data.body || 'New notification',
    icon: 'https://wecare.digital/get/o/stream/media/m/wecaredigital.png',
    badge: 'https://wecare.digital/get/o/stream/media/m/wecaredigital.png',
    data: data.data || {},
    actions: data.actions || [],
    tag: data.tag || 'stack-crm',
    renotify: true,
  };
  event.waitUntil( self.registration.showNotification( title, options ) );
} );

// Notification click handler
self.addEventListener( 'notificationclick', ( event ) =>
{
  event.notification.close();
  const url = event.notification.data?.url || '/dashboard';
  event.waitUntil(
    self.clients.matchAll( { type: 'window' } ).then( ( clients ) =>
    {
      for ( const client of clients )
      {
        // Matches 'wecare.digital', which covers the apex and www. It used to match
        // 'stack.wecare.digital' only, so after that host was retired an existing
        // window would never be found and every notification click opened a new tab.
        if ( client.url.includes( 'wecare.digital' ) && 'focus' in client )
        {
          client.focus();
          client.navigate( url );
          return;
        }
      }
      return self.clients.openWindow( url );
    } )
  );
} );
