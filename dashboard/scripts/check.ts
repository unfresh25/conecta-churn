// Comprueba que la regla en TypeScript reproduce la decisión del notebook (columna `contactar`).
import clients from "../data/clientes.json";
import { CONTACT_COST, EFFECTIVENESS, score, type Client } from "../lib/business";

const scored = score(clients as Client[], EFFECTIVENESS, CONTACT_COST);
const mismatches = scored.filter((c) => Number(c.call) !== c.contactar).length;
const calls = scored.filter((c) => c.call);
const net = calls.reduce((s, c) => s + c.value, 0);
const at20 = score(clients as Client[], 0.2, CONTACT_COST).filter((c) => c.call).length;
console.log(`clientes ${scored.length} | a llamar ${calls.length} | valor neto ${(net / 1e6).toFixed(1)} M | a llamar con 20 % ${at20} | diferencias con el notebook ${mismatches}`);
if (mismatches || calls.length !== 634) process.exit(1);
