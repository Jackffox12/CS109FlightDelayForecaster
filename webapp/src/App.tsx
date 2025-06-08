import { useState } from 'react'
import axios from 'axios'
import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, ResponsiveContainer } from 'recharts'

interface ForecastResponse {
  p_late: number
  alpha: number
  beta: number
  updated: boolean
}

function useForecast(carrier: string, number: string, depDate: string, enabled: boolean) {
  return useQuery<ForecastResponse, Error>({
    queryKey: ['forecast', carrier, number, depDate],
    queryFn: async () => {
      const { data } = await axios.get<ForecastResponse>(
        `http://localhost:8000/forecast/${carrier}/${number}/${depDate}`
      )
      return data
    },
    enabled,
    refetchInterval: enabled ? 60_000 : false,
  })
}

export default function App() {
  const [carrier, setCarrier] = useState('DL')
  const [number, setNumber] = useState('202')
  const [depDate, setDepDate] = useState('2025-06-07')
  const [live, setLive] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const query = useForecast(carrier, number, depDate, submitted)

  const sparkData = query.data
    ? [
        { x: 0, y: 0 },
        { x: 1, y: query.data!.p_late },
      ]
    : []

  return (
    <div className="min-h-screen flex flex-col items-center p-6 space-y-4 bg-gray-50">
      <h1 className="text-2xl font-bold">Flight Delay Bayesian Forecaster</h1>

      <div className="flex space-x-2">
        <input
          value={carrier}
          onChange={(e) => setCarrier(e.target.value.toUpperCase())}
          className="border p-2 w-16 text-center"
          placeholder="DL"
        />
        <input
          value={number}
          onChange={(e) => setNumber(e.target.value)}
          className="border p-2 w-24 text-center"
          placeholder="202"
        />
        <input
          type="date"
          value={depDate}
          onChange={(e) => setDepDate(e.target.value)}
          className="border p-2"
        />
        <button
          onClick={() => {
            setSubmitted(true)
          }}
          className="bg-blue-600 text-white px-4 py-2 rounded"
        >
          Get forecast
        </button>
        <label className="flex items-center space-x-1">
          <input
            type="checkbox"
            checked={live}
            onChange={() => {
              setLive(!live)
            }}
            className="h-4 w-4"
          />
          <span>Live update</span>
        </label>
      </div>

      {query.isLoading && <p>Loading...</p>}
      {query.error && <p className="text-red-600">{query.error.message}</p>}
      {query.data && (
        <div className="flex flex-col items-center space-y-4">
          <p className="text-5xl font-bold text-gray-800">
            {(query.data!.p_late * 100).toFixed(1)}%
          </p>
          <ResponsiveContainer width={200} height={60}>
            <LineChart data={sparkData} margin={{ left: -20, right: -20 }}>
              <Line type="monotone" dataKey="y" stroke="#3b82f6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
          <p className="text-sm text-gray-500">
            α={query.data!.alpha.toFixed(2)} β={query.data!.beta.toFixed(2)} Updated:{' '}
            {String(query.data!.updated)}
          </p>
        </div>
      )}
    </div>
  )
}
