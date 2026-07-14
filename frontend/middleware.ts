import { NextRequest, NextResponse } from "next/server";


export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const isProtectedPath =
    pathname === "/" ||
    pathname === "/agenda" ||
    pathname.startsWith("/agenda/") ||
    pathname === "/gestao" ||
    pathname.startsWith("/gestao/") ||
    pathname === "/configuracoes" ||
    pathname.startsWith("/configuracoes/") ||
    pathname.startsWith("/admin");

  if (isProtectedPath) {
    const hasUiSession = req.cookies.get("hagendei_ui_session")?.value === "1";
    if (!hasUiSession) {
      const url = new URL("/login", req.url);
      url.searchParams.set("next", pathname);
      return NextResponse.redirect(url);
    }
  }

  return NextResponse.next();
}


export const config = {
  matcher: ["/", "/agenda/:path*", "/gestao/:path*", "/configuracoes", "/configuracoes/:path*", "/admin/:path*"],
};
