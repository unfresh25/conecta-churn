"use client";

import { useMemo, useState } from "react";
import {
  CONTACT_COST, EFFECTIVENESS, PLANS, PRICES, expectedValue, score, threshold,
  type Client, type Decision, type Plan, type Risk, type Scored,
} from "../lib/business";
import { cop, int, pct, signed } from "../lib/format";

const SEGMENTS = ["Personal", "Pyme"];
const PLAN_LABEL: Record<Plan, string> = { Basico: "Básico", Estandar: "Estándar", Premium: "Premium", Familiar: "Familiar" };
const PLATFORMS: Record<string, string> = { android: "Android", ios: "iOS", web: "Web" };
const VIEWS = ["A llamar", "Todos", "En proceso de baja", "Usan la app 5.2.0"] as const;
type View = (typeof VIEWS)[number];
const PAGE_SIZE = 25;

const RISK_CLASS: Record<Risk, string> = { Alto: "red", Medio: "amber", Bajo: "grey" };
const DECISION_CLASS: Record<Decision, string> = { Llamar: "blue", "No llamar": "grey", "En proceso de baja": "violet" };
const RISK_COLOR: Record<Risk, string> = { Alto: "var(--red)", Medio: "var(--amber)", Bajo: "var(--muted)" };

function toggle<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}

const factorsOf = (c: Client) => [c.factor_1, c.factor_2, c.factor_3].filter((f): f is string => !!f);

