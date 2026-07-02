"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

// A lightweight, accessible tabs implementation (no Radix dependency). Supports
// controlled (`value`/`onValueChange`) and uncontrolled (`defaultValue`) use.

interface TabsContextValue {
  value: string;
  setValue: (v: string) => void;
  idBase: string;
}
const TabsContext = React.createContext<TabsContextValue | null>(null);

function useTabs(): TabsContextValue {
  const ctx = React.useContext(TabsContext);
  if (!ctx) throw new Error("Tabs components must be used within <Tabs>");
  return ctx;
}

interface TabsProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "onChange"> {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
}

function Tabs({ value, defaultValue, onValueChange, className, children, ...props }: TabsProps) {
  const [internal, setInternal] = React.useState(defaultValue ?? "");
  const current = value ?? internal;
  const idBase = React.useId();
  const setValue = React.useCallback(
    (v: string) => {
      if (value === undefined) setInternal(v);
      onValueChange?.(v);
    },
    [value, onValueChange],
  );
  return (
    <TabsContext.Provider value={{ value: current, setValue, idBase }}>
      <div className={className} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  );
}

const TabsList = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      role="tablist"
      className={cn(
        "inline-flex flex-wrap items-center gap-1 rounded-lg border border-border bg-muted/40 p-1 text-muted-foreground",
        className,
      )}
      {...props}
    />
  ),
);
TabsList.displayName = "TabsList";

interface TriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

const TabsTrigger = React.forwardRef<HTMLButtonElement, TriggerProps>(
  ({ className, value, ...props }, ref) => {
    const { value: current, setValue, idBase } = useTabs();
    const active = current === value;
    return (
      <button
        ref={ref}
        role="tab"
        type="button"
        id={`${idBase}-tab-${value}`}
        aria-selected={active}
        aria-controls={`${idBase}-panel-${value}`}
        tabIndex={active ? 0 : -1}
        onClick={() => setValue(value)}
        className={cn(
          "inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-all",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          active
            ? "bg-background text-foreground shadow-sm ring-1 ring-border"
            : "hover:bg-background/50 hover:text-foreground",
          className,
        )}
        {...props}
      />
    );
  },
);
TabsTrigger.displayName = "TabsTrigger";

interface ContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
}

const TabsContent = React.forwardRef<HTMLDivElement, ContentProps>(
  ({ className, value, ...props }, ref) => {
    const { value: current, idBase } = useTabs();
    if (current !== value) return null;
    return (
      <div
        ref={ref}
        role="tabpanel"
        id={`${idBase}-panel-${value}`}
        aria-labelledby={`${idBase}-tab-${value}`}
        className={cn("mt-4 animate-fade-in focus-visible:outline-none", className)}
        {...props}
      />
    );
  },
);
TabsContent.displayName = "TabsContent";

export { Tabs, TabsList, TabsTrigger, TabsContent };
