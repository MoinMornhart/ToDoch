import { api } from '$lib/api';
import type { Area } from '$lib/types';

const STORAGE_KEY = 'todoch.area';

function loadSelection(): string {
	try {
		return localStorage.getItem(STORAGE_KEY) ?? 'all';
	} catch {
		return 'all';
	}
}

class Areas {
	list = $state<Area[]>([]);
	selected = $state<string>(loadSelection());

	/** Area-ID für API-Filter oder `undefined` bei „Alle Bereiche“. */
	get filterId(): string | undefined {
		return this.selected === 'all' ? undefined : this.selected;
	}

	get current(): Area | undefined {
		return this.list.find((a) => a.id === this.selected);
	}

	byId(id: string): Area | undefined {
		return this.list.find((a) => a.id === id);
	}

	async refresh(): Promise<void> {
		this.list = await api<Area[]>('/areas');
		if (this.selected !== 'all' && !this.byId(this.selected)) this.select('all');
	}

	select(id: string): void {
		this.selected = id;
		try {
			localStorage.setItem(STORAGE_KEY, id);
		} catch {
			/* privater Modus */
		}
	}
}

export const areas = new Areas();