export default function Dashboard({ clients }: { clients: Client[] }) {
  const [effectiveness, setEffectiveness] = useState(EFFECTIVENESS);
  const [cost, setCost] = useState(CONTACT_COST);
  const [costText, setCostText] = useState(String(CONTACT_COST));
  const [plans, setPlans] = useState<Plan[]>(PLANS);
  const [segments, setSegments] = useState<string[]>(SEGMENTS);
  const [platforms, setPlatforms] = useState<string[]>(Object.keys(PLATFORMS));
  const [tab, setTab] = useState<"list" | "summary" | "rule">("list");
  const [view, setView] = useState<View>("A llamar");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const filtered = useMemo(
    () => clients.filter((c) => plans.includes(c.plan) && segments.includes(c.segmento) && platforms.includes(c.plataforma)),
    [clients, plans, segments, platforms],
  );
  const scored = useMemo(() => score(filtered, effectiveness, cost), [filtered, effectiveness, cost]);
  const base = useMemo(() => score(filtered, EFFECTIVENESS, CONTACT_COST), [filtered]);
  const changed = effectiveness !== EFFECTIVENESS || cost !== CONTACT_COST;

  const calls = scored.filter((c) => c.call);
  const net = calls.reduce((s, c) => s + c.value, 0);
  const baseCalls = base.filter((c) => c.call);
  const baseNet = baseCalls.reduce((s, c) => s + c.value, 0);
  const meanP = scored.reduce((s, c) => s + c.probabilidad, 0) / Math.max(scored.length, 1);

  const viewFilter: Record<View, (c: Scored) => boolean> = {
    "A llamar": (c) => c.call,
    Todos: () => true,
    "En proceso de baja": (c) => c.en_proceso === 1,
    "Usan la app 5.2.0": (c) => c.usa_520 === 1,
  };
  const rows = useMemo(() => {
    const q = query.trim();
    return scored
      .filter(viewFilter[view])
      .filter((c) => !q || String(c.cliente_id).startsWith(q))
      .sort((a, b) => b.value - a.value || b.probabilidad - a.probabilidad);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scored, view, query]);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const pageRows = rows.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE);
  const selected = rows.find((c) => c.cliente_id === selectedId) ?? rows[0];

  const resetFilters = () => {
    setPlans(PLANS); setSegments(SEGMENTS); setPlatforms(Object.keys(PLATFORMS)); setPage(0);
  };
  const resetAssumptions = () => { setEffectiveness(EFFECTIVENESS); setCost(CONTACT_COST); setCostText(String(CONTACT_COST)); };

  function downloadCsv() {
    const header = ["cliente_id", "plan", "segmento", "plataforma", "probabilidad", "valor_esperado", "decision", "factor_1", "factor_2", "factor_3"];
    const lines = rows.map((c) =>
      [c.cliente_id, c.plan, c.segmento, PLATFORMS[c.plataforma] ?? c.plataforma, c.probabilidad.toFixed(4), Math.round(c.value),
        c.decision, c.factor_1 ?? "", c.factor_2 ?? "", c.factor_3 ?? ""]
        .map((v) => `"${String(v).replaceAll('"', '""')}"`).join(","));
    const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "lista_contacto.csv" });
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">C+</span>Conecta+ · Retención</div>

        <section>
          <div className="side-title">Supuestos</div>
          <div className="field">
            <div className="field-row">
              <label htmlFor="eff">Efectividad de la llamada</label>
              <output htmlFor="eff">{pct(effectiveness)}</output>
            </div>
            <input id="eff" type="range" min={0.05} max={0.8} step={0.05} value={effectiveness}
              onChange={(e) => setEffectiveness(Number(e.target.value))} />
            <span className="hint">De los que se iban a ir, cuántos retiene la llamada. El enunciado supone 40 %.</span>
          </div>
          <div className="field">
            <label htmlFor="cost">Costo por llamada (COP)</label>
            <input id="cost" className="number" type="number" min={5000} max={100000} step={5000} value={costText}
              onChange={(e) => { setCostText(e.target.value); const v = Number(e.target.value); if (v >= 1000) setCost(v); }}
              onBlur={() => setCostText(String(cost))} />
          </div>
          {changed && <button className="reset" onClick={resetAssumptions}>Volver a los supuestos del enunciado</button>}
        </section>

        <section>
          <div className="side-title">Filtros</div>
          <div className="field">
            <label>Plan</label>
            <div className="chips">
              {PLANS.map((p) => (
                <button key={p} className="chip" aria-pressed={plans.includes(p)}
                  onClick={() => { setPlans(toggle(plans, p)); setPage(0); }}>{PLAN_LABEL[p]}</button>
              ))}
            </div>
          </div>
          <div className="field">
            <label>Segmento</label>
            <div className="chips">
              {SEGMENTS.map((s) => (
                <button key={s} className="chip" aria-pressed={segments.includes(s)}
                  onClick={() => { setSegments(toggle(segments, s)); setPage(0); }}>{s}</button>
              ))}
            </div>
          </div>
          <div className="field">
            <label>Plataforma</label>
            <div className="chips">
              {Object.entries(PLATFORMS).map(([k, label]) => (
                <button key={k} className="chip" aria-pressed={platforms.includes(k)}
                  onClick={() => { setPlatforms(toggle(platforms, k)); setPage(0); }}>{label}</button>
              ))}
            </div>
          </div>
          <button className="reset" onClick={resetFilters}>Quitar filtros</button>
        </section>

        <p className="side-foot">
          Puntaje al 31-dic-2025 del modelo final (LightGBM, sección 7 de solucion.ipynb). Sin ciudad, edad ni textos de tickets.
        </p>
      </aside>

      <main className="main">
        <header className="header">
          <h1>Campaña de retención · enero de 2026</h1>
          <p>A quién llamar este mes, cuánto se espera ganar y por qué cada cliente está en riesgo.</p>
        </header>

        <section className="kpis" aria-label="Indicadores">
          <Kpi label="Clientes activos" value={int(scored.length)} />
          <Kpi label="A llamar" value={int(calls.length)}
            delta={changed ? signed(calls.length - baseCalls.length, int) : undefined} trend={calls.length - baseCalls.length} />
          <Kpi label="Costo de las llamadas" value={cop(calls.length * cost)} />
          <Kpi label="Valor esperado neto" value={cop(net)}
            delta={changed ? signed(net - baseNet, cop) : undefined} trend={net - baseNet} />
          <Kpi label="Riesgo medio de baja" value={pct(meanP, 1)} delta="últimos cortes: 16,2 %" />
        </section>
        <p className="note">
          El valor esperado ya descuenta el costo de las llamadas.
          {changed && ` Los cambios se comparan con los supuestos del enunciado (40 % y ${int(CONTACT_COST)} COP).`}
        </p>

        <nav className="tabs" role="tablist">
          {([["list", "Lista de contacto"], ["summary", "Resumen"], ["rule", "Cómo se decide"]] as const).map(([k, label]) => (
            <button key={k} role="tab" className="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{label}</button>
          ))}
        </nav>

        {tab === "list" && (
          <>
            <div className="toolbar">
              <div className="segmented">
                {VIEWS.map((v) => (
                  <button key={v} aria-pressed={view === v} onClick={() => { setView(v); setPage(0); setSelectedId(null); }}>
                    {v}<span className="count">{int(scored.filter(viewFilter[v]).length)}</span>
                  </button>
                ))}
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <input className="search" inputMode="numeric" placeholder="Buscar por número de cliente" value={query}
                  onChange={(e) => { setQuery(e.target.value.replace(/\D/g, "")); setPage(0); }} />
                <button className="btn" onClick={downloadCsv}>Descargar CSV</button>
              </div>
            </div>

            <div className="split">
              <div className="card">
                {rows.length === 0 ? (
                  <div className="empty">No hay clientes con estos filtros.</div>
                ) : (
                  <>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Cliente</th><th>Plan</th><th>Plataforma</th><th>Riesgo de baja</th>
                            <th className="num">Valor esperado</th><th>Decisión</th><th>Motivo principal</th>
                          </tr>
                        </thead>
                        <tbody>
                          {pageRows.map((c) => (
                            <tr key={c.cliente_id} aria-selected={selected?.cliente_id === c.cliente_id}
                              onClick={() => setSelectedId(c.cliente_id)}>
                              <td>{c.cliente_id}</td>
                              <td>{PLAN_LABEL[c.plan]}</td>
                              <td>{PLATFORMS[c.plataforma] ?? c.plataforma}</td>
                              <td>
                                <div className="meter">
                                  <div className="meter-track">
                                    <div className="meter-fill" style={{ width: `${Math.min(c.probabilidad, 1) * 100}%`, background: RISK_COLOR[c.risk] }} />
                                  </div>
                                  <span>{pct(c.probabilidad)}</span>
                                </div>
                              </td>
                              <td className="num">{cop(c.value)}</td>
                              <td><span className={`badge ${DECISION_CLASS[c.decision]}`}>{c.decision}</span></td>
                              <td className="reason" title={c.factor_1 ?? ""}>{c.factor_1 ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="pager">
                      <span>{int(rows.length)} clientes, ordenados por valor esperado · página {current + 1} de {pages}</span>
                      <div className="pager-buttons">
                        <button className="btn" disabled={current === 0} onClick={() => setPage(current - 1)}>Anterior</button>
                        <button className="btn" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>Siguiente</button>
                      </div>
                    </div>
                  </>
                )}
              </div>
              {selected && <Detail c={selected} effectiveness={effectiveness} cost={cost} />}
            </div>
          </>
        )}

        {tab === "summary" && <Summary scored={scored} plans={plans} effectiveness={effectiveness} cost={cost} />}
        {tab === "rule" && <Rule effectiveness={effectiveness} cost={cost} />}
      </main>
    </div>
  );
}

function Kpi({ label, value, delta, trend = 0 }: { label: string; value: string; delta?: string; trend?: number }) {
  const cls = delta && trend !== 0 ? (trend > 0 ? "up" : "down") : "";
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      <div className={`kpi-delta ${cls}`}>{delta ?? " "}</div>
    </div>
  );
}

function Detail({ c, effectiveness, cost }: { c: Scored; effectiveness: number; cost: number }) {
  const explain: Record<Decision, string> = {
    Llamar: "Su riesgo supera el umbral de su plan: con estos supuestos, la llamada se paga sola.",
    "No llamar": "Su riesgo no alcanza el umbral de su plan: la llamada costaría más de lo que se espera retener.",
    "En proceso de baja":
      "Ya lo atiende el flujo de baja (llamada del equipo en los últimos 30 días o ticket de cancelar en 90). Casi todos esos clientes se van igual, así que no se recomienda llamarlo.",
  };
  const factors = factorsOf(c);
  return (
    <aside className="card detail" aria-label="Ficha del cliente">
      <h2>Cliente {c.cliente_id}</h2>
      <div className="badges">
        <span className={`badge ${DECISION_CLASS[c.decision]}`}>{c.decision}</span>
        <span className={`badge ${RISK_CLASS[c.risk]}`}>Riesgo {c.risk.toLowerCase()}</span>
        <span className="badge grey plain">{PLAN_LABEL[c.plan]}</span>
        <span className="badge grey plain">{c.segmento}</span>
        <span className="badge grey plain">{PLATFORMS[c.plataforma] ?? c.plataforma}</span>
      </div>
      <div className="stats">
        <div className="stat"><div className="stat-label">Riesgo de baja</div><div className="stat-value">{pct(c.probabilidad)}</div></div>
        <div className="stat"><div className="stat-label">Umbral del plan</div><div className="stat-value">{pct(threshold(c.plan, cost, effectiveness))}</div></div>
        <div className="stat"><div className="stat-label">Valor esperado</div><div className="stat-value">{cop(c.value)}</div></div>
      </div>
      <p className="explain">{explain[c.decision]}</p>
      <div className="section-title">Qué sube su riesgo</div>
      {factors.length ? (
        <ol className="factors">
          {factors.map((f, i) => <li key={f}><span className="n">{i + 1}</span>{f}</li>)}
        </ol>
      ) : <p className="explain">Ningún factor sube su riesgo.</p>}
      <p className="hint">Las tres variables que más suben su probabilidad según SHAP, con su valor.</p>
    </aside>
  );
}

function BarList({ items, color, format }: { items: { label: string; value: number; note?: string }[]; color: string; format: (v: number) => string }) {
  const max = Math.max(...items.map((i) => i.value), 1e-9);
  return (
    <div className="barlist">
      {items.map((i) => (
        <div className="bar-row" key={i.label}>
          <div className="bar-fill" style={{ width: `${(i.value / max) * 100}%`, background: color }} />
          <span>{i.label}{i.note && <span className="hint"> · {i.note}</span>}</span>
          <span className="v">{format(i.value)}</span>
        </div>
      ))}
    </div>
  );
}

function Summary({ scored, plans, effectiveness, cost }: { scored: Scored[]; plans: Plan[]; effectiveness: number; cost: number }) {
  const byPlan = PLANS.filter((p) => plans.includes(p)).map((p) => {
    const g = scored.filter((c) => c.plan === p);
    return { label: PLAN_LABEL[p], value: g.length ? g.filter((c) => c.call).length / g.length : 0,
      note: `umbral ${pct(threshold(p, cost, effectiveness), 1)}` };
  });
  const counts = new Map<string, number>();
  for (const c of scored) {
    if (!c.call || !c.factor_1) continue;
    const key = c.factor_1.split(":")[0];
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const reasons = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([label, value]) => ({ label, value }));
  const bySegment = SEGMENTS.map((s) => {
    const g = scored.filter((c) => c.segmento === s && c.call);
    return { label: s, value: g.reduce((t, c) => t + c.value, 0), note: `${int(g.length)} llamadas` };
  }).filter((s) => s.note !== "0 llamadas");

  return (
    <>
      <div className="grid2">
        <section className="card panel">
          <h3>A quién se llama, por plan</h3>
          <BarList items={byPlan} color="var(--accent)" format={(v) => pct(v)} />
          <p className="hint">Los planes caros tienen un umbral más bajo: retener a un cliente Familiar vale 2,5 veces lo que uno Básico.</p>
        </section>
        <section className="card panel">
          <h3>Motivos más frecuentes entre los clientes a llamar</h3>
          {reasons.length ? <BarList items={reasons} color="var(--orange)" format={int} /> : <p className="hint">Nadie a llamar con estos supuestos.</p>}
          <p className="hint">El motivo principal de cada cliente es la variable que más sube su probabilidad.</p>
        </section>
      </div>
      <div className="grid2">
        <section className="card panel curve">
          <h3>Cuánto depende el resultado de la efectividad</h3>
          <Curve scored={scored} effectiveness={effectiveness} cost={cost} />
          <p className="hint">
            La línea punteada es la efectividad elegida. Las llamadas actuales del equipo, que llegan tarde, retienen cerca del 3 %:
            por eso conviene medir la efectividad real con un piloto antes de escalar.
          </p>
        </section>
        <section className="card panel">
          <h3>Valor esperado neto por segmento</h3>
          {bySegment.length ? <BarList items={bySegment} color="var(--accent)" format={cop} /> : <p className="hint">Nadie a llamar con estos supuestos.</p>}
        </section>
      </div>
    </>
  );
}

function Curve({ scored, effectiveness, cost }: { scored: Scored[]; effectiveness: number; cost: number }) {
  const eligible = scored.filter((c) => c.en_proceso !== 1);
  const points = Array.from({ length: 16 }, (_, i) => {
    const e = Math.round((0.05 + i * 0.05) * 100) / 100;
    const vals = eligible.map((c) => expectedValue(c.probabilidad, c.plan, cost, e)).filter((v) => v > 0);
    return { e, value: vals.reduce((s, v) => s + v, 0), calls: vals.length };
  });
  const W = 520, H = 220, L = 52, R = 12, T = 12, B = 30;
  const maxV = Math.max(...points.map((p) => p.value), 1);
  const x = (e: number) => L + ((e - 0.05) / 0.75) * (W - L - R);
  const y = (v: number) => T + (1 - v / maxV) * (H - T - B);
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(p.e).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
  const ticks = [0, 0.5, 1].map((f) => f * maxV);
  const here = points.reduce((a, b) => (Math.abs(b.e - effectiveness) < Math.abs(a.e - effectiveness) ? b : a));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Valor esperado neto según la efectividad de la llamada">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="var(--line)" />
          <text x={L - 6} y={y(t) + 4} textAnchor="end">{cop(t)}</text>
        </g>
      ))}
      {[0.1, 0.2, 0.4, 0.6, 0.8].map((e) => <text key={e} x={x(e)} y={H - 10} textAnchor="middle">{pct(e)}</text>)}
      <line x1={x(effectiveness)} x2={x(effectiveness)} y1={T} y2={H - B} stroke="var(--muted)" strokeDasharray="4 4" />
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2} />
      <circle cx={x(here.e)} cy={y(here.value)} r={4.5} fill="var(--accent)" />
      <text x={Math.min(x(here.e) + 8, W - 150)} y={Math.max(y(here.value) - 8, T + 10)} style={{ fill: "var(--ink)", fontWeight: 600 }}>
        {cop(here.value)} · {int(here.calls)} llamadas
      </text>
    </svg>
  );
}

