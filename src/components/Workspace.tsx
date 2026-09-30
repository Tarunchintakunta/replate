export function Workspace() {
	return (
		<main className="flex-1 flex flex-col items-center justify-center p-4 lg:p-8">
			<div className="text-center mb-8">
				<p className="text-lg text-ink font-medium">
					Change the words. Keep the picture.
				</p>
			</div>

			<div className="w-full max-w-6xl mx-auto flex flex-col md:flex-row gap-6 flex-1 min-h-0">
				{/* Left column (Image / Drop area) */}
				<div
					data-testid="left-col"
					className="w-full md:w-[60%] flex flex-col relative"
				>
					<div className="flex-1 border border-rule rounded-md border-dashed bg-wash flex items-center justify-center p-6 focus-within:ring-2 focus-within:ring-green focus-within:ring-offset-2 focus-within:ring-offset-paper transition-shadow">
						{/* The drop area might need a button or input to be focusable */}
						<label className="cursor-pointer text-center flex flex-col items-center w-full h-full justify-center">
							<span className="text-ink font-medium">
								Drop a PNG, JPG, or WebP.
							</span>
							<input
								type="file"
								className="sr-only"
								aria-label="Drop a PNG, JPG, or WebP."
							/>
						</label>
					</div>
				</div>

				{/* Right column (Lines / Controls) */}
				<div
					data-testid="right-col"
					className="w-full md:w-[40%] flex flex-col gap-4"
				>
					<div className="flex-1 border border-rule rounded-md p-4 bg-paper flex flex-col">
						<h2 className="font-semibold text-ink mb-4">Lines</h2>
						{/* Empty space for future list */}
						<div className="text-sm text-ink opacity-70">
							No image uploaded.
						</div>
					</div>

					<div className="border-t border-rule pt-4 flex flex-col gap-2">
						<button
							type="button"
							disabled
							className="bg-green text-paper py-2 px-4 rounded-md font-medium opacity-40 cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-green focus:ring-offset-2 focus:ring-offset-paper transition-shadow"
						>
							Generate
						</button>
						<div className="text-sm text-center text-ink opacity-70">
							10 credits
						</div>
					</div>
				</div>
			</div>
		</main>
	);
}
