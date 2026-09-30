import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'ATLAS BI — Retail intelligence', description: 'Traceable retail analytics and predictive intelligence.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
