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
  windGust?: number;
  rainMm?: number;
  rainProb?: number;
  stormProb?: number;
  uv?: number;
  visibilityKm?: number;
  pressureHpa?: number;
  dewPoint?: number;
  heatIndex?: number;
  wetBulb?: number;
  cloudCover?: number;
  condition?: string;
  currentTime?: string;
}
interface WeatherHour {
  time: number;
  temp?: number;
  feelsLike?: number;
  rainProb?: number;
  rainMm?: number;
  stormProb?: number;
  uv?: number;
  condition?: string;
  icon?: string;
}
interface WeatherDay {
  time: number;
  label: string;
  dateLabel: string;
  min?: number;
  max?: number;
  rainProb?: number;
  condition?: string;
  icon?: string;
  sunrise?: string;
  sunset?: string;
}
interface AirPoint {
  time: number;
  aqi: number;
  word: string;
  pm25?: number;
}
interface WeatherAlertRow {
  id: string;
  title: string;
  description?: string;
  area?: string;
  severity?: string;
  urgency?: string;
  expires?: string;
}
interface SolarState {
  maxPanels?: number;
  roofAreaM2?: number;
  yearlyKwh?: number;
  sunshineHrs?: number;
}
interface PollenRow { label: string; index: number; word: string; day: string; }

