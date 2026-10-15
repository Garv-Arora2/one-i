import type { Metadata } from "next";

import { Footer } from "@/components/Footer";
import { Masthead } from "@/components/Masthead";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ONE I",
    template: "%s · ONE I",
  },
  description:
    "ONE I examines media coverage. For the same event, it shows what each source reported, where they differ in numbers and wording, and who covered what.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="sr-only">Skip to content</a>
        <Masthead />
        <main id="main">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
