type CalendarCheckLogoProps = {
  size?: number;
  variant?: "badge" | "mark";
};

export default function CalendarCheckLogo({ size = 32, variant = "badge" }: CalendarCheckLogoProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 88 88" role="img" aria-label="Hagendei">
      {variant === "badge" ? (
        <rect x="4" y="4" width="80" height="80" rx="20" fill="#1e3a5f" />
      ) : null}
      <rect x="24" y="26" width="40" height="36" rx="6" fill="#ffffff" />
      <rect x="24" y="26" width="40" height="10" rx="6" fill="#d99b3f" />
      <circle cx="34" cy="20" r="3" fill="#ffffff" />
      <circle cx="54" cy="20" r="3" fill="#ffffff" />
      <path
        d="M32 46 L40 54 L56 40"
        stroke="#1e3a5f"
        strokeWidth="4"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
