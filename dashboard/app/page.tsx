import Dashboard from "../components/Dashboard";
import clients from "../data/clientes.json";
import type { Client } from "../lib/business";

export default function Page() {
  return <Dashboard clients={clients as Client[]} />;
}
