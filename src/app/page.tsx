import { TopBar } from "@/components/TopBar";
import { Workspace } from "@/components/Workspace";

export default function Home() {
	return (
		<div className="flex flex-col min-h-screen bg-paper w-full">
			<TopBar />
			<Workspace />
		</div>
	);
}
