"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  MessageSquare,
  Grid2X2,
  Folder,
  Zap,
  Monitor,
  Settings,
  Sparkles,
  LucideIcon
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

const navItems: NavItem[] = [
  { label: "Home", href: "/", icon: Home },
  { label: "Chat", href: "/chat", icon: MessageSquare },
  { label: "Apps", href: "/apps", icon: Grid2X2 },
  { label: "Files", href: "/files", icon: Folder },
  { label: "Automations", href: "/automations", icon: Zap },
  { label: "System", href: "/system", icon: Monitor },
  { label: "Settings", href: "/settings", icon: Settings }
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-[235px] shrink-0 h-full bg-[#050506] border-r border-white/10 flex flex-col justify-between p-4 z-30 select-none">
      <div>
        {/* Logo Branding */}
        <div className="pt-2 pb-6 px-2 border-b border-white/5 mb-6">
          <div className="flex items-center gap-1">
            <h1 className="text-2xl font-light tracking-[0.35em] text-white flex items-center font-sans">
              P L U T
              <span className="relative text-[#ff1f2d] font-normal glow-o">
                O
              </span>
            </h1>
          </div>
          <p className="text-[9px] font-mono tracking-widest text-[#ff3344] uppercase mt-1">
            YOUR AI. A MORE CAPABLE YOU.
          </p>
        </div>

        {/* Navigation Items */}
        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "h-[46px] rounded-[11px] px-3.5 flex items-center gap-3 text-xs font-medium transition-all duration-200 group relative",
                  isActive
                    ? "text-white font-semibold shadow-[0_0_25px_rgba(255,31,45,0.12)]"
                    : "text-zinc-400 hover:text-zinc-100 hover:bg-white/5"
                )}
                style={
                  isActive
                    ? {
                        background:
                          "linear-gradient(90deg, rgba(255,31,45,0.18), rgba(255,31,45,0.03))",
                        border: "1px solid rgba(255,31,45,0.5)"
                      }
                    : {
                        border: "1px solid transparent"
                      }
                }
              >
                <Icon
                  className={cn(
                    "w-4 h-4 transition-colors",
                    isActive
                      ? "text-[#ff3344] drop-shadow-[0_0_8px_rgba(255,31,45,0.8)]"
                      : "text-zinc-400 group-hover:text-zinc-200"
                  )}
                />
                <span className="tracking-wide">{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Sidebar Bottom Card */}
      <div className="glass-panel p-4 rounded-xl border border-[#ff1f2d]/25 bg-gradient-to-br from-[#120708] to-[#050506] relative overflow-hidden group">
        <div className="absolute -right-4 -bottom-4 w-20 h-20 bg-[#ff1f2d]/20 rounded-full blur-xl pointer-events-none group-hover:scale-125 transition-transform" />
        <div className="flex items-center gap-2 text-[#ff3344] text-xs font-semibold mb-1">
          <Sparkles className="w-3.5 h-3.5 animate-pulse" />
          <span>PLUTO AI OS</span>
        </div>
        <p className="text-xs text-zinc-300 font-sans leading-relaxed">
          Explore more with PLUTO.
        </p>
        <p className="text-[11px] text-zinc-500 font-sans italic mt-0.5">
          Ideas become actions here.
        </p>
      </div>
    </aside>
  );
}
