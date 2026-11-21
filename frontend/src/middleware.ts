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

/**
 * Validates that redirect paths are strictly safe relative URLs,
 * preventing open redirect attacks and auth loops.
 */
function isSafeRedirect(url: string | null): boolean {
  if (!url) return false;
  return (
    url.startsWith("/") &&
    !url.startsWith("//") &&
    !url.includes("://") &&
    !url.startsWith("/login") &&
    !url.startsWith("/register")
  );
}

export function middleware(request: NextRequest) {
  const { pathname, search, searchParams } = request.nextUrl;
  const token = request.cookies.get("brandproof_token")?.value;

  const isProtected = PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
  const isAuthPage = AUTH_PAGES.some((page) => pathname.startsWith(page));

  // 1. If user reaches an auth page with an expired session or explicit logout, clear stale cookies
  const isExpired = searchParams.get("expired") === "true";
  const isLogout = searchParams.get("logout") === "true";
  const hasInvite = searchParams.has("invite");

  if (isAuthPage && (isExpired || isLogout)) {
    const response = NextResponse.next();
    response.cookies.delete("brandproof_token");
    response.cookies.delete("brandproof_active_org_id");
    return response;
  }

  // 2. Protect private application routes: redirect unauthenticated visitors to login
  if (isProtected && !token) {
    const returnUrl = pathname + search;
    const loginUrl = new URL("/login", request.url);
    if (isSafeRedirect(returnUrl) && returnUrl !== "/dashboard") {
      loginUrl.searchParams.set("redirect", returnUrl);
    }
    return NextResponse.redirect(loginUrl);
  }

  // 3. For auth pages (/login, /register):
  // Never trap users in a redirect loop. If an invitation token is present, allow access.
  // We leave session transition to client-side auth context once getMe() is verified,
  // preventing false-positive bounces caused by stale/expired cookies.
  if (isAuthPage && token && !isExpired && !hasInvite && !isLogout) {
    const redirectParam = searchParams.get("redirect");
    if (isSafeRedirect(redirectParam)) {
      return NextResponse.redirect(new URL(redirectParam!, request.url));
    }
    // Allow the login/register page to load cleanly. If the client confirms an active,
    // verified session via getMe(), the page will seamlessly navigate to /dashboard.
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
