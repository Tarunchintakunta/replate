import Link from "next/link";
import { CompareSlider } from "@/components/landing/CompareSlider";
import { ReplaceDemo } from "@/components/landing/ReplaceDemo";
import { Reveal } from "@/components/landing/Reveal";
import { currentUser } from "../../lib/auth/current-user";

export const dynamic = "force-dynamic";

const primary =
	"inline-flex items-center justify-center rounded-md bg-green px-5 py-2.5 font-medium text-paper transition-transform duration-150 hover:-translate-y-px active:translate-y-0 focus:outline-none focus:ring-2 focus:ring-green focus:ring-offset-2 focus:ring-offset-paper";
const secondary =
	"inline-flex items-center justify-center rounded-md border border-ink px-5 py-2.5 font-medium text-ink transition-colors duration-150 hover:bg-sheet focus:outline-none focus:ring-2 focus:ring-green focus:ring-offset-2 focus:ring-offset-paper";

const STEPS = [
	[
		"Upload",
		"Drop a PNG, JPG, or WebP up to 8 MB. Replate reads every line of text on it.",
	],
	[
		"Choose",
		"Tick the lines to change and type the new words. Draw a box for anything it missed.",
	],
	[
		"Download",
		"The old words are erased and the new ones set in the closest font, size, and colour.",
	],
] as const;

