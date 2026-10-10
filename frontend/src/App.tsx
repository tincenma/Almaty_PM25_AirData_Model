import { useEffect, useRef, useState } from 'react'
import {
  CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer,
  Scatter, Tooltip, XAxis, YAxis,
} from 'recharts'
import { forecastRequest, request } from './api'
import type { Forecast, ModelFamily, Overview, StationCatalog } from './api'

type View = 'forecast' | 'stations' | 'performance' | 'about'
type IconName = 'wind' | 'chart' | 'info' | 'arrow' | 'download' | 'pin' | 'clock' | 'check' | 'play'
const iconPaths: Record<IconName, string[]> = {
  wind: ['M3 8h12a3 3 0 1 0-3-3', 'M2 12h17a3 3 0 1 0-3-3', 'M5 16h9a3 3 0 1 1-3 3'],
  chart: ['M4 4v16h16', 'm7 14 4-5 4 3 5-7'],
  info: ['M12 11v6', 'M12 7h.01', 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0'],
  arrow: ['M4 12h16', 'm14 6 6 6-6 6'],
  download: ['M12 3v12', 'm7 10 5 5 5-5', 'M4 16v5h16v-5'],
  pin: ['M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0', 'M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0'],
  clock: ['M12 7v5l3 2', 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0'],
  check: ['m5 12 4 4L19 6'],
  play: ['m8 5 11 7-11 7V5'],
}
function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {iconPaths[name].map((path, i) => <path d={path} key={i} />)}
  </svg>
}

const dateOptions: Intl.DateTimeFormatOptions = { timeZone: 'Asia/Almaty', day: 'numeric', month: 'short', year: 'numeric' }
const dateLabel = (value: string) => new Date(value).toLocaleDateString('en-GB', dateOptions)
const timeLabel = (value: string | number) => new Date(value).toLocaleTimeString('en-GB', { timeZone: 'Asia/Almaty', hour: '2-digit', minute: '2-digit' })
const localDate = (value: string) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Almaty', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(value))
const number = (value: number) => value.toLocaleString('en-GB', { maximumFractionDigits: 1 })

function App() {
  const [view, setView] = useState<View>('forecast')
  const [overview, setOverview] = useState<Overview | null>(null)
  const [forecast, setForecast] = useState<Forecast | null>(null)
  const [date, setDate] = useState('')
  const [origin, setOrigin] = useState('')
  const [origins, setOrigins] = useState<string[]>([])
  const [model, setModel] = useState<ModelFamily>('XGBoost')
  const [showOutcomes, setShowOutcomes] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [originsLoading, setOriginsLoading] = useState(false)
  const [error, setError] = useState('')
  const [exporting, setExporting] = useState(false)
  const [catalog, setCatalog] = useState<StationCatalog | null>(null)
  const [stationLoading, setStationLoading] = useState(true)
  const [stationError, setStationError] = useState('')
  const dateRequest = useRef(0)

  async function initialize() {
    setLoading(true); setError('')
    try {
      const data = await request<Overview>('/overview')
      const firstDate = localDate(data.default_origin)
      const [hours, result] = await Promise.all([
        request<{ origins: string[] }>(`/origins?date=${firstDate}`),
        request<Forecast>('/forecast', forecastRequest(data.default_origin, 'XGBoost')),
      ])
      setOverview(data); setDate(firstDate); setOrigin(data.default_origin)
      setOrigins(hours.origins); setForecast(result); setModel('XGBoost')
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Unable to connect to the model service.')
    } finally { setLoading(false) }
  }
  useEffect(() => { void initialize() }, [])
  useEffect(() => {
    request<StationCatalog>('/stations').then(setCatalog)
      .catch(() => setStationError('Station information is unavailable. Try refreshing the station check.'))
      .finally(() => setStationLoading(false))
  }, [])

  async function refreshStations() {
    setStationLoading(true); setStationError('')
    try { setCatalog(await request<StationCatalog>('/stations/refresh', { method: 'POST' })) }
    catch { setStationError('Unable to refresh station information. The saved check is still shown.') }
    finally { setStationLoading(false) }
  }

  async function changeDate(value: string) {
    const id = ++dateRequest.current
    setDate(value); setOriginsLoading(true); setError('')
    try {
      const data = await request<{ origins: string[] }>(`/origins?date=${value}`)
      if (id === dateRequest.current) { setOrigins(data.origins); setOrigin(data.origins[0]) }
    } catch (failure) {
      if (id === dateRequest.current) { setOrigins([]); setError(failure instanceof Error ? failure.message : 'Unable to load hours.') }
    } finally { if (id === dateRequest.current) setOriginsLoading(false) }
  }

  async function runForecast() {
    setBusy(true); setError('')
    try {
      const result = await request<Forecast>('/forecast', forecastRequest(origin, model))
      setForecast(result); setShowOutcomes(false)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Forecast failed.')
    } finally { setBusy(false) }
  }

  async function exportForecast() {
    if (!forecast) return
    setExporting(true); setError('')
    try {
      const response = await fetch('/api/forecast/export', forecastRequest(forecast.origin, forecast.model))
      if (!response.ok) throw new Error('Unable to download the forecast. Please try again.')
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a'); link.href = url; link.download = 'almaty_forecast.csv'; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Download failed.') }
    finally { setExporting(false) }
  }

  const pendingChanges = forecast && (origin !== forecast.origin || model !== forecast.model)
  const title = view === 'forecast' ? 'A clearer view of the air ahead.' : view === 'stations' ? 'Know where the readings come from.' : view === 'performance' ? 'Every forecast, put to the test.' : 'Built on data. Grounded in reality.'

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#" onClick={(event) => { event.preventDefault(); setView('forecast') }} aria-label="Breathe home">
        <span className="brand-icon"><Icon name="wind" size={27} /></span><span>breathe<span className="brand-dot">.</span></span>
      </a>
      <div className="workspace-label">ALMATY AIR LAB</div>
      <nav aria-label="Main navigation">
        {([['forecast', 'wind', 'Forecast'], ['stations', 'pin', 'Station directory'], ['performance', 'chart', 'Model performance'], ['about', 'info', 'About the project']] as const).map(([key, icon, label]) =>
          <button key={key} aria-label={label} title={label} className={`nav-item ${view === key ? 'active' : ''}`} onClick={() => setView(key)} aria-current={view === key ? 'page' : undefined}>
            <Icon name={icon} /><span>{label}</span>{view === key && <span className="nav-dot" />}
          </button>)}
      </nav>
      <div className="sidebar-landscape" aria-hidden="true">
        <svg viewBox="0 0 200 130"><path d="M0 130 35 88 59 105 107 27 151 90 172 67 200 113V130" fill="#2b5248" /><path d="m75 78 32-51 23 34-20-8-11 17-8-5Z" fill="#699184" /><path d="M0 130 62 98 95 119 137 81 200 125V130" fill="#416759" /></svg>
        <p>A little more foresight.<br />A little more breathing room.</p>
      </div>
      <div className="sidebar-footer"><span className="status-dot" />Research prototype<span className="version">v1.0</span></div>
    </aside>

    <main className="main">
      <header className="topbar"><span>Air quality intelligence <span className="breadcrumb">/ {view === 'forecast' ? 'Forecast overview' : view === 'performance' ? 'Evaluation' : view === 'stations' ? 'Station directory' : 'Project'}</span></span>
        <span className="replay-badge"><Icon name="clock" size={13} /> Historical replay</span>
      </header>
      <div className="page-content">
        <section className="page-heading"><div><div className="eyebrow">{view === 'forecast' ? 'LOOK AHEAD' : view === 'stations' ? 'THE MONITORING NETWORK' : view === 'performance' ? 'THE EVIDENCE' : 'BEHIND THE FORECAST'}</div>
          <h1>{title}</h1><p>{view === 'forecast' ? 'Explore PM2.5 forecasts for Almaty, one measured hour at a time.' : view === 'stations' ? 'Latest published PM2.5 readings and reporting freshness across Almaty.' : view === 'performance' ? 'Independent results from 2024, a year held out from training.' : 'A practical experiment in forecasting Almaty’s air quality.'}</p></div>
          <div className="location-chip"><Icon name="pin" size={17} /><span>Almaty, Kazakhstan<small>Asia/Almaty local time</small></span></div>
        </section>

        {error && <div className="error-banner" role="alert"><Icon name="info" /><span>{error}</span>{!overview && <button onClick={() => void initialize()}>Retry connection</button>}</div>}
        {loading ? <div className="loading-state" role="status"><span className="spinner" />Connecting to the trained models…</div> : overview && forecast ? <>
          {view === 'forecast' && <>
            <section className="panel controls-panel" aria-label="Forecast controls">
              <div className="station-control"><span className="control-label">MONITORING STATION</span><div className="station-name"><span className="station-dot" />{overview.station.name}</div><small>One station · PM2.5 concentration</small></div>
              <label className="field"><span className="control-label">REPLAY DATE</span><select value={date} onChange={event => void changeDate(event.target.value)} disabled={busy}>
                {overview.available_dates.map(value => <option key={value} value={value}>{dateLabel(`${value}T12:00:00+05:00`)}</option>)}
              </select></label>
              <label className="field time-field"><span className="control-label">MEASURED HOUR</span><select value={origin} onChange={event => setOrigin(event.target.value)} disabled={busy || originsLoading}>
                {origins.map(value => <option key={value} value={value}>{timeLabel(value)}</option>)}
              </select></label>
              <label className="field"><span className="control-label">MODEL</span><select value={model} onChange={event => setModel(event.target.value as ModelFamily)} disabled={busy}>
                {overview.models.map(value => <option key={value}>{value}</option>)}
              </select></label>
              <button className="primary-button" onClick={() => void runForecast()} disabled={busy || originsLoading || !origins.length}>
                {busy ? <span className="spinner small" /> : <Icon name="play" size={16} />} {busy ? 'Predicting…' : 'Run forecast'}
              </button>
            </section>
            <section className="station-status-strip" aria-label="Model station reporting status">
              <Icon name="info" size={17} /><div><strong>{catalog?.trained_station ? (catalog.trained_station.reporting_status === 'recent' ? 'Model station has recent published readings' : 'Model station has no recent published readings') : 'Current station activity has not been verified'}</strong>
                <span>{catalog?.trained_station ? `Last published reading: ${dateLabel(catalog.trained_station.latest_measurement)}, ${timeLabel(catalog.trained_station.latest_measurement)} · ${catalog.trained_station.source_name}. ` : ''}This model uses historical replay.</span></div>
              <button className="text-button" onClick={() => setView('stations')}>View station info <Icon name="arrow" size={14} /></button>
            </section>
            <div className="results-caption" aria-live="polite"><span><span className="status-dot" />{forecast.model} forecasts · {dateLabel(forecast.origin)} · measured hour {timeLabel(forecast.origin)}</span><span>{pendingChanges ? 'Selection changed — run forecast to update' : `Measured ${number(forecast.current_pm25)} µg/m³ · ${forecast.input_coverage_24h}/24 recent hours observed`}</span></div>
            <section className="forecast-cards" aria-label="PM2.5 forecast results">
              {forecast.forecasts.map((estimate, index) => {
                const difference = estimate.predicted - forecast.current_pm25
                const metric = overview.metrics.find(row => row.model === forecast.model && row.horizon_hours === estimate.horizon_hours)!
                return <article className={`forecast-card card-${index}`} key={estimate.horizon_hours}>
                  <div className="card-top"><span>IN {estimate.horizon_hours} {estimate.horizon_hours === 1 ? 'HOUR' : 'HOURS'}</span><span className="horizon-icon"><Icon name="wind" size={19} /></span></div>
                  <div className="forecast-number">{number(estimate.predicted)}<span>µg/m³</span></div>
                  <div className="forecast-description">Predicted PM2.5 concentration</div>
                  <div className="card-divider" />
                  <div className="card-bottom"><span className={difference <= 0 ? 'change down' : 'change up'}>{difference <= 0 ? '↘' : '↗'} {number(Math.abs(difference))} {difference <= 0 ? 'lower' : 'higher'}</span><span>than measured</span></div>
                  <div className="card-note">Test MAE {metric.MAE.toFixed(1)} µg/m³{showOutcomes && <span> · observed {number(estimate.observed)}</span>}</div>
                </article>
              })}
            </section>
            <section className="panel chart-panel">
              <div className="panel-header"><div><h2>From recent history to what’s ahead</h2><p>Past 24 hours of measurements and three future estimates.</p></div>
                <label className="toggle-label"><input type="checkbox" checked={showOutcomes} onChange={event => setShowOutcomes(event.target.checked)} /><span className="toggle-track" />Reveal outcomes</label>
              </div>
              <ForecastChart forecast={forecast} showOutcomes={showOutcomes} />
              <div className="chart-footer"><span><Icon name="info" size={14} />Dots represent individual forecast hours. Gaps indicate missing observations.</span>
                <button className="text-button" onClick={() => void exportForecast()} disabled={exporting}><Icon name="download" size={15} />{exporting ? 'Downloading…' : 'Export forecast'}</button>
              </div>
            </section>
            <div className="bottom-grid"><section className="panel insight-panel"><div className="insight-icon"><Icon name="chart" /></div><div><h3>A forecast you can evaluate</h3><p>{forecast.model}’s 6-hour forecast {overview.metrics.find(m => m.model === forecast.model && m.horizon_hours === 6)!.MAE_improvement_vs_persistence_pct >= 0 ? 'reduces' : 'increases'} test error by <strong>{Math.abs(overview.metrics.find(m => m.model === forecast.model && m.horizon_hours === 6)!.MAE_improvement_vs_persistence_pct).toFixed(1)}%</strong> versus carrying the latest reading forward.</p><button className="text-button" onClick={() => setView('performance')}>Explore model performance <Icon name="arrow" size={15} /></button></div></section>
              <section className="replay-note"><Icon name="clock" size={20} /><div><h3>A look back to look ahead</h3><p>This is a replay of held-out measurements from 2024. Predictions run on the trained models, using only observations available at the selected origin.</p></div></section></div>
          </>}
          {view === 'performance' && <Performance overview={overview} />}
          {view === 'stations' && <StationDirectory catalog={catalog} loading={stationLoading} error={stationError} refresh={() => void refreshStations()} />}
          {view === 'about' && <About overview={overview} />}
        </> : !error && <div className="loading-state">The model service is unavailable.</div>}
        <footer className="page-footer"><span>Powered by AirData.kz · Original measurement providers</span><span>Research forecasts · Station-level estimates</span></footer>
      </div>
    </main>
  </div>
}

