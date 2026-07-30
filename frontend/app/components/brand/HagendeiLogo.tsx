import styles from "./HagendeiLogo.module.css";

type HagendeiMarkProps = {
  className?: string;
  size?: number;
  themed?: boolean;
};

type HagendeiLogoProps = HagendeiMarkProps & {
  light?: boolean;
  showWordmark?: boolean;
};

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export function HagendeiMark({ className, size = 44, themed = false }: HagendeiMarkProps) {
  const primary = themed ? "var(--logo-primary, var(--accent))" : "#3D97E8";
  const secondary = themed ? "var(--logo-secondary, var(--accent-panel))" : "#182742";
  const ribbon = themed ? "var(--logo-ribbon, var(--accent))" : "#228BE0";

  return (
    <svg
      aria-hidden="true"
      className={cx(styles.mark, className)}
      width={size}
      height={size}
      viewBox="0 0 96 96"
      fill="none"
    >
      <path
        d="M11 11h27v37C23.1 48 11 35.9 11 21V11Z"
        fill={primary}
      />
      <path
        d="M58 11h10c9.4 0 17 7.6 17 17v3c0 9.4-7.6 17-17 17H58V11Z"
        fill={secondary}
      />
      <path
        d="M11 65c0-9.4 7.6-17 17-17h10v37H25c-7.7 0-14-6.3-14-14v-6Z"
        fill={secondary}
      />
      <path
        d="M58 48h10c9.4 0 17 7.6 17 17v20H58V48Z"
        fill={primary}
      />
      <path
        d="M11 37c6.8 7.3 13.1 11 19.2 11 7.1 0 10.8-9.2 18.2-9.2 7.3 0 11.2 9.2 18.5 9.2 5.8 0 11.9-3.6 18.1-10.8v17.1C78.8 61.4 72.8 65 66.8 65c-7.4 0-11.2-9.2-18.5-9.2-7.4 0-11.1 9.2-18.2 9.2C23.8 65 17.5 61.5 11 54.5V37Z"
        fill={ribbon}
      />
      <path
        d="M11 37c6.8 7.3 13.1 11 19.2 11 5.1 0 8.5-4.8 12.7-7.4l11.6 12.7c-1.9 1.5-3.8 2.5-6.2 2.5-7.4 0-11.1 9.2-18.2 9.2C23.8 65 17.5 61.5 11 54.5V37Z"
        fill={secondary}
      />
    </svg>
  );
}

export default function HagendeiLogo({
  className,
  light = false,
  showWordmark = true,
  size = 44,
  themed = false,
}: HagendeiLogoProps) {
  return (
    <span
      className={cx(styles.logo, light && styles.light, className)}
      style={{ fontSize: size }}
      aria-label="Hagendei"
      role="img"
    >
      <HagendeiMark size={size} themed={themed} />
      {showWordmark ? <span className={styles.wordmark}>Hagendei</span> : null}
    </span>
  );
}
