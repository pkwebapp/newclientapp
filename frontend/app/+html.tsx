import { ScrollViewStyleReset } from "expo-router/html";
import { type PropsWithChildren } from "react";

/**
 * Root HTML document for every statically-rendered web route.
 * Runs ONLY in Node during export/prerender — no browser APIs, no global CSS.
 * Site-wide <head> metadata + JSON-LD business schema live here.
 */

const SITE = "https://www.pikconnect.com";
const STUDIO_SITE = "https://www.pkphotography.in";
const OG_IMAGE = `${SITE}/pik-connect-share-card.png`;
const REVIEW_URL = "https://g.page/r/CVhvUcwRhP2GEAE/review";

const FAVICON = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiByeD0iMTYiIGZpbGw9IiMwRTBEMEMiLz48Y2lyY2xlIGN4PSIzMiIgY3k9IjMyIiByPSIyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjRjQ3QjRBIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1kYXNoYXJyYXk9IjIyIDciLz48cGF0aCBkPSJNMzIgMTZsMTEgNnYxM0wzMiA0MiAyMSAzNVYyMnpNMzIgMjRsNiAzdjdsLTYgMy02LTN2LTd6IiBmaWxsPSIjRjQ3QjRBIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiLz48Y2lyY2xlIGN4PSIzMiIgY3k9IjMyIiByPSIzIiBmaWxsPSIjMEUwRDBDIi8+PC9zdmc+";

const schema = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${STUDIO_SITE}/#org`,
      name: "PK Photography",
      alternateName: "PIK Connect",
      url: STUDIO_SITE,
      logo: OG_IMAGE,
      image: OG_IMAGE,
      email: "prabhakar@pkphotography.in",
      telephone: "+918888766739",
      founder: { "@type": "Person", name: "Prabhakar Kumar" },
      sameAs: [STUDIO_SITE, REVIEW_URL],
      areaServed: ["Mumbai", "Goa", "India"],
    },
    {
      "@type": "WebSite",
      "@id": `${SITE}/#website`,
      name: "PIK Connect",
      url: SITE,
      description:
        "PIK Connect is the client photo-gallery and delivery platform of PK Photography — find your event photos instantly with a selfie.",
      publisher: { "@id": `${STUDIO_SITE}/#org` },
      inLanguage: "en-IN",
    },
    {
      "@type": "SoftwareApplication",
      "@id": `${SITE}/#software`,
      name: "PIK Connect",
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web, iOS, Android",
      url: SITE,
      description: "Photo gallery, AI face search, digital albums and client management for photographers.",
      datePublished: "2026-01-15",
      dateModified: "2026-06-01",
      offers: { "@type": "Offer", price: "499", priceCurrency: "INR" },
      publisher: { "@id": `${STUDIO_SITE}/#org` },
    },
    {
      "@type": "Service",
      "@id": `${SITE}/#service`,
      name: "Event Photo Gallery & AI Face Search",
      serviceType: "Photo gallery, AI face search and digital album delivery",
      url: SITE,
      description:
        "Take one selfie and PIK Connect's AI face search finds every photo of you across a private event photo gallery, with instant digital albums and photo sharing.",
      provider: { "@id": `${STUDIO_SITE}/#org` },
      areaServed: ["Mumbai", "Goa", "India"],
    },
    {
      "@type": "FAQPage",
      "@id": `${SITE}/#faq`,
      mainEntity: [
        {
          "@type": "Question",
          name: "How do I find my photos?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Open the private gallery link your photographer shares (or scan their QR code), take one quick selfie, and PIK Connect's AI face search instantly surfaces every photo of you across the whole event gallery — no scrolling through hundreds of images.",
          },
        },
        {
          "@type": "Question",
          name: "Do I need an app or an account?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "No. PIK Connect opens right in your browser on any phone or laptop. There's no app to download and no account to create — just the gallery link and a selfie to find yourself.",
          },
        },
        {
          "@type": "Question",
          name: "Is my gallery private and secure?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Yes. Every gallery is a private, secure link that only people with the link can open. Your selfie is used solely to match your face to your photos — it's never shared, sold or used for anything else.",
          },
        },
        {
          "@type": "Question",
          name: "Can I download and share my photos?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Absolutely. Once the AI finds you, you can view and save every match in full quality, share them directly, and return to your personal digital album from the same link whenever you like.",
          },
        },
        {
          "@type": "Question",
          name: "What is a digital album or flipbook?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Photographers can turn a designed album PDF into a realistic, page-turning flipbook you can flip through and share online — a beautiful way to relive the event beyond individual photos.",
          },
        },
        {
          "@type": "Question",
          name: "What if the AI misses some of my photos?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Try retaking your selfie in good, even lighting facing the camera. Face search works best with a clear, front-facing shot. If some shots still don't appear, your photographer can help surface them.",
          },
        },
        {
          "@type": "Question",
          name: "I'm a photographer — how does PIK Connect help my studio?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "PIK Connect gives you private client galleries, one-tap QR sharing and AI face search for guests, plus a light studio workspace to manage leads, quotes, payments, shoots and digital albums — all in one place.",
          },
        },
        {
          "@type": "Question",
          name: "How much does PIK Connect cost?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "It's free for guests finding their photos. For studios, plans start at ₹499/mo (Standard) and ₹999/mo (Pro), scaling galleries, albums, storage and clients as your studio grows.",
          },
        },
        {
          "@type": "Question",
          name: "Which cities do you cover?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "PK Photography runs studios in Andheri West, Mumbai and Morjim, Goa — and takes on destination and pan-India shoots for weddings, events and portraits.",
          },
        },
      ],
    },
    {
      "@type": ["LocalBusiness", "ProfessionalService"],
      "@id": `${SITE}/#mumbai`,
      name: "PK Photography — Mumbai Studio",
      image: OG_IMAGE,
      url: SITE,
      telephone: "+918888766739",
      email: "prabhakar@pkphotography.in",
      priceRange: "₹₹",
      parentOrganization: { "@id": `${STUDIO_SITE}/#org` },
      address: {
        "@type": "PostalAddress",
        streetAddress:
          "C1302, Evershine Cosmic, Opp. Infiniti Mall, Veera Desai Industrial Estate",
        addressLocality: "Andheri West, Mumbai",
        addressRegion: "Maharashtra",
        postalCode: "400053",
        addressCountry: "IN",
      },
      geo: { "@type": "GeoCoordinates", latitude: 19.1367, longitude: 72.8291 },
      areaServed: ["Mumbai", "Navi Mumbai", "Thane", "Maharashtra"],
      openingHours: "Mo-Su 09:00-20:00",
      aggregateRating: {
        "@type": "AggregateRating",
        ratingValue: "4.9",
        reviewCount: "380",
      },
    },
    {
      "@type": ["LocalBusiness", "ProfessionalService"],
      "@id": `${SITE}/#goa`,
      name: "PK Photography — Goa Studio",
      image: OG_IMAGE,
      url: SITE,
      telephone: "+918188881165",
      email: "prabhakar@pkphotography.in",
      priceRange: "₹₹",
      parentOrganization: { "@id": `${STUDIO_SITE}/#org` },
      address: {
        "@type": "PostalAddress",
        streetAddress: "House No. 1053 A, Madhlavaddo",
        addressLocality: "Morjim, Goa",
        addressRegion: "Goa",
        postalCode: "403512",
        addressCountry: "IN",
      },
      geo: { "@type": "GeoCoordinates", latitude: 15.6297, longitude: 73.7349 },
      areaServed: ["Goa", "Morjim", "North Goa"],
      openingHours: "Mo-Su 09:00-20:00",
    },
  ],
};

