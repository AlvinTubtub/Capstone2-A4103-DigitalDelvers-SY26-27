import { Metadata } from "next";
import { getCompanies, getMetrics } from "@/lib/data";
import WatchlistClient from "./WatchlistClient";

export const metadata: Metadata = {
  title: "My Watchlist | PSE Pulse",
  description: "Monitor up to 5 PSE-listed companies and track their next-day PSE Pulse price predictions.",
};

export default async function WatchlistPage() {
  const [companies, metrics] = await Promise.all([getCompanies(), getMetrics()]);

  return <WatchlistClient allCompanies={companies} metrics={metrics} />;
}
