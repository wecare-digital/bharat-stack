import React, { useCallback, useEffect, useRef, useState } from 'react';
import BlogContribution from './BlogContribution';
import ShareLinks from './ShareLinks';
import { SITE_ORIGIN } from '../config/share';

/**
 * VayuLok LIVE content, appended BELOW the rotating-word hero on /vayulok/.
 *
 * WHAT THIS IS. The REAL, live-wired version of docs/mocks/vayulok-live-mock.html.
 * The mock is a VISUAL reference only: its layout and styled-jsx design tokens are
 * ported verbatim here, but every static sample value is replaced with LIVE data
 * fetched CLIENT-SIDE from Google's India-SKU APIs plus the Maps JavaScript API.
 *
 * THE MOCK'S "never call these from a browser" STANCE IS A MOCK CONSTRAINT, NOT THIS
 * PAGE'S. The mock header says weather/air/solar/pollen are server-side web services
 * and uses static placeholders. For the real page the owner wants LIVE data, and these
 * Google APIs ARE called client-side from the browser with the referrer-restricted
 * browser key - exactly as the shipped src/components/ContactLocation.tsx already calls
 * Open-Meteo client-side. So this component follows ContactLocation's proven approach.
 *
 * THE KEY. Read ONLY from process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY, exactly as
 * ContactLocation.tsx does. With output:'export', that value is inlined into a JS chunk
 * at build time - never into the prerendered HTML, because it is only read inside a
 * useEffect. No key literal appears anywhere in this file. A Maps BROWSER key is public
 * by design and Google restricts it by HTTP referrer (*.wecare.digital/*); the live map
 * therefore only renders on a deployed *.wecare.digital origin, never in CI or sandbox.
 *
 * HONEST DEGRADATION. When the key is absent, this renders the hero (owned by the page)
 * plus the content shell WITHOUT the map and WITHOUT live panels, and fires ZERO network
 * calls. No spinner, no "--" placeholder. Each API fetch uses AbortController + cleanup,
 * `if(!res.ok) return`, Number.isFinite guards (0 is a real value), and silent catch, so
 * any failed call simply omits its fields rather than showing broken state.
 *
 * ON USER ACTION ONLY. The AQI heatmap tile overlay is created ONLY when the user presses
 * a layer-control button. It is never requested on page load.
 *
 * SELF-STYLING via styled-jsx with a vl-live- scope. styled-jsx only attaches its scoping
 * class to markup it can statically see, so every element stays INLINE in this component's
 * return tree. No bare html/body/* selectors; the mock's data-vl-preview-only block and
 * .vl-preview-shell are PREVIEW-ONLY and are NOT ported.
 *
 * ATTRIBUTION. There is no CSS targeting .gm-style-cc, a[href*="google"] or
 * img[alt="Google"], and every overlay stays inset from the map's bottom corners, where
 * Google paints its logo and legal notices (Maps Platform ToS).
 */

const MAPS_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY || '';

// India bounds, so the map cannot be panned off the product's area. Verbatim from the
// mock's map options.
const INDIA_BOUNDS = { north: 37.6, south: 6.4, west: 68.1, east: 97.4 };

// Default place: Connaught Place, New Delhi - the mock's default centre.
const DEFAULT_PLACE = {
  name: 'Connaught Place',
  addr: 'New Delhi, Delhi 110001',
  lat: 28.6139,
  lng: 77.2090,
};

// GEOMETRY ON THE REPO PALETTE, ported verbatim from the mock's map styles.
const MAP_STYLES = [
  { elementType: 'geometry', stylers: [ { color: '#fafafa' } ] },
  { elementType: 'labels.text.fill', stylers: [ { color: '#1a3a2a' } ] },
  { elementType: 'labels.text.stroke', stylers: [ { color: '#ffffff' } ] },
  { featureType: 'poi', elementType: 'labels', stylers: [ { visibility: 'off' } ] },
  { featureType: 'poi.park', elementType: 'geometry', stylers: [ { color: '#f5fde0' } ] },
  { featureType: 'road', elementType: 'geometry', stylers: [ { color: '#ffffff' } ] },
  { featureType: 'road', elementType: 'geometry.stroke', stylers: [ { color: '#e5e7eb' } ] },
  { featureType: 'road.highway', elementType: 'geometry', stylers: [ { color: '#ffffff' } ] },
  { featureType: 'transit', stylers: [ { visibility: 'off' } ] },
  { featureType: 'water', elementType: 'geometry', stylers: [ { color: '#e8eeea' } ] },
];

/* ---- AQI category + severity-form mapping ------------------------------------------
   India AQI (CPCB) bands. Severity is encoded by FORM (dot/bar class) AND the category
   WORD in text, never colour alone (WCAG 1.4.1). NO red anywhere - the ramp walks dark
   green -> lime -> amber, matching the mock's severity ramp. */
type Sev = 'good' | 'sat' | 'mod' | 'poor' | 'worst';

function aqiCategory( aqi: number ): { word: string; sev: Sev } {
  if ( aqi <= 50 ) return { word: 'Good', sev: 'good' };
  if ( aqi <= 100 ) return { word: 'Satisfactory', sev: 'sat' };
  if ( aqi <= 200 ) return { word: 'Moderate', sev: 'mod' };
  if ( aqi <= 300 ) return { word: 'Poor', sev: 'poor' };
  if ( aqi <= 400 ) return { word: 'Very Poor', sev: 'worst' };
  return { word: 'Severe', sev: 'worst' };
}

// Pollen category 0-5 UPI -> word (Google's universal pollen index).
function pollenCategory( idx: number ): string {
  if ( idx <= 0 ) return 'None';
  if ( idx === 1 ) return 'Very Low';
  if ( idx === 2 ) return 'Low';
  if ( idx === 3 ) return 'Moderate';
  if ( idx === 4 ) return 'High';
  return 'Very High';
}

/* ---- live data shapes ---------------------------------------------------------------
   Every field is optional: a value only enters state once it actually arrived, so the
   markup renders only the fields that are present and never a placeholder. */
interface AirState {
  aqi: number;
  word: string;
  sev: Sev;
  dominant?: string;
  pollutants: { code: string; label: string; value: number; unit: string }[];
  advisory?: string;
}
interface WeatherState {
  temp?: number;
  feelsLike?: number;
  humidity?: number;
  windSpeed?: number;
  windUnit?: string;
  windDir?: string;
  condition?: string;
}
interface SolarState {
  maxPanels?: number;
  roofAreaM2?: number;
  yearlyKwh?: number;
  sunshineHrs?: number;
}
interface PollenRow { label: string; index: number; word: string; }

const COMPASS = [ 'N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW' ];
function windDirection( deg: number ): string {
  return COMPASS[ Math.round( deg / 45 ) % 8 ];
}
// Short display label for the wind-speed unit the Weather API returns on wind.speed.unit
// (e.g. KILOMETERS_PER_HOUR, MILES_PER_HOUR). Fall back to km/h under unitsSystem=METRIC.
function windUnitLabel( unit?: string ): string {
  switch ( unit ) {
    case 'MILES_PER_HOUR': return 'mph';
    case 'METERS_PER_SECOND': return 'm/s';
    case 'KILOMETERS_PER_HOUR': return 'km/h';
    default: return 'km/h';
  }
}