function Rule({ effectiveness, cost }: { effectiveness: number; cost: number }) {
  return (
    <section className="card rules">
      <p>
        Por cada cliente, el modelo estima la probabilidad de que se vaya en los próximos 90 días. Llamarlo conviene si lo que se espera
        retener supera el costo de la llamada:
      </p>
      <div className="formula">probabilidad × efectividad × 12 × precio del plan &gt; costo de la llamada</div>
      <p>Con los supuestos actuales (efectividad {pct(effectiveness)}, costo {int(cost)} COP), el umbral de cada plan es:</p>
      <table className="mini">
        <thead><tr><th>Plan</th><th className="num">Precio mensual</th><th className="num">Umbral</th></tr></thead>
        <tbody>
          {PLANS.map((p) => (
            <tr key={p} style={{ cursor: "default" }}>
              <td>{PLAN_LABEL[p]}</td><td className="num">{int(PRICES[p])}</td><td className="num">{pct(threshold(p, cost, effectiveness), 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul>
        <li>No se llama a quien ya está en proceso de baja (llamada del equipo en los últimos 30 días o ticket de cancelar en los últimos 90): lo atiende el flujo actual y casi todos se van igual.</li>
        <li>El valor esperado ya descuenta el costo de la llamada. Si es negativo, la llamada cuesta más de lo que se espera retener.</li>
        <li>La efectividad del 40 % es un supuesto del enunciado y es lo que más pesa en el resultado. El piloto con grupo de control propuesto en el memo sirve para reemplazarlo por la efectividad medida.</li>
      </ul>
    </section>
  );
}
