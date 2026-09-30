import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Newsreader } from "next/font/google";
import "./globals.css";

const newsreader = Newsreader({
	subsets: ["latin"],
	style: ["normal", "italic"],
	variable: "--font-newsreader",
});

const ibmPlexSans = IBM_Plex_Sans({
	weight: ["400", "500", "600", "700"],
	subsets: ["latin"],
	variable: "--font-ibm-plex-sans",
});

const ibmPlexMono = IBM_Plex_Mono({
	weight: ["400", "500"],
	subsets: ["latin"],
	variable: "--font-ibm-plex-mono",
});

export const metadata: Metadata = {
	title: "Replate",
	description: "Change the words. Keep the picture.",
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html
			lang="en"
			className={`${newsreader.variable} ${ibmPlexSans.variable} ${ibmPlexMono.variable} h-full antialiased`}
		>
			<body className="min-h-full flex flex-col">{children}</body>
		</html>
	);
}