const COMPASS = [ 'N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW' ];
function windDirection( deg: number ): string {
  return COMPASS[ Math.round( deg / 45 ) % 8 ];
}
// The Air Quality API returns concentration units as long SCREAMING_SNAKE enums
// (MICROGRAMS_PER_CUBIC_METER, PARTS_PER_BILLION, ...). Rendered verbatim they blow
// out the value column and collide with the category word. Map them to short symbols.
function concUnitLabel( unit?: string ): string {
  switch ( unit ) {
    case 'MICROGRAMS_PER_CUBIC_METER': return '\u00B5g/m\u00B3';
    case 'PARTS_PER_BILLION': return 'ppb';
    case 'PARTS_PER_MILLION': return 'ppm';
    case 'MILLIGRAMS_PER_CUBIC_METER': return 'mg/m\u00B3';
    case 'NANOGRAMS_PER_CUBIC_METER': return 'ng/m\u00B3';
    default: return unit || '';
  }
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

function n( value: unknown ): number {
  const out = Number( value );
  return Number.isFinite( out ) ? out : NaN;
}

function weatherHourFromApi( row: Record<string, any> ): WeatherHour | null {
  const time = new Date( row?.interval?.startTime || row?.dateTime || 0 ).getTime();
  if ( !Number.isFinite( time ) ) return null;
  const out: WeatherHour = { time };
  const temp = n( row?.temperature?.degrees );
  const feels = n( row?.feelsLikeTemperature?.degrees );
  const rain = n( row?.precipitation?.probability?.percent );
  const rainMm = n( row?.precipitation?.qpf?.quantity );
  const storm = n( row?.thunderstormProbability );
  const uv = n( row?.uvIndex );
  if ( Number.isFinite( temp ) ) out.temp = Math.round( temp );
  if ( Number.isFinite( feels ) ) out.feelsLike = Math.round( feels );
  if ( Number.isFinite( rain ) ) out.rainProb = Math.round( rain );
  if ( Number.isFinite( rainMm ) ) out.rainMm = rainMm;
  if ( Number.isFinite( storm ) ) out.stormProb = Math.round( storm );
  if ( Number.isFinite( uv ) ) out.uv = Math.round( uv );
  if ( typeof row?.weatherCondition?.description?.text === 'string' ) out.condition = row.weatherCondition.description.text;
  if ( typeof row?.weatherCondition?.iconBaseUri === 'string' ) out.icon = row.weatherCondition.iconBaseUri;
  return out;
}

function airPointFromApi( row: Record<string, any> ): AirPoint | null {
  const time = new Date( row?.dateTime || row?.period?.startTime || row?.interval?.startTime || 0 ).getTime();
  if ( !Number.isFinite( time ) ) return null;
  const indexes = Array.isArray( row?.indexes ) ? row.indexes : [];
  const idx = indexes.find( ( i: any ) => i?.code === 'ind_cpcb' ) || indexes.find( ( i: any ) => i?.code === 'uaqi' ) || indexes[ 0 ];
  const aqi = n( idx?.aqi );
  if ( !Number.isFinite( aqi ) ) return null;
  const pm = ( Array.isArray( row?.pollutants ) ? row.pollutants : [] ).find( ( p: any ) => p?.code === 'pm25' );
  const pm25 = n( pm?.concentration?.value );
  return {
    time,
    aqi: Math.round( aqi ),
    word: typeof idx?.category === 'string' ? idx.category : aqiCategory( aqi ).word,
    ...( Number.isFinite( pm25 ) ? { pm25 } : {} ),
  };
}

function hourLabel( ms: number ): string {
  return new Intl.DateTimeFormat( 'en-IN', { timeZone: 'Asia/Kolkata', hour: 'numeric' } ).format( new Date( ms ) );
}

function istTimeLabel(): string {
  return new Intl.DateTimeFormat( 'en-IN', { timeZone: 'Asia/Kolkata', hour: 'numeric', minute: '2-digit' } ).format( new Date() ) + ' IST';
}

function bestOutsideWindow( weatherHours: WeatherHour[], airHours: AirPoint[] ): { label: string; note: string } | null {
  if ( weatherHours.length < 2 ) return null;
  const scored = weatherHours.slice( 0, 24 ).map( ( w, i ) => {
    const a = airHours.find( p => Math.abs( p.time - w.time ) < 45 * 60 * 1000 ) || airHours[ i ];
    let score = 100;
    if ( Number.isFinite( w.rainProb ) ) score -= ( w.rainProb as number ) * .45;
    if ( Number.isFinite( w.stormProb ) ) score -= ( w.stormProb as number ) * .65;
    if ( Number.isFinite( w.uv ) && ( w.uv as number ) > 5 ) score -= ( ( w.uv as number ) - 5 ) * 5;
    if ( Number.isFinite( w.temp ) ) {
      if ( ( w.temp as number ) > 34 ) score -= ( ( w.temp as number ) - 34 ) * 5;
      if ( ( w.temp as number ) < 15 ) score -= ( 15 - ( w.temp as number ) ) * 2;
    }
    if ( a && Number.isFinite( a.aqi ) && a.aqi > 50 ) score -= ( a.aqi - 50 ) * .22;
    return { w, a, score };
  } );
  let best: { start: typeof scored[number]; end: typeof scored[number]; score: number } | null = null;
  for ( let i = 0; i < scored.length - 1; i++ ) {
    const pairScore = ( scored[ i ].score + scored[ i + 1 ].score ) / 2;
    if ( !best || pairScore > best.score ) best = { start: scored[ i ], end: scored[ i + 1 ], score: pairScore };
  }
  if ( !best ) return null;
  const end = new Date( best.end.w.time + 60 * 60 * 1000 ).getTime();
  const notes: string[] = [];
  if ( Number.isFinite( best.start.w.temp ) ) notes.push( String( best.start.w.temp ) + '°C' );
  if ( Number.isFinite( best.start.w.rainProb ) ) notes.push( String( best.start.w.rainProb ) + '% rain' );
  if ( best.start.a ) notes.push( 'AQI ' + String( best.start.a.aqi ) );
  if ( Number.isFinite( best.start.w.uv ) ) notes.push( 'UV ' + String( best.start.w.uv ) );
  return { label: hourLabel( best.start.w.time ) + '–' + hourLabel( end ), note: notes.join( ' · ' ) || 'Best upcoming outdoor window' };
}

const VayuLokLive: React.FC = () => {
  // The selected place drives every fetch. Default is Connaught Place; search updates it.
  const [ place, setPlace ] = useState( DEFAULT_PLACE );
  const [ mapReady, setMapReady ] = useState( false );

  const [ air, setAir ] = useState<AirState | null>( null );
  const [ weather, setWeather ] = useState<WeatherState | null>( null );
  const [ solar, setSolar ] = useState<SolarState | null>( null );
  const [ pollen, setPollen ] = useState<PollenRow[] | null>( null );
  const [ weatherHourly, setWeatherHourly ] = useState<WeatherHour[]>( [] );
  const [ weatherDaily, setWeatherDaily ] = useState<WeatherDay[]>( [] );
  const [ weatherAlerts, setWeatherAlerts ] = useState<WeatherAlertRow[]>( [] );
  const [ airForecast, setAirForecast ] = useState<AirPoint[]>( [] );
  const [ airHistory, setAirHistory ] = useState<AirPoint[]>( [] );
  const [ historyRange, setHistoryRange ] = useState<24 | 168 | 720>( 24 );
  const [ historyLoading, setHistoryLoading ] = useState( false );

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

    // loading=async deliberately decouples Maps API readiness from the script
    // element's load event. Poll the namespace instead, so a newly injected loader,
    // an already-existing loader, and client-side route transitions all converge on
    // the same readiness path.
    const waitForMaps = async () => {
      for ( let i = 0; i < 50; i++ ) {
        if ( cancelled ) return null;
        const g = w.google?.maps;
        if ( g ) return g;
        await new Promise( r => setTimeout( r, 100 ) );
      }
      return w.google?.maps || null;
    };

    const init = async () => {
      const g = await waitForMaps();
      if ( cancelled || !g ) return;
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
        disableDefaultUI: true,
        zoomControl: false,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        scaleControl: false,
        rotateControl: false,
        cameraControl: false,
        keyboardShortcuts: false,
        clickableIcons: false,
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

      // A constructed Map is not the same thing as a painted map. With an invalid or
      // refused browser key Google can still create the map object while its tiles never
      // arrive, which previously hid the fallback and exposed a blank panel. Only reveal
      // the Maps JS canvas after the first visible tile batch has loaded.
      const mapWithEvents = map as {
        addListener?: ( eventName: string, handler: () => void ) => { remove?: () => void };
      };
      if ( typeof mapWithEvents.addListener === 'function' ) {
        let painted = false;
        mapWithEvents.addListener( 'tilesloaded', () => {
          if ( painted || cancelled ) return;
          painted = true;
          requestAnimationFrame( () => {
            if ( !cancelled ) setMapReady( true );
          } );
        } );
      } else {
        // Legacy/test doubles without Maps event support: preserve the old behavior.
        requestAnimationFrame( () => {
          if ( !cancelled ) setMapReady( true );
        } );
      }
    };

    // init is async (it awaits importLibrary); wrap so no unhandled promise floats.
    const runInit = () => { void init(); };

    // Do not use the script element's 'load' event as the readiness signal.
    // With Google's loading=async mode, API readiness is intentionally decoupled
    // from that event. runInit() waits for google.maps and then importLibrary().
    if ( w.google?.maps ) { runInit(); return () => { cancelled = true; }; }

    const ID = 'gmaps-js';
    const existing = document.getElementById( ID );
    if ( existing ) {
      runInit();
      return () => { cancelled = true; };
    }

    const script = document.createElement( 'script' );
    script.id = ID;
    script.async = true;
    // Places library requested so client-side India-scoped autocomplete can run.
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent( MAPS_KEY )}&libraries=places&loading=async`;
    document.head.appendChild( script );
    // Start the same namespace-readiness path immediately; it will resolve once
    // the async loader exposes google.maps, without depending on a DOM load event.
    runInit();
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
            pollutants.push( { code: p.code as string, label, value: v as number, unit: concUnitLabel( p.concentration?.units ) } );
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
        const gust = n( d?.wind?.gust?.value );
        const rainMm = n( d?.precipitation?.qpf?.quantity );
        const rainProb = n( d?.precipitation?.probability?.percent );
        const stormProb = n( d?.thunderstormProbability );
        const uv = n( d?.uvIndex );
        const visibility = n( d?.visibility?.distance );
        const pressure = n( d?.airPressure?.meanSeaLevelMillibars );
        const dew = n( d?.dewPoint?.degrees );
        const heat = n( d?.heatIndex?.degrees );
        const wet = n( d?.wetBulbTemperature?.degrees );
        const cloud = n( d?.cloudCover );
        if ( Number.isFinite( gust ) ) out.windGust = Math.round( gust );
        if ( Number.isFinite( rainMm ) ) out.rainMm = rainMm;
        if ( Number.isFinite( rainProb ) ) out.rainProb = Math.round( rainProb );
        if ( Number.isFinite( stormProb ) ) out.stormProb = Math.round( stormProb );
        if ( Number.isFinite( uv ) ) out.uv = Math.round( uv );
        if ( Number.isFinite( visibility ) ) out.visibilityKm = visibility;
        if ( Number.isFinite( pressure ) ) out.pressureHpa = Math.round( pressure );
        if ( Number.isFinite( dew ) ) out.dewPoint = Math.round( dew );
        if ( Number.isFinite( heat ) ) out.heatIndex = Math.round( heat );
        if ( Number.isFinite( wet ) ) out.wetBulb = Math.round( wet );
        if ( Number.isFinite( cloud ) ) out.cloudCover = Math.round( cloud );
        if ( typeof d?.currentTime === 'string' ) out.currentTime = d.currentTime;
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
          `https://pollen.googleapis.com/v1/forecast:lookup?key=${encodeURIComponent( MAPS_KEY )}&location.latitude=${lat}&location.longitude=${lng}&days=5`,
          { signal: ac.signal },
        );
        if ( !res.ok ) return;
        const d = await res.json();
        const daily = Array.isArray( d?.dailyInfo ) ? d.dailyInfo : [];
        const rows: PollenRow[] = [];
        daily.forEach( ( day: any, dayIndex: number ) => {
          const date = day?.date;
          const dateObj = date?.year && date?.month && date?.day
            ? new Date( Date.UTC( date.year, date.month - 1, date.day ) )
            : null;
          const dayLabel = dayIndex === 0
            ? 'Today'
            : dateObj
              ? new Intl.DateTimeFormat( 'en-IN', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' } ).format( dateObj )
              : 'Day ' + String( dayIndex + 1 );
          const types: { code?: string; displayName?: string; indexInfo?: { value?: number } }[] = day?.pollenTypeInfo || [];
          types.forEach( t => {
            const v = t.indexInfo?.value;
            if ( t.displayName && Number.isFinite( v ) ) {
              rows.push( { label: t.displayName, index: v as number, word: pollenCategory( v as number ), day: dayLabel } );
            }
          } );
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

  /* Extended forecast/history calls are separate from current conditions so a slow
     long-range endpoint never blocks the "Now" experience. */
  useEffect( () => {
    if ( !MAPS_KEY || typeof window === 'undefined' ) return;
    const ac = new AbortController();
    const { lat, lng } = place;
    setWeatherHourly( [] );
    setWeatherDaily( [] );
    setWeatherAlerts( [] );
    setAirForecast( [] );

    const getJson = async ( url: string ) => {
      const res = await fetch( url, { signal: ac.signal } );
      if ( !res.ok ) return null;
      return res.json();
    };

    const loadHourly = async () => {
      const url = 'https://weather.googleapis.com/v1/forecast/hours:lookup?key=' + encodeURIComponent( MAPS_KEY )
        + '&location.latitude=' + lat + '&location.longitude=' + lng
        + '&hours=24&pageSize=24&unitsSystem=METRIC&languageCode=en';
      const data = await getJson( url );
      if ( !data || ac.signal.aborted ) return;
      setWeatherHourly( ( Array.isArray( data.forecastHours ) ? data.forecastHours : [] )
        .map( ( row: Record<string, any> ) => weatherHourFromApi( row ) )
        .filter( Boolean ) as WeatherHour[] );
    };

    const loadDaily = async () => {
      const url = 'https://weather.googleapis.com/v1/forecast/days:lookup?key=' + encodeURIComponent( MAPS_KEY )
        + '&location.latitude=' + lat + '&location.longitude=' + lng
        + '&days=10&unitsSystem=METRIC&languageCode=en';
      const data = await getJson( url );
      if ( !data || ac.signal.aborted ) return;
      const rows: WeatherDay[] = ( Array.isArray( data.forecastDays ) ? data.forecastDays : [] ).map( ( row: any, i: number ) => {
        const d = row?.displayDate || {};
        const date = d?.year && d?.month && d?.day ? new Date( Date.UTC( d.year, d.month - 1, d.day ) ) : new Date();
        const p = row?.daytimeForecast || row?.nighttimeForecast || {};
        const min = n( row?.minTemperature?.degrees );
        const max = n( row?.maxTemperature?.degrees );
        const rain = n( p?.precipitation?.probability?.percent );
        return {
          time: date.getTime(),
          label: i === 0 ? 'Today' : new Intl.DateTimeFormat( 'en-IN', { weekday: 'short', timeZone: 'UTC' } ).format( date ),
          dateLabel: new Intl.DateTimeFormat( 'en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' } ).format( date ),
          ...( Number.isFinite( min ) ? { min: Math.round( min ) } : {} ),
          ...( Number.isFinite( max ) ? { max: Math.round( max ) } : {} ),
          ...( Number.isFinite( rain ) ? { rainProb: Math.round( rain ) } : {} ),
          ...( typeof p?.weatherCondition?.description?.text === 'string' ? { condition: p.weatherCondition.description.text } : {} ),
          ...( typeof p?.weatherCondition?.iconBaseUri === 'string' ? { icon: p.weatherCondition.iconBaseUri } : {} ),
          ...( typeof row?.sunEvents?.sunriseTime === 'string' ? { sunrise: row.sunEvents.sunriseTime } : {} ),
          ...( typeof row?.sunEvents?.sunsetTime === 'string' ? { sunset: row.sunEvents.sunsetTime } : {} ),
        };
      } );
      setWeatherDaily( rows );
    };

    const loadAlerts = async () => {
      const url = 'https://weather.googleapis.com/v1/publicAlerts:lookup?key=' + encodeURIComponent( MAPS_KEY )
        + '&location.latitude=' + lat + '&location.longitude=' + lng + '&languageCode=en';
      const data = await getJson( url );
      if ( !data || ac.signal.aborted ) return;
      const rows: WeatherAlertRow[] = ( Array.isArray( data.weatherAlerts ) ? data.weatherAlerts : [] ).slice( 0, 3 ).map( ( a: any ) => ( {
        id: String( a?.alertId || a?.eventType || Math.random() ),
        title: String( a?.alertTitle?.text || a?.description || a?.eventType || 'Weather alert' ),
        description: typeof a?.description === 'string' ? a.description : undefined,
        area: typeof a?.areaName === 'string' ? a.areaName : undefined,
        severity: typeof a?.severity === 'string' ? a.severity.replaceAll( '_', ' ' ) : undefined,
        urgency: typeof a?.urgency === 'string' ? a.urgency.replaceAll( '_', ' ' ) : undefined,
        expires: typeof a?.expirationTime === 'string' ? a.expirationTime : undefined,
      } ) );
      setWeatherAlerts( rows );
    };

    const loadAirForecast = async () => {
      const start = new Date();
      start.setUTCMinutes( 0, 0, 0 );
      start.setUTCHours( start.getUTCHours() + 1 );
      const end = new Date( start.getTime() + 96 * 60 * 60 * 1000 );
      const res = await fetch(
        'https://airquality.googleapis.com/v1/forecast:lookup?key=' + encodeURIComponent( MAPS_KEY ),
        {
          method: 'POST',
          signal: ac.signal,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify( {
            location: { latitude: lat, longitude: lng },
            period: { startTime: start.toISOString(), endTime: end.toISOString() },
            pageSize: 96,
            universalAqi: true,
            customLocalAqis: [ { regionCode: 'IN', aqi: 'ind_cpcb' } ],
            extraComputations: [ 'LOCAL_AQI', 'POLLUTANT_CONCENTRATION', 'DOMINANT_POLLUTANT_CONCENTRATION' ],
            languageCode: 'en',
          } ),
        },
      );
      if ( !res.ok || ac.signal.aborted ) return;
      const data = await res.json();
      setAirForecast( ( Array.isArray( data.hourlyForecasts ) ? data.hourlyForecasts : [] )
        .map( ( row: Record<string, any> ) => airPointFromApi( row ) )
        .filter( Boolean ) as AirPoint[] );
    };

    void Promise.allSettled( [ loadHourly(), loadDaily(), loadAlerts(), loadAirForecast() ] );
    return () => ac.abort();
  }, [ place ] );

  useEffect( () => {
    if ( !MAPS_KEY || typeof window === 'undefined' ) return;
    const ac = new AbortController();
    const { lat, lng } = place;
    setHistoryLoading( true );
    setAirHistory( [] );

    const run = async () => {
      const points: AirPoint[] = [];
      let pageToken = '';
      let page = 0;
      do {
        const body: Record<string, unknown> = {
          location: { latitude: lat, longitude: lng },
          hours: historyRange,
          pageSize: Math.min( 100, historyRange ),
          universalAqi: true,
          customLocalAqis: [ { regionCode: 'IN', aqi: 'ind_cpcb' } ],
          extraComputations: [ 'LOCAL_AQI', 'POLLUTANT_CONCENTRATION' ],
          languageCode: 'en',
        };
        if ( pageToken ) body.pageToken = pageToken;
        const res = await fetch(
          'https://airquality.googleapis.com/v1/history:lookup?key=' + encodeURIComponent( MAPS_KEY ),
          {
            method: 'POST',
            signal: ac.signal,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify( body ),
          },
        );
        if ( !res.ok ) break;
        const data = await res.json();
        ( Array.isArray( data.hoursInfo ) ? data.hoursInfo : [] ).forEach( ( row: Record<string, any> ) => {
          const p = airPointFromApi( row );
          if ( p ) points.push( p );
        } );
        pageToken = typeof data.nextPageToken === 'string' ? data.nextPageToken : '';
        page += 1;
      } while ( pageToken && page < 8 && !ac.signal.aborted );
      if ( !ac.signal.aborted ) {
        points.sort( ( a, b ) => a.time - b.time );
        setAirHistory( points );
        setHistoryLoading( false );
      }
    };
    void run().catch( () => { if ( !ac.signal.aborted ) setHistoryLoading( false ); } );
    return () => ac.abort();
  }, [ place, historyRange ] );

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

    const w = window as unknown as {
      google?: { maps?: {
        places?: { PlacesService?: new ( el: HTMLElement ) => unknown; PlacesServiceStatus?: { OK?: string } };
        Geocoder?: new () => unknown;
      } };
    };
    const gmaps = w.google?.maps;

    // SEARCH MUST NOT DEPEND ON THE MAP. placesSvc/geocoder used to be created only
    // inside the map's init(); if the map failed to build, search silently did
    // nothing (no request fired). Create our own service lazily from the loaded
    // Maps library so search works whenever google.maps.places is available,
    // regardless of the map. A detached div is a valid PlacesService attribution node.
    if ( !placesSvc.current && gmaps?.places?.PlacesService ) {
      try { placesSvc.current = new gmaps.places.PlacesService( document.createElement( 'div' ) ); } catch { /* fall through to geocoder */ }
    }
    if ( !geocoder.current && gmaps?.Geocoder ) {
      try { geocoder.current = new gmaps.Geocoder(); } catch { /* no geocoder */ }
    }

    const svc = placesSvc.current as {
      textSearch?: ( req: Record<string, unknown>, cb: ( r: unknown[] | null, status: string ) => void ) => void;
    } | null;
    const OK = gmaps?.places?.PlacesServiceStatus?.OK || 'OK';

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
  const bestOutside = bestOutsideWindow( weatherHourly, airForecast );
  const combinedHours = weatherHourly.slice( 0, 24 ).map( ( w, i ) => ( {
    ...w,
    air: airForecast.find( a => Math.abs( a.time - w.time ) < 45 * 60 * 1000 ) || airForecast[ i ],
  } ) );
  const forecastBest = airForecast.length ? airForecast.reduce( ( a, b ) => b.aqi < a.aqi ? b : a ) : null;
  const forecastWorst = airForecast.length ? airForecast.reduce( ( a, b ) => b.aqi > a.aqi ? b : a ) : null;
  const forecastDelta = airForecast.length > 1 ? airForecast[ airForecast.length - 1 ].aqi - airForecast[ 0 ].aqi : 0;
  const forecastTrend = Math.abs( forecastDelta ) < 6 ? 'Stable' : forecastDelta < 0 ? 'Improving' : 'Worsening';

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
                  <div className="vl-live-fact" key="cond-pm25"><p className="vl-live-label">PM2.5</p><span className="vl-live-metric-md">{ Math.round( p.value ) } { p.unit }</span></div>
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

          { bestOutside && (
            <div className="vl-live-block">
              <p className="vl-live-eyebrow">Best outside</p>
              <div className="vl-live-best-outside">
                <div>
                  <span className="vl-live-metric-lg">{ bestOutside.label }</span>
                  <p className="vl-live-body">{ bestOutside.note }</p>
                </div>
                <p className="vl-live-small">Calculated from the upcoming Google Weather and Air Quality forecasts.</p>
              </div>
            </div>
          ) }

          { combinedHours.length > 0 && (
            <div className="vl-live-block">
              <h3 className="vl-live-h2">Next 24 hours</h3>
              <div className="vl-live-hour-rail" aria-label="Next 24 hours">
                { combinedHours.map( ( h, i ) => (
                  <article className="vl-live-hour-card" key={ h.time }>
                    <time>{ hourLabel( h.time ) }</time>
                    { h.icon && <img src={ h.icon + '.svg' } alt="" loading="lazy" /> }
                    <strong>{ Number.isFinite( h.temp ) ? h.temp + '°' : '—' }</strong>
                    <span>{ Number.isFinite( h.rainProb ) ? h.rainProb + '% rain' : 'No rain data' }</span>
                    <span>{ h.air ? 'AQI ' + h.air.aqi : 'AQI —' }</span>
                    { i === 0 && <em>Next</em> }
                  </article>
                ) ) }
              </div>
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
                    <span className="vl-live-metric-md">{ Math.round( p.value ) } { p.unit }</span>
                    <span className="vl-live-prow-cat">{ cat.word }</span>
                  </div>
                );
              } ) }
            </div>
          ) }

          { ( airForecast.length > 0 || airHistory.length > 0 ) && (
            <section className="vl-live-section" aria-labelledby="vl-live-air-intelligence">
              <h3 className="vl-live-h2" id="vl-live-air-intelligence">Air intelligence</h3>
              <div className="vl-live-insight-grid">
                <div><p className="vl-live-label">Best hour</p><strong>{ forecastBest ? hourLabel( forecastBest.time ) + ' · AQI ' + forecastBest.aqi : '—' }</strong></div>
                <div><p className="vl-live-label">Peak hour</p><strong>{ forecastWorst ? hourLabel( forecastWorst.time ) + ' · AQI ' + forecastWorst.aqi : '—' }</strong></div>
                <div><p className="vl-live-label">Trend</p><strong>{ forecastTrend }</strong></div>
              </div>

              { airForecast.length > 0 && (
                <>
                  <h4 className="vl-live-minor-title">96-hour AQ forecast</h4>
                  <div className="vl-live-hour-rail" aria-label="Air quality forecast">
                    { airForecast.filter( ( _, i ) => i % 3 === 0 ).map( p => (
                      <article className="vl-live-hour-card vl-live-hour-card-air" key={ p.time }>
                        <time>{ hourLabel( p.time ) }</time>
                        <strong>AQI { p.aqi }</strong>
                        <span>{ p.word }</span>
                        { Number.isFinite( p.pm25 ) && <span>PM2.5 { Math.round( p.pm25! ) }</span> }
                      </article>
                    ) ) }
                  </div>
                </>
              ) }

              <div className="vl-live-history-head">
                <h4 className="vl-live-minor-title">AQ history</h4>
                <div className="vl-live-history-controls" role="group" aria-label="Air quality history range">
                  { ( [ [ 24, '24h' ], [ 168, '7d' ], [ 720, '30d' ] ] as const ).map( ( [ hours, label ] ) => (
                    <button type="button" key={ hours } aria-pressed={ historyRange === hours } onClick={ () => setHistoryRange( hours ) }>{ label }</button>
                  ) ) }
                </div>
              </div>
              { historyLoading ? (
                <p className="vl-live-small">Loading history…</p>
              ) : airHistory.length > 0 ? (
                <div className="vl-live-history" aria-label={ 'AQI history for ' + historyRange + ' hours' }>
                  { airHistory.filter( ( _, i ) => {
                    const step = Math.max( 1, Math.ceil( airHistory.length / 72 ) );
                    return i % step === 0 || i === airHistory.length - 1;
                  } ).map( p => (
                    <i key={ p.time } style={ { height: Math.max( 8, Math.min( 100, p.aqi / 5 ) ) + '%' } } title={ hourLabel( p.time ) + ' · AQI ' + p.aqi } />
                  ) ) }
                </div>
              ) : (
                <p className="vl-live-small">History is not available for this location right now.</p>
              ) }
            </section>
          ) }

          { weather && (
            <section className="vl-live-section" aria-labelledby="vl-live-weather-detail">
              <h3 className="vl-live-h2" id="vl-live-weather-detail">Weather detail</h3>
              <div className="vl-live-weather-grid">
                { [
                  [ 'Feels', Number.isFinite( weather.feelsLike ) ? weather.feelsLike + '°' : null ],
                  [ 'Humidity', Number.isFinite( weather.humidity ) ? weather.humidity + '%' : null ],
                  [ 'Wind', Number.isFinite( weather.windSpeed ) ? weather.windSpeed + ' ' + ( weather.windUnit || 'km/h' ) : null ],
                  [ 'Wind direction', weather.windDir || null ],
                  [ 'Gust', Number.isFinite( weather.windGust ) ? weather.windGust + ' km/h' : null ],
                  [ 'Rainfall', Number.isFinite( weather.rainMm ) ? weather.rainMm + ' mm' : null ],
                  [ 'Rain chance', Number.isFinite( weather.rainProb ) ? weather.rainProb + '%' : null ],
                  [ 'Storm chance', Number.isFinite( weather.stormProb ) ? weather.stormProb + '%' : null ],
                  [ 'UV index', Number.isFinite( weather.uv ) ? String( weather.uv ) : null ],
                  [ 'Visibility', Number.isFinite( weather.visibilityKm ) ? weather.visibilityKm + ' km' : null ],
                  [ 'Pressure', Number.isFinite( weather.pressureHpa ) ? weather.pressureHpa + ' hPa' : null ],
                  [ 'Dew point', Number.isFinite( weather.dewPoint ) ? weather.dewPoint + '°' : null ],
                  [ 'Heat index', Number.isFinite( weather.heatIndex ) ? weather.heatIndex + '°' : null ],
                  [ 'Wet bulb', Number.isFinite( weather.wetBulb ) ? weather.wetBulb + '°' : null ],
                  [ 'Cloud cover', Number.isFinite( weather.cloudCover ) ? weather.cloudCover + '%' : null ],
                ].filter( row => row[ 1 ] !== null ).map( row => (
                  <div key={ String( row[ 0 ] ) }><p className="vl-live-label">{ row[ 0 ] }</p><strong>{ row[ 1 ] }</strong></div>
                ) ) }
              </div>

              { weatherDaily.length > 0 && (
                <>
                  <div className="vl-live-sunline">
                    <div><p className="vl-live-label">Sunrise</p><strong>{ weatherDaily[ 0 ].sunrise ? new Intl.DateTimeFormat( 'en-IN', { timeZone: 'Asia/Kolkata', hour: 'numeric', minute: '2-digit' } ).format( new Date( weatherDaily[ 0 ].sunrise! ) ) : '—' }</strong></div>
                    <div><p className="vl-live-label">Sunset</p><strong>{ weatherDaily[ 0 ].sunset ? new Intl.DateTimeFormat( 'en-IN', { timeZone: 'Asia/Kolkata', hour: 'numeric', minute: '2-digit' } ).format( new Date( weatherDaily[ 0 ].sunset! ) ) : '—' }</strong></div>
                  </div>
                  <h4 className="vl-live-minor-title">10-day outlook</h4>
                  <div className="vl-live-day-rail" aria-label="10-day weather outlook">
                    { weatherDaily.map( d => (
                      <article className="vl-live-day-card" key={ d.time }>
                        <strong>{ d.label }</strong>
                        <span>{ d.dateLabel }</span>
                        { d.icon && <img src={ d.icon + '.svg' } alt="" loading="lazy" /> }
                        <b>{ Number.isFinite( d.max ) ? d.max + '°' : '—' } / { Number.isFinite( d.min ) ? d.min + '°' : '—' }</b>
                        <span>{ Number.isFinite( d.rainProb ) ? d.rainProb + '% rain' : d.condition || 'Forecast' }</span>
                      </article>
                    ) ) }
                  </div>
                </>
              ) }

              { weatherAlerts.length > 0 && (
                <div className="vl-live-alerts">
                  <h4 className="vl-live-minor-title">Weather alerts</h4>
                  { weatherAlerts.map( alert => (
                    <article className="vl-live-alert" key={ alert.id }>
                      <strong>{ alert.title }</strong>
                      { alert.description && <p>{ alert.description }</p> }
                      <span>{ [ alert.area, alert.severity, alert.urgency, alert.expires ? 'Until ' + new Intl.DateTimeFormat( 'en-IN', { timeZone: 'Asia/Kolkata', hour: 'numeric', minute: '2-digit' } ).format( new Date( alert.expires ) ) : '' ].filter( Boolean ).join( ' · ' ) }</span>
                    </article>
                  ) ) }
                </div>
              ) }
            </section>
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
              <p className="vl-live-small vl-live-mb16">Up to five days of pollen conditions, when Google Pollen has coverage for the selected place.</p>
              <div className="vl-live-pollen-grid">
                { pollen.map( ( row, i ) => (
                  <article className="vl-live-pollen-card" key={ row.day + '-' + row.label + '-' + i }>
                    <p className="vl-live-label">{ row.day }</p>
                    <strong>{ row.label }</strong>
                    <span>Index { row.index } · { row.word }</span>
                  </article>
                ) ) }
              </div>
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

        {/* ===== RIGHT COLUMN: resilient map =====
            The keyed Maps JS canvas is the enhanced path. A keyless Google Maps embed
            sits underneath it until mapReady becomes true, so a rejected/delayed
            browser key can never leave visitors staring at a blank grey panel. */}
        <div className="vl-live-right">
          <div className="vl-live-map-sticky">
            <div className="vl-live-map-stage">
              { !mapReady && (
                <div
                  className="vl-live-map-fallback"
                  role="status"
                  aria-label={ `Loading map of ${place.name}` }
                >
                  <span className="vl-live-map-fallback-pin" aria-hidden="true" />
                  <div className="vl-live-map-fallback-copy">
                    <p className="vl-live-map-fallback-place">{ place.name }</p>
                    <p className="vl-live-map-fallback-status">Loading live map…</p>
                  </div>
                </div>
              ) }
              { liveActive && (
                <div
                  className={ `vl-live-map-canvas ${mapReady ? 'is-ready' : ''}`.trim() }
                  ref={ mapHost }
                  role="img"
                  aria-label={ `Map of ${place.name}` }
                />
              ) }

              {/* Heatmap controls only make sense once the Maps JS canvas exists.
                  On the fallback map they stay hidden rather than implying a layer
                  can be toggled when there is no ImageMapType to receive it. */}
              { mapReady && (
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
              ) }

              { mapReady && (
                <div className="vl-live-map-legend">
                  <p className="vl-live-label">AQI heatmap</p>
                  <div className="vl-live-scale" aria-hidden="true" />
                  <div className="vl-live-scale-ends"><span>Good</span><span>Severe</span></div>
                  <p className="vl-live-scale-mid">Good · Satisfactory · Moderate · Poor · Very Poor · Severe</p>
                </div>
              ) }

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
                        <div key="prev-pm25"><p className="vl-live-label">PM2.5</p><span className="vl-live-metric-md">{ Math.round( p.value ) }</span><p className="vl-live-preview-cat">{ p.unit }</p></div>
                      ) ) }
                    </div>
                  </div>
                ) }
            </div>
          </div>
        </div>
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

        /* Type ladder MEASURED from the live home page (wecare.digital): Inter,
           text #1a1a1a; h2 40px/700/-1.2px; eyebrow 12px/700/0.72px-tracking
           uppercase in dark green #1a3a2a (NOT the light --green, which read as
           loose/washed-out against the home language); body a tighter 17px. */
        .vl-live-h2{margin:0 0 14px;font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.1;letter-spacing:-1.2px;color:#1a1a1a}
        .vl-live-card-h{margin:0 0 6px;font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;color:#1a1a1a}
        .vl-live-body{margin:0;max-width:62ch;font-size:17px;font-weight:400;line-height:1.55;letter-spacing:-.1px;color:rgba(0,0,0,.72)}
        .vl-live-eyebrow{margin:0 0 12px;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#1a3a2a}
        .vl-live-label{margin:0 0 7px;font-size:12px;font-weight:600;letter-spacing:.01em;color:rgba(0,0,0,.54)}
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
        .vl-live-map-stage{position:relative;height:340px;overflow:hidden;border:1px solid var(--hair);border-radius:18px;background:var(--ground);box-shadow:0 8px 28px rgba(26,58,42,.08)}
        .vl-live-map-fallback{
          position:absolute;inset:0;z-index:0;display:flex;align-items:center;justify-content:center;gap:14px;
          width:100%;height:100%;padding:24px;border:0;border-radius:inherit;overflow:hidden;
          background-color:#eef3ef;
          background-image:
            linear-gradient(rgba(26,58,42,.055) 1px,transparent 1px),
            linear-gradient(90deg,rgba(26,58,42,.055) 1px,transparent 1px),
            radial-gradient(circle at 22% 24%,rgba(209,244,112,.55),transparent 24%),
            radial-gradient(circle at 78% 72%,rgba(26,58,42,.08),transparent 28%);
          background-size:36px 36px,36px 36px,100% 100%,100% 100%;
        }
        .vl-live-map-fallback-pin{width:18px;height:18px;flex:0 0 18px;border:5px solid var(--green);border-radius:50% 50% 50% 0;background:var(--lime);transform:rotate(-45deg);box-shadow:0 4px 12px rgba(26,58,42,.18)}
        .vl-live-map-fallback-copy{position:relative;z-index:1}
        .vl-live-map-fallback-place{margin:0;font-size:16px;font-weight:700;line-height:1.25;color:var(--green)}
        .vl-live-map-fallback-status{margin:3px 0 0;font-size:13px;line-height:1.35;color:var(--ink-muted)}
        .vl-live-map-canvas{position:absolute;inset:0;z-index:2;opacity:0;pointer-events:none;border-radius:inherit;overflow:hidden;background:transparent}
        .vl-live-map-canvas.is-ready{opacity:1;pointer-events:auto}

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
        /* One control, matching the shipped BlogSearch field: a single bordered box
           (2px rgba(26,58,42,.22), 12px radius, 52px) that darkens its border and
           shows a lime ring on focus. The field owns the ONLY border and the ONLY
           focus ring; the input inside is fully neutralised below. */
        .vl-live-search-field{display:flex;align-items:center;gap:10px;min-height:52px;padding:0 16px;border:2px solid rgba(26,58,42,.22);border-radius:12px;background:#fff}
        .vl-live-search-field:focus-within{border-color:#1a3a2a;box-shadow:0 0 0 3px rgba(209,244,112,.45)}
        /* The input is neutralised against the site's GLOBAL input:focus rules
           (inner-pages.css / Dashboard.css), which were drawing a second rounded
           box (lime box-shadow + 8px radius + padding) INSIDE this field - the
           "inner border" the owner reported. Zero every box-defining property with
           !important so no global rule can reintroduce an inner box. */
        .vl-live-search-input{flex:1 1 auto;min-width:0;height:auto;font:inherit;font-size:17px;color:#1a1a1a;background:transparent !important;border:0 !important;outline:0 !important;box-shadow:none !important;border-radius:0 !important;padding:0 !important}
        .vl-live-search-input:focus,.vl-live-search-input:focus-visible{box-shadow:none !important;border:0 !important;outline:0 !important}
        .vl-live-search-input::placeholder{color:rgba(0,0,0,.44)}
        .vl-live-search-results{position:absolute;top:calc(100% + 6px);inset-inline:0;z-index:5;margin:0;padding:0;list-style:none;overflow:hidden;border:1px solid var(--hair);border-radius:var(--r-field);background:var(--paper)}
        .vl-live-search-option{display:block;min-height:52px;padding:10px 14px;cursor:pointer}
        .vl-live-search-option + .vl-live-search-option{border-top:1px solid var(--hair)}
        .vl-live-search-option[aria-selected="true"]{background:var(--lime)}
        .vl-live-search-option-name{display:block;font-size:16px;font-weight:600;line-height:1.3;color:var(--ink-strong)}
        .vl-live-search-option-addr{display:block;margin-top:2px;font-size:13px;line-height:1.4;color:var(--ink-muted)}

        /* NOW figures - tightened to the home scale. The place name is a clean
           20px/700, the address a muted 15px (was an oversized 20px that made the
           header feel loose), figures stay large (the home h1 rung) and body/cond
           text drops to the home 17px with the home muted tone. */
        .vl-live-place{margin:0 0 4px;font-size:20px;font-weight:700;line-height:1.25;letter-spacing:-.4px;color:#1a1a1a}
        .vl-live-place-addr{margin:0 0 28px;max-width:62ch;font-size:15px;font-weight:400;line-height:1.5;letter-spacing:0;color:rgba(0,0,0,.54)}
        .vl-live-now{padding-top:28px;border-top:1px solid var(--hair)}
        .vl-live-figure{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:8px 0 0}
        .vl-live-metric-xl{font-size:clamp(40px,4.3vw,56px);font-weight:600;line-height:1.04;letter-spacing:-0.04em;color:#1a1a1a}
        .vl-live-metric-lg{font-size:clamp(32px,3.2vw,40px);font-weight:600;line-height:1.08;letter-spacing:-1.6px;color:#1a1a1a}
        .vl-live-metric-md{display:block;font-size:20px;font-weight:700;line-height:1.25;letter-spacing:-.4px;color:#1a1a1a}
        .vl-live-cond{margin:14px 0 0;max-width:46ch;font-size:17px;font-weight:400;line-height:1.55;letter-spacing:-.1px;color:rgba(0,0,0,.72)}
        .vl-live-sub-fact{margin:8px 0 0;font-size:14px;line-height:1.5;color:rgba(0,0,0,.54)}

        /* AQI mark - severity encoded by FORM as well as tone. */
        .vl-live-dot{display:inline-block;width:16px;height:16px;border-radius:50%;flex:0 0 auto}
        .vl-live-dot-good{background:var(--aqi-good);border:2px solid var(--green)}
        .vl-live-dot-sat{background:var(--aqi-sat);border:2px solid var(--green)}
        .vl-live-dot-mod{background:var(--aqi-mod);border:2px solid var(--green)}
        .vl-live-dot-poor{background:var(--paper);border:5px solid var(--aqi-poor);box-shadow:0 0 0 1px var(--green)}
        .vl-live-dot-worst{background:var(--aqi-worst);border:3px solid var(--paper);box-shadow:0 0 0 2px var(--aqi-worst),0 0 0 3px var(--green)}

        .vl-live-cat{display:inline-flex;align-items:center;padding:5px 14px;border:1.5px solid #1a3a2a;border-radius:var(--r-pill);background:var(--paper);font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#1a3a2a;white-space:nowrap}

        /* Map overlays - inset from the bottom corners (Maps Platform ToS). No rule
           anywhere targets .gm-style-cc, a[href*="google"] or img[alt="Google"]. */
        .vl-live-map-controls{position:absolute;top:16px;left:16px;z-index:4;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
        .vl-live-layer{min-height:44px;padding:0 18px;border:2px solid var(--hair);border-radius:var(--r-pill);background:var(--paper);color:var(--green);font:inherit;font-size:14px;font-weight:600;letter-spacing:-.125px;cursor:pointer;transition:background-color .2s,border-color .2s,transform .2s,box-shadow .2s}
        .vl-live-layer:hover{border-color:var(--lime);background:var(--lime-tint);transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
        .vl-live-layer:focus-visible{outline:3px solid var(--green);outline-offset:3px}
        .vl-live-layer[aria-pressed="true"]{border-color:var(--green);background:var(--lime)}

        .vl-live-map-legend{position:absolute;top:16px;right:16px;z-index:4;width:224px;padding:16px;border:1px solid var(--hair);border-radius:14px;background:var(--paper);box-shadow:0 6px 20px rgba(26,58,42,.12)}
        .vl-live-scale{height:10px;border-radius:var(--r-pill);background:linear-gradient(90deg,var(--aqi-good) 0%,var(--aqi-sat) 22%,var(--aqi-mod) 48%,var(--aqi-poor) 74%,var(--aqi-worst) 100%)}
        .vl-live-scale-ends{display:flex;justify-content:space-between;margin-top:8px;gap:8px}
        .vl-live-scale-ends span{font-size:12px;font-weight:700;color:var(--green)}
        .vl-live-scale-mid{margin:8px 0 0;font-size:12px;line-height:1.4;color:var(--ink-muted)}

        /* bottom:16px (was 76px): the 60px clearance existed to keep off Google's
           bottom-corner attribution, which is hidden for this test. Rounded + soft
           shadow for a cleaner card. RESTORE bottom:76px when attribution returns. */
        .vl-live-map-preview{position:absolute;left:16px;bottom:16px;z-index:4;width:296px;padding:18px;border:1px solid var(--hair);border-radius:16px;background:var(--paper);box-shadow:0 6px 20px rgba(26,58,42,.12)}
        .vl-live-preview-metrics{display:grid;grid-template-columns:repeat(3,1fr);margin-top:14px;border-top:1px solid var(--hair)}
        .vl-live-preview-metrics>div{padding:12px 0 0}
        .vl-live-preview-metrics>div+div{padding-left:14px;border-left:1px solid var(--hair)}
        .vl-live-preview-metrics .vl-live-label{margin-bottom:4px}
        .vl-live-preview-metrics .vl-live-metric-md{font-size:17px}
        .vl-live-preview-cat{margin:4px 0 0;font-size:12px;font-weight:700;letter-spacing:.01em;color:var(--ink-muted)}

        .vl-live-best-outside{display:grid;gap:10px;padding:24px;border-radius:18px;background:var(--green);color:#fff}
        .vl-live-best-outside .vl-live-metric-lg,.vl-live-best-outside .vl-live-body{color:#fff}
        .vl-live-best-outside .vl-live-small{color:rgba(255,255,255,.76)}
        .vl-live-hour-rail,.vl-live-day-rail{display:flex;gap:10px;overflow-x:auto;scroll-snap-type:x proximity;padding:2px 0 8px;scrollbar-width:thin}
        .vl-live-hour-card{position:relative;flex:0 0 112px;min-height:144px;padding:14px;border:1px solid var(--hair);border-radius:14px;background:#fff;scroll-snap-align:start}
        .vl-live-hour-card time,.vl-live-hour-card span{display:block;font-size:12px;line-height:1.35;color:var(--ink-muted)}
        .vl-live-hour-card strong{display:block;margin:9px 0;font-size:19px;color:var(--green)}
        .vl-live-hour-card img{display:block;width:30px;height:30px;margin-top:8px}
        .vl-live-hour-card em{position:absolute;top:8px;right:8px;font-size:9px;font-style:normal;font-weight:700;color:var(--green)}
        .vl-live-hour-card-air{flex-basis:128px}
        .vl-live-insight-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:1px solid var(--hair);border-bottom:1px solid var(--hair)}
        .vl-live-insight-grid>div{padding:18px 16px}
        .vl-live-insight-grid>div+div{border-left:1px solid var(--hair)}
        .vl-live-insight-grid strong{font-size:15px;color:var(--green)}
        .vl-live-minor-title{margin:28px 0 12px;font-size:16px;font-weight:700;color:#1a1a1a}
        .vl-live-history-head{display:flex;align-items:end;justify-content:space-between;gap:16px;margin-top:24px}
        .vl-live-history-head .vl-live-minor-title{margin:0}
        .vl-live-history-controls{display:flex;gap:6px}
        .vl-live-history-controls button{min-height:34px;padding:0 11px;border:1px solid var(--hair);border-radius:999px;background:#fff;color:var(--green);font:inherit;font-size:12px;font-weight:700;cursor:pointer}
        .vl-live-history-controls button[aria-pressed="true"]{border-color:var(--green);background:var(--lime)}
        .vl-live-history{height:132px;display:flex;align-items:flex-end;gap:2px;margin-top:14px;padding:10px 0 2px;border-bottom:1px solid var(--hair)}
        .vl-live-history i{flex:1 1 0;min-width:2px;max-width:10px;border-radius:4px 4px 0 0;background:linear-gradient(180deg,var(--lime),var(--green))}
        .vl-live-weather-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));border-top:1px solid var(--hair)}
        .vl-live-weather-grid>div{padding:16px 14px 16px 0;border-bottom:1px solid var(--hair)}
        .vl-live-weather-grid>div:nth-child(even){padding-left:14px;border-left:1px solid var(--hair)}
        .vl-live-weather-grid strong{font-size:15px;color:#1a1a1a}
        .vl-live-sunline{display:grid;grid-template-columns:1fr 1fr;margin-top:18px;border:1px solid var(--hair);border-radius:14px;overflow:hidden}
        .vl-live-sunline>div{padding:16px}
        .vl-live-sunline>div+div{border-left:1px solid var(--hair)}
        .vl-live-day-card{flex:0 0 112px;min-height:150px;padding:14px;border:1px solid var(--hair);border-radius:14px;background:#fff;scroll-snap-align:start;text-align:center}
        .vl-live-day-card>span,.vl-live-day-card>b{display:block;margin-top:5px;font-size:12px;color:var(--ink-muted)}
        .vl-live-day-card>b{font-size:14px;color:#1a1a1a}
        .vl-live-day-card img{width:34px;height:34px;margin:8px auto 2px}
        .vl-live-alerts{margin-top:24px}
        .vl-live-alert{padding:16px;border-radius:14px;background:var(--tint-warn)}
        .vl-live-alert+.vl-live-alert{margin-top:8px}
        .vl-live-alert strong{display:block;color:#6e4a18}
        .vl-live-alert p{margin:6px 0 0;font-size:13px;line-height:1.45;color:#5f4a2b}
        .vl-live-alert span{display:block;margin-top:6px;font-size:11px;color:#7f6845}
        .vl-live-pollen-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
        .vl-live-pollen-card{padding:14px;border:1px solid var(--hair);border-radius:14px;background:#fff}
        .vl-live-pollen-card strong{display:block;font-size:15px;color:#1a1a1a}
        .vl-live-pollen-card span{display:block;margin-top:5px;font-size:12px;color:var(--ink-muted)}

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
          .vl-live-map-preview{left:12px;bottom:12px;width:216px;padding:14px}
        }
        @media(max-width:767px){
          .vl-live-wrap{padding-inline:16px}
          .vl-live-insight-grid{grid-template-columns:1fr}
          .vl-live-insight-grid>div+div{border-left:0;border-top:1px solid var(--hair)}
          .vl-live-weather-grid{grid-template-columns:1fr}
          .vl-live-weather-grid>div:nth-child(even){padding-left:0;border-left:0}
          .vl-live-pollen-grid{grid-template-columns:1fr}
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
