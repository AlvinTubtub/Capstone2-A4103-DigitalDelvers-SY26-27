"use client";

import React, { useState, useEffect, useRef, useId, useCallback } from "react";
import { COMPANY_TOOLTIPS, type CompanyTooltipId } from "@/lib/tooltipContent";

export interface InfoTooltipProps {
  id: CompanyTooltipId;
  align?: "left" | "right" | "auto";
  className?: string;
}

export default function InfoTooltip({
  id,
  align = "auto",
  className = "",
}: InfoTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [horizontalAlign, setHorizontalAlign] = useState<"left" | "right">("left");
  const [verticalPlacement, setVerticalPlacement] = useState<"bottom" | "top">("bottom");

  const containerRef = useRef<HTMLSpanElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const reactId = useId();
  const tooltipContent = COMPANY_TOOLTIPS[id];

  // Adjust placement based on viewport boundaries when opened
  const calculatePosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const tooltipWidth = 260; // Approximate card width
    const tooltipHeight = 110; // Approximate card height

    // Horizontal positioning
    if (align === "right") {
      setHorizontalAlign("right");
    } else if (align === "left") {
      setHorizontalAlign("left");
    } else {
      // Auto: if not enough space on right, align right
      const spaceOnRight = window.innerWidth - rect.left;
      if (spaceOnRight < tooltipWidth + 16 && rect.right > tooltipWidth) {
        setHorizontalAlign("right");
      } else {
        setHorizontalAlign("left");
      }
    }

    // Vertical positioning
    const spaceBelow = window.innerHeight - rect.bottom;
    if (spaceBelow < tooltipHeight + 16 && rect.top > tooltipHeight + 16) {
      setVerticalPlacement("top");
    } else {
      setVerticalPlacement("bottom");
    }
  }, [align]);

  const closeTooltip = useCallback(() => {
    setIsOpen(false);
  }, []);

  const openTooltip = useCallback(() => {
    // Notify all other tooltips to close so only one remains open
    window.dispatchEvent(
      new CustomEvent("pse-tooltip-opened", { detail: { id: reactId } })
    );
    calculatePosition();
    setIsOpen(true);
  }, [calculatePosition, reactId]);

  const toggleTooltip = useCallback(() => {
    if (isOpen) {
      closeTooltip();
    } else {
      openTooltip();
    }
  }, [isOpen, closeTooltip, openTooltip]);

  // Listen for other tooltips opening
  useEffect(() => {
    const handleOtherOpen = (e: Event) => {
      const customEvent = e as CustomEvent<{ id: string }>;
      if (customEvent.detail?.id !== reactId) {
        setIsOpen(false);
      }
    };

    window.addEventListener("pse-tooltip-opened", handleOtherOpen);
    return () => {
      window.removeEventListener("pse-tooltip-opened", handleOtherOpen);
    };
  }, [reactId]);

  // Handle outside click, escape key, and scroll/resize repositioning when open
  useEffect(() => {
    if (!isOpen) return;

    const handlePointerDown = (e: PointerEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        closeTooltip();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeTooltip();
        triggerRef.current?.focus();
      }
    };

    const handleResizeOrScroll = () => {
      calculatePosition();
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("resize", handleResizeOrScroll, { passive: true });

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("resize", handleResizeOrScroll);
    };
  }, [isOpen, closeTooltip, calculatePosition]);

  if (!tooltipContent) {
    if (process.env.NODE_ENV !== "production") {
      console.warn(`[InfoTooltip] Unknown tooltip ID: "${id}"`);
    }
    return null;
  }

  const tooltipElementId = `tooltip-${id}`;
  const triggerElementId = `tooltip-trigger-${id}`;

  return (
    <span
      ref={containerRef}
      className={`relative inline-flex items-center align-middle pointer-events-auto ${className}`}
    >
      <button
        ref={triggerRef}
        id={triggerElementId}
        type="button"
        data-tooltip-id={id}
        aria-label={`More information about ${tooltipContent.title}`}
        aria-expanded={isOpen}
        aria-controls={tooltipElementId}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          toggleTooltip();
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            e.stopPropagation();
            toggleTooltip();
          }
        }}
        className="group inline-flex items-center justify-center p-0.5 rounded-full text-slate-400 hover:text-brand-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-1 focus-visible:ring-offset-dark-bg cursor-pointer transition-colors"
      >
        <svg
          className="w-3.5 h-3.5 text-slate-400 group-hover:text-brand-300 group-focus-visible:text-brand-300 transition-colors"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {isOpen && (
        <div
          ref={tooltipRef}
          id={tooltipElementId}
          role="tooltip"
          className={`absolute z-50 w-64 max-w-[calc(100vw-2rem)] p-3 rounded-xl bg-slate-900 border border-slate-700/90 shadow-2xl shadow-black/80 text-left select-text pointer-events-auto transition-opacity duration-150 animate-in fade-in-0 zoom-in-95 ${
            verticalPlacement === "top"
              ? "bottom-full mb-1.5"
              : "top-full mt-1.5"
          } ${
            horizontalAlign === "right" ? "right-0" : "left-0"
          }`}
          onClick={(e) => e.stopPropagation()}
        >
          <h4 className="text-xs font-semibold text-white tracking-tight mb-1">
            {tooltipContent.title}
          </h4>
          <p className="text-[11px] leading-relaxed text-slate-300">
            {tooltipContent.body}
          </p>
        </div>
      )}
    </span>
  );
}
