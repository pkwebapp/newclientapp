import { Ionicons } from "@expo/vector-icons";

/**
 * Central, data-driven navigation config.
 *
 * Future-proofing: adding a new primary section is a one-line change here —
 * both the mobile bottom tab bar and the desktop sidebar read from these
 * arrays, so navigation stays consistent across form factors automatically.
 */
export type IconName = keyof typeof Ionicons.glyphMap;

export type TabItem = {
  key: string;
  label: string; // short label for the bottom bar
  icon: IconName; // inactive
  activeIcon: IconName; // active (filled)
  href: string;
  isActive: (path: string) => boolean;
};

export type DrawerItem = {
  key: string;
  label: string;
  sublabel?: string;
  icon: IconName;
  href?: string; // navigate to a route
  action?: "signout" | "home"; // built-in actions handled by the shell
  tone?: "default" | "danger";
};

// ---- Admin (Studio Console) ----
export const ADMIN_TABS: TabItem[] = [
  {
    key: "home",
    label: "Home",
    icon: "home-outline",
    activeIcon: "home",
    href: "/admin",
    isActive: (p) => p === "/admin",
  },
  {
    key: "bookings",
    label: "Bookings",
    icon: "calendar-outline",
    activeIcon: "calendar",
    href: "/admin/bookings",
    isActive: (p) => p.startsWith("/admin/bookings") || p.startsWith("/admin/booking"),
  },
  {
    key: "galleries",
    label: "Galleries",
    icon: "images-outline",
    activeIcon: "images",
    href: "/admin/galleries",
    isActive: (p) => p.startsWith("/admin/galleries") || p.startsWith("/admin/event"),
  },
  {
    key: "clients",
    label: "Clients",
    icon: "people-outline",
    activeIcon: "people",
    href: "/admin/clients",
    isActive: (p) => p === "/admin/clients" || p.startsWith("/admin/client"),
  },
  {
    key: "albums",
    label: "Albums",
    icon: "book-outline",
    activeIcon: "book",
    href: "/admin/albums",
    isActive: (p) => p.startsWith("/admin/album"),
  },
];

// Top-level routes where the bottom tab bar is shown. On any deeper drill-down
// screen (event/client/album detail, create forms, settings) the bar hides so
// the back affordance leads instead — standard native tab behaviour.
export const ADMIN_TAB_ROOTS = [
  "/admin",
  "/admin/bookings",
  "/admin/galleries",
  "/admin/clients",
  "/admin/albums",
];

// Less-used destinations live in the slide-in drawer to keep the tab bar clean.
export const ADMIN_DRAWER_ITEMS: DrawerItem[] = [
  {
    key: "billing",
    label: "Plan & Billing",
    sublabel: "Your plan, usage & upgrades",
    icon: "card-outline",
    href: "/admin/billing",
  },
  {
    key: "settings",
    label: "Studio Settings",
    sublabel: "WhatsApp, call number & review link",
    icon: "settings-outline",
    href: "/admin/settings",
  },
];
// ---- Client (Client Gallery) ----
export const CLIENT_DRAWER_ITEMS: DrawerItem[] = [
  {
    key: "bookings",
    label: "My Bookings",
    sublabel: "Review enquiries, quotes & shoot dates",
    icon: "calendar-outline",
    href: "/client/bookings",
  },
  {
    key: "profile",
    label: "My Profile",
    sublabel: "Your contact & personal details",
    icon: "person-circle-outline",
    href: "/client/profile",
  },
  {
    key: "services",
    label: "Explore Services",
    sublabel: "Photography, films & creative services",
    icon: "sparkles-outline",
    href: "/client/services",
  },
];



export const ADMIN_DRAWER_FOOTER: DrawerItem[] = [
  { key: "home", label: "Landing page", icon: "home-outline", action: "home" },
  { key: "signout", label: "Sign out", icon: "log-out-outline", action: "signout", tone: "danger" },
];