const VayuLokLive: React.FC = () => {
  // The selected place drives every fetch. Default is Connaught Place; search updates it.
  const [ place, setPlace ] = useState( DEFAULT_PLACE );
  const [ mapReady, setMapReady ] = useState( false );

  const [ air, setAir ] = useState<AirState | null>( null );
  const [ weather, setWeather ] = useState<WeatherState | null>( null );
  const [ solar, setSolar ] = useState<SolarState | null>( null );
  const [ pollen, setPollen ] = useState<PollenRow[] | null>( null );

  // Search combobox state.
  const [ query, setQuery ] = useState( '' );
  const [ results, setResults ] = useState<{ name: string; addr: string; lat: number; lng: number }[]>( [] );
  const [ open, setOpen ] = useState( false );
  const [ active, setActive ] = useState( -1 );

  // Which heatmap layer is active (user action only). null = none on load.
  const [ layer, setLayer ] = useState<'AQI' | 'PM25' | null>( null );

  const mapHost = useRef<HTMLDivElement | null>( null );
  const mapRef = useRef<unknown>( null );
  const markerRef = useRef<unknown>( null );
  const placesSvc = useRef<unknown>( null );
  const geocoder = useRef<unknown>( null );
  // Cache the last fetched values per "lat,lng" so re-selecting a place bills nothing.
  const cache = useRef<Record<string, { air: AirState | null; weather: WeatherState | null; solar: SolarState | null; pollen: PollenRow[] | null }>>( {} );
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>( null );

  /* ---------------------------------------------------------------------------------
     MAP. Fires on load WHEN a key is present. The Maps JS script is injected once per
     document with id 'gmaps-js' and reused across remounts, exactly as ContactLocation.
     Guarded by `if(!MAPS_KEY) return;` so no key means no script and no map. */
  useEffect( () => {
    if ( !MAPS_KEY || typeof window === 'undefined' ) return;
    const w = window as unknown as {
      google?: { maps?: Record<string, unknown> & {
        importLibrary?: ( name: string ) => Promise<Record<string, unknown>>;
      } };
    };

    let cancelled = false;

    // Wait up to ~5s for the canvas ref to attach. The effect can fire its init
    // before React has painted the conditionally-rendered map canvas, in which case
    // mapHost.current is still null; bailing then left a blank map with no error.
    const waitForHost = async (): Promise<HTMLDivElement | null> => {
      for ( let i = 0; i < 50; i++ ) {
        if ( cancelled ) return null;
        if ( mapHost.current ) return mapHost.current;
        await new Promise( r => setTimeout( r, 100 ) );
      }
      return mapHost.current;
    };

    const init = async () => {
      const g = w.google?.maps;
      if ( !g ) return;
      const host = await waitForHost();
      if ( cancelled || !host ) return;

      // WITH loading=async, the google.maps NAMESPACE exists on script load but its
      // constructors (Map, Marker, ...) are NOT populated until the relevant library
      // is imported. Calling `new google.maps.Map()` directly throws
      // "Map is not a constructor". The modern loader requires importLibrary().
      // We await the maps/marker/places libraries, then construct. Fall back to the
      // legacy namespace for any older loader that already populated it.
      type MapsCtors = {
        Map: new ( el: HTMLElement, opts: Record<string, unknown> ) => unknown;
        Marker: new ( opts: Record<string, unknown> ) => unknown;
        Geocoder: new () => unknown;
        places?: { PlacesService: new ( attr: HTMLElement ) => unknown };
      };
      // Import each library INDEPENDENTLY. A Promise.all here meant that if any one
      // import rejected (e.g. 'marker' under a loader that bundles it differently),
      // the whole block hit the catch and the map silently never built - exactly the
      // blank-canvas-no-error symptom. The map library is the only one that is
      // required; marker and places are best-effort and must not block the map.
      const imp = async ( name: string ): Promise<Record<string, unknown> | null> => {
        try {
          return typeof g.importLibrary === 'function' ? await g.importLibrary( name ) : null;
        } catch { return null; }
      };

      const legacy = g as unknown as MapsCtors;
      const mapsLib = await imp( 'maps' );
      if ( cancelled ) return;
      const MapCtor = ( mapsLib as { Map?: MapsCtors['Map'] } | null )?.Map || legacy.Map;
      if ( !MapCtor || !host ) return; // no map constructor -> degrade, no crash

      const markerLib = await imp( 'marker' );
      const placesLib = await imp( 'places' );
      const maps: MapsCtors = {
        Map: MapCtor,
        Marker: ( markerLib as { Marker?: MapsCtors['Marker'] } | null )?.Marker || legacy.Marker,
        Geocoder: legacy.Geocoder,
        places: ( placesLib as unknown as MapsCtors['places'] ) || legacy.places,
      };
      if ( cancelled ) return;

      const map = new maps.Map( host, {
        center: { lat: DEFAULT_PLACE.lat, lng: DEFAULT_PLACE.lng },
        zoom: 11,
        gestureHandling: 'greedy',
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        restriction: { latLngBounds: INDIA_BOUNDS, strictBounds: false },
        styles: MAP_STYLES,
      } );
      mapRef.current = map;

      if ( maps.Marker ) {
        markerRef.current = new maps.Marker( {
          position: { lat: DEFAULT_PLACE.lat, lng: DEFAULT_PLACE.lng },
          map,
          title: DEFAULT_PLACE.name,
        } );
      }

      if ( maps.Geocoder ) geocoder.current = new maps.Geocoder();
      if ( maps.places?.PlacesService ) {
        placesSvc.current = new maps.places.PlacesService( host );
      }

      // First setState via requestAnimationFrame to avoid react-hooks/set-state-in-effect.
      requestAnimationFrame( () => setMapReady( true ) );
    };

    // init is async (it awaits importLibrary); wrap so no unhandled promise floats.
    const runInit = () => { void init(); };

    // If the loader is already present (namespace or script tag), call init
    // DIRECTLY - the script's 'load' event has already fired and will not fire
    // again, so relying on the listener would leave the map unbuilt. init() awaits
    // importLibrary itself, so it is safe to call before the libraries finish.
    if ( w.google?.maps ) { runInit(); return () => { cancelled = true; }; }

    const ID = 'gmaps-js';
    const existing = document.getElementById( ID );
    if ( existing ) {
      existing.addEventListener( 'load', runInit );
      // Also call directly in case 'load' already fired for this existing tag.
      runInit();
      return () => { cancelled = true; existing.removeEventListener( 'load', runInit ); };
    }

    const script = document.createElement( 'script' );
    script.id = ID;
    script.async = true;
    // Places library requested so client-side India-scoped autocomplete can run.
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent( MAPS_KEY )}&libraries=places&loading=async`;
    script.addEventListener( 'load', runInit );
    document.head.appendChild( script );
    return () => { cancelled = true; };
  }, [] );

  /* ---------------------------------------------------------------------------------
     LIVE DATA for the selected place. Air + Weather + Solar + Pollen all fire together
     whenever the place changes AND a key is present. Each is independently guarded,
     uses AbortController + Number.isFinite + silent degradation, and caches per place. */
  useEffect( () => {
    if ( !MAPS_KEY || typeof window === 'undefined' ) return;
    const { lat, lng } = place;
    const cacheKey = `${lat.toFixed( 4 )},${lng.toFixed( 4 )}`;

    const cached = cache.current[ cacheKey ];
    if ( cached ) {
      requestAnimationFrame( () => {
        setAir( cached.air );
        setWeather( cached.weather );
        setSolar( cached.solar );
        setPollen( cached.pollen );
      } );
      return;
    }

    const ac = new AbortController();
    const store: { air: AirState | null; weather: WeatherState | null; solar: SolarState | null; pollen: PollenRow[] | null } = {
      air: null, weather: null, solar: null, pollen: null,
    };

    // AIR QUALITY - India SKU currentConditions:lookup, India local AQI preferred.
    const fetchAir = async () => {
      try {
        const res = await fetch(
          `https://airquality.googleapis.com/v1/currentConditions:lookup?key=${encodeURIComponent( MAPS_KEY )}`,
          {
            method: 'POST',
            signal: ac.signal,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify( {
              location: { latitude: lat, longitude: lng },
              extraComputations: [
                'POLLUTANT_CONCENTRATION',
                'LOCAL_AQI',
                'HEALTH_RECOMMENDATIONS',
                'DOMINANT_POLLUTANT_CONCENTRATION',
              ],
              languageCode: 'en',
              universalAqi: true,
            } ),
          },
        );
        if ( !res.ok ) return;
        const data = await res.json();
        const indexes: { code?: string; aqi?: number; dominantPollutant?: string }[] = data?.indexes || [];
        // Prefer the India CPCB local AQI when present, else the universal AQI.
        const idx = indexes.find( i => i.code === 'ind_cpcb' ) || indexes.find( i => i.code === 'uaqi' ) || indexes[ 0 ];
        if ( !idx || !Number.isFinite( idx.aqi ) ) return;
        const aqi = idx.aqi as number;
        const cat = aqiCategory( aqi );
        const pollutants: AirState['pollutants'] = [];
        const WANT: Record<string, string> = {
          pm25: 'PM2.5', pm10: 'PM10', no2: 'NO\u2082', o3: 'O\u2083', co: 'CO', so2: 'SO\u2082',
        };
        ( data?.pollutants || [] ).forEach( ( p: { code?: string; concentration?: { value?: number; units?: string } } ) => {
          const label = p.code ? WANT[ p.code ] : undefined;
          const v = p.concentration?.value;
          if ( label && Number.isFinite( v ) ) {
            pollutants.push( { code: p.code as string, label, value: v as number, unit: p.concentration?.units || '' } );
          }
        } );
        const advisory = data?.healthRecommendations?.generalPopulation;
        store.air = {
          aqi,
          word: cat.word,
          sev: cat.sev,
          dominant: idx.dominantPollutant || undefined,
          pollutants,
          advisory: typeof advisory === 'string' ? advisory : undefined,
        };
      } catch { /* silent degradation */ }
    };

    // WEATHER - India SKU currentConditions:lookup (cheapest current snapshot).
    const fetchWeather = async () => {
      try {
        const res = await fetch(
          `https://weather.googleapis.com/v1/currentConditions:lookup?key=${encodeURIComponent( MAPS_KEY )}&location.latitude=${lat}&location.longitude=${lng}&unitsSystem=METRIC`,
          { signal: ac.signal },
        );
        if ( !res.ok ) return;
        const d = await res.json();
        const temp = d?.temperature?.degrees;
        const feels = d?.feelsLikeTemperature?.degrees;
        const humidity = d?.relativeHumidity;
        const windSpeed = d?.wind?.speed?.value;
        const windUnit = d?.wind?.speed?.unit;
        const windDeg = d?.wind?.direction?.degrees;
        const condition = d?.weatherCondition?.description?.text;
        const out: WeatherState = {};
        if ( Number.isFinite( temp ) ) out.temp = Math.round( temp );
        if ( Number.isFinite( feels ) ) out.feelsLike = Math.round( feels );
        if ( Number.isFinite( humidity ) ) out.humidity = Math.round( humidity );
        if ( Number.isFinite( windSpeed ) ) {
          out.windSpeed = Math.round( windSpeed );
          out.windUnit = windUnitLabel( typeof windUnit === 'string' ? windUnit : undefined );
        }
        if ( Number.isFinite( windDeg ) ) out.windDir = windDirection( windDeg );
        if ( typeof condition === 'string' ) out.condition = condition;
        // Only keep weather if at least one field arrived.
        if ( Object.keys( out ).length ) store.weather = out;
      } catch { /* silent degradation */ }
    };

    // SOLAR - India SKU Building Insights only. 404/NOT_FOUND is common; degrade silently.
    const fetchSolar = async () => {
      try {
        const res = await fetch(
          `https://solar.googleapis.com/v1/buildingInsights:findClosest?key=${encodeURIComponent( MAPS_KEY )}&location.latitude=${lat}&location.longitude=${lng}`,
          { signal: ac.signal },
        );
        if ( !res.ok ) return;
        const d = await res.json();
        const sp = d?.solarPotential;
        if ( !sp ) return;
        const out: SolarState = {};
        if ( Number.isFinite( sp.maxArrayPanelsCount ) ) out.maxPanels = sp.maxArrayPanelsCount;
        if ( Number.isFinite( sp.maxArrayAreaMeters2 ) ) out.roofAreaM2 = Math.round( sp.maxArrayAreaMeters2 );
        if ( Number.isFinite( sp.maxSunshineHoursPerYear ) ) out.sunshineHrs = Math.round( sp.maxSunshineHoursPerYear );
        const cfg = Array.isArray( sp.solarPanelConfigs ) ? sp.solarPanelConfigs[ sp.solarPanelConfigs.length - 1 ] : null;
        if ( cfg && Number.isFinite( cfg.yearlyEnergyDcKwh ) ) out.yearlyKwh = Math.round( cfg.yearlyEnergyDcKwh );
        if ( Object.keys( out ).length ) store.solar = out;
      } catch { /* silent degradation */ }
    };

    // POLLEN - forecast:lookup, one day. Degrade silently if absent.
    const fetchPollen = async () => {
      try {
        const res = await fetch(
          `https://pollen.googleapis.com/v1/forecast:lookup?key=${encodeURIComponent( MAPS_KEY )}&location.latitude=${lat}&location.longitude=${lng}&days=1`,
          { signal: ac.signal },
        );
        if ( !res.ok ) return;
        const d = await res.json();
        const daily = Array.isArray( d?.dailyInfo ) ? d.dailyInfo[ 0 ] : null;
        const types: { code?: string; displayName?: string; indexInfo?: { value?: number } }[] = daily?.pollenTypeInfo || [];
        const rows: PollenRow[] = [];
        types.forEach( t => {
          const v = t.indexInfo?.value;
          if ( t.displayName && Number.isFinite( v ) ) {
            rows.push( { label: t.displayName, index: v as number, word: pollenCategory( v as number ) } );
          }
        } );
        if ( rows.length ) store.pollen = rows;
      } catch { /* silent degradation */ }
    };

    ( async () => {
      await Promise.all( [ fetchAir(), fetchWeather(), fetchSolar(), fetchPollen() ] );
      if ( ac.signal.aborted ) return;
      cache.current[ cacheKey ] = store;
      // First setState via rAF to avoid react-hooks/set-state-in-effect.
      requestAnimationFrame( () => {
        if ( ac.signal.aborted ) return;
        setAir( store.air );
        setWeather( store.weather );
        setSolar( store.solar );
        setPollen( store.pollen );
      } );
    } )();

    return () => ac.abort();
  }, [ place ] );

  /* ---------------------------------------------------------------------------------
     RECENTRE the map + move the marker when the place changes (after the map exists). */
  useEffect( () => {
    const w = window as unknown as { google?: { maps?: { LatLng: new ( a: number, b: number ) => unknown } } };
    const map = mapRef.current as { setCenter?: ( p: { lat: number; lng: number } ) => void } | null;
    const marker = markerRef.current as { setPosition?: ( p: { lat: number; lng: number } ) => void; setTitle?: ( t: string ) => void } | null;
    if ( !map || !marker || !w.google?.maps ) return;
    map.setCenter?.( { lat: place.lat, lng: place.lng } );
    marker.setPosition?.( { lat: place.lat, lng: place.lng } );
    marker.setTitle?.( place.name );
  }, [ place, mapReady ] );

  /* ---------------------------------------------------------------------------------
     AQI HEATMAP OVERLAY - ON USER ACTION ONLY. The ImageMapType is created and its
     tiles requested only when a layer button is pressed; never on page load. */
  useEffect( () => {
    const w = window as unknown as {
      google?: { maps?: { ImageMapType: new ( opts: Record<string, unknown> ) => unknown } };
    };
    const map = mapRef.current as { overlayMapTypes?: { clear: () => void; push: ( t: unknown ) => void } } | null;
    if ( !map || !w.google?.maps ) return;
    map.overlayMapTypes?.clear();
    if ( !layer ) return;
    // Air Quality API mapType enum values. Use the universal AQI scale (UAQI_RED_GREEN)
    // rather than US_AQI so heatmap colours line up with the India-CPCB legend/panels on
    // this page, and PM25_INDIGO_PERSIAN for PM2.5 (PM25_HEATMAP is not a valid enum value).
    const mapType = layer === 'PM25' ? 'PM25_INDIGO_PERSIAN' : 'UAQI_RED_GREEN';
    const overlay = new w.google.maps.ImageMapType( {
      name: layer,
      tileSize: { width: 256, height: 256 },
      getTileUrl: ( coord: { x: number; y: number }, zoom: number ) =>
        `https://airquality.googleapis.com/v1/mapTypes/${mapType}/heatmapTiles/${zoom}/${coord.x}/${coord.y}?key=${encodeURIComponent( MAPS_KEY )}`,
    } );
    map.overlayMapTypes?.push( overlay );
  }, [ layer ] );

  /* ---------------------------------------------------------------------------------
     SEARCH - debounced (~300ms), India-scoped. Prefer Places Autocomplete when the
     library loaded, else Geocoding with components=country:in. Client-side only. */
  const runSearch = useCallback( ( text: string ) => {
    if ( !MAPS_KEY || !text.trim() ) { setResults( [] ); setOpen( false ); return; }
    const svc = placesSvc.current as {
      textSearch?: ( req: Record<string, unknown>, cb: ( r: unknown[] | null, status: string ) => void ) => void;
    } | null;
    const w = window as unknown as { google?: { maps?: { places?: { PlacesServiceStatus?: { OK?: string } } } } };
    const OK = w.google?.maps?.places?.PlacesServiceStatus?.OK || 'OK';

    if ( svc?.textSearch ) {
      svc.textSearch(
        {
          query: text,
          region: 'in',
          locationRestriction: {
            north: INDIA_BOUNDS.north, south: INDIA_BOUNDS.south,
            east: INDIA_BOUNDS.east, west: INDIA_BOUNDS.west,
          },
        },
        ( r, status ) => {
          if ( status !== OK || !Array.isArray( r ) ) { setResults( [] ); setOpen( true ); return; }
          const mapped = r.slice( 0, 6 ).map( ( p: unknown ) => {
            const pr = p as { name?: string; formatted_address?: string; geometry?: { location?: { lat: () => number; lng: () => number } } };
            const loc = pr.geometry?.location;
            return {
              name: pr.name || 'Place',
              addr: pr.formatted_address || '',
              lat: loc ? loc.lat() : DEFAULT_PLACE.lat,
              lng: loc ? loc.lng() : DEFAULT_PLACE.lng,
            };
          } );
          setResults( mapped );
          setActive( mapped.length ? 0 : -1 );
          setOpen( true );
        },
      );
      return;
    }

    // Fallback: Geocoding restricted to India.
    const gc = geocoder.current as {
      geocode?: ( req: Record<string, unknown>, cb: ( r: unknown[] | null, status: string ) => void ) => void;
    } | null;
    if ( gc?.geocode ) {
      gc.geocode(
        { address: text, componentRestrictions: { country: 'in' }, region: 'in' },
        ( r, status ) => {
          if ( status !== 'OK' || !Array.isArray( r ) ) { setResults( [] ); setOpen( true ); return; }
          const mapped = r.slice( 0, 6 ).map( ( p: unknown ) => {
            const pr = p as { formatted_address?: string; geometry?: { location?: { lat: () => number; lng: () => number } } };
            const loc = pr.geometry?.location;
            return {
              name: pr.formatted_address?.split( ',' )[ 0 ] || 'Place',
              addr: pr.formatted_address || '',
              lat: loc ? loc.lat() : DEFAULT_PLACE.lat,
              lng: loc ? loc.lng() : DEFAULT_PLACE.lng,
            };
          } );
          setResults( mapped );
          setActive( mapped.length ? 0 : -1 );
          setOpen( true );
        },
      );
    }
  }, [] );

  const onQueryChange = ( e: React.ChangeEvent<HTMLInputElement> ) => {
    const v = e.target.value;
    setQuery( v );
    if ( searchTimer.current ) clearTimeout( searchTimer.current );
    searchTimer.current = setTimeout( () => runSearch( v ), 300 );
  };

  const choose = ( r: { name: string; addr: string; lat: number; lng: number } ) => {
    setPlace( { name: r.name, addr: r.addr, lat: r.lat, lng: r.lng } );
    setQuery( r.name );
    setOpen( false );
    setResults( [] );
    setActive( -1 );
  };

  const onKeyDown = ( e: React.KeyboardEvent<HTMLInputElement> ) => {
    if ( !open || !results.length ) return;
    if ( e.key === 'ArrowDown' ) { e.preventDefault(); setActive( i => Math.min( i + 1, results.length - 1 ) ); }
    else if ( e.key === 'ArrowUp' ) { e.preventDefault(); setActive( i => Math.max( i - 1, 0 ) ); }
    else if ( e.key === 'Enter' ) { e.preventDefault(); if ( active >= 0 ) choose( results[ active ] ); }
    else if ( e.key === 'Escape' ) { setOpen( false ); }
  };

  useEffect( () => () => { if ( searchTimer.current ) clearTimeout( searchTimer.current ); }, [] );

  const dotClass = ( sev: Sev ) => `vl-live-dot vl-live-dot-${sev}`;
  const liveActive = Boolean( MAPS_KEY );

  return (
    <section className="vl-live" aria-labelledby="vl-live-title">
      <h2 className="vl-live-sr" id="vl-live-title">Live air quality and weather</h2>

      <div className="vl-live-wrap vl-live-grid">
        {/* ===== LEFT COLUMN: all content, stacked ===== */}
        <div className="vl-live-left">

          {/* SEARCH - drives the map. Inert/hidden when there is no key. */}
          { liveActive && (
            <div className="vl-live-block vl-live-block-top">
              <label className="vl-live-label" htmlFor="vl-live-search">Search a city or place</label>
              <div className="vl-live-search">
                <div className="vl-live-search-field">
                  <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                    <circle cx="9" cy="9" r="6.25" stroke="#1a3a2a" strokeWidth="2" />
                    <path d="M13.8 13.8 L18.5 18.5" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                  <input
                    className="vl-live-search-input"
                    id="vl-live-search"
                    type="text"
                    role="combobox"
                    aria-controls="vl-live-search-results"
                    aria-expanded={ open }
                    aria-autocomplete="list"
                    autoComplete="off"
                    autoCorrect="off"
                    spellCheck={ false }
                    placeholder="Search a city or place"
                    value={ query }
                    onChange={ onQueryChange }
                    onKeyDown={ onKeyDown }
                  />
                </div>
                <ul
                  className="vl-live-search-results"
                  id="vl-live-search-results"
                  role="listbox"
                  aria-label="Matching places"
                  hidden={ !open || !results.length }
                >
                  { results.map( ( r, i ) => (
                    <li
                      key={ `${r.name}-${r.lat}-${r.lng}` }
                      className="vl-live-search-option"
                      role="option"
                      aria-selected={ i === active }
                      onMouseDown={ e => { e.preventDefault(); choose( r ); } }
                    >
                      <span className="vl-live-search-option-name">{ r.name }</span>
                      { r.addr && <span className="vl-live-search-option-addr">{ r.addr }</span> }
                    </li>
                  ) ) }
                </ul>
              </div>
            </div>
          ) }

          {/* NOW - editorial display type. The whole block is gated on a key: with no key
              there is no map and no live data, so a bare place name would be misleading.
              The place name renders once live context exists; the live figures only once
              they actually arrived. */}
          { liveActive && (
          <div className="vl-live-block">
            <p className="vl-live-place">{ place.name }</p>
            <p className="vl-live-place-addr">{ place.addr }</p>

            { ( air || weather ) && (
              <div className="vl-live-now vl-live-band">
                { air && (
                  <div>
                    <p className="vl-live-label">Air quality now</p>
                    <div className="vl-live-figure">
                      <span className={ dotClass( air.sev ) } aria-hidden="true" />
                      <span className="vl-live-metric-xl">{ air.aqi }</span>
                      <span className="vl-live-cat">{ air.word }</span>
                    </div>
                    { air.dominant && (
                      <p className="vl-live-cond">{ air.word } air. Dominant pollutant { air.dominant }.</p>
                    ) }
                    <p className="vl-live-sub-fact">AQI { air.aqi } · { air.word } band</p>
                  </div>
                ) }
                { weather && (
                  <div className="vl-live-band-aside">
                    <p className="vl-live-label">Weather now</p>
                    { Number.isFinite( weather.temp ) && (
                      <div className="vl-live-figure"><span className="vl-live-metric-lg">{ weather.temp }°</span></div>
                    ) }
                    { weather.condition && <p className="vl-live-cond">{ weather.condition }</p> }
                    <p className="vl-live-sub-fact">
                      { Number.isFinite( weather.feelsLike ) && <>Feels like { weather.feelsLike }°</> }
                      { Number.isFinite( weather.humidity ) && <> · humidity { weather.humidity }%</> }
                      { Number.isFinite( weather.windSpeed ) && <> · wind { weather.windSpeed } { weather.windUnit || 'km/h' }{ weather.windDir ? ` ${weather.windDir}` : '' }</> }
                    </p>
                  </div>
                ) }
              </div>
            ) }
          </div>
          ) }

          {/* CONDITIONS - rail of live weather/air facts; omit any that did not arrive. */}
          { ( weather || air ) && (
            <div className="vl-live-block">
              <h3 className="vl-live-h2" id="vl-live-facts">Conditions</h3>
              <div className="vl-live-rail" aria-labelledby="vl-live-facts">
                { Number.isFinite( weather?.humidity ) && (
                  <div className="vl-live-fact"><p className="vl-live-label">Humidity</p><span className="vl-live-metric-md">{ weather!.humidity }%</span></div>
                ) }
                { Number.isFinite( weather?.windSpeed ) && (
                  <div className="vl-live-fact"><p className="vl-live-label">Wind speed</p><span className="vl-live-metric-md">{ weather!.windSpeed } { weather!.windUnit || 'km/h' }</span></div>
                ) }
                { weather?.windDir && (
                  <div className="vl-live-fact"><p className="vl-live-label">Wind direction</p><span className="vl-live-metric-md">{ weather.windDir }</span></div>
                ) }
                { Number.isFinite( weather?.temp ) && (
                  <div className="vl-live-fact"><p className="vl-live-label">Temperature</p><span className="vl-live-metric-md">{ weather!.temp }°</span></div>
                ) }
                { air && air.pollutants.filter( p => p.code === 'pm25' ).map( p => (
                  <div className="vl-live-fact" key="cond-pm25"><p className="vl-live-label">PM2.5</p><span className="vl-live-metric-md">{ p.value } { p.unit }</span></div>
                ) ) }
              </div>
            </div>
          ) }

          {/* HEALTH ADVISORY - only when the API supplied one. */}
          { air?.advisory && (
            <div className="vl-live-block">
              <p className="vl-live-eyebrow">Health advisory</p>
              <h3 className="vl-live-h2" id="vl-live-health">{ air.word } air today.</h3>
              <p className="vl-live-body">{ air.advisory }</p>
              <span className="vl-live-advisory-rule" aria-hidden="true" />
            </div>
          ) }

          {/* AIR / WEATHER DETAIL - pollutant rows from the live response. */}
          { air && air.pollutants.length > 0 && (
            <div className="vl-live-block">
              <h3 className="vl-live-h2" id="vl-live-detail-title">Air &amp; weather detail</h3>
              { air.pollutants.map( p => {
                const cat = aqiCategory( air.aqi );
                return (
                  <div className="vl-live-prow" key={ p.code }>
                    <p className="vl-live-label">{ p.label }</p>
                    <span className="vl-live-track"><span className={ `vl-live-bar vl-live-bar-${cat.sev}` } style={ { width: `${Math.min( 100, Math.round( ( p.value / 250 ) * 100 ) )}%` } } /></span>
                    <span className="vl-live-metric-md">{ p.value } { p.unit }</span>
                    <span className="vl-live-prow-cat">{ cat.word }</span>
                  </div>
                );
              } ) }
            </div>
          ) }

          {/* SOLAR - Building Insights. Section renders only when the API returned data. */}
          { solar && ( Number.isFinite( solar.maxPanels ) || Number.isFinite( solar.roofAreaM2 ) || Number.isFinite( solar.yearlyKwh ) || Number.isFinite( solar.sunshineHrs ) ) && (
            <section className="vl-live-section" aria-labelledby="vl-live-solar-title">
              <h3 className="vl-live-h2" id="vl-live-solar-title">Solar &ndash; Building Insights</h3>
              <p className="vl-live-small vl-live-mb16">Rooftop solar potential for this address, from the Solar API&rsquo;s building insights.</p>
              { Number.isFinite( solar.maxPanels ) && (
                <div className="vl-live-prow"><p className="vl-live-label">Max panels</p><span className="vl-live-track"><span className="vl-live-bar vl-live-bar-mod" style={ { width: '62%' } } /></span><span className="vl-live-metric-md">{ solar.maxPanels } panels</span><span className="vl-live-prow-cat">Rooftop</span></div>
              ) }
              { Number.isFinite( solar.sunshineHrs ) && (
                <div className="vl-live-prow"><p className="vl-live-label">Sunshine</p><span className="vl-live-track"><span className="vl-live-bar vl-live-bar-poor" style={ { width: '78%' } } /></span><span className="vl-live-metric-md">{ solar.sunshineHrs!.toLocaleString( 'en-IN' ) } hrs/yr</span><span className="vl-live-prow-cat">Per year</span></div>
              ) }
              { Number.isFinite( solar.roofAreaM2 ) && (
                <div className="vl-live-prow"><p className="vl-live-label">Roof area</p><span className="vl-live-track"><span className="vl-live-bar vl-live-bar-sat" style={ { width: '48%' } } /></span><span className="vl-live-metric-md">{ solar.roofAreaM2 } m²</span><span className="vl-live-prow-cat">Usable</span></div>
              ) }
              { Number.isFinite( solar.yearlyKwh ) && (
                <div className="vl-live-prow"><p className="vl-live-label">Yearly energy</p><span className="vl-live-track"><span className="vl-live-bar vl-live-bar-poor" style={ { width: '71%' } } /></span><span className="vl-live-metric-md">{ solar.yearlyKwh!.toLocaleString( 'en-IN' ) } kWh</span><span className="vl-live-prow-cat">Estimated</span></div>
              ) }
            </section>
          ) }

          {/* POLLEN - section renders only when the forecast returned types. */}
          { pollen && pollen.length > 0 && (
            <section className="vl-live-section" aria-labelledby="vl-live-pollen-title">
              <h3 className="vl-live-h2" id="vl-live-pollen-title">Pollen</h3>
              <p className="vl-live-small vl-live-mb16">Today&rsquo;s pollen index by type, from the Pollen API forecast.</p>
              { pollen.map( row => (
                <div className="vl-live-prow" key={ row.label }>
                  <p className="vl-live-label">{ row.label }</p>
                  <span className="vl-live-track"><span className="vl-live-bar vl-live-bar-mod" style={ { width: `${Math.min( 100, row.index * 20 )}%` } } /></span>
                  <span className="vl-live-metric-md">Index { row.index }</span>
                  <span className="vl-live-prow-cat">{ row.word }</span>
                </div>
              ) ) }
            </section>
          ) }

          {/* SUBSCRIBE - the shipped WhatsApp anchor, verbatim URL from the user instruction. */}
          <section className="vl-live-section" aria-label="Subscribe on WhatsApp">
            <a
              className="vl-live-wa-subscribe"
              href="https://wa.me/message/BEA3HNW3LNM3A1"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Subscribe on WhatsApp"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" width="20" height="20">
                <path fill="currentColor" d="M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.16-.17.2-.35.22-.64.08-.3-.15-1.26-.46-2.4-1.48-.88-.79-1.48-1.76-1.65-2.06-.17-.3-.02-.46.13-.61.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.03-.52-.07-.15-.67-1.61-.91-2.21-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.8.37-.27.3-1.03 1.02-1.03 2.48 0 1.46 1.06 2.87 1.21 3.07.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.62.71.23 1.36.2 1.87.12.57-.09 1.76-.72 2-1.41.25-.7.25-1.29.18-1.42-.08-.12-.28-.2-.57-.35M12.05 21.79h-.01a9.87 9.87 0 01-5.03-1.38l-.36-.21-3.74.98 1-3.65-.24-.37a9.86 9.86 0 01-1.51-5.26C2.16 6.45 6.6 2.01 12.05 2.01c2.64 0 5.12 1.03 6.99 2.9a9.83 9.83 0 012.89 6.99c0 5.45-4.44 9.89-9.88 9.89M20.46 3.49A11.82 11.82 0 0012.05 0C5.5 0 .16 5.34.16 11.89c0 2.1.55 4.14 1.59 5.95L.06 24l6.3-1.65a11.88 11.88 0 005.69 1.45c6.55 0 11.89-5.34 11.89-11.89 0-3.18-1.24-6.17-3.48-8.42z" />
              </svg>
              <span>Subscribe on WhatsApp</span>
            </a>
          </section>

          {/* CONTRIBUTE - reuse the shipped component. It reads shipped presets from
              src/config/contribution.ts (CONTRIBUTION_PRESETS_PAISE [20000,40000,60000]);
              the mock's Rs50/Rs200/Rs400 are NOT shipped and changing those is out of scope
              here, so this renders the shipped presets. src/config/contribution.ts unchanged. */}
          <section className="vl-live-section">
            <BlogContribution postId="vayulok" slug="vayulok" />
          </section>

          {/* SHARE - reuse the shipped component with the canonical /vayulok/ url. */}
          <section className="vl-live-section">
            <ShareLinks url={ `${SITE_ORIGIN}/vayulok/` } title="VayuLok — Bharat air and weather intelligence" />
          </section>
        </div>

        {/* ===== RIGHT COLUMN: the map, and nothing else ===== */}
        { liveActive && (
          <div className="vl-live-right">
            <div className="vl-live-map-sticky">
              <div className="vl-live-map-stage">
                <div className="vl-live-map-canvas" ref={ mapHost } role="img" aria-label={ `Map of ${place.name}` } />

                {/* Layer buttons - top-left, clear of Google's bottom-corner notices.
                    The heatmap overlay is created ONLY when one is pressed. */}
                <div className="vl-live-map-controls">
                  <button
                    className="vl-live-layer"
                    type="button"
                    aria-pressed={ layer === 'AQI' }
                    onClick={ () => setLayer( l => ( l === 'AQI' ? null : 'AQI' ) ) }
                  >AQI</button>
                  <button
                    className="vl-live-layer"
                    type="button"
                    aria-pressed={ layer === 'PM25' }
                    onClick={ () => setLayer( l => ( l === 'PM25' ? null : 'PM25' ) ) }
                  >PM2.5</button>
                </div>

                <div className="vl-live-map-legend">
                  <p className="vl-live-label">AQI heatmap</p>
                  <div className="vl-live-scale" aria-hidden="true" />
                  <div className="vl-live-scale-ends"><span>Good</span><span>Severe</span></div>
                  <p className="vl-live-scale-mid">Good · Satisfactory · Moderate · Poor · Very Poor · Severe</p>
                </div>

                {/* Place preview - bottom:76px, never bottom:0: Google's logo and legal
                    notices own the bottom corners. Renders live values when present. */}
                { ( air || weather ) && (
                  <div className="vl-live-map-preview">
                    <p className="vl-live-card-h">{ place.name }</p>
                    <p className="vl-live-small">{ place.addr }</p>
                    <div className="vl-live-preview-metrics">
                      { Number.isFinite( weather?.temp ) && (
                        <div><p className="vl-live-label">Temp</p><span className="vl-live-metric-md">{ weather!.temp }°</span></div>
                      ) }
                      { air && (
                        <div><p className="vl-live-label">AQI</p><span className="vl-live-metric-md">{ air.aqi }</span><p className="vl-live-preview-cat">{ air.word }</p></div>
                      ) }
                      { air && air.pollutants.filter( p => p.code === 'pm25' ).map( p => (
                        <div key="prev-pm25"><p className="vl-live-label">PM2.5</p><span className="vl-live-metric-md">{ p.value }</span><p className="vl-live-preview-cat">{ p.unit }</p></div>
                      ) ) }
                    </div>
                  </div>
                ) }
              </div>
            </div>
          </div>
        ) }
      </div>

      <style jsx>{`
        /* vl-live- prefixed, scoped under this component root. The custom properties live
           on .vl-live rather than :root. No reset, no html/body/* rule, no bare element
           selector. Design tokens are ported from docs/mocks/vayulok-live-mock.html. */
        .vl-live{
          font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
          color:#1a1a1a;-webkit-font-smoothing:antialiased;background:#fff;

          --paper:#fff;--ground:#fafafa;
          --lime:#d1f470;--lime-tint:rgba(209,244,112,.22);--lime-solid:#f5fde0;
          --green:#1a3a2a;--green-dot:#3da35a;--hair:#e5e7eb;
          --ink-head:rgba(0,0,0,.95);--ink-body:rgba(0,0,0,.898);--ink-strong:#000;
          --ink-base:#1a1a1a;--ink-muted:rgba(0,0,0,.54);--ink-status:rgba(0,0,0,.7);--ink-second:rgba(0,0,0,.66);

          /* AQI severity ramp - NO red: dark green -> lime -> amber. */
          --aqi-good:#1a3a2a;--aqi-sat:#4b8058;--aqi-mod:#d1f470;--aqi-poor:#e8c547;--aqi-worst:#c98a2e;
          --tint-warn:#fdf4e3;

          --r-panel:14px;--r-field:10px;--r-pill:999px;--r-btn:13px;
          --e-glide:cubic-bezier(.16,1,.3,1);--e-draw:cubic-bezier(.22,.61,.36,1);
        }
        .vl-live,.vl-live *{box-sizing:border-box}
        .vl-live [hidden]{display:none !important}

        .vl-live-wrap{width:100%;max-width:1300px;margin:0 auto;padding:0 24px}
        .vl-live-sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}

        /* Type ladder from index.tsx + the two Blog components. */
        .vl-live-h2{margin:0 0 14px;font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;letter-spacing:-1.2px;color:var(--ink-head)}
        .vl-live-card-h{margin:0 0 6px;font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;color:var(--ink-strong)}
        .vl-live-body{margin:0;max-width:62ch;font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;color:var(--ink-body)}
        .vl-live-eyebrow{margin:0 0 14px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--green)}
        .vl-live-label{margin:0 0 7px;font-size:12px;font-weight:700;letter-spacing:.01em;color:var(--green)}
        .vl-live-small{margin:0;font-size:13px;line-height:1.4;color:var(--ink-muted)}
        .vl-live-mb16{margin-bottom:16px}

        .vl-live-block{padding-block:44px}
        .vl-live-block:first-child{padding-top:0}
        .vl-live-block-top{padding-top:0}

        /* The grid. ONE grid, TWO columns, TWO items. */
        .vl-live-grid{display:grid;grid-template-columns:minmax(0,1fr);row-gap:40px;padding-top:40px}
        .vl-live-left{min-width:0;container-type:inline-size;container-name:vllive}
        .vl-live-right{min-width:0}

        .vl-live-left > .vl-live-section{margin-top:44px;padding-top:24px;border-top:1px solid var(--hair)}

        .vl-live-map-sticky{display:flex;flex-direction:column;gap:10px}
        .vl-live-map-stage{position:relative;height:340px;overflow:hidden;border:1px solid var(--hair);border-radius:var(--r-panel);background:var(--ground)}
        .vl-live-map-canvas{position:absolute;inset:0}

        @media(min-width:1024px){
          /* Two equal columns with a fixed gap so they cannot overlap. The earlier
             track definition summed past the container width once the gap was added,
             so the right map column slid over the left content. */
          .vl-live-grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr);column-gap:40px;row-gap:0}
          .vl-live-map-sticky{position:sticky;top:96px;height:calc(100vh - 120px)}
          .vl-live-map-stage{flex:1 1 auto;min-height:0;height:auto}
        }

        /* The asymmetric band - stacks in a narrow column, two-up above 620px. */
        .vl-live-band{display:grid;grid-template-columns:minmax(0,1fr);gap:28px;align-items:start}
        .vl-live-band-aside{min-width:0;padding-top:28px;border-top:1px solid var(--hair)}
        @container vllive (min-width:620px){
          .vl-live-band{grid-template-columns:minmax(0,1fr) 380px;gap:44px}
          .vl-live-band-aside{padding-top:0;border-top:0;padding-left:44px;border-left:1px solid var(--hair)}
        }

        /* Search. */
        .vl-live-search{position:relative;max-width:520px}
        .vl-live-search-field{display:flex;align-items:center;gap:10px;min-height:52px;padding:0 14px;border:1px solid var(--hair);border-radius:var(--r-field);background:var(--paper)}
        .vl-live-search-field:focus-within{border-color:var(--green)}
        .vl-live-search-input{flex:1 1 auto;min-width:0;border:0;outline:0;background:transparent;font:inherit;font-size:16px;color:var(--ink-base)}
        .vl-live-search-input::placeholder{color:var(--ink-muted)}
        .vl-live-search-results{position:absolute;top:calc(100% + 6px);inset-inline:0;z-index:5;margin:0;padding:0;list-style:none;overflow:hidden;border:1px solid var(--hair);border-radius:var(--r-field);background:var(--paper)}
        .vl-live-search-option{display:block;min-height:52px;padding:10px 14px;cursor:pointer}
        .vl-live-search-option + .vl-live-search-option{border-top:1px solid var(--hair)}
        .vl-live-search-option[aria-selected="true"]{background:var(--lime)}
        .vl-live-search-option-name{display:block;font-size:16px;font-weight:600;line-height:1.3;color:var(--ink-strong)}
        .vl-live-search-option-addr{display:block;margin-top:2px;font-size:13px;line-height:1.4;color:var(--ink-muted)}

        /* NOW figures. */
        .vl-live-place{margin:0 0 6px;font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;color:var(--ink-strong)}
        .vl-live-place-addr{margin:0 0 36px;max-width:62ch;font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;color:var(--ink-body)}
        .vl-live-now{padding-top:32px;border-top:1px solid var(--hair)}
        .vl-live-figure{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:10px 0 0}
        .vl-live-metric-xl{font-size:clamp(36px,4.3vw,60px);font-weight:600;line-height:1.04;letter-spacing:-0.04em;color:var(--ink-head)}
        .vl-live-metric-lg{font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;letter-spacing:-1.2px;color:var(--ink-head)}
        .vl-live-metric-md{display:block;font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;color:var(--ink-strong)}
        .vl-live-cond{margin:16px 0 0;max-width:46ch;font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;color:var(--ink-body)}
        .vl-live-sub-fact{margin:8px 0 0;font-size:15px;line-height:1.5;color:var(--ink-second)}

        /* AQI mark - severity encoded by FORM as well as tone. */
        .vl-live-dot{display:inline-block;width:16px;height:16px;border-radius:50%;flex:0 0 auto}
        .vl-live-dot-good{background:var(--aqi-good);border:2px solid var(--green)}
        .vl-live-dot-sat{background:var(--aqi-sat);border:2px solid var(--green)}
        .vl-live-dot-mod{background:var(--aqi-mod);border:2px solid var(--green)}
        .vl-live-dot-poor{background:var(--paper);border:5px solid var(--aqi-poor);box-shadow:0 0 0 1px var(--green)}
        .vl-live-dot-worst{background:var(--aqi-worst);border:3px solid var(--paper);box-shadow:0 0 0 2px var(--aqi-worst),0 0 0 3px var(--green)}

        .vl-live-cat{display:inline-flex;align-items:center;padding:4px 14px;border:1px solid var(--green);border-radius:var(--r-pill);background:var(--paper);font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--green);white-space:nowrap}

        /* Map overlays - inset from the bottom corners (Maps Platform ToS). No rule
           anywhere targets .gm-style-cc, a[href*="google"] or img[alt="Google"]. */
        .vl-live-map-controls{position:absolute;top:16px;left:16px;z-index:4;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
        .vl-live-layer{min-height:44px;padding:0 18px;border:2px solid var(--hair);border-radius:var(--r-pill);background:var(--paper);color:var(--green);font:inherit;font-size:14px;font-weight:600;letter-spacing:-.125px;cursor:pointer;transition:background-color .2s,border-color .2s,transform .2s,box-shadow .2s}
        .vl-live-layer:hover{border-color:var(--lime);background:var(--lime-tint);transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
        .vl-live-layer:focus-visible{outline:3px solid var(--green);outline-offset:3px}
        .vl-live-layer[aria-pressed="true"]{border-color:var(--green);background:var(--lime)}

        .vl-live-map-legend{position:absolute;top:16px;right:16px;z-index:4;width:224px;padding:16px;border:1px solid var(--hair);border-radius:var(--r-panel);background:var(--paper)}
        .vl-live-scale{height:10px;border-radius:var(--r-pill);background:linear-gradient(90deg,var(--aqi-good) 0%,var(--aqi-sat) 22%,var(--aqi-mod) 48%,var(--aqi-poor) 74%,var(--aqi-worst) 100%)}
        .vl-live-scale-ends{display:flex;justify-content:space-between;margin-top:8px;gap:8px}
        .vl-live-scale-ends span{font-size:12px;font-weight:700;color:var(--green)}
        .vl-live-scale-mid{margin:8px 0 0;font-size:12px;line-height:1.4;color:var(--ink-muted)}

        .vl-live-map-preview{position:absolute;left:16px;bottom:76px;z-index:4;width:296px;padding:18px;border:1px solid var(--hair);border-radius:var(--r-panel);background:var(--paper)}
        .vl-live-preview-metrics{display:grid;grid-template-columns:repeat(3,1fr);margin-top:14px;border-top:1px solid var(--hair)}
        .vl-live-preview-metrics>div{padding:12px 0 0}
        .vl-live-preview-metrics>div+div{padding-left:14px;border-left:1px solid var(--hair)}
        .vl-live-preview-metrics .vl-live-label{margin-bottom:4px}
        .vl-live-preview-metrics .vl-live-metric-md{font-size:17px}
        .vl-live-preview-cat{margin:4px 0 0;font-size:12px;font-weight:700;letter-spacing:.01em;color:var(--ink-muted)}

        /* Conditions rail. */
        .vl-live-rail{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));border-top:1px solid var(--hair)}
        .vl-live-fact{padding:22px 24px 22px 0}
        .vl-live-fact:nth-child(even){padding-left:24px;border-left:1px solid var(--hair)}
        .vl-live-fact:nth-child(n+3){border-top:1px solid var(--hair)}
        .vl-live-fact .vl-live-label{margin-bottom:10px}
        @container vllive (min-width:860px){
          .vl-live-rail{grid-template-columns:repeat(4,minmax(0,1fr))}
          .vl-live-fact:nth-child(even){padding-left:0;border-left:0}
          .vl-live-fact:nth-child(n+3){border-top:0}
          .vl-live-fact:not(:nth-child(4n+1)){padding-left:24px;border-left:1px solid var(--hair)}
          .vl-live-fact:nth-child(n+5){border-top:1px solid var(--hair)}
        }

        /* Health advisory accent rule. */
        .vl-live-advisory-rule{display:block;height:3px;width:120px;margin:30px 0 0;background:var(--lime)}

        /* Pollutant rows. */
        .vl-live-prow{display:grid;grid-template-columns:92px minmax(0,1fr);gap:8px 16px;align-items:center;padding:16px 0;border-bottom:1px solid var(--hair)}
        .vl-live-prow:first-of-type{border-top:1px solid var(--hair)}
        .vl-live-prow .vl-live-label{margin:0}
        .vl-live-prow .vl-live-track{grid-column:2}
        .vl-live-prow .vl-live-metric-md,.vl-live-prow .vl-live-prow-cat{grid-column:2;text-align:left}
        .vl-live-prow .vl-live-metric-md{font-size:17px}
        @container vllive (min-width:560px){
          .vl-live-prow{grid-template-columns:100px minmax(0,1fr) 104px 112px;gap:16px}
          .vl-live-prow .vl-live-metric-md{grid-column:3;text-align:right}
          .vl-live-prow .vl-live-prow-cat{grid-column:4;text-align:right}
        }
        .vl-live-track{display:block;height:8px;background:var(--ground);border-radius:2px;overflow:hidden}
        .vl-live-bar{display:block;height:100%}
        .vl-live-bar-good{background:var(--aqi-good)}
        .vl-live-bar-sat{background:var(--aqi-sat)}
        .vl-live-bar-mod{background:var(--aqi-mod)}
        .vl-live-bar-poor{background:var(--aqi-poor)}
        .vl-live-bar-worst{background:var(--aqi-worst)}
        .vl-live-prow-cat{font-size:12px;font-weight:700;letter-spacing:.01em;color:var(--ink-muted)}

        .vl-live-section{padding-top:0}

        /* SUBSCRIBE - the shipped .blog-wa-subscribe pill (ROLE 8). */
        .vl-live-wa-subscribe{display:inline-flex;align-items:center;gap:10px;padding:12px 20px;border-radius:999px;background:var(--lime);color:var(--green);font-weight:700;font-size:17px;text-decoration:none;transition:transform .2s,box-shadow .2s}
        .vl-live-wa-subscribe svg{flex:0 0 auto}
        .vl-live-wa-subscribe:hover,.vl-live-wa-subscribe:focus-visible{transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.18)}
        .vl-live-wa-subscribe:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px}

        @media(max-width:1023px){
          .vl-live-map-legend{top:12px;right:12px;width:168px;padding:12px}
          .vl-live-map-legend .vl-live-scale-mid{display:none}
          .vl-live-map-preview{left:12px;bottom:68px;width:216px;padding:14px}
        }
        @media(max-width:767px){
          .vl-live-wrap{padding-inline:16px}
          .vl-live-section{padding-top:0}
          .vl-live-block{padding-block:36px}
          .vl-live-map-controls{top:12px;left:12px}
          .vl-live-map-legend{width:136px}
          .vl-live-map-preview{width:190px}
          .vl-live-map-preview .vl-live-card-h{font-size:17px}
        }
        @media(prefers-reduced-motion:reduce){
          .vl-live-layer,.vl-live-wa-subscribe{transition:none}
          .vl-live-layer:hover,.vl-live-wa-subscribe:hover,.vl-live-wa-subscribe:focus-visible{transform:none;box-shadow:none}
        }
      `}</style>
    </section>
  );
};

export default VayuLokLive;
