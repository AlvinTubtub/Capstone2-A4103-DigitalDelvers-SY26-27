import { notFound } from "next/navigation";
import CompanyDetailView from "@/components/company/CompanyDetailView";
import { getAllSymbols, getCompanyDetail } from "@/lib/data";

export async function generateStaticParams() {
  const symbols = await getAllSymbols();
  return symbols.map((symbol) => ({ symbol }));
}

export default async function CompanyDetailPage({ params }: { params: { symbol: string } }) {
  const company = await getCompanyDetail(params.symbol);
  if (!company) notFound();

  return <CompanyDetailView key={company.symbol} company={company} />;
}
