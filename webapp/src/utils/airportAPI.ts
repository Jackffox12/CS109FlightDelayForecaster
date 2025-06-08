// Airport coordinate API service for dynamic lookups

interface AirportData {
  lat: number;
  lng: number;
}

// Cache to avoid repeated API calls
const airportCache = new Map<string, AirportData | null>();

/**
 * Fetch airport coordinates from external API sources
 */
async function fetchAirportFromAPI(airportCode: string): Promise<AirportData | null> {
  // Check cache first
  if (airportCache.has(airportCode)) {
    return airportCache.get(airportCode) || null;
  }

  try {
    // Option 1: Try Airport-Data.com API (free, no key required)
    const response = await fetch(`https://www.airport-data.com/api/ap_info.json?iata=${airportCode}`);
    
    if (response.ok) {
      const data = await response.json();
      if (data.latitude && data.longitude) {
        const result = {
          lat: parseFloat(data.latitude),
          lng: parseFloat(data.longitude)
        };
        airportCache.set(airportCode, result);
        return result;
      }
    }
  } catch (error) {
    console.warn(`Failed to fetch airport data for ${airportCode} from Airport-Data.com:`, error);
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
    // Option 3: Try OpenFlights airport database API
    const response = await fetch(`https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat`);
    
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

  // Cache null result to avoid repeated failed attempts
  airportCache.set(airportCode, null);
  return null;
}

/**
 * Get airport coordinates with intelligent fallback
 * 1. Check static lookup first (fastest)
 * 2. If not found, try API services
 * 3. Cache results for future use
 */
export async function getAirportCoordinates(airportCode: string): Promise<AirportData | null> {
  // Dynamic import to avoid circular dependency
  const { AIRPORT_LOOKUP } = await import('./airportCoords');
  
  // First, check static lookup
  const staticResult = AIRPORT_LOOKUP[airportCode.toUpperCase()];
  if (staticResult) {
    return staticResult;
  }

  // If not in static lookup, try API
  console.log(`Airport ${airportCode} not in static database, trying API lookup...`);
  return await fetchAirportFromAPI(airportCode.toUpperCase());
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
} 