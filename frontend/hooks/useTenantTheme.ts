"use client";

import { useEffect } from "react";
import { useAuthSession } from "@/services/auth";
import {
  applyTenantTheme,
  DEFAULT_ACCENT_COLOR,
  DEFAULT_BACKGROUND_COLOR,
} from "@/lib/theme";

export function useTenantTheme() {
  const session = useAuthSession();

  useEffect(() => {
    const root = document.documentElement;
    const apply = () =>
      applyTenantTheme(
        root,
        session?.accentColor || DEFAULT_ACCENT_COLOR,
        session?.bgColor || DEFAULT_BACKGROUND_COLOR,
      );

    apply();

    const observer = new MutationObserver((mutations) => {
      if (mutations.some((mutation) => mutation.attributeName === "data-theme")) {
        apply();
      }
    });
    observer.observe(root, { attributes: true, attributeFilter: ["data-theme"] });

    return () => observer.disconnect();
  }, [session?.accentColor, session?.bgColor]);
}