export default function Root({ children }: PropsWithChildren) {
  return (
    <html lang="en-IN">
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, shrink-to-fit=no, viewport-fit=cover"
        />
        <meta name="theme-color" content="#0E0D0C" />
        <meta name="application-name" content="PIK Connect" />
        <meta name="robots" content="index, follow, max-image-preview:large" />
        <meta name="author" content="PK Photography (Prabhakar Kumar)" />
        <meta name="publisher" content="PK Photography" />
        <meta name="geo.region" content="IN-MH" />
        <meta name="geo.placename" content="Mumbai, Goa" />
        <meta property="og:site_name" content="PIK Connect" />
        <meta property="og:locale" content="en_IN" />
        <meta property="og:image" content={OG_IMAGE} />
        <meta property="og:image:alt" content="PIK Connect private photo gallery for photographers" />
        <meta property="og:image:width" content="1200" />
        <meta property="og:image:height" content="630" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:image" content={OG_IMAGE} />
        {/* Fallback <title> for non-indexable app routes without their own <Head>.
            Public, indexable routes (home + marketing) set title/description/
            canonical/og per-page via expo-router <Head>. */}
        <title>AI Face Search Photo Gallery for Events | PIK Connect</title>
        <link rel="icon" type="image/svg+xml" href={FAVICON} />
        <link rel="alternate icon" type="image/png" href="/favicon.png" />
        <link rel="apple-touch-icon" href="/favicon.png" />
        <link rel="preconnect" href="https://pkphotography.in" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
        />
        <ScrollViewStyleReset />
        <style
          dangerouslySetInnerHTML={{
            __html: `
              /* Paint the browser canvas in the app background so no white
                 strip can ever show through on mobile first load, while the
                 dynamic address bar is settling. */
              html, body, #root { background-color: #D8D0C4; }
              html, body { overscroll-behavior-y: none; }
              /* Track the *dynamic* visible viewport (address bar show/hide)
                 instead of the stale 100% computed at first paint. */
              @supports (height: 100dvh) {
                html, body, #root { height: 100dvh; }
              }
            `,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