export default async function Landing() {
	const user = await currentUser();

	return (
		<div className="flex flex-col min-h-screen bg-paper text-ink">
			<header className="sticky top-0 z-20 border-b border-rule bg-paper">
				<nav className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
					<Link
						href="/"
						className="font-display italic text-2xl font-semibold tracking-tight"
					>
						Replate
					</Link>
					<div className="flex items-center gap-2 sm:gap-4 text-sm">
						<a
							href="#how"
							className="hidden sm:inline text-ink/80 hover:text-ink"
						>
							How it works
						</a>
						<a
							href="#example"
							className="hidden sm:inline text-ink/80 hover:text-ink"
						>
							Example
						</a>
						{user ? (
							<Link href="/dashboard" className={`${primary} px-4 py-2`}>
								Open dashboard
							</Link>
						) : (
							<>
								<Link
									href="/signin"
									className="px-2 py-2 text-ink hover:underline underline-offset-4"
								>
									Sign in
								</Link>
								<Link href="/signup" className={`${primary} px-4 py-2`}>
									Create account
								</Link>
							</>
						)}
					</div>
				</nav>
			</header>

			<main className="flex-1">
				{/* Hero */}
				<section className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-14 sm:px-6 md:grid-cols-[1.05fr_1fr] md:py-24">
					<div>
						<p className="rise font-mono text-xs uppercase tracking-[0.18em] text-green">
							Text replacement for finished images
						</p>
						<h1
							className="rise mt-4 font-display text-5xl font-semibold leading-[1.02] tracking-tight sm:text-6xl lg:text-7xl"
							style={{ animationDelay: "80ms" }}
						>
							Change the words.
							<br />
							<span className="italic text-green">Keep the picture.</span>
						</h1>
						<p
							className="rise mt-6 max-w-xl text-lg leading-relaxed text-ink/80"
							style={{ animationDelay: "160ms" }}
						>
							Upload a poster, menu, or screenshot. Pick the lines, type the new
							words, and download the same image with the text changed, in a
							matching font, size, and colour.
						</p>
						<div
							className="rise mt-8 flex flex-wrap gap-3"
							style={{ animationDelay: "240ms" }}
						>
							{user ? (
								<Link href="/dashboard" className={primary}>
									Open dashboard
								</Link>
							) : (
								<>
									<Link href="/signup" className={primary}>
										Start free with 10 credits
									</Link>
									<Link href="/signin" className={secondary}>
										Sign in
									</Link>
								</>
							)}
						</div>
						<p
							className="rise mt-4 text-sm text-ink/60"
							style={{ animationDelay: "320ms" }}
						>
							One image costs 10 credits. Font and background matching is
							best-effort.
						</p>
					</div>
					<div
						className="rise flex justify-center md:justify-end"
						style={{ animationDelay: "200ms" }}
					>
						<ReplaceDemo />
					</div>
				</section>

				{/* Example */}
				<section id="example" className="border-y border-rule bg-sheet">
					<div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
						<Reveal className="max-w-2xl">
							<h2 className="font-display text-4xl font-semibold tracking-tight sm:text-5xl">
								One poster, four new lines.
							</h2>
							<p className="mt-4 text-lg text-ink/80">
								This is real output from the Replate built-in editor. The
								headline kept its Didot, the date its Futura, the details their
								Gill Sans. Drag the handle to compare.
							</p>
						</Reveal>
						<Reveal className="mt-10 mx-auto max-w-4xl" delay={120}>
							<CompareSlider
								before="/demo/before.webp"
								after="/demo/after.webp"
								alt="a market poster, Summer Market on 14 June changed to Autumn Market on 21 September"
							/>
						</Reveal>
					</div>
				</section>

				{/* How it works */}
				<section
					id="how"
					className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24"
				>
					<Reveal>
						<h2 className="font-display text-4xl font-semibold tracking-tight sm:text-5xl">
							How it works
						</h2>
					</Reveal>
					<ol className="mt-10 grid gap-6 md:grid-cols-3">
						{STEPS.map(([title, body], i) => (
							<li key={title}>
								<Reveal delay={i * 120} className="h-full">
									<div className="group h-full rounded-md border border-rule bg-sheet p-6 transition-colors duration-150 hover:border-ink">
										<span className="font-display text-5xl italic text-green">
											{i + 1}
										</span>
										<h3 className="mt-3 text-xl font-semibold">{title}</h3>
										<p className="mt-2 text-ink/75 leading-relaxed">{body}</p>
									</div>
								</Reveal>
							</li>
						))}
					</ol>
				</section>

				{/* Honest limits */}
				<section className="border-t border-rule">
					<div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-2 md:py-20">
						<Reveal>
							<h2 className="font-display text-3xl font-semibold tracking-tight">
								Good at
							</h2>
							<ul className="mt-4 space-y-2 text-ink/80">
								<li>Flat and gradient backgrounds</li>
								<li>Posters, menus, price tags, slides, and screenshots</li>
								<li>Keeping every pixel outside the changed lines untouched</li>
								<li>Spelling the new words exactly as typed</li>
							</ul>
						</Reveal>
						<Reveal delay={120}>
							<h2 className="font-display text-3xl font-semibold tracking-tight">
								Still hard
							</h2>
							<ul className="mt-4 space-y-2 text-ink/80">
								<li>
									Text over busy photos, where the erased patch can look soft
								</li>
								<li>Curved, rotated, or hand-lettered text</li>
								<li>
									A replacement much longer than the original, which shrinks to
									fit
								</li>
							</ul>
						</Reveal>
					</div>
				</section>

				{/* Call to action */}
				<section className="bg-green text-paper">
					<Reveal className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 px-4 py-14 sm:px-6 md:flex-row md:items-center">
						<div>
							<h2 className="font-display text-4xl font-semibold italic tracking-tight">
								Fix the typo, not the design.
							</h2>
							<p className="mt-2 text-paper/80">Your first image is on us.</p>
						</div>
						<Link
							href={user ? "/dashboard" : "/signup"}
							className="inline-flex items-center justify-center rounded-md bg-paper px-5 py-2.5 font-medium text-green transition-transform duration-150 hover:-translate-y-px focus:outline-none focus:ring-2 focus:ring-paper focus:ring-offset-2 focus:ring-offset-green"
						>
							{user ? "Open dashboard" : "Create account"}
						</Link>
					</Reveal>
				</section>
			</main>

			<footer className="border-t border-rule">
				<div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-sm text-ink/60 sm:px-6">
					<span className="font-display italic text-lg text-ink">Replate</span>
					<span>Change the words. Keep the picture.</span>
				</div>
			</footer>
		</div>
	);
}
