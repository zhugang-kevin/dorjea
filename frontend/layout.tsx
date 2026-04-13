import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "Dorjea AI Factory",
  description: "Meta-Agent Control Panel",
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, padding: 0, background: "#0f172a", color: "#e2e8f0", fontFamily: "system-ui, sans-serif" }}>
        {children}
      </body>
    </html>
  );
}