function StationDirectory({ catalog, loading, error, refresh }: { catalog: StationCatalog | null; loading: boolean; error: string; refresh: () => void }) {
  const [recentOnly, setRecentOnly] = useState(true)
  const [search, setSearch] = useState('')
  const [source, setSource] = useState('all')
  const trained = catalog?.trained_station
  const all = catalog?.stations ?? []
  const sources = [...new Map(all.map(station => [station.source, station.source_name])).entries()]
  const visible = all.filter(station => (!recentOnly || station.reporting_status === 'recent')
    && (source === 'all' || station.source === source)
    && `${station.name} ${station.id}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
  return <>
    <section className="panel station-summary"><div><div className="eyebrow">STATION USED BY OUR MODEL</div><h2>{trained?.name ?? 'Almaty (US Embassy)'}</h2>
      <p>{trained ? <>Last published measurement: <strong>{dateLabel(trained.latest_measurement)}, {timeLabel(trained.latest_measurement)}</strong> · {trained.source_name}</> : 'The current reporting status is not available.'}</p>
      <p>Recently reporting stations below need their own model training or validation before they can provide forecasts in this app.</p></div>
      <span className={`station-badge ${trained?.reporting_status === 'recent' ? 'recent' : 'stale'}`}>{trained ? trained.reporting_status === 'recent' ? 'Recently reporting' : 'No recent readings' : 'Status unavailable'}</span>
    </section>
    <div className="station-directory-bar"><div><strong>{all.filter(station => station.reporting_status === 'recent').length}</strong><span>stations with published readings in the past 48 hours</span></div><button className="secondary-button" onClick={refresh} disabled={loading}><Icon name="clock" size={15} />{loading ? 'Checking…' : 'Refresh station info'}</button></div>
    {(error || catalog?.refresh_error) && <div className="error-banner" role="alert">{error || catalog?.refresh_error}</div>}
    <section className="panel station-directory-panel">
      <div className="station-filters"><label><span className="control-label">SEARCH STATIONS</span><input type="search" placeholder="Name or station ID" value={search} onChange={event => setSearch(event.target.value)} /></label>
        <label><span className="control-label">DATA SOURCE</span><select value={source} onChange={event => setSource(event.target.value)}><option value="all">All sources</option>{sources.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <label className="toggle-label"><input type="checkbox" checked={recentOnly} onChange={event => setRecentOnly(event.target.checked)} /><span className="toggle-track" />Recently reporting only</label>
      </div>
      <div className="table-scroll"><table><thead><tr><th>Station</th><th>Source</th><th>Latest PM2.5</th><th>Measured hour · Almaty time</th><th>Reporting</th></tr></thead><tbody>
        {visible.map(station => <tr key={station.id}><td><span className="directory-station-name">{station.name}</span><small className="directory-station-id">{station.id}{station.model_available ? ' · model station' : ''}</small></td><td>{station.source_name}</td><td>{station.latest_pm25 === null ? 'Unavailable' : `${number(station.latest_pm25)} µg/m³`}</td><td>{dateLabel(station.latest_measurement)}<small className="directory-station-id">{timeLabel(station.latest_measurement)}</small></td><td><span className={`station-badge ${station.reporting_status === 'recent' ? 'recent' : 'stale'}`}>{station.reporting_status === 'recent' ? 'Recent' : station.reporting_status === 'not_recent' ? 'No recent readings' : 'Unverified timestamp'}</span></td></tr>)}
      </tbody></table></div>
      {!visible.length && <p className="station-empty" role="status">{loading ? 'Checking station data…' : 'No stations match these filters.'}</p>}
      <div className="table-note">{visible.length} stations shown · Last successful check: {catalog?.checked_at ? `${dateLabel(catalog.checked_at)}, ${timeLabel(catalog.checked_at)}` : 'Not checked'}</div>
    </section>
    <section className="replay-note"><Icon name="info" /><div><h3>Recent readings are evidence of reporting</h3><p>Status is inferred from the latest AirData.kz publication within 48 hours. It does not verify official operational status or a continuous live connection. A recent concentration is a measurement, not a forecast. Publication delays and gaps can occur.</p><a href="https://github.com/qazybekb/AirDatakz-OpenData" target="_blank" rel="noreferrer" className="text-button">AirData.kz source <Icon name="arrow" size={14} /></a></div></section>
  </>
}

function ForecastChart({ forecast, showOutcomes }: { forecast: Forecast; showOutcomes: boolean }) {
  const origin = new Date(forecast.origin).getTime()
  const history = forecast.history.filter(point => new Date(point.time).getTime() >= origin - 24 * 3600000)
  const data = [...history.map(point => ({ time: new Date(point.time).getTime(), observed: point.value, outcome: null as number | null })),
    ...forecast.outcomes.map(point => ({ time: new Date(point.time).getTime(), observed: null, outcome: showOutcomes ? point.value : null }))]
  const estimates = forecast.forecasts.map(point => ({ time: new Date(point.target_time).getTime(), predicted: point.predicted }))
  const upperBound = Math.max(10, Math.ceil(Math.max(...data.map(point => Math.max(point.observed ?? 0, point.outcome ?? 0)), ...estimates.map(point => point.predicted)) * 1.15 / 10) * 10)
  return <div className="chart-wrapper" aria-label="PM2.5 history and forecast chart">
    <span className="chart-unit">PM2.5 · µg/m³</span>
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ top: 22, right: 24, bottom: 5, left: 0 }}>
        <CartesianGrid stroke="#e9ede7" vertical={false} strokeDasharray="3 4" />
        <XAxis type="number" dataKey="time" domain={[origin - 24 * 3600000, origin + 24 * 3600000]} ticks={[-24, -18, -12, -6, 0, 6, 12, 18, 24].map(hour => origin + hour * 3600000)} tickFormatter={timeLabel} axisLine={false} tickLine={false} minTickGap={25} tick={{ fill: '#7a827b', fontSize: 11 }} />
        <YAxis tickLine={false} axisLine={false} width={43} tick={{ fill: '#7a827b', fontSize: 11 }} domain={[0, upperBound]} allowDataOverflow />
        <Tooltip labelFormatter={value => `${dateLabel(new Date(Number(value)).toISOString())}, ${timeLabel(Number(value))}`} formatter={(value, name) => [`${Number(value).toFixed(1)} µg/m³`, name]} contentStyle={{ borderRadius: 12, border: '1px solid #dfe5dc', fontSize: 12 }} />
        <Legend verticalAlign="bottom" iconType="circle" iconSize={7} wrapperStyle={{ paddingTop: 16, fontSize: 12 }} />
        <ReferenceLine x={origin} stroke="#a6b6a3" strokeDasharray="4 5" label={{ value: 'Forecast origin', position: 'insideTopRight', fill: '#7a827b', fontSize: 11 }} />
        <Line name="Measured history" dataKey="observed" stroke="#315f50" strokeWidth={2.4} dot={false} connectNulls={false} isAnimationActive={false} />
        {showOutcomes && <Line name="Observed outcomes" dataKey="outcome" stroke="#a5afa0" strokeWidth={2} strokeDasharray="4 4" dot={false} connectNulls={false} isAnimationActive={false} />}
        <Scatter name="Model forecasts" data={estimates} dataKey="predicted" fill="#9dad44" isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  </div>
}

function Performance({ overview }: { overview: Overview }) {
  const [horizon, setHorizon] = useState(6)
  const [family, setFamily] = useState<ModelFamily>('XGBoost')
  const rows = overview.metrics.filter(row => row.horizon_hours === horizon).sort((a, b) => a.MAE - b.MAE)
  const maxError = Math.max(...rows.map(row => row.MAE))
  const seasons = overview.seasons.filter(row => row.horizon_hours === horizon && row.model === family)
  return <>
    <div className="performance-controls"><div className="segmented" aria-label="Evaluation horizon">{overview.horizons.map(h => <button key={h} className={horizon === h ? 'selected' : ''} onClick={() => setHorizon(h)}>{h}-hour forecast</button>)}</div><span>Lower MAE and RMSE are better</span></div>
    <section className="panel performance-panel"><div className="panel-header"><div><h2>How the models compare</h2><p>Identical eligible test hours for every model within each horizon.</p></div><span className="subtle-badge">2024 test year</span></div>
      <div className="table-scroll"><table><thead><tr><th>Model</th><th>Mean absolute error</th><th>RMSE</th><th>R²</th><th>MAE improvement*</th></tr></thead><tbody>{rows.map(row => <tr key={row.model}><td><span className={`model-dot ${row.model === 'XGBoost' ? 'green' : row.model === 'Ridge' ? 'olive' : 'gray'}`} />{row.model}</td><td><div className="error-meter"><span>{row.MAE.toFixed(2)} <small>µg/m³</small></span><div><i style={{ width: `${row.MAE / maxError * 100}%` }} /></div></div></td><td>{row.RMSE.toFixed(2)}</td><td>{row.R2.toFixed(3)}</td><td className={row.MAE_improvement_vs_persistence_pct > 0 ? 'positive' : ''}>{row.MAE_improvement_vs_persistence_pct.toFixed(1)}%</td></tr>)}</tbody></table></div>
      <div className="table-note">*Compared with persistence: using the latest measured concentration as the forecast.</div>
    </section>
    <div className="bottom-grid"><section className="panel season-panel"><div className="panel-header"><div><h2>Accuracy through the seasons</h2><p>{horizon}-hour test MAE by season</p></div><select aria-label="Season comparison model" value={family} onChange={event => setFamily(event.target.value as ModelFamily)}><option>XGBoost</option><option>Ridge</option></select></div>
      {['Winter', 'Spring', 'Summer', 'Autumn'].map(season => { const row = seasons.find(s => s.season === season); return row && <div className="season-row" key={season}><span>{season}<small>{row.n.toLocaleString()} test hours</small></span><strong>{row.MAE.toFixed(1)}<small> µg/m³</small></strong></div> })}
    </section><section className="panel methodology-panel"><div className="eyebrow">A FAIR COMPARISON</div><h2>Time moves forward.<br />So does our evaluation.</h2><div className="timeline"><div><span className="timeline-dot" /><strong>2020–2022</strong><small>Train the models</small></div><div><span className="timeline-dot" /><strong>2023</strong><small>Select settings</small></div><div><span className="timeline-dot test" /><strong>2024</strong><small>Independent test</small></div></div><p>Forecast targets do not cross split boundaries. Missing target readings are excluded, and preprocessing is fitted only on pre-test data.</p><p>Scores describe eligible hours at this station. They do not establish citywide performance.</p></section></div>
  </>
}

function About({ overview }: { overview: Overview }) {
  return <>
    <section className="panel about-hero"><div><div className="eyebrow">BREATHE · ALMATY AIR LAB</div><h2>Making air quality<br />a little more predictable.</h2><p>We trained models on Almaty’s historical PM2.5 measurements to explore how well pollution can be forecast one, six and twenty-four hours ahead.</p></div><div className="about-symbol"><Icon name="wind" size={100} /></div></section>
    <div className="about-grid"><section className="panel about-card"><Icon name="pin" /><h3>One station, real measurements</h3><p>{overview.station.name}. {overview.observed_hours.toLocaleString()} observed hours in the experiment period, with {overview.coverage_pct}% coverage.</p><p>Location: {overview.station.latitude.toFixed(3)}° N, {overview.station.longitude.toFixed(3)}° E.</p></section>
      <section className="panel about-card"><Icon name="chart" /><h3>Models we can explain</h3><p>Ridge regression and XGBoost use recent concentrations, hourly lags, trailing averages, and calendar patterns. Weather is not an input in this experiment.</p></section>
      <section className="panel about-card"><Icon name="clock" /><h3>A historical demonstration</h3><p>Choose from {overview.eligible_origins.toLocaleString()} eligible test origins. A timestamp labels the measured hour; inference assumes that hour’s reading has arrived. Actual outcomes are revealed separately.</p></section></div>
    <section className="panel limitations-panel"><div><Icon name="info" /><h2>Know the limits of the forecast</h2></div><p>One monitoring station cannot represent every neighborhood. Missing measurements, retrospective data cleaning, and reporting delays may affect performance on live data. Point forecasts do not express uncertainty and should not be treated as medical advice or a validated public alert system.</p></section>
    <section className="panel source-panel"><div><h3>Open data, with attribution</h3><p>{overview.dataset.attribution}</p><small>{overview.dataset.license}</small></div><a className="secondary-button" href="https://github.com/qazybekb/AirDatakz-OpenData" target="_blank" rel="noreferrer">Explore the dataset <Icon name="arrow" size={15} /></a></section>
  </>
}

export default App

