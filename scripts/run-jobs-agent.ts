import { CAREERS } from "../lib/careers";
import { fetchListingsForCareer } from "../lib/jobs-agent";

async function main() {
  const summary: Array<{ career: string; count: number; topPay: number }> = [];
  for (const c of CAREERS) {
    const listings = await fetchListingsForCareer(c.id);
    summary.push({
      career: c.name,
      count: listings.length,
      topPay: listings[0]?.annualPayUsd ?? 0,
    });
  }
  console.table(summary);
  const totalOver100k = summary.reduce((a, b) => a + b.count, 0);
  console.log(`\nTotal ≥$100K listings across ${CAREERS.length} careers: ${totalOver100k}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
