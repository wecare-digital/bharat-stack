import { webMethod, Permissions } from '@wix/web-methods';
import { secrets } from '@wix/secrets';
import { auth } from '@wix/essentials';
import { fetch } from 'wix-fetch';

const GOOGLE_SECRET_NAME = 'GOOGLE_SERVER_API_KEY';
const getSecretValue = auth.elevate(secrets.getSecretValue);
const ALLOWED_SERVICES = new Set(['weather', 'forecast', 'air', 'solar']);

function cleanCoordinates(payload = {}) {
  const lat = Number(payload.lat);
  const lng = Number(payload.lng);
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) throw new Error('Invalid latitude');
  if (!Number.isFinite(lng) || lng < -180 || lng > 180) throw new Error('Invalid longitude');
  return { lat, lng };
}

async function getGoogleKey() {
  const response = await getSecretValue(GOOGLE_SECRET_NAME);
  const key = String(response?.value || '').trim();
  if (!key) throw new Error('Google server API key is not configured');
  return key;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.headers || {})
    }
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`Google service request failed (${response.status})`);
  return data;
}

async function weather(key, lat, lng) {
  const url = new URL('https://weather.googleapis.com/v1/currentConditions:lookup');
  url.searchParams.set('key', key);
  url.searchParams.set('location.latitude', String(lat));
  url.searchParams.set('location.longitude', String(lng));
  url.searchParams.set('unitsSystem', 'METRIC');
  return requestJson(url.toString());
}

async function forecast(key, lat, lng, payload = {}) {
  const days = Math.max(1, Math.min(10, Number(payload.days) || 10));
  const minimal = Boolean(payload.minimal);
  const allDays = [];
  let pageToken = '';
  let timeZone = null;

  for (let page = 0; page < 2 && allDays.length < days; page += 1) {
    const url = new URL('https://weather.googleapis.com/v1/forecast/days:lookup');
    url.searchParams.set('key', key);
    url.searchParams.set('location.latitude', String(lat));
    url.searchParams.set('location.longitude', String(lng));
    url.searchParams.set('days', String(days));
    url.searchParams.set('pageSize', String(days));
    if (!minimal) {
      url.searchParams.set('unitsSystem', 'METRIC');
      url.searchParams.set('languageCode', 'en');
    }
    if (pageToken) url.searchParams.set('pageToken', pageToken);

    const data = await requestJson(url.toString());
    if (Array.isArray(data?.forecastDays)) allDays.push(...data.forecastDays);
    timeZone = timeZone || data?.timeZone || null;
    pageToken = String(data?.nextPageToken || '');
    if (!pageToken) break;
  }

  if (!allDays.length) throw new Error('Forecast response contained no days');
  return { forecastDays: allDays.slice(0, days), timeZone };
}

async function airQuality(key, lat, lng) {
  const url = new URL('https://airquality.googleapis.com/v1/currentConditions:lookup');
  url.searchParams.set('key', key);
  return requestJson(url.toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      location: { latitude: lat, longitude: lng },
      universalAqi: true,
      extraComputations: [
        'LOCAL_AQI',
        'HEALTH_RECOMMENDATIONS',
        'DOMINANT_POLLUTANT_CONCENTRATION',
        'POLLUTANT_CONCENTRATION'
      ],
      languageCode: 'en'
    })
  });
}

async function solar(key, lat, lng) {
  const url = new URL('https://solar.googleapis.com/v1/buildingInsights:findClosest');
  url.searchParams.set('key', key);
  url.searchParams.set('location.latitude', String(lat));
  url.searchParams.set('location.longitude', String(lng));
  url.searchParams.set('requiredQuality', 'BASE');
  return requestJson(url.toString());
}

export const googleEnvironment = webMethod(
  Permissions.Anyone,
  async (service, payload = {}) => {
    if (!ALLOWED_SERVICES.has(service)) throw new Error('Unsupported Google service');
    const { lat, lng } = cleanCoordinates(payload);
    const key = await getGoogleKey();

    switch (service) {
      case 'weather':
        return weather(key, lat, lng);
      case 'forecast':
        return forecast(key, lat, lng, payload);
      case 'air':
        return airQuality(key, lat, lng);
      case 'solar':
        return solar(key, lat, lng);
      default:
        throw new Error('Unsupported Google service');
    }
  }
);
