import Globe from 'react-globe.gl';
import { useEffect, useRef } from 'react';

type Props = {
  origin: { lat: number; lng: number };
  dest: { lat: number; lng: number };
};

const R = 6371; // km, Earth radius
function toRad(deg: number) { return (deg * Math.PI) / 180; }
function greatCircleKm(a: { lat: number, lng: number }, b: { lat: number, lng: number }) {
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function FlightGlobe({ origin, dest }: Props) {
  console.log('[FlightGlobe] origin=', origin, 'dest=', dest);
  
  const globeRef = useRef<any>(null);

  useEffect(() => {
    if (!globeRef.current) {
      console.warn('[FlightGlobe] Globe ref is null');
      return;
    }

    const dist = greatCircleKm(origin, dest);          // km
    const alt = Math.min(1.2, Math.max(0.25, dist / 12000)); // clamp 0.25-1.2

    // Mid-point for camera centre (simple average is fine visually)
    const mid = {
      lat: (origin.lat + dest.lat) / 2,
      lng: (origin.lng + dest.lng) / 2,
      alt
    };

    globeRef.current.controls().autoRotate = true;
    // Animate camera: 1000 ms
    globeRef.current.pointOfView(mid, 1000);

  }, [origin, dest]);

  const arcsData = [{
    startLat: origin.lat,
    startLng: origin.lng,
    endLat: dest.lat,
    endLng: dest.lng,
    color: '#ff4444'
  }];

  if (!origin || !dest) {
    return <p className="text-red-400">Missing coords</p>;
  }

  return (
    <div className="h-[50vh] w-full flex items-center justify-center">
      <Globe
        ref={globeRef}
        width={700}
        height={400}
        
        globeImageUrl="//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
        backgroundColor="rgba(0,0,0,0)"
        
        arcsData={arcsData}
        arcColor={(arc: any) => arc.color}
        arcStroke={2}
        arcDashLength={0.4}
        arcDashGap={2}
        arcDashInitialGap={1}
        arcDashAnimateTime={2000}
        
        showAtmosphere={true}
        atmosphereColor="#4a90e2"
        atmosphereAltitude={0.15}
        
        enablePointerInteraction={true}
        animateIn={false}
      />
    </div>
  );
} 