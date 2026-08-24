import { NextRequest, NextResponse } from "next/server";
import { fetchListingsForCareer } from "@/lib/jobs-agent";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const careerId = req.nextUrl.searchParams.get("career");
  if (!careerId) {
    return NextResponse.json({ error: "career query param required" }, { status: 400 });
  }
  const listings = await fetchListingsForCareer(careerId);
  return NextResponse.json({ listings });
}
