"use client"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface MetricsCardProps {
  label: string
  value: string | number
  icon: React.ReactNode
  trend?: "up" | "down" | "neutral"
  className?: string
}

export function MetricsCard({ label, value, icon, trend, className }: MetricsCardProps) {
  return (
    <Card className={cn("bg-card border-border/50", className)}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              {label}
            </p>
            <p className="text-2xl font-semibold text-foreground">{value}</p>
          </div>
          <div
            className={cn(
              "w-10 h-10 rounded-lg flex items-center justify-center",
              trend === "up" && "bg-emerald-500/10 text-emerald-500",
              trend === "down" && "bg-red-500/10 text-red-500",
              (!trend || trend === "neutral") && "bg-primary/10 text-primary"
            )}
          >
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
