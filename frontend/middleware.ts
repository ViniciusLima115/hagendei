import { NextRequest, NextResponse } from "next/server";


export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (pathname.startsWith("/admin")) {
    const token = req.cookies.get("token")?.value;
    if (!token) {
      const url = new URL("/login", req.url);
      url.searchParams.set("next", pathname);
      return NextResponse.redirect(url);
    }
  }

  return NextResponse.next();
}


export const config = {
  matcher: ["/admin/:path*"],
};
