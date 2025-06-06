import React from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient, api } from "./api";
import SearchForm, { SearchValues } from "./components/SearchForm";
import ProbabilityGauge from "./components/ProbabilityGauge";
import PredictiveCdfChart from "./components/PredictiveCdfChart";
import ThemeToggle from "./components/ThemeToggle";
import { useBayesWorker } from "./hooks/useBayesWorker";

function handleSubmit(v: SearchValues) {
  console.log("search", v);
  // TODO call backend
}

const App: React.FC = () => {
  const { pLate, cdf, update } = useBayesWorker();

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen p-6 transition-colors">
        <header className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold">Flight Delay Forecaster</h1>
          <ThemeToggle />
        </header>

        <main className="max-w-6xl mx-auto space-y-8">
          <SearchForm onSubmit={handleSubmit} />
          
          <div className="flex flex-wrap gap-8">
            <div className="p-6 bg-gray-50 dark:bg-gray-800 rounded-lg shadow-lg">
              <ProbabilityGauge pLate={pLate} label="P(delay > 15 min)" />
            </div>
            
            <div className="flex-1 min-w-[500px] p-6 bg-gray-50 dark:bg-gray-800 rounded-lg shadow-lg">
              <PredictiveCdfChart cdf={cdf} />
            </div>
          </div>

          {/* Test buttons */}
          <div className="flex gap-3">
            <button onClick={() => update(true)} className="button">
              Simulate Late Event
            </button>
            <button onClick={() => update(false)} className="button">
              Simulate On-Time Event
            </button>
          </div>
        </main>
      </div>
    </QueryClientProvider>
  );
};

export default App; 