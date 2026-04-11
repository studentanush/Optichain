import { useCallback, useEffect, useMemo, useState } from 'react';
import DemandForecastPage from './DemandForecastPage';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table';

import { fetchJson, postJson } from './lib/api';
import type { Brief, Health, Kpis, Risk, SkuMeta } from './types';

function EmptyState({ health }: { health: Health | null }) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-8 text-left max-w-2xl mx-auto">
      <h2 className="font-display text-xl font-semibold text-white mb-3">Setup required</h2>
      <p className="text-slate-400 mb-4">
        The API is reachable but analytics files are missing or incomplete. Generate artifacts from the
        notebooks, then run the ETL script from the repo root:
      </p>
      <pre className="text-sm bg-surface p-4 rounded-lg border border-surface-border overflow-x-auto text-emerald-400/90">
        python scripts/build_case_study_tables.py
      </pre>
      <p className="text-slate-500 text-sm mt-4">
        Start the API from the <code className="text-slate-400">backend</code> folder:{' '}
        <code className="text-slate-400">python -m uvicorn app.main:app --reload --port 8000</code>
      </p>
      {health?.messages?.length ? (
        <ul className="mt-4 text-sm text-amber-200/80 list-disc pl-5">
          {health.messages.slice(0, 8).map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function KpiCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number | string;
  hint: string;
  tone: 'danger' | 'warn' | 'ok' | 'neutral';
}) {
  const toneCls =
    tone === 'danger'
      ? 'text-danger'
      : tone === 'warn'
        ? 'text-warn'
        : tone === 'ok'
          ? 'text-ok'
          : 'text-white';
  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-5">
      <p className="text-xs uppercase tracking-wider text-slate-500 font-medium">{label}</p>
      <p className={`font-display text-3xl font-semibold mt-1 ${toneCls}`}>{value}</p>
      <p className="text-slate-500 text-sm mt-2">{hint}</p>
    </div>
  );
}

const col = createColumnHelper<Risk>();

function RiskTable({ risks }: { risks: Risk[] }) {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'severity', desc: true }]);

  const columns = useMemo(
    () => [
      col.accessor('sku_id', { header: 'SKU' }),
      col.accessor('warehouse_id', { header: 'WH' }),
      col.accessor('risk_type', {
        header: 'Type',
        cell: (i) => (
          <span
            className={
              i.getValue() === 'stockout'
                ? 'text-danger'
                : i.getValue() === 'overstock'
                  ? 'text-warn'
                  : ''
            }
          >
            {i.getValue()}
          </span>
        ),
      }),
      col.accessor('severity', { header: 'Severity' }),
      col.accessor('weeks_of_cover', { header: 'Wks cover' }),
      col.accessor('lead_time_days', { header: 'Lead d' }),
      col.accessor('reasons', {
        header: 'Why',
        cell: (i) => (
          <span className="text-slate-400 text-xs">{i.getValue().join(' ')}</span>
        ),
      }),
    ],
    [],
  );

  const table = useReactTable({
    data: risks,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="overflow-x-auto rounded-xl border border-surface-border">
      <table className="w-full text-sm text-left">
        <thead className="bg-surface-raised text-slate-400 text-xs uppercase">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => (
                <th key={h.id} className="px-4 py-3 font-medium border-b border-surface-border">
                  {h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="border-b border-surface-border/60 hover:bg-surface-raised/50">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-4 py-2.5 text-slate-300">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {risks.length === 0 ? (
        <p className="p-6 text-slate-500 text-center">No risk flags with current thresholds.</p>
      ) : null}
    </div>
  );
}

