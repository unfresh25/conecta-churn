"use client";

import { useMemo, useState } from "react";
import {
  Button, Card, Chip, Drawer, Dropdown, Label, Meter, NumberField, Pagination, Popover, SearchField, Slider, Table,
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
const SEGMENTS = ["Personal", "Pyme"];
const PLATFORMS: Record<string, string> = { android: "Android", ios: "iOS", web: "Web" };
const VIEWS = ["Todos", "A llamar", "En proceso de baja", "Usan la app 5.2.0"] as const;
type View = (typeof VIEWS)[number];
type Page = "summary" | "clients" | "rule";
const PAGE_SIZE = 12;

const RISK_COLOR: Record<Risk, "danger" | "warning" | "default"> = { Alto: "danger", Medio: "warning", Bajo: "default" };
const DECISION_COLOR: Record<Decision, "accent" | "default" | "warning"> = {
  Llamar: "accent", "No llamar": "default", "En proceso de baja": "warning",
};
const VIEW_FILTER: Record<View, (c: Scored) => boolean> = {
  Todos: () => true,
  "A llamar": (c) => c.call,
  "En proceso de baja": (c) => c.en_proceso === 1,
  "Usan la app 5.2.0": (c) => c.usa_520 === 1,
};

const factorsOf = (c: Client) => [c.factor_1, c.factor_2, c.factor_3].filter((f): f is string => !!f);
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
  download: "M12 4v11M7 10l5 5 5-5M5 20h14",
  sliders: "M4 7h10M18 7h2M4 17h4M12 17h8M14 4v6M8 14v6",
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

// ------------------------------------------------------------------------------------------------ página
export default function Dashboard({ clients }: { clients: Client[] }) {
  const [page, setPage] = useState<Page>("summary");
  const [effectiveness, setEffectiveness] = useState(EFFECTIVENESS);
  const [cost, setCost] = useState(CONTACT_COST);

  const scored = useMemo(() => score(clients, effectiveness, cost), [clients, effectiveness, cost]);
  const base = useMemo(() => score(clients, EFFECTIVENESS, CONTACT_COST), [clients]);
  const changed = effectiveness !== EFFECTIVENESS || cost !== CONTACT_COST;

  const nav: { id: Page; label: string; icon: string }[] = [
    { id: "summary", label: "Resumen", icon: ICONS.chart },
    { id: "clients", label: "Clientes", icon: ICONS.users },
    { id: "rule", label: "Cómo se decide", icon: ICONS.book },
  ];
  const title = nav.find((n) => n.id === page)!.label;

  return (
    <div className="flex min-h-screen bg-white">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-zinc-200 bg-zinc-50/60 px-3 py-4 md:flex">
        <div className="flex items-center gap-2 px-2 pb-5">
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
        <div className="mt-auto flex flex-col gap-3 px-2 text-xs text-zinc-500">
          <p>Puntaje al 31-dic-2025 del modelo final (LightGBM). Sin ciudad, edad ni textos de tickets.</p>
          <ColabBadge />
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 hover:text-zinc-900">
            <Icon d={ICONS.github} className="size-3.5" />Repositorio
          </a>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between gap-3 border-b border-zinc-200 bg-white/90 px-4 backdrop-blur md:px-8">
          <div className="flex min-w-0 items-center gap-2 text-sm">
            <span className="hidden text-zinc-500 sm:inline">Campaña de enero de 2026</span>
            <span className="hidden text-zinc-300 sm:inline">/</span>
            <span className="font-medium text-zinc-900">{title}</span>
          </div>
          <div className="flex items-center gap-2">
            <Assumptions effectiveness={effectiveness} cost={cost} changed={changed}
              onEffectiveness={setEffectiveness} onCost={setCost}
              onReset={() => { setEffectiveness(EFFECTIVENESS); setCost(CONTACT_COST); }} />
            <ColabBadge />
          </div>
        </header>

        <nav className="flex gap-1 border-b border-zinc-200 px-4 py-2 md:hidden">
          {nav.map((n) => (
            <Button key={n.id} size="sm" variant={page === n.id ? "secondary" : "ghost"} onPress={() => setPage(n.id)}>{n.label}</Button>
          ))}
        </nav>

        <main className="mx-auto w-full max-w-[1200px] px-4 py-8 md:px-8">
          {page === "summary" && <Summary scored={scored} base={base} changed={changed} effectiveness={effectiveness} cost={cost} />}
          {page === "clients" && <Clients scored={scored} effectiveness={effectiveness} cost={cost} />}
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
        <Button size="sm" variant={props.changed ? "primary" : "secondary"}>
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
function Summary({ scored, base, changed, effectiveness, cost }: {
  scored: Scored[]; base: Scored[]; changed: boolean; effectiveness: number; cost: number;
}) {
  const calls = scored.filter((c) => c.call);
  const net = calls.reduce((s, c) => s + c.value, 0);
  const baseCalls = base.filter((c) => c.call);
  const baseNet = baseCalls.reduce((s, c) => s + c.value, 0);
  const meanP = scored.reduce((s, c) => s + c.probabilidad, 0) / scored.length;

  const kpis = [
    { label: "Clientes activos", value: int(scored.length), note: "al 31-dic-2025" },
    { label: "A llamar", value: int(calls.length), note: changed ? `${signed(calls.length - baseCalls.length, int)} vs. enunciado` : `${pct(calls.length / scored.length)} de los clientes` },
    { label: "Costo de las llamadas", value: cop(calls.length * cost), note: `${int(cost)} COP por llamada` },
    { label: "Valor esperado neto", value: cop(net), note: changed ? `${signed(net - baseNet, cop)} vs. enunciado` : "ya descuenta el costo" },
    { label: "Riesgo medio de baja", value: pct(meanP, 1), note: "últimos cortes: 16,2 %" },
  ];

  const byPlan = PLANS.map((p) => {
    const g = scored.filter((c) => c.plan === p);
    const n = g.filter((c) => c.call).length;
    return { label: PLAN_LABEL[p], sub: `umbral ${pct(threshold(p, cost, effectiveness), 1)}`, value: n / g.length, shown: `${int(n)} · ${pct(n / g.length)}` };
  });
  const reasonCount = new Map<string, number>();
  for (const c of calls) if (c.factor_1) reasonCount.set(c.factor_1.split(":")[0], (reasonCount.get(c.factor_1.split(":")[0]) ?? 0) + 1);
  const reasons = [...reasonCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6)
    .map(([label, n]) => ({ label, value: n, shown: int(n) }));
  const group = (key: (c: Scored) => string, labels: Record<string, string>) =>
    Object.entries(labels).map(([k, label]) => {
      const g = calls.filter((c) => key(c) === k);
      return { label, value: g.reduce((s, c) => s + c.value, 0), shown: copM(g.reduce((s, c) => s + c.value, 0)), sub: `${int(g.length)} llamadas` };
    });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Resumen de la campaña</h1>
        <p className="mt-1 text-sm text-zinc-500">A quién llamar en enero, cuánto se espera ganar y de qué depende.</p>
      </div>

      <Card className="grid grid-cols-2 gap-0 overflow-hidden p-0 lg:grid-cols-5">
        {kpis.map((k, i) => (
          <div key={k.label} className={`p-4 ${i ? "border-l border-zinc-200" : ""} ${i > 1 ? "max-lg:border-t" : ""} ${i === 2 ? "max-lg:border-l-0" : ""} ${i === 4 ? "max-lg:border-l-0" : ""}`}>
            <div className="text-xs font-medium text-zinc-500">{k.label}</div>
            <div className="mt-1 text-2xl font-semibold tracking-tight text-zinc-900">{k.value}</div>
            <div className="mt-0.5 text-xs text-zinc-500">{k.note}</div>
          </div>
        ))}
      </Card>

      <Card>
        <Card.Header>
          <Card.Title className="text-base font-semibold text-zinc-900">Valor esperado según la efectividad de la llamada</Card.Title>
          <p className="text-sm text-zinc-500">
            Si la llamada retiene a menos clientes de los que supone el enunciado, la lista vale mucho menos. Las llamadas actuales,
            que llegan tarde, retienen cerca del 3 %.
          </p>
        </Card.Header>
        <Card.Content><Curve scored={scored} effectiveness={effectiveness} cost={cost} /></Card.Content>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <ListCard title="A quién se llama, por plan" head={["Plan", "A llamar"]} rows={byPlan} color="bg-blue-500/15"
          foot="Los planes caros tienen un umbral más bajo: retener a un cliente Familiar vale 2,5 veces lo que uno Básico." />
        <ListCard title="Motivo principal de los clientes a llamar" head={["Motivo", "Clientes"]} rows={reasons} color="bg-orange-500/15"
          foot="La variable que más sube la probabilidad de cada cliente, según SHAP." />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <ListCard title="Valor por segmento" head={["Segmento", "Valor neto"]} rows={group((c) => c.segmento, { Personal: "Personal", Pyme: "Pyme" })} color="bg-blue-500/15" />
        <ListCard title="Valor por plataforma" head={["Plataforma", "Valor neto"]} rows={group((c) => c.plataforma, PLATFORMS)} color="bg-blue-500/15"
          foot="La versión 5.2.0 de la app, solo en Android, concentra a buena parte de la lista." />
      </div>
    </div>
  );
}

function ListCard({ title, head, rows, color, foot }: {
  title: string; head: [string, string]; rows: { label: string; sub?: string; value: number; shown: string }[]; color: string; foot?: string;
}) {
  const max = Math.max(...rows.map((r) => r.value), 1e-9);
  return (
    <Card>
      <Card.Header><Card.Title className="text-base font-semibold text-zinc-900">{title}</Card.Title></Card.Header>
      <Card.Content className="flex flex-col gap-1">
        <div className="flex justify-between px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-zinc-400">
          <span>{head[0]}</span><span>{head[1]}</span>
        </div>
        {rows.length === 0 && <p className="px-2 text-sm text-zinc-500">Nadie a llamar con estos supuestos.</p>}
        {rows.map((r) => (
          <div key={r.label} className="relative flex items-center justify-between rounded-md px-2 py-1.5 text-sm">
            <div className={`absolute inset-y-0 left-0 rounded-md ${color}`} style={{ width: `${Math.max(r.value / max, 0) * 100}%` }} />
            <span className="relative text-zinc-800">{r.label}{r.sub && <span className="text-zinc-400"> · {r.sub}</span>}</span>
            <span className="relative font-medium text-zinc-900">{r.shown}</span>
          </div>
        ))}
      </Card.Content>
      {foot && <Card.Footer><p className="text-xs text-zinc-500">{foot}</p></Card.Footer>}
    </Card>
  );
}

function Curve({ scored, effectiveness, cost }: { scored: Scored[]; effectiveness: number; cost: number }) {
  const eligible = scored.filter((c) => c.en_proceso !== 1);
  const points = Array.from({ length: 16 }, (_, i) => {
    const e = Math.round((0.05 + i * 0.05) * 100) / 100;
    const vals = eligible.map((c) => expectedValue(c.probabilidad, c.plan, cost, e)).filter((v) => v > 0);
    return { e, value: vals.reduce((s, v) => s + v, 0), calls: vals.length };
  });
  const W = 1000, H = 260, L = 56, R = 16, T = 16, B = 28;
  const maxV = Math.max(...points.map((p) => p.value), 1);
  const x = (e: number) => L + ((e - 0.05) / 0.75) * (W - L - R);
  const y = (v: number) => T + (1 - v / maxV) * (H - T - B);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(p.e).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
  const area = `${line} L${x(0.8)},${y(0)} L${x(0.05)},${y(0)} Z`;
  const here = points.reduce((a, b) => (Math.abs(b.e - effectiveness) < Math.abs(a.e - effectiveness) ? b : a));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Valor esperado neto según la efectividad">
      <defs>
        <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#6366f1" stopOpacity="0.22" />
          <stop offset="1" stopColor="#6366f1" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 0.25, 0.5, 0.75, 1].map((f) => (
        <g key={f}>
          <line x1={L} x2={W - R} y1={y(f * maxV)} y2={y(f * maxV)} stroke="#f0f0f2" />
          <text x={L - 8} y={y(f * maxV) + 4} textAnchor="end" className="fill-zinc-400 text-[11px]">{cop(f * maxV)}</text>
        </g>
      ))}
      {[0.05, 0.2, 0.4, 0.6, 0.8].map((e) => (
        <text key={e} x={x(e)} y={H - 6} textAnchor="middle" className="fill-zinc-400 text-[11px]">{pct(e)}</text>
      ))}
      <path d={area} fill="url(#area)" />
      <path d={line} fill="none" stroke="#6366f1" strokeWidth={2} />
      <line x1={x(here.e)} x2={x(here.e)} y1={T} y2={H - B} stroke="#a1a1aa" strokeDasharray="4 4" />
      <circle cx={x(here.e)} cy={y(here.value)} r={5} fill="#6366f1" stroke="#fff" strokeWidth={2} />
      <g transform={`translate(${Math.min(x(here.e) + 12, W - 210)}, ${Math.max(y(here.value) - 44, T)})`}>
        <rect width={196} height={40} rx={8} fill="#18181b" />
        <text x={12} y={17} className="fill-white text-[12px] font-semibold">{cop(here.value)} netos</text>
        <text x={12} y={32} className="fill-zinc-300 text-[11px]">{pct(here.e)} de efectividad · {int(here.calls)} llamadas</text>
      </g>
    </svg>
  );
}

