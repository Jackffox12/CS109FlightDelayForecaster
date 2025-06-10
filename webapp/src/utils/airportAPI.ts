// Airport coordinate API service for dynamic lookups

import { AIRPORT_COORDINATES } from './airportCoords';

interface AirportData {
  lat: number;
  lng: number;
}

// Cache to avoid repeated API calls
const airportCache = new Map<string, AirportData | null>();

// Local airport database (if available)
let localAirports: Record<string, any> | null = null;

/**
 * Load local airport database if available
 */
async function loadLocalAirports(): Promise<Record<string, any> | null> {
  if (localAirports) return localAirports;
  
  try {
    // Try to load the comprehensive local database
    const response = await fetch('/src/data/airports.json');
    if (response.ok) {
      localAirports = await response.json();
      console.log(`✅ Loaded ${Object.keys(localAirports || {}).length} airports from local database`);
      return localAirports;
    }
  } catch (error) {
    console.warn('Local airport database not available:', error);
  }
  
  return null;
}

/**
 * Get airport data from local database
 */
async function getFromLocalDatabase(airportCode: string): Promise<AirportData | null> {
  const airports = await loadLocalAirports();
  
  if (airports && airports[airportCode.toUpperCase()]) {
    const airport = airports[airportCode.toUpperCase()];
    return {
      lat: airport.lat,
      lng: airport.lng
    };
  }
  
  return null;
}

/**
 * Fetch airport coordinates from external API sources (fallback only)
 */
async function fetchAirportFromAPI(airportCode: string): Promise<AirportData | null> {
  // Check cache first
  if (airportCache.has(airportCode)) {
    return airportCache.get(airportCode) || null;
  }

  try {
    // Option 1: Try OpenFlights data (most reliable, GitHub-hosted)
    const response = await fetch('https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat');
    
    if (response.ok) {
      const csvText = await response.text();
      const lines = csvText.split('\n');
      
      for (const line of lines) {
        const fields = line.split(',');
        if (fields.length >= 8) {
          // CSV format: ID,Name,City,Country,IATA,ICAO,Latitude,Longitude,...
          const iata = fields[4]?.replace(/"/g, '');
          if (iata === airportCode) {
            const lat = parseFloat(fields[6]);
            const lng = parseFloat(fields[7]);
            if (!isNaN(lat) && !isNaN(lng)) {
              const result = { lat, lng };
              airportCache.set(airportCode, result);
              return result;
            }
          }
        }
      }
    }
  } catch (error) {
    console.warn(`Failed to fetch airport data for ${airportCode} from OpenFlights:`, error);
  }

  try {
    // Option 2: Try AviationStack airport API (requires API key)
    const apiKey = import.meta.env.VITE_AVIATIONSTACK_KEY;
    if (apiKey) {
      const response = await fetch(
        `https://api.aviationstack.com/v1/airports?access_key=${apiKey}&iata_code=${airportCode}`
      );
      
      if (response.ok) {
        const data = await response.json();
        if (data.data && data.data[0] && data.data[0].latitude && data.data[0].longitude) {
          const airport = data.data[0];
          const result = {
            lat: parseFloat(airport.latitude),
            lng: parseFloat(airport.longitude)
          };
          airportCache.set(airportCode, result);
          return result;
        }
      }
    }
  } catch (error) {
    console.warn(`Failed to fetch airport data for ${airportCode} from AviationStack:`, error);
  }

  try {
    // Option 3: Try Airport-Info.live API (free, reliable)
    const response = await fetch(`https://api.airport-info.live/airport/${airportCode}`);
    
    if (response.ok) {
      const data = await response.json();
      if (data.location && data.location.lat && data.location.lng) {
        const result = {
          lat: parseFloat(data.location.lat),
          lng: parseFloat(data.location.lng)
        };
        airportCache.set(airportCode, result);
        return result;
      }
    }
  } catch (error) {
    console.warn(`Failed to fetch airport data for ${airportCode} from Airport-Info.live:`, error);
  }

  // Cache null result to avoid repeated failed attempts
  airportCache.set(airportCode, null);
  return null;
}

/**
 * Get airport coordinates with intelligent fallback
 * 1. Check local comprehensive database first (6,000+ airports)
 * 2. Check static lookup (fallback coordinates)
 * 3. Try external APIs only if needed
 * 4. Cache results for future use
 */
export async function getAirportCoordinates(airportCode: string): Promise<AirportData | null> {
  const code = airportCode.toUpperCase();
  
  // 1. Try comprehensive local database first (best option)
  const localResult = await getFromLocalDatabase(code);
  if (localResult) {
    return localResult;
  }
  
  // 2. Try static lookup for immediate availability
  const { AIRPORT_LOOKUP } = await import('./airportCoords');
  const staticResult = AIRPORT_LOOKUP[code];
  if (staticResult) {
    return staticResult;
  }
  
  // 3. Try fallback coordinates
  const coords = AIRPORT_COORDINATES[code];
  if (coords) {
    return {
      lat: coords[0],
      lng: coords[1]
    };
  }
  
  // 4. Only try external APIs as absolute last resort
  console.log(`Airport ${code} not in local databases, trying external APIs...`);
  
  try {
    return await fetchAirportFromAPI(code);
  } catch (error) {
    console.warn(`All airport lookups failed for ${code}:`, error);
    return null;
  }
}

/**
 * Preload airport coordinates for multiple airports
 * Useful for batch loading when you know which airports you'll need
 */
export async function preloadAirportCoordinates(airportCodes: string[]): Promise<Map<string, AirportData | null>> {
  const results = new Map<string, AirportData | null>();
  
  // Process in parallel for better performance
  const promises = airportCodes.map(async (code) => {
    const coords = await getAirportCoordinates(code);
    results.set(code.toUpperCase(), coords);
    return { code: code.toUpperCase(), coords };
  });
  
  await Promise.all(promises);
  return results;
}

/**
 * Clear the airport coordinate cache
 */
export function clearAirportCache(): void {
  airportCache.clear();
  localAirports = null; // Also clear local database cache
}

/**
 * Get airport search suggestions from local database
 */
export async function searchAirports(query: string, limit: number = 10): Promise<Array<{iata: string, name: string, city: string}>> {
  const airports = await loadLocalAirports();
  if (!airports) return [];
  
  const normalizedQuery = query.toLowerCase();
  const matches = Object.values(airports)
    .filter((airport: any) => 
      airport.iata.toLowerCase().includes(normalizedQuery) ||
      airport.name.toLowerCase().includes(normalizedQuery) ||
      airport.city.toLowerCase().includes(normalizedQuery)
    )
    .slice(0, limit)
    .map((airport: any) => ({
      iata: airport.iata,
      name: airport.name,
      city: airport.city
    }));
  
  return matches;
}