import Image from "next/image";

interface BrandLogoProps {
  variant?: "navbar" | "full" | "mark";
  size?: "sm" | "md" | "lg";
  forceDark?: boolean;
  className?: string;
  priority?: boolean;
}

export default function BrandLogo({
  variant = "navbar",
  size = "md",
  forceDark = false,
  className = "",
  priority = true,
}: BrandLogoProps) {
  if (variant === "mark") {
    const markHeightClasses =
      size === "sm"
        ? "h-5 sm:h-6 w-auto"
        : size === "lg"
        ? "h-10 sm:h-12 lg:h-14 w-auto"
        : "h-7 sm:h-8 lg:h-9 w-auto";

    if (forceDark) {
      return (
        <div className={`relative flex items-center shrink-0 ${className}`}>
          <Image
            src="/brand/pse-pulse-mark-dark.png"
            alt="PSE Pulse Mark"
            width={70}
            height={56}
            priority={priority}
            className={`${markHeightClasses} object-contain select-none pointer-events-none`}
          />
        </div>
      );
    }

    return (
      <div className={`relative flex items-center shrink-0 ${className}`}>
        {/* Dark Mode Mark (also displayed inside dark surfaces) */}
        <Image
          src="/brand/pse-pulse-mark-dark.png"
          alt="PSE Pulse Mark"
          width={70}
          height={56}
          priority={priority}
          className={`hidden dark:block [.dark-surface_&]:block ${markHeightClasses} object-contain select-none pointer-events-none`}
        />
        {/* Light Mode Mark (hidden in dark mode or inside dark surfaces) */}
        <Image
          src="/brand/pse-pulse-mark-light.png"
          alt="PSE Pulse Mark"
          width={70}
          height={56}
          priority={priority}
          className={`block dark:hidden [.dark-surface_&]:hidden ${markHeightClasses} object-contain select-none pointer-events-none`}
        />
      </div>
    );
  }

  // navbar / full wordmark
  const heightClasses =
    size === "sm"
      ? "h-6 sm:h-7 w-auto"
      : size === "lg"
      ? "h-10 sm:h-12 w-auto"
      : variant === "navbar"
      ? "h-7 sm:h-8 w-auto"
      : "h-9 sm:h-10 w-auto";

  if (forceDark) {
    return (
      <div className={`relative flex items-center shrink-0 ${className}`}>
        <Image
          src="/brand/pse-pulse-wordmark-dark.png"
          alt="PSE Pulse"
          width={140}
          height={45}
          priority={priority}
          className={`${heightClasses} object-contain select-none pointer-events-none`}
        />
      </div>
    );
  }

  return (
    <div className={`relative flex items-center shrink-0 ${className}`}>
      {/* Dark Mode Wordmark (White text and pulse, vibrant mark) */}
      <Image
        src="/brand/pse-pulse-wordmark-dark.png"
        alt="PSE Pulse"
        width={140}
        height={45}
        priority={priority}
        className={`hidden dark:block [.dark-surface_&]:block ${heightClasses} object-contain select-none pointer-events-none`}
      />
      {/* Light Mode Wordmark (Dark slate text and pulse, vibrant mark) */}
      <Image
        src="/brand/pse-pulse-wordmark-light.png"
        alt="PSE Pulse"
        width={140}
        height={45}
        priority={priority}
        className={`block dark:hidden [.dark-surface_&]:hidden ${heightClasses} object-contain select-none pointer-events-none`}
      />
    </div>
  );
}
