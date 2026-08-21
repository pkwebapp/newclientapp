import { ScrollViewStyleReset } from "expo-router/html";
import { type PropsWithChildren } from "react";

/**
 * Root HTML document for every statically-rendered web route.
 * Runs ONLY in Node during export/prerender — no browser APIs, no global CSS.
 * Site-wide <head> metadata + JSON-LD business schema live here.
 */

const SITE = "https://www.pikconnect.com";
const STUDIO_SITE = "https://www.pkphotography.in";
const OG_IMAGE = "https://pkphotography.in/pricing/PKP_0763%20cover.jpg";
const REVIEW_URL = "https://g.page/r/CVhvUcwRhP2GEAE/review";

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
        <meta name="author" content="PK Photography (Prabhakar Kumar)" />
        <meta name="publisher" content="PK Photography" />
        <meta name="geo.region" content="IN-MH" />
        <meta name="geo.placename" content="Mumbai, Goa" />
        <meta property="og:site_name" content="PIK Connect" />
        <meta property="og:locale" content="en_IN" />
        <title>PIK Connect — Event Photo Galleries by PK Photography</title>
        <meta
          name="description"
          content="Find your event & wedding photos instantly with a selfie. PIK Connect delivers private photo galleries for PK Photography clients across Mumbai & Goa."
        />
        <meta
          name="keywords"
          content="PIK Connect, PK Photography, wedding photographer Mumbai, event photographer Goa, pre-wedding photography Goa, corporate photography Mumbai, event photo gallery, find my photos selfie, destination wedding photographer Goa"
        />
        <meta property="og:type" content="website" />
        <meta property="og:title" content="PIK Connect — Event Photo Galleries by PK Photography" />
        <meta
          property="og:description"
          content="Find your event & wedding photos instantly with a selfie — private galleries for PK Photography clients in Mumbai & Goa."
        />
        <meta property="og:url" content={SITE + "/"} />
        <meta property="og:image" content={OG_IMAGE} />
        <meta property="og:image:width" content="1200" />
        <meta property="og:image:height" content="630" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="PIK Connect — Event Photo Galleries by PK Photography" />
        <meta
          name="twitter:description"
          content="Find your event & wedding photos instantly with a selfie — private galleries for PK Photography clients in Mumbai & Goa."
        />
        <meta name="twitter:image" content={OG_IMAGE} />
        <link rel="canonical" href={SITE + "/"} />
        <link rel="icon" href="/favicon.png" />
        <link rel="apple-touch-icon" href="/favicon.png" />
        <link rel="preconnect" href="https://pkphotography.in" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
        />
        <ScrollViewStyleReset />
      </head>
      <body>{children}</body>
    </html>
  );
}
