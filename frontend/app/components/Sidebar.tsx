"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import CalendarCheckLogo from "./icons/CalendarCheckLogo";
import styles from "./Sidebar.module.css";

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export type NavItem = {
  href: string;
  label: string;
  icon: React.ElementType;
};

type SidebarProps = {
  navItems: NavItem[];
};

export default function Sidebar({ navItems }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside className={styles.sidebar} aria-label="Navegacao principal">
      <Link href="/" className={styles.brand} aria-label="Hagendei">
        <CalendarCheckLogo size={26} variant="mark" />
      </Link>

      <nav className={styles.nav}>
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cx(styles.navLink, isActive && styles.navLinkActive)}
            >
              <Icon size={20} />
              <span className={styles.tooltip}>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
