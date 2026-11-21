"use client";

import { useMemo, useRef, useState } from "react";
import {
  Button, Chip, Drawer, Dropdown, Label, Meter, NumberField, Pagination, Popover, SearchField, Slider, Table, Tabs,
  type Selection,
} from "@heroui/react";
import {
  CONTACT_COST, EFFECTIVENESS, PLANS, PRICES, expectedValue, score, threshold,
  type Client, type Decision, type Plan, type Risk, type Scored,
} from "../lib/business";
import { cop, copM, int, pct, signed } from "../lib/format";

const COLAB_URL = "https://colab.research.google.com/github/unfresh25/conecta-churn/blob/main/solucion.ipynb";
const REPO_URL = "https://github.com/unfresh25/conecta-churn";
const PLAN_LABEL: Record<Plan, string> = { Basico: "Básico", Estandar: "Estándar", Premium: "Premium", Familiar: "Familiar" };
const SEGMENTS: Record<string, string> = { Personal: "Personal", Pyme: "Pyme" };
const PLATFORMS: Record<string, string> = { android: "Android", ios: "iOS", web: "Web" };
const VIEWS = ["A llamar", "Todos", "En proceso de baja", "Usan la app 5.2.0"] as const;
type View = (typeof VIEWS)[number];
type Page = "summary" | "clients" | "rule";
const PAGE_SIZE = 12;

const RISK_COLOR: Record<Risk, "danger" | "warning" | "default"> = { Alto: "danger", Medio: "warning", Bajo: "default" };
const DECISION_COLOR: Record<Decision, "accent" | "default" | "warning"> = {
  Llamar: "accent", "No llamar": "default", "En proceso de baja": "warning",
};
const VIEW_FILTER: Record<View, (c: Scored) => boolean> = {
  "A llamar": (c) => c.call,
  Todos: () => true,
  "En proceso de baja": (c) => c.en_proceso === 1,
  "Usan la app 5.2.0": (c) => c.usa_520 === 1,
};

type Filters = { plans: Set<string>; segments: Set<string>; platforms: Set<string>; reason: string | null };
const ALL_FILTERS: Filters = {
  plans: new Set(PLANS), segments: new Set(Object.keys(SEGMENTS)), platforms: new Set(Object.keys(PLATFORMS)), reason: null,
};

const factorsOf = (c: Client) => [c.factor_1, c.factor_2, c.factor_3].filter((f): f is string => !!f);
const reasonOf = (c: Client) => (c.factor_1 ? c.factor_1.split(":")[0] : "");
const asSet = (keys: Selection, all: string[]) => (keys === "all" ? new Set(all) : new Set([...keys].map(String)));

// ------------------------------------------------------------------------------------------------ iconos
function Icon({ d, className = "size-4" }: { d: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"
      className={className} aria-hidden>
      <path d={d} />
    </svg>
  );
}
const ICONS = {
  chart: "M4 19V5M4 19h16M8 15v-4M12 15V8M16 15v-6",
  users: "M16 19v-1a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v1M9.5 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6M21 19v-1a4 4 0 0 0-3-3.9M15 4.1a3 3 0 0 1 0 5.8",
  book: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5zM8 7h7",
  plus: "M12 5v14M5 12h14",
  x: "M6 6l12 12M18 6L6 18",
  download: "M12 4v11M7 10l5 5 5-5M5 20h14",
  sliders: "M4 7h10M18 7h2M4 17h4M12 17h8M14 4v6M8 14v6",
  arrow: "M9 6l6 6-6 6",
  github: "M9 19c-4 1.3-4-2-6-2.5M15 21v-3.4a3 3 0 0 0-.8-2.3c2.8-.3 5.8-1.4 5.8-6.2a4.8 4.8 0 0 0-1.3-3.3 4.5 4.5 0 0 0-.1-3.3s-1-.3-3.4 1.3a11.6 11.6 0 0 0-6.2 0C6.6 1.9 5.6 2.2 5.6 2.2a4.5 4.5 0 0 0-.1 3.3A4.8 4.8 0 0 0 4.2 8.8c0 4.8 3 5.9 5.8 6.2a3 3 0 0 0-.8 2.3V21",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
};

function ColabBadge() {
  return (
    <a href={COLAB_URL} target="_blank" rel="noreferrer" className="inline-flex shrink-0">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab" width={117} height={20} />
    </a>
  );
}

