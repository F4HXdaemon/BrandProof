import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/reviews",
  "/evidence",
  "/knowledge",
  "/audit",
  "/insights",
  "/evaluation",
  "/settings",
  "/onboarding",
];

const AUTH_PAGES = ["/login", "/register"];

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const token = request.cookies.get("brandproof_token")?.value;

  const isProtected = PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
  const isAuthPage = AUTH_PAGES.some((page) => pathname.startsWith(page));

  // 1. Redirect unauthenticated users attempting to access protected pages
  if (isProtected && !token) {
    const returnUrl = pathname + search;
    const loginUrl = new URL("/login", request.url);
    if (returnUrl && returnUrl !== "/dashboard") {
      loginUrl.searchParams.set("redirect", returnUrl);
    }
    return NextResponse.redirect(loginUrl);
  }

  // 2. Redirect authenticated users away from login/register
  if (isAuthPage && token) {
    const redirectParam = request.nextUrl.searchParams.get("redirect");
    const target =
      redirectParam &&
      redirectParam.startsWith("/") &&
      !redirectParam.startsWith("//") &&
      !redirectParam.startsWith("/login")
        ? redirectParam
        : "/dashboard";
    return NextResponse.redirect(new URL(target, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/reviews/:path*",
    "/evidence/:path*",
    "/knowledge/:path*",
    "/audit/:path*",
    "/insights/:path*",
    "/evaluation/:path*",
    "/settings/:path*",
    "/onboarding/:path*",
    "/login",
    "/register",
  ],
};
