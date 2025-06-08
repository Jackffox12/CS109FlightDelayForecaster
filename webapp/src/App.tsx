import { useState, useEffect } from 'react'
import axios from 'axios'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { FlightGlobe } from './components/FlightGlobe'
import { getAirportCoordinates } from './utils/airportAPI'
import dayjs from 'dayjs'

interface ForecastResp {
  carrier: string
  flight_num: string
  origin: string
  dest: string
  sched_dep_local: string | null
  pred_dep_local: string | null
  p_late: number
  alpha: number
  beta: number
  updated: boolean
}

export default function App() {
  const [flightId, setFlightId] = useState('')
  const [live, setLive] = useState(false)
  const [requestedId, setRequestedId] = useState<string | null>(null)
  const [airportCoords, setAirportCoords] = useState<{
    origin: { lat: number; lng: number } | null;
    dest: { lat: number; lng: number } | null;
  }>({ origin: null, dest: null })
  const [loadingCoords, setLoadingCoords] = useState(false)

  const today = dayjs().format('YYYY-MM-DD')

  const forecastQuery = useQuery<ForecastResp, Error>({
    queryKey: ['forecast', requestedId, today],
    enabled: false,
    queryFn: async () => {
      if (!requestedId) throw new Error('No flight')
      const carrier = requestedId.slice(0, 2)
      const number = requestedId.slice(2)
      const { data } = await axios.get<ForecastResp>(
        `http://localhost:8000/forecast/${carrier}/${number}/${today}`
      )
      return data
    },
    refetchInterval: live ? 60_000 : false,
  })

  // Fetch airport coordinates when flight data changes
  useEffect(() => {
    const fetchAirportCoordinates = async () => {
      if (!forecastQuery.data) {
        setAirportCoords({ origin: null, dest: null })
        return
      }

      setLoadingCoords(true)
      
      try {
        const [originCoords, destCoords] = await Promise.all([
          getAirportCoordinates(forecastQuery.data.origin),
          getAirportCoordinates(forecastQuery.data.dest)
        ])

        setAirportCoords({
          origin: originCoords,
          dest: destCoords
        })
      } catch (error) {
        console.error('Failed to fetch airport coordinates:', error)
        setAirportCoords({ origin: null, dest: null })
      } finally {
        setLoadingCoords(false)
      }
    }

    fetchAirportCoordinates()
  }, [forecastQuery.data])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const match = /^([A-Z]{2})(\d{1,4})$/.exec(flightId.trim().toUpperCase())
    if (!match) {
      alert('Flight must be like DL202')
      return
    }
    const normalized = match[1] + match[2]
    setRequestedId(normalized)
    forecastQuery.refetch()
  }

  const { data, isSuccess, isFetching } = forecastQuery

  // Check if we have coordinates for both airports
  const hasValidRoute = data && airportCoords.origin && airportCoords.dest

  return (
    <main
      className={`flex flex-col min-h-screen px-4 text-white
                ${isSuccess ? 'items-start justify-start' : 'items-center justify-center'}`}
    >
      <Helmet>
        <title>Flight Delay Forecaster</title>
        <meta name="description" content="Real-time Bayesian forecast of US flight delays" />
      </Helmet>

      {/* --- Header --- */}
      <header className="w-full pt-6 text-center">
        <h1 className="text-3xl md:text-4xl font-bold">Flight Delay Bayesian Forecaster</h1>

        {/* Input row */}
        <form
          onSubmit={handleSubmit}
          className="mt-4 flex flex-wrap gap-3 justify-center"
        >
          <input
            value={flightId}
            onChange={(e) => setFlightId(e.target.value.toUpperCase())}
            placeholder="DL202"
            className="border border-gray-600 bg-black text-white px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={isFetching}
            className="bg-white text-black px-4 py-2 rounded-lg hover:bg-gray-200 transition disabled:opacity-50"
          >
            {isFetching ? 'Loading...' : 'Get forecast'}
          </button>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={live}
              onChange={() => setLive(!live)}
            />
            Live update
          </label>
        </form>
      </header>

      {/* Loading and Error States */}
      {isFetching && !isSuccess && <p className="mt-6">Loading…</p>}
      {forecastQuery.error && <p className="text-red-500 mt-6">{forecastQuery.error.message}</p>}

      {/* --- Centered Globe --- */}
      {isSuccess && data && (
        <section className="flex-1 w-full flex items-center justify-center">
          {loadingCoords ? (
            <div className="h-[70vh] w-full max-w-4xl bg-gray-800/30 rounded-lg border border-gray-600 flex items-center justify-center">
              <div className="text-center">
                <p className="text-gray-400 mb-2">Loading airport coordinates...</p>
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white mx-auto"></div>
              </div>
            </div>
          ) : hasValidRoute ? (
            <div className="w-full max-w-6xl">
              <FlightGlobe
                origin={airportCoords.origin!}
                dest={airportCoords.dest!}
              />
            </div>
          ) : (
            <div className="h-[70vh] w-full max-w-4xl bg-gray-800/30 rounded-lg border border-gray-600 flex items-center justify-center">
              <div className="text-center">
                <p className="text-gray-400 mb-2">Route visualization unavailable</p>
                <p className="text-sm text-gray-500">
                  Missing coordinates for {!airportCoords.origin ? data.origin : data.dest}
                </p>
                <p className="text-xs text-gray-600 mt-2">
                  Airport may not be in our database or API lookup failed
                </p>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Stats below globe */}
      {isSuccess && data && (
        <section className="w-full max-w-md mx-auto mt-6 bg-white/10 rounded-xl p-6 backdrop-blur-lg">
          <div className="text-center space-y-1 mb-4">
            <p className="text-5xl font-bold">{(data.p_late * 100).toFixed(1)}%</p>
            <p className="text-sm text-gray-300">chance of departing ≥15&nbsp;min late</p>
          </div>

          <div className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-sm">
            <span className="text-gray-400">Route</span>
            <span>{data.origin} ▸ {data.dest}</span>

            <span className="text-gray-400">Scheduled</span>
            <span>{data.sched_dep_local ? dayjs(data.sched_dep_local).format('LT') : '—'}</span>

            <span className="text-gray-400">Predicted</span>
            <span>{data.pred_dep_local ? dayjs(data.pred_dep_local).format('LT') : '—'}</span>

            <span className="text-gray-400">α / β</span>
            <span>{data.alpha.toFixed(2)} / {data.beta.toFixed(2)}</span>

            <span className="text-gray-400">Updated</span>
            <span>{String(data.updated)}</span>
          </div>
        </section>
      )}
    </main>
  )
}