export default function App() {
  const [activePage, setActivePage] = useState<'dashboard' | 'forecast'>('dashboard');
  const [health, setHealth] = useState<Health | null>(null);
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [skus, setSkus] = useState<SkuMeta[]>([]);
  const [sku, setSku] = useState('');
  const [risks, setRisks] = useState<Risk[]>([]);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [inf, setInf] = useState<Record<string, unknown> | null>(null);
  const [demandPts, setDemandPts] = useState<
    { date: string; units_sold: number; predicted_units?: number }[]
  >([]);
  const [sigPts, setSigPts] = useState<{ date: string; signal_type: string; volume: number }[]>([]);
  const [simSku, setSimSku] = useState('');
  const [simWh, setSimWh] = useState('W1');
  const [extraOrder, setExtraOrder] = useState(0);
  const [leadDelta, setLeadDelta] = useState(0);
  const [simResult, setSimResult] = useState<{
    points: { day: number; projected_stock: number }[];
    assumptions: string[];
  } | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const ready = health?.demand_predictions_present && health?.inventory_present && health?.signals_present;

  const loadCore = useCallback(async () => {
    setLoading(true);
    setLoadErr(null);
    try {
      const h = await fetchJson<Health>('/api/health');
      setHealth(h);
      if (!h.demand_predictions_present) {
        setLoading(false);
        return;
      }
      const [k, m, r, b, infRes] = await Promise.all([
        fetchJson<Kpis>('/api/kpis/dashboard'),
        fetchJson<{ skus: SkuMeta[] }>('/api/meta/skus'),
        fetchJson<{ risks: Risk[] }>('/api/risk/skus'),
        fetchJson<Brief>('/api/brief/weekly'),
        fetchJson<Record<string, unknown>>('/api/influencer/summary').catch(() => null),
      ]);
      setKpis(k);
      setSkus(m.skus);
      setRisks(r.risks);
      setBrief(b);
      setInf(infRes);
      const first = m.skus[0]?.sku_id ?? '';
      setSku((s) => s || first);
      setSimSku((s) => s || first);
    } catch (e) {
      setLoadErr(e instanceof Error ? e.message : 'Failed to load API');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCore();
  }, [loadCore]);

  useEffect(() => {
    if (!sku || !ready) return;
    void (async () => {
      try {
        const d = await fetchJson<{ points: typeof demandPts }>(
          `/api/demand/timeseries?sku_id=${encodeURIComponent(sku)}`,
        );
        setDemandPts(d.points);
        const s = await fetchJson<{ points: typeof sigPts }>(
          `/api/signals/timeseries?sku_id=${encodeURIComponent(sku)}`,
        );
        const social = s.points.filter((p) => p.signal_type === 'social');
        setSigPts(social.slice(-90));
      } catch {
        setDemandPts([]);
        setSigPts([]);
      }
    })();
  }, [sku, ready]);

  const chartData = useMemo(() => {
    return demandPts.map((p) => ({
      ...p,
      predicted_units: p.predicted_units ?? null,
    }));
  }, [demandPts]);

  const metricsTargets = inf?.metrics as { targets?: Record<string, { rmse: number; mae: number }> } | undefined;
  const barData = metricsTargets?.targets
    ? Object.entries(metricsTargets.targets).map(([name, v]) => ({
        name,
        rmse: v.rmse,
      }))
    : [];

  async function runSim() {
    try {
      const res = await postJson<{
        points: { day: number; projected_stock: number }[];
        assumptions: string[];
      }>('/api/simulate', {
        sku_id: simSku,
        warehouse_id: simWh,
        extra_on_order: extraOrder,
        lead_time_delta_days: leadDelta,
      });
      setSimResult(res);
    } catch (e) {
      setSimResult(null);
      alert(e instanceof Error ? e.message : 'Simulate failed');
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-surface-border bg-surface-raised/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-accent font-medium tracking-wide uppercase">Williams-Sonoma style demo</p>
            <h1 className="font-display text-2xl font-semibold text-white">Supply chain control tower</h1>
          </div>
          <div className="flex items-center gap-3">
            {/* Page tabs */}
            <div className="flex rounded-lg border border-surface-border bg-surface overflow-hidden">
              <button
                id="nav-tab-dashboard"
                type="button"
                onClick={() => setActivePage('dashboard')}
                className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                  activePage === 'dashboard'
                    ? 'bg-accent text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Dashboard
              </button>
              <button
                id="nav-tab-forecast"
                type="button"
                onClick={() => setActivePage('forecast')}
                className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                  activePage === 'forecast'
                    ? 'bg-violet-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                ⚡ Demand Forecast
              </button>
            </div>
            {health ? (
              <span
                className={`text-xs px-3 py-1 rounded-full border ${
                  health.ok ? 'border-ok/40 text-ok bg-ok/10' : 'border-warn/40 text-warn bg-warn/10'
                }`}
              >
                API {health.ok ? 'healthy' : 'degraded'}
              </span>
            ) : null}
            <button
              type="button"
              onClick={() => void loadCore()}
              className="text-sm px-4 py-2 rounded-lg bg-accent text-white hover:bg-blue-500 transition"
            >
              Refresh
            </button>
          </div>
        </div>
      </header>

      {activePage === 'forecast' ? (
        <DemandForecastPage />
      ) : (
        <main className="max-w-7xl mx-auto px-6 py-10 space-y-10">
        {loadErr ? (
          <div className="rounded-lg border border-danger/40 bg-danger/10 text-danger px-4 py-3">
            {loadErr} — is the backend running on port 8000?
          </div>
        ) : null}

        {loading ? (
          <div className="animate-pulse space-y-4">
            <div className="h-32 bg-surface-raised rounded-xl" />
            <div className="h-64 bg-surface-raised rounded-xl" />
          </div>
        ) : !ready ? (
          <EmptyState health={health} />
        ) : (
          <>
            <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <KpiCard
                label="Stockout risk SKUs"
                value={kpis?.stockout_skus ?? '—'}
                hint="Demand vs cover in lead-time window"
                tone="danger"
              />
              <KpiCard
                label="Overstock risk SKUs"
                value={kpis?.overstock_skus ?? '—'}
                hint="High weeks-of-cover + soft trend"
                tone="warn"
              />
              <KpiCard
                label="Signal spikes"
                value={kpis?.signal_spikes ?? '—'}
                hint="WoW intensity uptick (social/search)"
                tone="neutral"
              />
              <KpiCard
                label="Inventory rows"
                value={kpis?.total_inventory_skus ?? '—'}
                hint="SKU × warehouse positions tracked"
                tone="ok"
              />
            </section>

            <section className="grid lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 space-y-4">
                <div className="flex flex-wrap items-end gap-4">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">SKU</label>
                    <select
                      value={sku}
                      onChange={(e) => setSku(e.target.value)}
                      className="bg-surface-raised border border-surface-border rounded-lg px-3 py-2 text-sm text-white min-w-[220px]"
                    >
                      {skus.map((s) => (
                        <option key={s.sku_id} value={s.sku_id}>
                          {s.sku_id} — {s.category}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="rounded-xl border border-surface-border bg-surface-raised p-4 h-80">
                  <h3 className="font-display text-sm font-semibold text-slate-300 mb-2">Demand vs model</h3>
                  <ResponsiveContainer width="100%" height="90%">
                    <ComposedChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#243041" />
                      <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} />
                      <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{ background: '#161d26', border: '1px solid #243041' }}
                        labelStyle={{ color: '#94a3b8' }}
                      />
                      <Legend />
                      <Line type="monotone" dataKey="units_sold" name="Actual" stroke="#34d399" dot={false} strokeWidth={2} />
                      <Line
                        type="monotone"
                        dataKey="predicted_units"
                        name="Predicted"
                        stroke="#3b82f6"
                        dot={false}
                        strokeWidth={2}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
                <div className="rounded-xl border border-surface-border bg-surface-raised p-4 h-64">
                  <h3 className="font-display text-sm font-semibold text-slate-300 mb-2">
                    External signal (social, last 90d)
                  </h3>
                  <ResponsiveContainer width="100%" height="85%">
                    <BarChart data={sigPts}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#243041" />
                      <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 9 }} interval={8} />
                      <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{ background: '#161d26', border: '1px solid #243041' }}
                        labelStyle={{ color: '#94a3b8' }}
                      />
                      <Bar dataKey="volume" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
                <h3 className="font-display text-lg font-semibold text-white">{brief?.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{brief?.summary}</p>
                <ul className="text-sm text-slate-300 space-y-2 list-disc pl-4">
                  {brief?.bullets.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
                <p className="text-xs text-slate-600">Generated {brief?.generated_at}</p>
              </div>
            </section>

            <section>
              <h2 className="font-display text-lg font-semibold text-white mb-4">Unified risk register</h2>
              <RiskTable risks={risks} />
            </section>

            <section className="grid lg:grid-cols-2 gap-6">
              <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
                <h3 className="font-display text-lg font-semibold text-white">What-if simulation</h3>
                <p className="text-slate-500 text-sm">
                  Linear drawdown using recent predicted/actual run-rate — illustrates expedite vs extra PO.
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-500">SKU</label>
                    <select
                      value={simSku}
                      onChange={(e) => setSimSku(e.target.value)}
                      className="w-full mt-1 bg-surface border border-surface-border rounded-lg px-2 py-2 text-sm"
                    >
                      {skus.map((s) => (
                        <option key={s.sku_id} value={s.sku_id}>
                          {s.sku_id}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">Warehouse</label>
                    <input
                      value={simWh}
                      onChange={(e) => setSimWh(e.target.value)}
                      className="w-full mt-1 bg-surface border border-surface-border rounded-lg px-2 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">Extra on order</label>
                    <input
                      type="number"
                      value={extraOrder}
                      onChange={(e) => setExtraOrder(Number(e.target.value))}
                      className="w-full mt-1 bg-surface border border-surface-border rounded-lg px-2 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">Lead time delta (days)</label>
                    <input
                      type="number"
                      value={leadDelta}
                      onChange={(e) => setLeadDelta(Number(e.target.value))}
                      className="w-full mt-1 bg-surface border border-surface-border rounded-lg px-2 py-2 text-sm"
                    />
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => void runSim()}
                  className="w-full py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium"
                >
                  Run simulation
                </button>
                {simResult ? (
                  <div className="text-xs text-slate-400 space-y-2">
                    {simResult.assumptions.map((a) => (
                      <p key={a}>{a}</p>
                    ))}
                    <ResponsiveContainer width="100%" height={160}>
                      <BarChart data={simResult.points}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#243041" />
                        <XAxis dataKey="day" tick={{ fill: '#64748b', fontSize: 10 }} />
                        <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                        <Tooltip
                          contentStyle={{ background: '#161d26', border: '1px solid #243041' }}
                          labelStyle={{ color: '#94a3b8' }}
                        />
                        <Bar dataKey="projected_stock" fill="#10b981" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : null}
              </div>

              <div className="rounded-xl border border-surface-border bg-surface-raised p-5">
                <h3 className="font-display text-lg font-semibold text-white mb-2">Influencer models (MODEL2)</h3>
                <p className="text-slate-500 text-sm mb-4">
                  Targets loaded in API: <strong className="text-slate-300">{health?.model2_targets_loaded ?? 0}</strong>
                </p>
                {barData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={barData} layout="vertical" margin={{ left: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#243041" />
                      <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} />
                      <YAxis type="category" dataKey="name" width={100} tick={{ fill: '#94a3b8', fontSize: 9 }} />
                      <Tooltip
                        contentStyle={{ background: '#161d26', border: '1px solid #243041' }}
                        labelStyle={{ color: '#94a3b8' }}
                      />
                      <Bar dataKey="rmse" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-slate-500 text-sm">
                    Run MODEL2 training and ETL to create <code className="text-slate-400">influencer_metrics.json</code>.
                  </p>
                )}
              </div>
            </section>
          </>
        )}
        </main>
      )}
    </div>
  );
}