// ------------------------------------------------------------------------------------------------ clientes
function Clients({ scored, effectiveness, cost }: { scored: Scored[]; effectiveness: number; cost: number }) {
  const [view, setView] = useState<View>("A llamar");
  const [plans, setPlans] = useState<Set<string>>(new Set(PLANS));
  const [segments, setSegments] = useState<Set<string>>(new Set(SEGMENTS));
  const [platforms, setPlatforms] = useState<Set<string>>(new Set(Object.keys(PLATFORMS)));
  const [query, setQuery] = useState("");
  const [pageIndex, setPageIndex] = useState(0);
  const [openId, setOpenId] = useState<number | null>(null);

  const filtered = scored.filter((c) => plans.has(c.plan) && segments.has(c.segmento) && platforms.has(c.plataforma));
  const rows = filtered
    .filter(VIEW_FILTER[view])
    .filter((c) => !query || String(c.cliente_id).startsWith(query))
    .sort((a, b) => b.value - a.value || b.probabilidad - a.probabilidad);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(pageIndex, pages - 1);
  const pageRows = rows.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE);
  const open = scored.find((c) => c.cliente_id === openId) ?? null;

  function downloadCsv() {
    const header = ["cliente_id", "plan", "segmento", "plataforma", "probabilidad", "valor_esperado", "decision", "factor_1", "factor_2", "factor_3"];
    const lines = rows.map((c) => [c.cliente_id, c.plan, c.segmento, c.plataforma, c.probabilidad.toFixed(4), Math.round(c.value),
      c.decision, c.factor_1 ?? "", c.factor_2 ?? "", c.factor_3 ?? ""].map((v) => `"${String(v).replaceAll('"', '""')}"`).join(","));
    const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "lista_contacto.csv" });
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const filterMenu = (label: string, options: Record<string, string>, selected: Set<string>, set: (s: Set<string>) => void) => {
    const all = Object.keys(options);
    const active = selected.size < all.length;
    return (
      <Dropdown>
        <Dropdown.Trigger>
          <Button size="sm" variant={active ? "secondary" : "outline"} className={active ? "" : "border-dashed"}>
            <Icon d={ICONS.plus} className="size-3.5" />
            {label}{active && `: ${[...selected].map((k) => options[k]).join(", ") || "ninguno"}`}
          </Button>
        </Dropdown.Trigger>
        <Dropdown.Popover placement="bottom start">
          <Dropdown.Menu aria-label={label} selectionMode="multiple" selectedKeys={selected}
            onSelectionChange={(keys) => { set(asSet(keys, all)); setPageIndex(0); }}>
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
          <p className="mt-1 text-sm text-zinc-500">Ordenados por valor esperado. Abre un cliente para ver por qué está en riesgo.</p>
        </div>
        <Button size="sm" variant="secondary" onPress={downloadCsv}><Icon d={ICONS.download} />Exportar CSV</Button>
      </div>

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {VIEWS.map((v) => {
          const active = view === v;
          return (
            <button key={v} onClick={() => { setView(v); setPageIndex(0); }}
              className={`rounded-xl border px-4 py-3 text-left transition-colors ${
                active ? "border-indigo-500 bg-indigo-50/60 ring-1 ring-indigo-500" : "border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50"}`}>
              <div className={`text-sm ${active ? "font-medium text-indigo-700" : "text-zinc-600"}`}>{v}</div>
              <div className="mt-0.5 text-lg font-semibold text-zinc-900">{int(filtered.filter(VIEW_FILTER[v]).length)}</div>
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-2">
          {filterMenu("Plan", PLAN_LABEL, plans, setPlans)}
          {filterMenu("Segmento", { Personal: "Personal", Pyme: "Pyme" }, segments, setSegments)}
          {filterMenu("Plataforma", PLATFORMS, platforms, setPlatforms)}
        </div>
        <SearchField aria-label="Buscar cliente" value={query} onChange={(v) => { setQuery(v.replace(/\D/g, "")); setPageIndex(0); }}
          className="w-full sm:w-64">
          <SearchField.Group>
            <SearchField.SearchIcon />
            <SearchField.Input placeholder="Buscar por número de cliente" className="placeholder:text-zinc-400" />
            <SearchField.ClearButton />
          </SearchField.Group>
        </SearchField>
      </div>

      <Table>
        <Table.ScrollContainer>
          <Table.Content aria-label="Clientes" onRowAction={(key) => setOpenId(Number(key))} className="min-w-[860px]">
            <Table.Header>
              <Table.Column isRowHeader className="text-xs font-medium text-zinc-600">Cliente</Table.Column>
              <Table.Column className="text-xs font-medium text-zinc-600">Plan</Table.Column>
              <Table.Column className="text-xs font-medium text-zinc-600">Riesgo de baja</Table.Column>
              <Table.Column className="text-xs font-medium text-zinc-600">Nivel</Table.Column>
              <Table.Column className="text-right text-xs font-medium text-zinc-600">Valor esperado</Table.Column>
              <Table.Column className="text-xs font-medium text-zinc-600">Decisión</Table.Column>
              <Table.Column className="text-xs font-medium text-zinc-600">Motivo principal</Table.Column>
            </Table.Header>
            <Table.Body renderEmptyState={() => <div className="py-10 text-center text-sm text-zinc-500">No hay clientes con estos filtros.</div>}>
              {pageRows.map((c) => (
                <Table.Row key={c.cliente_id} id={c.cliente_id} className="cursor-pointer">
                  <Table.Cell>
                    <div className="font-medium text-zinc-900">{c.cliente_id}</div>
                    <div className="text-xs text-zinc-500">{c.segmento} · {PLATFORMS[c.plataforma]}</div>
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
        <Drawer.Content placement="right" className="w-full sm:max-w-md">
          <Drawer.Dialog>
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
                <Drawer.Body className="flex flex-col gap-5">
                  <div className="flex flex-wrap gap-1.5">
                    <Chip size="sm" variant="soft" color={DECISION_COLOR[client.decision]}>{client.decision}</Chip>
                    <Chip size="sm" variant="soft" color={RISK_COLOR[client.risk]}>Riesgo {client.risk.toLowerCase()}</Chip>
                    {client.usa_520 === 1 && <Chip size="sm" variant="soft">Usa la app 5.2.0</Chip>}
                  </div>

                  <section>
                    <h3 className="mb-2 text-sm font-semibold text-zinc-900">Resumen</h3>
                    <div className="grid grid-cols-3 overflow-hidden rounded-xl border border-zinc-200">
                      {[["Riesgo de baja", pct(client.probabilidad)], ["Umbral del plan", pct(threshold(client.plan, cost, effectiveness))],
                        ["Valor esperado", cop(client.value)]].map(([k, v], i) => (
                        <div key={k} className={`p-3 ${i ? "border-l border-zinc-200" : ""}`}>
                          <div className="text-lg font-semibold text-zinc-900">{v}</div>
                          <div className="text-xs text-zinc-500">{k}</div>
                        </div>
                      ))}
                    </div>
                    <p className="mt-3 text-sm text-zinc-600">{explain[client.decision]}</p>
                  </section>

                  <section>
                    <h3 className="mb-2 text-sm font-semibold text-zinc-900">Qué sube su riesgo</h3>
                    <ol className="flex flex-col gap-2">
                      {factorsOf(client).map((f, i) => (
                        <li key={f} className="flex gap-3 rounded-lg border border-zinc-200 px-3 py-2 text-sm">
                          <span className="grid size-5 shrink-0 place-items-center rounded-full bg-indigo-50 text-[11px] font-semibold text-indigo-700">{i + 1}</span>
                          <span className="text-zinc-800">{f}</span>
                        </li>
                      ))}
                      {factorsOf(client).length === 0 && <li className="text-sm text-zinc-500">Ningún factor sube su riesgo.</li>}
                    </ol>
                    <p className="mt-2 text-xs text-zinc-500">Las tres variables que más suben su probabilidad según SHAP, con su valor.</p>
                  </section>

                  <section>
                    <h3 className="mb-2 text-sm font-semibold text-zinc-900">Propiedades</h3>
                    <dl className="divide-y divide-zinc-100 rounded-xl border border-zinc-200 text-sm">
                      {[["Plan", `${PLAN_LABEL[client.plan]} · ${int(PRICES[client.plan])} COP al mes`], ["Segmento", client.segmento],
                        ["Plataforma", PLATFORMS[client.plataforma]], ["En proceso de baja", client.en_proceso ? "Sí" : "No"],
                        ["Usa la app 5.2.0", client.usa_520 ? "Sí" : "No"]].map(([k, v]) => (
                        <div key={k} className="flex justify-between px-3 py-2"><dt className="text-zinc-500">{k}</dt><dd className="text-zinc-900">{v}</dd></div>
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
    <div className="flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Cómo se decide</h1>
        <p className="mt-1 text-sm text-zinc-500">La misma regla de la sección 7 del notebook.</p>
      </div>
      <Card>
        <Card.Header>
          <Card.Title className="text-base font-semibold text-zinc-900">Llamar conviene si lo que se espera retener supera el costo</Card.Title>
          <p className="text-sm text-zinc-500">El modelo estima, para cada cliente, la probabilidad de que se vaya en los próximos 90 días.</p>
        </Card.Header>
        <Card.Content>
          <div className="rounded-lg bg-zinc-50 px-4 py-3 text-sm font-medium text-zinc-900">
            probabilidad × efectividad × 12 × precio del plan &gt; costo de la llamada
          </div>
        </Card.Content>
      </Card>
      <Card>
        <Card.Header>
          <Card.Title className="text-base font-semibold text-zinc-900">Umbral por plan</Card.Title>
          <p className="text-sm text-zinc-500">Con efectividad de {pct(effectiveness)} y costo de {int(cost)} COP por llamada.</p>
        </Card.Header>
        <Card.Content>
          <Table variant="secondary">
            <Table.ScrollContainer>
              <Table.Content aria-label="Umbral por plan">
                <Table.Header>
                  <Table.Column isRowHeader className="text-xs font-medium text-zinc-600">Plan</Table.Column>
                  <Table.Column className="text-right text-xs font-medium text-zinc-600">Precio mensual</Table.Column>
                  <Table.Column className="text-right text-xs font-medium text-zinc-600">Umbral de riesgo</Table.Column>
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
        </Card.Content>
      </Card>
      <Card>
        <Card.Header><Card.Title className="text-base font-semibold text-zinc-900">Reglas adicionales</Card.Title></Card.Header>
        <Card.Content>
          <ul className="flex list-disc flex-col gap-2 pl-5 text-sm text-zinc-700">
            <li>No se llama a quien ya está en proceso de baja (llamada del equipo en los últimos 30 días o ticket de cancelar en los últimos 90): lo atiende el flujo actual y casi todos se van igual.</li>
            <li>El valor esperado ya descuenta el costo de la llamada. Si es negativo, la llamada cuesta más de lo que se espera retener.</li>
            <li>La efectividad del 40 % es un supuesto del enunciado y es lo que más pesa en el resultado. El piloto con grupo de control propuesto en el memo sirve para reemplazarlo por la efectividad medida.</li>
          </ul>
        </Card.Content>
      </Card>
    </div>
  );
}