function SectionTitle({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="mb-3">
      <h2 className="text-[15px] font-semibold text-zinc-900">{title}</h2>
      {hint && <p className="mt-0.5 text-sm text-zinc-500">{hint}</p>}
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ página
export default function Dashboard({ clients }: { clients: Client[] }) {
  const [page, setPage] = useState<Page>("summary");
  const [effectiveness, setEffectiveness] = useState(EFFECTIVENESS);
  const [cost, setCost] = useState(CONTACT_COST);
  const [filters, setFilters] = useState<Filters>(ALL_FILTERS);
  const [view, setView] = useState<View>("A llamar");

  const scored = useMemo(() => score(clients, effectiveness, cost), [clients, effectiveness, cost]);
  const base = useMemo(() => score(clients, EFFECTIVENESS, CONTACT_COST), [clients]);
  const changed = effectiveness !== EFFECTIVENESS || cost !== CONTACT_COST;

  const openClients = (patch: Partial<Filters>, nextView: View = "A llamar") => {
    setFilters({ ...ALL_FILTERS, ...patch });
    setView(nextView);
    setPage("clients");
  };

  const nav: { id: Page; label: string; icon: string }[] = [
    { id: "summary", label: "Resumen", icon: ICONS.chart },
    { id: "clients", label: "Clientes", icon: ICONS.users },
    { id: "rule", label: "Cómo se decide", icon: ICONS.book },
  ];
  const title = nav.find((n) => n.id === page)!.label;

  return (
    <div className="flex min-h-screen bg-white">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-zinc-50 px-3 py-5 md:flex">
        <div className="flex items-center gap-2 px-2 pb-6">
          <span className="grid size-7 place-items-center rounded-lg bg-zinc-900 text-[11px] font-bold text-white">C+</span>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-zinc-900">Conecta+</div>
            <div className="text-xs text-zinc-500">Retención</div>
          </div>
        </div>
        <nav className="flex flex-col gap-0.5">
          {nav.map((n) => (
            <button key={n.id} onClick={() => setPage(n.id)}
              className={`flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors ${
                page === n.id ? "bg-zinc-200/70 font-medium text-zinc-900" : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"}`}>
              <Icon d={n.icon} />{n.label}
            </button>
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-3 px-2 text-xs leading-relaxed text-zinc-500">
          <p>Riesgo calculado con los datos hasta el 31 de diciembre de 2025.</p>
          <ColabBadge />
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 hover:text-zinc-900">
            <Icon d={ICONS.github} className="size-3.5" />Repositorio
          </a>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between gap-3 bg-white/90 px-4 backdrop-blur md:px-10">
          <div className="flex min-w-0 items-center gap-2 text-sm">
            <span className="hidden text-zinc-500 sm:inline">Campaña de enero de 2026</span>
            <span className="hidden text-zinc-300 sm:inline">/</span>
            <span className="font-medium text-zinc-900">{title}</span>
          </div>
          <Assumptions effectiveness={effectiveness} cost={cost} changed={changed}
            onEffectiveness={setEffectiveness} onCost={setCost}
            onReset={() => { setEffectiveness(EFFECTIVENESS); setCost(CONTACT_COST); }} />
        </header>

        <nav className="flex items-center gap-1 px-4 pb-2 md:hidden">
          {nav.map((n) => (
            <Button key={n.id} size="sm" variant={page === n.id ? "secondary" : "ghost"} onPress={() => setPage(n.id)}>{n.label}</Button>
          ))}
          <span className="ml-auto"><ColabBadge /></span>
        </nav>

        <main className="mx-auto w-full max-w-[1180px] px-4 pb-16 pt-6 md:px-10">
          {page === "summary" && (
            <Summary scored={scored} base={base} changed={changed} effectiveness={effectiveness} cost={cost}
              onEffectiveness={setEffectiveness} onOpen={openClients} />
          )}
          {page === "clients" && (
            <Clients scored={scored} effectiveness={effectiveness} cost={cost} filters={filters} setFilters={setFilters}
              view={view} setView={setView} />
          )}
          {page === "rule" && <Rule effectiveness={effectiveness} cost={cost} />}
        </main>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ supuestos
function Assumptions(props: {
  effectiveness: number; cost: number; changed: boolean;
  onEffectiveness: (v: number) => void; onCost: (v: number) => void; onReset: () => void;
}) {
  return (
    <Popover>
      <Popover.Trigger>
        <Button size="sm" variant={props.changed ? "primary" : "ghost"}>
          <Icon d={ICONS.sliders} />
          Supuestos · {pct(props.effectiveness)} · {int(props.cost)} COP
        </Button>
      </Popover.Trigger>
      <Popover.Content placement="bottom end" className="w-80">
        <Popover.Dialog className="flex flex-col gap-5 p-4">
          <div>
            <Popover.Heading className="text-sm font-semibold">Supuestos de la campaña</Popover.Heading>
            <p className="mt-1 text-xs text-zinc-500">Cambian el umbral de cada plan y, con él, la lista. El enunciado usa 40 % y 25.000 COP.</p>
          </div>
          <Slider value={props.effectiveness} onChange={(v) => props.onEffectiveness(v as number)} minValue={0.05} maxValue={0.8}
            step={0.05} formatOptions={{ style: "percent" }} className="w-full">
            <div className="flex justify-between"><Label>Efectividad de la llamada</Label><Slider.Output /></div>
            <Slider.Track><Slider.Fill /><Slider.Thumb /></Slider.Track>
          </Slider>
          <NumberField value={props.cost} onChange={(v) => props.onCost(v && v >= 1000 ? v : CONTACT_COST)} minValue={1000}
            maxValue={200000} step={5000} formatOptions={{ maximumFractionDigits: 0 }}>
            <Label>Costo por llamada (COP)</Label>
            <NumberField.Group>
              <NumberField.DecrementButton />
              <NumberField.Input />
              <NumberField.IncrementButton />
            </NumberField.Group>
          </NumberField>
          {props.changed && <Button size="sm" variant="ghost" onPress={props.onReset}>Volver a los supuestos del enunciado</Button>}
        </Popover.Dialog>
      </Popover.Content>
    </Popover>
  );
}

// ------------------------------------------------------------------------------------------------ resumen
type Metric = "value" | "calls";

function Summary({ scored, base, changed, effectiveness, cost, onEffectiveness, onOpen }: {
  scored: Scored[]; base: Scored[]; changed: boolean; effectiveness: number; cost: number;
  onEffectiveness: (v: number) => void; onOpen: (patch: Partial<Filters>, view?: View) => void;
}) {
  const [metric, setMetric] = useState<Metric>("value");
  const calls = scored.filter((c) => c.call);
  const net = calls.reduce((s, c) => s + c.value, 0);
  const baseCalls = base.filter((c) => c.call);
  const baseNet = baseCalls.reduce((s, c) => s + c.value, 0);
  const meanP = scored.reduce((s, c) => s + c.probabilidad, 0) / scored.length;

  const byPlan = PLANS.map((p) => {
    const g = scored.filter((c) => c.plan === p);
    const n = g.filter((c) => c.call).length;
    return { key: p, label: PLAN_LABEL[p], sub: `umbral ${pct(threshold(p, cost, effectiveness), 1)}`, value: n / g.length,
      shown: `${int(n)} · ${pct(n / g.length)}`, open: () => onOpen({ plans: new Set([p]) }) };
  });
  const reasonCount = new Map<string, number>();
  for (const c of calls) if (c.factor_1) reasonCount.set(reasonOf(c), (reasonCount.get(reasonOf(c)) ?? 0) + 1);
  const reasons = [...reasonCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6)
    .map(([label, n]) => ({ key: label, label, value: n, shown: int(n), open: () => onOpen({ reason: label }) }));
  const group = (field: "segmento" | "plataforma", labels: Record<string, string>) =>
    Object.entries(labels).map(([k, label]) => {
      const g = calls.filter((c) => c[field] === k);
      const v = g.reduce((s, c) => s + c.value, 0);
      return { key: k, label, value: v, shown: copM(v), sub: `${int(g.length)} llamadas`,
        open: () => onOpen(field === "segmento" ? { segments: new Set([k]) } : { platforms: new Set([k]) }) };
    });

  const kpis: { label: string; value: string; note: string; metric?: Metric; onClick?: () => void }[] = [
    { label: "Clientes activos", value: int(scored.length), note: "ver todos", onClick: () => onOpen({}, "Todos") },
    { label: "A llamar", value: int(calls.length), metric: "calls",
      note: changed ? `${signed(calls.length - baseCalls.length, int)} vs. enunciado` : `${pct(calls.length / scored.length)} de los clientes` },
    { label: "Valor esperado neto", value: cop(net), metric: "value",
      note: changed ? `${signed(net - baseNet, cop)} vs. enunciado` : "ya descuenta el costo" },
    { label: "Costo de las llamadas", value: cop(calls.length * cost), note: `${int(cost)} COP por llamada` },
    { label: "Riesgo medio de baja", value: pct(meanP, 1), note: "últimos meses: 16,2 %" },
  ];

  return (
    <div className="flex flex-col gap-12">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Resumen de la campaña</h1>
        <p className="mt-1 text-sm text-zinc-500">A quién llamar en enero, cuánto se espera ganar y de qué depende.</p>
      </div>

      <section>
        <div className="grid grid-cols-2 gap-x-6 gap-y-5 lg:grid-cols-5">
          {kpis.map((k) => {
            const selectable = k.metric !== undefined;
            const active = selectable && metric === k.metric;
            const Tag = selectable || k.onClick ? "button" : "div";
            return (
              <Tag key={k.label} onClick={k.metric ? () => setMetric(k.metric!) : k.onClick}
                className={`group text-left ${selectable || k.onClick ? "cursor-pointer" : ""}`}>
                <div className={`text-xs font-medium ${active ? "text-indigo-600" : "text-zinc-500"}`}>{k.label}</div>
                <div className="mt-1 text-[26px] font-semibold tracking-tight text-zinc-900">{k.value}</div>
                <div className={`mt-0.5 text-xs ${k.onClick ? "text-indigo-600 group-hover:underline" : "text-zinc-500"}`}>{k.note}</div>
                <div className={`mt-3 h-0.5 rounded-full ${active ? "bg-indigo-500" : selectable ? "bg-zinc-100 group-hover:bg-zinc-200" : "bg-transparent"}`} />
              </Tag>
            );
          })}
        </div>

        <div className="mt-6">
          <Curve scored={scored} effectiveness={effectiveness} cost={cost} metric={metric} onPick={onEffectiveness} />
          <p className="mt-2 text-xs text-zinc-500">
            Pasa el cursor para ver cada nivel de efectividad y haz clic para usarlo. Las llamadas actuales, que llegan tarde, retienen
            cerca del 3 %.
          </p>
        </div>
      </section>

      <div className="grid gap-x-14 gap-y-12 lg:grid-cols-2">
        <BarList title="A quién se llama, por plan" hint="Los planes caros tienen un umbral más bajo." head={["Plan", "A llamar"]}
          rows={byPlan} color="bg-indigo-500/12" />
        <BarList title="Motivo principal" hint="La variable que más sube el riesgo de cada cliente a llamar." head={["Motivo", "Clientes"]}
          rows={reasons} color="bg-orange-500/15" />
        <BarList title="Valor por segmento" head={["Segmento", "Valor neto"]} rows={group("segmento", SEGMENTS)} color="bg-indigo-500/12" />
        <BarList title="Valor por plataforma" hint="La versión 5.2.0, solo en Android, concentra buena parte de la lista."
          head={["Plataforma", "Valor neto"]} rows={group("plataforma", PLATFORMS)} color="bg-indigo-500/12" />
      </div>
    </div>
  );
}

function BarList({ title, hint, head, rows, color }: {
  title: string; hint?: string; head: [string, string]; color: string;
  rows: { key: string; label: string; sub?: string; value: number; shown: string; open: () => void }[];
}) {
  const max = Math.max(...rows.map((r) => r.value), 1e-9);
  return (
    <section>
      <SectionTitle title={title} hint={hint} />
      <div className="flex justify-between px-2 pb-1.5 text-[11px] font-medium uppercase tracking-wide text-zinc-400">
        <span>{head[0]}</span><span>{head[1]}</span>
      </div>
      {rows.length === 0 && <p className="px-2 text-sm text-zinc-500">Nadie a llamar con estos supuestos.</p>}
      <div className="flex flex-col gap-1">
        {rows.map((r) => (
          <button key={r.key} onClick={r.open} title="Ver estos clientes"
            className="group relative flex items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-zinc-50">
            <span className={`absolute inset-y-0 left-0 rounded-md ${color} transition-[width] duration-300`}
              style={{ width: `${Math.max(r.value / max, 0) * 100}%` }} />
            <span className="relative text-zinc-800">{r.label}{r.sub && <span className="text-zinc-400"> · {r.sub}</span>}</span>
            <span className="relative flex items-center gap-1 font-medium text-zinc-900">
              {r.shown}
              <Icon d={ICONS.arrow} className="size-3.5 text-zinc-300 opacity-0 transition-opacity group-hover:opacity-100" />
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}

function Curve({ scored, effectiveness, cost, metric, onPick }: {
  scored: Scored[]; effectiveness: number; cost: number; metric: Metric; onPick: (e: number) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const points = useMemo(() => {
    const eligible = scored.filter((c) => c.en_proceso !== 1);
    return Array.from({ length: 16 }, (_, i) => {
      const e = Math.round((0.05 + i * 0.05) * 100) / 100;
      const vals = eligible.map((c) => expectedValue(c.probabilidad, c.plan, cost, e)).filter((v) => v > 0);
      return { e, value: vals.reduce((s, v) => s + v, 0), calls: vals.length };
    });
  }, [scored, cost]);

  const W = 1000, H = 280, L = 58, R = 12, T = 20, B = 28;
  const get = (p: (typeof points)[number]) => (metric === "value" ? p.value : p.calls);
  const fmt = (v: number) => (metric === "value" ? cop(v) : int(v));
  const maxV = Math.max(...points.map(get), 1);
  const x = (e: number) => L + ((e - 0.05) / 0.75) * (W - L - R);
  const y = (v: number) => T + (1 - v / maxV) * (H - T - B);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(p.e).toFixed(1)},${y(get(p)).toFixed(1)}`).join(" ");
  const area = `${line} L${x(0.8)},${y(0)} L${x(0.05)},${y(0)} Z`;
  const selectedIndex = points.reduce((best, p, i) => (Math.abs(p.e - effectiveness) < Math.abs(points[best].e - effectiveness) ? i : best), 0);
  const shown = points[hover ?? selectedIndex];

  const indexAt = (clientX: number) => {
    const rect = svgRef.current!.getBoundingClientRect();
    const vx = ((clientX - rect.left) / rect.width) * W;
    const e = 0.05 + ((vx - L) / (W - L - R)) * 0.75;
    return Math.min(points.length - 1, Math.max(0, Math.round((e - 0.05) / 0.05)));
  };

  const tipX = Math.min(Math.max(x(shown.e) - 98, L), W - R - 196);
  const tipY = Math.max(y(get(shown)) - 58, 0);

  return (
    <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="h-auto w-full cursor-crosshair select-none" role="img"
      aria-label={metric === "value" ? "Valor esperado neto según la efectividad" : "Llamadas según la efectividad"}
      onMouseMove={(ev) => setHover(indexAt(ev.clientX))} onMouseLeave={() => setHover(null)}
      onClick={(ev) => onPick(points[indexAt(ev.clientX)].e)}>
      <defs>
        <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#6366f1" stopOpacity="0.18" />
          <stop offset="1" stopColor="#6366f1" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 0.25, 0.5, 0.75, 1].map((f) => (
        <g key={f}>
          <line x1={L} x2={W - R} y1={y(f * maxV)} y2={y(f * maxV)} stroke="#f2f2f4" />
          <text x={L - 10} y={y(f * maxV) + 4} textAnchor="end" className="fill-zinc-400 text-[11px]">{fmt(f * maxV)}</text>
        </g>
      ))}
      {points.filter((_, i) => i % 3 === 0 || i === points.length - 1).map((p) => (
        <text key={p.e} x={x(p.e)} y={H - 6} textAnchor="middle" className="fill-zinc-400 text-[11px]">{pct(p.e)}</text>
      ))}
      <rect x={L} y={T} width={W - L - R} height={H - T - B} fill="transparent" />
      <path d={area} fill="url(#area)" />
      <path d={line} fill="none" stroke="#6366f1" strokeWidth={2} />
      <line x1={x(points[selectedIndex].e)} x2={x(points[selectedIndex].e)} y1={T} y2={H - B} stroke="#c7c7cc" strokeDasharray="4 4" />
      {hover !== null && hover !== selectedIndex && (
        <line x1={x(shown.e)} x2={x(shown.e)} y1={T} y2={H - B} stroke="#6366f1" strokeOpacity={0.35} />
      )}
      <circle cx={x(points[selectedIndex].e)} cy={y(get(points[selectedIndex]))} r={4} fill="#fff" stroke="#6366f1" strokeWidth={2} />
      <circle cx={x(shown.e)} cy={y(get(shown))} r={5.5} fill="#6366f1" stroke="#fff" strokeWidth={2} />
      <g transform={`translate(${tipX}, ${tipY})`} pointerEvents="none">
        <rect width={196} height={44} rx={8} fill="#18181b" />
        <text x={12} y={19} className="fill-white text-[12.5px] font-semibold">
          {metric === "value" ? `${cop(shown.value)} netos` : `${int(shown.calls)} llamadas`}
        </text>
        <text x={12} y={35} className="fill-zinc-400 text-[11px]">
          {pct(shown.e)} de efectividad · {metric === "value" ? `${int(shown.calls)} llamadas` : `${cop(shown.value)} netos`}
        </text>
      </g>
    </svg>
  );
}

// ------------------------------------------------------------------------------------------------ clientes
function Clients({ scored, effectiveness, cost, filters, setFilters, view, setView }: {
  scored: Scored[]; effectiveness: number; cost: number; filters: Filters; setFilters: (f: Filters) => void;
  view: View; setView: (v: View) => void;
}) {
  const [query, setQuery] = useState("");
  const [pageIndex, setPageIndex] = useState(0);
  const [openId, setOpenId] = useState<number | null>(null);

  const filtered = scored.filter((c) => filters.plans.has(c.plan) && filters.segments.has(c.segmento)
    && filters.platforms.has(c.plataforma) && (!filters.reason || reasonOf(c) === filters.reason));
  const rows = filtered
    .filter(VIEW_FILTER[view])
    .filter((c) => !query || String(c.cliente_id).startsWith(query))
    .sort((a, b) => b.value - a.value || b.probabilidad - a.probabilidad);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(pageIndex, pages - 1);
  const pageRows = rows.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE);
  const open = scored.find((c) => c.cliente_id === openId) ?? null;
  const update = (patch: Partial<Filters>) => { setFilters({ ...filters, ...patch }); setPageIndex(0); };

  function downloadCsv() {
    const header = ["cliente_id", "plan", "segmento", "plataforma", "probabilidad", "valor_esperado", "decision", "factor_1", "factor_2", "factor_3"];
    const lines = rows.map((c) => [c.cliente_id, c.plan, c.segmento, c.plataforma, c.probabilidad.toFixed(4), Math.round(c.value),
      c.decision, c.factor_1 ?? "", c.factor_2 ?? "", c.factor_3 ?? ""].map((v) => `"${String(v).replaceAll('"', '""')}"`).join(","));
    const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "lista_contacto.csv" });
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const filterMenu = (label: string, options: Record<string, string>, field: "plans" | "segments" | "platforms") => {
    const all = Object.keys(options);
    const selected = filters[field];
    const active = selected.size < all.length;
    return (
      <Dropdown>
        <Dropdown.Trigger>
          <Button size="sm" variant={active ? "secondary" : "ghost"}>
            <Icon d={ICONS.plus} className="size-3.5" />
            {label}{active && `: ${[...selected].map((k) => options[k]).join(", ") || "ninguno"}`}
          </Button>
        </Dropdown.Trigger>
        <Dropdown.Popover placement="bottom start">
          <Dropdown.Menu aria-label={label} selectionMode="multiple" selectedKeys={selected}
            onSelectionChange={(keys) => update({ [field]: asSet(keys, all) })}>
            {all.map((k) => (
              <Dropdown.Item key={k} id={k} textValue={options[k]}>
                <Label>{options[k]}</Label>
                <Dropdown.ItemIndicator />
              </Dropdown.Item>
            ))}
          </Dropdown.Menu>
        </Dropdown.Popover>
      </Dropdown>
    );
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Clientes</h1>
          <p className="mt-1 text-sm text-zinc-500">Ordenados por valor esperado. Haz clic en un cliente para ver por qué está en riesgo.</p>
        </div>
        <Button size="sm" variant="ghost" onPress={downloadCsv}><Icon d={ICONS.download} />Exportar CSV</Button>
      </div>

      <Tabs selectedKey={view} onSelectionChange={(k) => { setView(k as View); setPageIndex(0); }} variant="secondary">
        <Tabs.ListContainer>
          <Tabs.List aria-label="Vista">
            {VIEWS.map((v) => (
              <Tabs.Tab key={v} id={v} className="text-zinc-500 data-[selected=true]:text-zinc-900">
                {v}<span className="ml-1.5 text-zinc-400">{int(filtered.filter(VIEW_FILTER[v]).length)}</span>
                <Tabs.Indicator />
              </Tabs.Tab>
            ))}
          </Tabs.List>
        </Tabs.ListContainer>
      </Tabs>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1">
          {filterMenu("Plan", PLAN_LABEL, "plans")}
          {filterMenu("Segmento", SEGMENTS, "segments")}
          {filterMenu("Plataforma", PLATFORMS, "platforms")}
          {filters.reason && (
            <Button size="sm" variant="secondary" onPress={() => update({ reason: null })}>
              Motivo: {filters.reason}<Icon d={ICONS.x} className="size-3.5" />
            </Button>
          )}
        </div>
        <SearchField aria-label="Buscar cliente" value={query} onChange={(v) => { setQuery(v.replace(/\D/g, "")); setPageIndex(0); }}
          className="w-full sm:w-64">
          <SearchField.Group className="border-0 bg-zinc-100 shadow-none">
            <SearchField.SearchIcon />
            <SearchField.Input placeholder="Buscar por número de cliente" className="placeholder:text-zinc-400" />
            <SearchField.ClearButton />
          </SearchField.Group>
        </SearchField>
      </div>

      <Table variant="secondary">
        <Table.ScrollContainer>
          <Table.Content aria-label="Clientes" onRowAction={(key) => setOpenId(Number(key))}
            className="min-w-[860px] [&_thead_th]:!bg-transparent [&_thead_tr]:!bg-transparent [&_thead]:border-b [&_thead]:border-zinc-200">
            <Table.Header>
              <Table.Column isRowHeader className="text-xs font-medium text-zinc-500">Cliente</Table.Column>
              <Table.Column className="text-xs font-medium text-zinc-500">Plan</Table.Column>
              <Table.Column className="text-xs font-medium text-zinc-500">Riesgo de baja</Table.Column>
              <Table.Column className="text-xs font-medium text-zinc-500">Nivel</Table.Column>
              <Table.Column className="text-right text-xs font-medium text-zinc-500">Valor esperado</Table.Column>
              <Table.Column className="text-xs font-medium text-zinc-500">Decisión</Table.Column>
              <Table.Column className="text-xs font-medium text-zinc-500">Motivo principal</Table.Column>
            </Table.Header>
            <Table.Body renderEmptyState={() => <div className="py-10 text-center text-sm text-zinc-500">No hay clientes con estos filtros.</div>}>
              {pageRows.map((c) => (
                <Table.Row key={c.cliente_id} id={c.cliente_id} className="cursor-pointer">
                  <Table.Cell>
                    <div className="font-medium text-zinc-900">{c.cliente_id}</div>
                    <div className="text-xs text-zinc-500">{SEGMENTS[c.segmento] ?? c.segmento} · {PLATFORMS[c.plataforma]}</div>
                  </Table.Cell>
                  <Table.Cell>{PLAN_LABEL[c.plan]}</Table.Cell>
                  <Table.Cell>
                    <Meter aria-label="Riesgo de baja" value={c.probabilidad * 100} color={RISK_COLOR[c.risk]} size="sm" className="w-32">
                      <div className="flex justify-end text-xs text-zinc-600">{pct(c.probabilidad)}</div>
                      <Meter.Track><Meter.Fill /></Meter.Track>
                    </Meter>
                  </Table.Cell>
                  <Table.Cell><Chip size="sm" variant="soft" color={RISK_COLOR[c.risk]}>{c.risk}</Chip></Table.Cell>
                  <Table.Cell className="text-right font-medium tabular-nums text-zinc-900">{cop(c.value)}</Table.Cell>
                  <Table.Cell><Chip size="sm" variant="soft" color={DECISION_COLOR[c.decision]}>{c.decision}</Chip></Table.Cell>
                  <Table.Cell className="max-w-[240px] truncate text-zinc-500">{c.factor_1 ?? "—"}</Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Content>
        </Table.ScrollContainer>
        <Table.Footer>
          <Pagination className="flex w-full items-center justify-between">
            <Pagination.Summary className="text-sm text-zinc-500">
              {int(rows.length)} resultados · página {current + 1} de {pages}
            </Pagination.Summary>
            <Pagination.Content>
              <Pagination.Item>
                <Pagination.Previous isDisabled={current === 0} onPress={() => setPageIndex(current - 1)}>
                  <Pagination.PreviousIcon />Anterior
                </Pagination.Previous>
              </Pagination.Item>
              <Pagination.Item>
                <Pagination.Next isDisabled={current >= pages - 1} onPress={() => setPageIndex(current + 1)}>
                  Siguiente<Pagination.NextIcon />
                </Pagination.Next>
              </Pagination.Item>
            </Pagination.Content>
          </Pagination>
        </Table.Footer>
      </Table>

      <ClientDrawer client={open} onClose={() => setOpenId(null)} effectiveness={effectiveness} cost={cost} />
    </div>
  );
}

function ClientDrawer({ client, onClose, effectiveness, cost }: {
  client: Scored | null; onClose: () => void; effectiveness: number; cost: number;
}) {
  const explain: Record<Decision, string> = {
    Llamar: "Su riesgo supera el umbral de su plan: con estos supuestos, la llamada se paga sola.",
    "No llamar": "Su riesgo no alcanza el umbral de su plan: la llamada costaría más de lo que se espera retener.",
    "En proceso de baja": "Ya lo atiende el flujo de baja (llamada del equipo en los últimos 30 días o ticket de cancelar en 90). Casi todos esos clientes se van igual, así que no se recomienda llamarlo.",
  };
  return (
    <Drawer>
      <Drawer.Backdrop isOpen={client !== null} onOpenChange={(o) => { if (!o) onClose(); }}>
        <Drawer.Content placement="right">
          <Drawer.Dialog className="h-full w-full max-w-md">
            {client && (
              <>
                <Drawer.CloseTrigger />
                <Drawer.Header>
                  <div className="flex items-center gap-3">
                    <span className="grid size-10 place-items-center rounded-full bg-zinc-100 text-zinc-500"><Icon d={ICONS.user} className="size-5" /></span>
                    <div>
                      <Drawer.Heading>Cliente {client.cliente_id}</Drawer.Heading>
                      <p className="text-sm text-zinc-500">{PLAN_LABEL[client.plan]} · {client.segmento} · {PLATFORMS[client.plataforma]}</p>
                    </div>
                  </div>
                </Drawer.Header>
                <Drawer.Body className="flex flex-col gap-7">
                  <div className="flex flex-wrap gap-1.5">
                    <Chip size="sm" variant="soft" color={DECISION_COLOR[client.decision]}>{client.decision}</Chip>
                    <Chip size="sm" variant="soft" color={RISK_COLOR[client.risk]}>Riesgo {client.risk.toLowerCase()}</Chip>
                    {client.usa_520 === 1 && <Chip size="sm" variant="soft">Usa la app 5.2.0</Chip>}
                  </div>

                  <section>
                    <SectionTitle title="Resumen" />
                    <div className="grid grid-cols-3 gap-4">
                      {[["Riesgo de baja", pct(client.probabilidad)], ["Umbral del plan", pct(threshold(client.plan, cost, effectiveness))],
                        ["Valor esperado", cop(client.value)]].map(([k, v]) => (
                        <div key={k}>
                          <div className="text-xl font-semibold text-zinc-900">{v}</div>
                          <div className="text-xs text-zinc-500">{k}</div>
                        </div>
                      ))}
                    </div>
                    <p className="mt-3 text-sm text-zinc-600">{explain[client.decision]}</p>
                  </section>

                  <section>
                    <SectionTitle title="Qué sube su riesgo" hint="Las tres variables que más suben su probabilidad según SHAP, con su valor." />
                    <ol className="flex flex-col gap-2.5">
                      {factorsOf(client).map((f, i) => (
                        <li key={f} className="flex items-start gap-3 text-sm">
                          <span className="grid size-5 shrink-0 place-items-center rounded-full bg-indigo-50 text-[11px] font-semibold text-indigo-700">{i + 1}</span>
                          <span className="text-zinc-800">{f}</span>
                        </li>
                      ))}
                      {factorsOf(client).length === 0 && <li className="text-sm text-zinc-500">Ningún factor sube su riesgo.</li>}
                    </ol>
                  </section>

                  <section>
                    <SectionTitle title="Propiedades" />
                    <dl className="flex flex-col gap-2 text-sm">
                      {[["Plan", `${PLAN_LABEL[client.plan]} · ${int(PRICES[client.plan])} COP al mes`], ["Segmento", client.segmento],
                        ["Plataforma", PLATFORMS[client.plataforma]], ["En proceso de baja", client.en_proceso ? "Sí" : "No"],
                        ["Usa la app 5.2.0", client.usa_520 ? "Sí" : "No"]].map(([k, v]) => (
                        <div key={k} className="flex justify-between"><dt className="text-zinc-500">{k}</dt><dd className="text-zinc-900">{v}</dd></div>
                      ))}
                    </dl>
                  </section>
                </Drawer.Body>
              </>
            )}
          </Drawer.Dialog>
        </Drawer.Content>
      </Drawer.Backdrop>
    </Drawer>
  );
}

// ------------------------------------------------------------------------------------------------ regla
function Rule({ effectiveness, cost }: { effectiveness: number; cost: number }) {
  return (
    <div className="flex max-w-3xl flex-col gap-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Cómo se decide</h1>
        <p className="mt-1 text-sm text-zinc-500">La misma regla de la sección 7 del notebook.</p>
      </div>
      <section>
        <SectionTitle title="Llamar conviene si lo que se espera retener supera el costo"
          hint="El modelo estima, para cada cliente, la probabilidad de que se vaya en los próximos 90 días." />
        <p className="text-base font-medium text-zinc-900">probabilidad × efectividad × 12 × precio del plan &gt; costo de la llamada</p>
      </section>
      <section>
        <SectionTitle title="Umbral por plan" hint={`Con efectividad de ${pct(effectiveness)} y costo de ${int(cost)} COP por llamada.`} />
        <Table variant="secondary">
          <Table.ScrollContainer>
            <Table.Content aria-label="Umbral por plan" className="[&_thead_th]:!bg-transparent [&_thead_tr]:!bg-transparent [&_thead]:border-b [&_thead]:border-zinc-200">
              <Table.Header>
                <Table.Column isRowHeader className="text-xs font-medium text-zinc-500">Plan</Table.Column>
                <Table.Column className="text-right text-xs font-medium text-zinc-500">Precio mensual</Table.Column>
                <Table.Column className="text-right text-xs font-medium text-zinc-500">Umbral de riesgo</Table.Column>
              </Table.Header>
              <Table.Body>
                {PLANS.map((p) => (
                  <Table.Row key={p} id={p}>
                    <Table.Cell>{PLAN_LABEL[p]}</Table.Cell>
                    <Table.Cell className="text-right">{int(PRICES[p])} COP</Table.Cell>
                    <Table.Cell className="text-right font-medium">{pct(threshold(p, cost, effectiveness), 1)}</Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Content>
          </Table.ScrollContainer>
        </Table>
      </section>
      <section>
        <SectionTitle title="Reglas adicionales" />
        <ul className="flex list-disc flex-col gap-2 pl-5 text-sm text-zinc-700">
          <li>No se llama a quien ya está en proceso de baja (llamada del equipo en los últimos 30 días o ticket de cancelar en los últimos 90): lo atiende el flujo actual y casi todos se van igual.</li>
          <li>El valor esperado ya descuenta el costo de la llamada. Si es negativo, la llamada cuesta más de lo que se espera retener.</li>
          <li>La efectividad del 40 % es un supuesto del enunciado y es lo que más pesa en el resultado. El piloto con grupo de control propuesto en el memo sirve para reemplazarlo por la efectividad medida.</li>
          <li>Por privacidad, el tablero no incluye ciudad, edad ni textos de los tickets de los clientes.</li>
        </ul>
      </section>
    </div>
  );
}
