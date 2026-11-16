import {
  Backpack,
  Flame,
  Flashlight,
  Footprints,
  GlassWater,
  Layers,
  Package,
  RotateCcw,
  Search,
  Shirt,
  ShoppingBag,
  Tent,
  Truck,
  type LucideIcon,
} from "lucide-react";
import { useEffect } from "react";

import { Badge } from "@/components/ui";
import { getStore, type Product } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { formatPrice } from "@/lib/utils";

const ICONS: [string, LucideIcon][] = [
  ["tent", Tent],
  ["boots", Footprints],
  ["socks", Layers],
  ["jacket", Shirt],
  ["backpack", Backpack],
  ["bottle", GlassWater],
  ["headlamp", Flashlight],
  ["stove", Flame],
];

const TINTS = [
  "from-emerald-50 to-emerald-100/60 text-emerald-800",
  "from-stone-50 to-stone-100 text-stone-700",
  "from-sky-50 to-sky-100/60 text-sky-800",
  "from-amber-50 to-amber-100/60 text-amber-800",
];

const DEMO_ORDERS = [
  { order: "TS-1002", email: "liam.okafor@example.com", note: "Shipped, in transit" },
  { order: "TS-1003", email: "sofia.ramirez@example.com", note: "Delivered" },
  { order: "TS-1001", email: "maya.chen@example.com", note: "Delivered" },
];

function productIcon(product: Product): LucideIcon {
  return ICONS.find(([tag]) => product.tags.includes(tag))?.[1] ?? Package;
}

function useChatWidget(title: string) {
  useEffect(() => {
    if (document.querySelector("script[data-support-widget]")) return;
    const script = document.createElement("script");
    script.src = "/widget.js";
    script.defer = true;
    script.dataset.supportWidget = "";
    script.dataset.title = title;
    document.body.appendChild(script);
  }, [title]);
}

export function Storefront() {
  const { data } = useAsync(getStore);
  const storeName = data?.name ?? "Trailhead Supply Co.";
  useChatWidget(`${storeName.replace(/ Co\.$/, "")} Support`);

  return (
    <div className="min-h-screen bg-white">
      <div className="bg-zinc-900 px-4 py-2 text-center text-xs text-zinc-300">
        Free US shipping on orders over $75 · 30-day returns
      </div>

      <header className="border-b border-zinc-200">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-8 px-4 sm:px-6">
          <a href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="flex size-7 items-center justify-center rounded-md bg-brand-700 text-white">
              <Tent className="size-4" aria-hidden />
            </span>
            {storeName}
          </a>
          <nav className="hidden gap-6 text-sm text-zinc-600 md:flex">
            <a className="hover:text-zinc-900" href="#shop">
              Shop all
            </a>
            <a className="hover:text-zinc-900" href="#shop">
              Camping
            </a>
            <a className="hover:text-zinc-900" href="#shop">
              Hiking
            </a>
            <a className="hover:text-zinc-900" href="#help">
              Help
            </a>
          </nav>
          <div className="ml-auto flex items-center gap-4 text-zinc-600">
            <Search className="size-5" aria-label="Search" />
            <ShoppingBag className="size-5" aria-label="Cart" />
          </div>
        </div>
      </header>

      <section className="border-b border-zinc-200 bg-gradient-to-b from-brand-50 to-white">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-[1.2fr_1fr] md:items-center md:py-24">
          <div>
            <p className="text-sm font-medium text-brand-700">New season gear</p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-balance text-zinc-900 sm:text-5xl">
              Built for long days on the trail.
            </h1>
            <p className="mt-4 max-w-md text-zinc-600">
              Waterproof shells, broken-in-ready boots and shelters that pitch in five minutes.
              Tested in the rain so you don&apos;t have to.
            </p>
            <a
              href="#shop"
              className="mt-8 inline-flex h-11 items-center rounded-lg bg-zinc-900 px-5 text-sm font-medium text-white hover:bg-zinc-700"
            >
              Shop the collection
            </a>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[Tent, Backpack, Footprints, Shirt].map((Icon, i) => (
              <div
                key={i}
                className={`flex aspect-square items-center justify-center rounded-2xl bg-gradient-to-br ${TINTS[i]}`}
              >
                <Icon className="size-12 opacity-80" strokeWidth={1.25} aria-hidden />
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="shop" className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="flex items-end justify-between">
          <h2 className="text-2xl font-semibold tracking-tight">Shop all gear</h2>
          <p className="text-sm text-zinc-500">{data?.products.length ?? 0} products</p>
        </div>
        <div className="mt-8 grid grid-cols-1 gap-x-6 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
          {data?.products.map((product, i) => {
            const Icon = productIcon(product);
            return (
              <article key={product.sku} className="group">
                <div
                  className={`flex aspect-[4/5] items-center justify-center rounded-xl bg-gradient-to-br ${TINTS[i % TINTS.length]}`}
                >
                  <Icon
                    className="size-16 opacity-80 transition group-hover:scale-105"
                    strokeWidth={1.1}
                    aria-hidden
                  />
                </div>
                <div className="mt-3 flex items-start justify-between gap-3">
                  <h3 className="text-sm font-medium text-zinc-900">{product.title}</h3>
                  <p className="text-sm text-zinc-900">
                    {formatPrice(product.price, product.currency)}
                  </p>
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-zinc-500">{product.description}</p>
                {!product.in_stock && (
                  <div className="mt-2">
                    <Badge>Back soon</Badge>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </section>

      <section id="help" className="border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-14 sm:px-6 md:grid-cols-3">
          {[
            {
              icon: Truck,
              title: "Fast shipping",
              text: "Orders before 2 pm ET ship the same day.",
            },
            { icon: RotateCcw, title: "30-day returns", text: "Free US returns on unused gear." },
            {
              icon: Package,
              title: "1-year warranty",
              text: "Covers manufacturing defects on everything we sell.",
            },
          ].map(({ icon: Icon, title, text }) => (
            <div key={title} className="flex gap-3">
              <Icon className="mt-0.5 size-5 text-brand-700" aria-hidden />
              <div>
                <p className="text-sm font-medium">{title}</p>
                <p className="mt-1 text-sm text-zinc-600">{text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <div className="rounded-xl border border-dashed border-zinc-300 p-6">
          <p className="text-sm font-semibold">Try the support assistant</p>
          <p className="mt-1 text-sm text-zinc-600">
            This is a demo store with fictional orders. Open the chat in the corner and ask about
            one of these orders, or ask about shipping, returns or a product.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-md text-left text-sm">
              <thead className="text-xs text-zinc-500">
                <tr>
                  <th className="py-2 font-medium">Order</th>
                  <th className="py-2 font-medium">Email</th>
                  <th className="py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {DEMO_ORDERS.map((row) => (
                  <tr key={row.order}>
                    <td className="py-2 font-mono text-[13px]">{row.order}</td>
                    <td className="py-2 font-mono text-[13px]">{row.email}</td>
                    <td className="py-2 text-zinc-600">{row.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <footer className="border-t border-zinc-200">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-xs text-zinc-500 sm:flex-row sm:justify-between sm:px-6">
          <p>
            © {new Date().getFullYear()} {storeName}. A fictional store for demonstration.
          </p>
          <a href="/admin" className="hover:text-zinc-900">
            Store admin
          </a>
        </div>
      </footer>
    </div>
  );
}
