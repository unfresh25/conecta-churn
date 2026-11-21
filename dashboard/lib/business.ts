// Economía del contacto, igual que conecta/business.py:
// valor esperado = p · efectividad · 12 · precio − costo; se llama si es positivo y el cliente no está en proceso de baja.

export const PRICES = { Basico: 23_900, Estandar: 34_900, Premium: 49_900, Familiar: 59_900 } as const;
export type Plan = keyof typeof PRICES;
export const PLANS = Object.keys(PRICES) as Plan[];
export const CONTACT_COST = 25_000;
export const EFFECTIVENESS = 0.4;
const VALUE_MONTHS = 12;

export type Client = {
  cliente_id: number;
  plan: Plan;
  segmento: string;
  plataforma: string;
  probabilidad: number;
  en_proceso: number;
  usa_520: number;
  contactar: number;
  factor_1: string | null;
  factor_2: string | null;
  factor_3: string | null;
};

export type Decision = "Llamar" | "No llamar" | "En proceso de baja";
export type Risk = "Alto" | "Medio" | "Bajo";
export type Scored = Client & { value: number; call: boolean; decision: Decision; risk: Risk };

export function threshold(plan: Plan, cost = CONTACT_COST, effectiveness = EFFECTIVENESS): number {
  return cost / (effectiveness * VALUE_MONTHS * PRICES[plan]);
}

export function expectedValue(p: number, plan: Plan, cost = CONTACT_COST, effectiveness = EFFECTIVENESS): number {
  return p * effectiveness * VALUE_MONTHS * PRICES[plan] - cost;
}

export function riskLevel(p: number): Risk {
  return p >= 0.3 ? "Alto" : p >= 0.15 ? "Medio" : "Bajo";
}

export function score(clients: Client[], effectiveness: number, cost: number): Scored[] {
  return clients.map((c) => {
    const value = expectedValue(c.probabilidad, c.plan, cost, effectiveness);
    const inProcess = c.en_proceso === 1;
    const call = value > 0 && !inProcess;
    const decision: Decision = inProcess ? "En proceso de baja" : call ? "Llamar" : "No llamar";
    return { ...c, value, call, decision, risk: riskLevel(c.probabilidad) };
  });
}
