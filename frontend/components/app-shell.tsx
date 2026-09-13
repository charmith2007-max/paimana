'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  FolderKanban,
  ShieldAlert,
  Cpu,
  FileUp,
  Menu,
  X,
  
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ApiStatus } from '@/components/api-status'

const NAV = [
  { href: '/', label: 'Overview', icon: LayoutDashboard },
  { href: '/projects', label: 'Projects', icon: FolderKanban },
  { href: '/data-ingestion', label: 'Data Ingestion', icon: FileUp },
  { href: '/risk-intelligence', label: 'Risk Intelligence', icon: ShieldAlert },
  { href: '/model-info', label: 'Model Information', icon: Cpu },
]

function isActive(pathname: string, href: string) {
  if (href === '/') return pathname === '/'
  return pathname === href || pathname.startsWith(`${href}/`)
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex size-9 items-center justify-center rounded-md bg-primary/15 ring-1 ring-inset ring-primary/30">
        <span className="text-sm font-bold tracking-tight text-primary">PA</span>
      </div>
      <div className="leading-tight">
        <p className="text-sm font-bold tracking-[0.18em] text-sidebar-foreground">
          PAIMANA
        </p>
        <p className="text-[10px] font-medium tracking-wide text-muted-foreground">
          GOV INFRA MONITOR
        </p>
      </div>
    </div>
  )
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname()
  return (
    <nav className="flex flex-col gap-1">
      {NAV.map((item) => {
        const active = isActive(pathname, item.href)
        const Icon = item.icon
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              active
                ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
            )}
          >
            <Icon
              className={cn(
                'size-4 transition-colors',
                active ? 'text-primary' : 'text-muted-foreground group-hover:text-sidebar-foreground',
              )}
            />
            {item.label}
          </Link>
        )
      })}
    </nav>
  )
}

function SidebarInner({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 px-4 py-5">
      <Brand />
      <div className="flex-1">
        <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Platform
        </p>
        <NavLinks onNavigate={onNavigate} />
      </div>
      <ApiStatus />
    </div>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="min-h-svh bg-background">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-sidebar-border bg-sidebar lg:block">
        <SidebarInner />
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-sidebar/95 px-4 py-3 backdrop-blur lg:hidden">
        <Brand />
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open navigation menu"
          className="flex size-9 items-center justify-center rounded-md border border-border text-muted-foreground transition-colors hover:text-foreground"
        >
          <Menu className="size-5" />
        </button>
      </header>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85%] border-r border-sidebar-border bg-sidebar shadow-xl">
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close navigation menu"
              className="absolute right-3 top-4 flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="size-5" />
            </button>
            <SidebarInner onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}

      <div className="lg:pl-64">
        <main className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  )
}
