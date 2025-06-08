// Airport information mapping for enhanced route display
export const AIRPORT_INFO: Record<string, { city: string; country: string }> = {
  // United States - Major Hubs
  ATL: { city: "Atlanta", country: "USA" },
  LAX: { city: "Los Angeles", country: "USA" },
  ORD: { city: "Chicago", country: "USA" },
  DFW: { city: "Dallas", country: "USA" },
  DEN: { city: "Denver", country: "USA" },
  JFK: { city: "New York", country: "USA" },
  SFO: { city: "San Francisco", country: "USA" },
  LAS: { city: "Las Vegas", country: "USA" },
  SEA: { city: "Seattle", country: "USA" },
  CLT: { city: "Charlotte", country: "USA" },
  MIA: { city: "Miami", country: "USA" },
  PHX: { city: "Phoenix", country: "USA" },
  IAH: { city: "Houston", country: "USA" },
  MCO: { city: "Orlando", country: "USA" },
  EWR: { city: "Newark", country: "USA" },
  MSP: { city: "Minneapolis", country: "USA" },
  BOS: { city: "Boston", country: "USA" },
  DTW: { city: "Detroit", country: "USA" },
  PHL: { city: "Philadelphia", country: "USA" },
  LGA: { city: "New York", country: "USA" },
  DCA: { city: "Washington", country: "USA" },
  IAD: { city: "Washington", country: "USA" },
  BWI: { city: "Baltimore", country: "USA" },
  MDW: { city: "Chicago", country: "USA" },
  SLC: { city: "Salt Lake City", country: "USA" },
  PDX: { city: "Portland", country: "USA" },
  SAN: { city: "San Diego", country: "USA" },
  TPA: { city: "Tampa", country: "USA" },
  STL: { city: "St. Louis", country: "USA" },
  CVG: { city: "Cincinnati", country: "USA" },
  CMH: { city: "Columbus", country: "USA" },
  IND: { city: "Indianapolis", country: "USA" },
  MKE: { city: "Milwaukee", country: "USA" },
  MSY: { city: "New Orleans", country: "USA" },
  AUS: { city: "Austin", country: "USA" },
  SAT: { city: "San Antonio", country: "USA" },
  MCI: { city: "Kansas City", country: "USA" },
  OMA: { city: "Omaha", country: "USA" },
  TUL: { city: "Tulsa", country: "USA" },
  OKC: { city: "Oklahoma City", country: "USA" },
  ABQ: { city: "Albuquerque", country: "USA" },
  RNO: { city: "Reno", country: "USA" },
  BOI: { city: "Boise", country: "USA" },
  ANC: { city: "Anchorage", country: "USA" },
  HNL: { city: "Honolulu", country: "USA" },

  // Europe
  LHR: { city: "London", country: "UK" },
  LGW: { city: "London", country: "UK" },
  MAN: { city: "Manchester", country: "UK" },
  CDG: { city: "Paris", country: "France" },
  ORY: { city: "Paris", country: "France" },
  FRA: { city: "Frankfurt", country: "Germany" },
  MUC: { city: "Munich", country: "Germany" },
  AMS: { city: "Amsterdam", country: "Netherlands" },
  MAD: { city: "Madrid", country: "Spain" },
  BCN: { city: "Barcelona", country: "Spain" },
  FCO: { city: "Rome", country: "Italy" },
  MXP: { city: "Milan", country: "Italy" },
  ZUR: { city: "Zurich", country: "Switzerland" },
  VIE: { city: "Vienna", country: "Austria" },
  ATH: { city: "Athens", country: "Greece" },
  IST: { city: "Istanbul", country: "Turkey" },
  SVO: { city: "Moscow", country: "Russia" },
  CPH: { city: "Copenhagen", country: "Denmark" },
  ARN: { city: "Stockholm", country: "Sweden" },
  OSL: { city: "Oslo", country: "Norway" },
  HEL: { city: "Helsinki", country: "Finland" },
  DUB: { city: "Dublin", country: "Ireland" },
  BRU: { city: "Brussels", country: "Belgium" },
  LIS: { city: "Lisbon", country: "Portugal" },
  PRG: { city: "Prague", country: "Czech Republic" },
  WAW: { city: "Warsaw", country: "Poland" },
  BUD: { city: "Budapest", country: "Hungary" },

  // Asia-Pacific
  NRT: { city: "Tokyo", country: "Japan" },
  HND: { city: "Tokyo", country: "Japan" },
  ICN: { city: "Seoul", country: "South Korea" },
  PEK: { city: "Beijing", country: "China" },
  PVG: { city: "Shanghai", country: "China" },
  CAN: { city: "Guangzhou", country: "China" },
  HKG: { city: "Hong Kong", country: "Hong Kong" },
  SIN: { city: "Singapore", country: "Singapore" },
  BKK: { city: "Bangkok", country: "Thailand" },
  KUL: { city: "Kuala Lumpur", country: "Malaysia" },
  CGK: { city: "Jakarta", country: "Indonesia" },
  MNL: { city: "Manila", country: "Philippines" },
  TPE: { city: "Taipei", country: "Taiwan" },
  DEL: { city: "Delhi", country: "India" },
  BOM: { city: "Mumbai", country: "India" },
  SYD: { city: "Sydney", country: "Australia" },
  MEL: { city: "Melbourne", country: "Australia" },
  PER: { city: "Perth", country: "Australia" },
  AKL: { city: "Auckland", country: "New Zealand" },

  // Middle East & Africa
  DXB: { city: "Dubai", country: "UAE" },
  AUH: { city: "Abu Dhabi", country: "UAE" },
  DOH: { city: "Doha", country: "Qatar" },
  KWI: { city: "Kuwait", country: "Kuwait" },
  RUH: { city: "Riyadh", country: "Saudi Arabia" },
  JED: { city: "Jeddah", country: "Saudi Arabia" },
  CAI: { city: "Cairo", country: "Egypt" },
  JNB: { city: "Johannesburg", country: "South Africa" },
  CPT: { city: "Cape Town", country: "South Africa" },
  ADD: { city: "Addis Ababa", country: "Ethiopia" },
  NBO: { city: "Nairobi", country: "Kenya" },

  // South America
  GRU: { city: "São Paulo", country: "Brazil" },
  GIG: { city: "Rio de Janeiro", country: "Brazil" },
  EZE: { city: "Buenos Aires", country: "Argentina" },
  LIM: { city: "Lima", country: "Peru" },
  BOG: { city: "Bogotá", country: "Colombia" },
  SCL: { city: "Santiago", country: "Chile" },
  CCS: { city: "Caracas", country: "Venezuela" },

  // Canada
  YYZ: { city: "Toronto", country: "Canada" },
  YVR: { city: "Vancouver", country: "Canada" },
  YUL: { city: "Montreal", country: "Canada" },
  YYC: { city: "Calgary", country: "Canada" },
  YOW: { city: "Ottawa", country: "Canada" },
  YEG: { city: "Edmonton", country: "Canada" },

  // Mexico & Central America
  MEX: { city: "Mexico City", country: "Mexico" },
  CUN: { city: "Cancún", country: "Mexico" },
  GDL: { city: "Guadalajara", country: "Mexico" },
  PTY: { city: "Panama City", country: "Panama" },
  SJO: { city: "San José", country: "Costa Rica" },
};

/**
 * Get formatted airport display with city and country
 * @param airportCode - 3-letter IATA airport code
 * @returns Formatted string like "JFK (New York, USA)" or just the code if not found
 */
export function formatAirportDisplay(airportCode: string): string {
  const info = AIRPORT_INFO[airportCode.toUpperCase()];
  if (info) {
    return `${airportCode.toUpperCase()} (${info.city}, ${info.country})`;
  }
  return airportCode.toUpperCase();
}

/**
 * Get formatted route display
 * @param origin - Origin airport code
 * @param dest - Destination airport code
 * @returns Formatted route string like "JFK (New York, USA) ▸ ATH (Athens, Greece)"
 */
export function formatRouteDisplay(origin: string, dest: string): string {
  return `${formatAirportDisplay(origin)} ▸ ${formatAirportDisplay(dest)}`;
} 