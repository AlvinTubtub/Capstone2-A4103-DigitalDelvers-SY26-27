import Image from "next/image";

interface BrandLogoProps {
  variant?: "navbar" | "full" | "mark";
  className?: string;
  priority?: boolean;
}

export default function BrandLogo({
  variant = "navbar",
  className = "",
  priority = true,
}: BrandLogoProps) {
  if (variant === "mark") {
    return (
      <div className={`relative flex items-center shrink-0 ${className}`}>
        {/* Dark Mode Mark */}
        <Image
          src="/brand/pse-pulse-mark-dark.png"
          alt="PSE Pulse Mark"
          width={40}
          height={32}
          priority={priority}
          className="hidden dark:block h-8 w-auto object-contain select-none pointer-events-none"
        />
        {/* Light Mode Mark */}
        <Image
          src="/brand/pse-pulse-mark-light.png"
          alt="PSE Pulse Mark"
          width={40}
          height={32}
          priority={priority}
          className="block dark:hidden h-8 w-auto object-contain select-none pointer-events-none"
        />
      </div>
    );
  }

  // navbar / full wordmark
  const heightClasses =
    variant === "navbar"
      ? "h-7 sm:h-8 w-auto"
      : "h-9 sm:h-10 w-auto";

  return (
    <div className={`relative flex items-center shrink-0 ${className}`}>
      {/* Dark Mode Wordmark (White text and pulse, vibrant mark) */}
      <Image
        src="/brand/pse-pulse-wordmark-dark.png"
        alt="PSE Pulse"
        width={140}
        height={45}
        priority={priority}
        className={`hidden dark:block ${heightClasses} object-contain select-none pointer-events-none`}
      />
      {/* Light Mode Wordmark (Dark slate text and pulse, vibrant mark) */}
      <Image
        src="/brand/pse-pulse-wordmark-light.png"
        alt="PSE Pulse"
        width={140}
        height={45}
        priority={priority}
        className={`block dark:hidden ${heightClasses} object-contain select-none pointer-events-none`}
      />
    </div>
  );
}
