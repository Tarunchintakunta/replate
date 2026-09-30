export function TopBar() {
	return (
		<header className="h-[56px] border-b border-rule flex items-center justify-between px-4 shrink-0">
			<div className="flex items-center">
				<h1 className="font-display italic text-2xl font-semibold tracking-tight text-ink">
					Replate
				</h1>
			</div>
			<div className="flex items-center gap-4 text-sm">
				<div className="flex items-center gap-2">
					<span className="text-ink">Credits:</span>
					<span className="font-mono bg-wash px-2 py-0.5 rounded text-ink border border-rule">
						10
					</span>
				</div>
				<div className="bg-wash px-2 py-0.5 rounded text-ink border border-rule">
					Local preview
				</div>
			</div>
		</header>
	);
}
