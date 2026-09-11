import { api, ApiError } from '$lib/api';
import { t } from '$lib/i18n/index.svelte';
import { areas } from '$lib/stores/areas.svelte';
import { toasts } from '$lib/stores/toasts.svelte';
import { ui } from '$lib/stores/ui.svelte';
import type { CompleteResult, Task } from '$lib/types';

type Params = Record<string, string | undefined>;

/**
 * Reaktive Aufgabenliste: lädt neu, wenn sich Parameter, Bereichsauswahl oder
 * Aufgaben (ui.version) ändern. Muss während der Komponenten-Initialisierung laufen.
 */
export function taskQuery(params: () => Params) {
	const state = $state({ tasks: [] as Task[], loading: true, error: null as string | null });
	let sequence = 0;

	$effect(() => {
		const query = { ...params(), area_id: areas.filterId };
		void ui.version;
		const mine = ++sequence;
		state.loading = true;
		api<Task[]>('/tasks', { query })
			.then((tasks) => {
				if (mine === sequence) {
					state.tasks = tasks;
					state.error = null;
				}
			})
			.catch((error: unknown) => {
				if (mine === sequence)
					state.error = error instanceof ApiError ? error.message : t('error.generic');
			})
			.finally(() => {
				if (mine === sequence) state.loading = false;
			});
	});

	return state;
}

function report(error: unknown): void {
	toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
}

async function refreshCounts(): Promise<void> {
	await areas.refresh().catch(() => undefined);
}

export async function toggleTask(task: Task): Promise<void> {
	try {
		if (task.status === 'done') {
			await api<Task>(`/tasks/${task.id}/reopen`, { method: 'POST' });
			ui.changed();
			void refreshCounts();
			return;
		}
		const result = await api<CompleteResult>(`/tasks/${task.id}/complete`, { method: 'POST' });
		ui.changed();
		void refreshCounts();
		toasts.show(t('task.completed'), {
			action: {
				label: t('task.undo'),
				run: async () => {
					await api(`/tasks/${task.id}/reopen`, { method: 'POST' });
					if (result.next) {
						await api(`/tasks/${result.next.id}`, { method: 'DELETE' });
						await api(`/tasks/${task.id}`, {
							method: 'PATCH',
							body: { recurrence: task.recurrence }
						});
					}
					ui.changed();
					void refreshCounts();
				}
			}
		});
	} catch (error) {
		report(error);
	}
}

export async function deleteTask(task: Task): Promise<boolean> {
	try {
		await api(`/tasks/${task.id}`, { method: 'DELETE' });
		ui.changed();
		void refreshCounts();
		toasts.show(t('task.deleted'));
		return true;
	} catch (error) {
		report(error);
		return false;
	}
}

export function groupByDate(tasks: Task[], today: string): { key: string; tasks: Task[] }[] {
	const groups = new Map<string, Task[]>();
	for (const task of tasks) {
		let key = task.due_date ?? 'none';
		if (task.due_date && task.due_date < today) key = 'overdue';
		const bucket = groups.get(key) ?? [];
		bucket.push(task);
		groups.set(key, bucket);
	}
	const keys = [...groups.keys()].sort((a, b) => {
		const rank = (k: string) => (k === 'overdue' ? 0 : k === 'none' ? 2 : 1);
		return rank(a) - rank(b) || a.localeCompare(b);
	});
	return keys.map((key) => ({ key, tasks: groups.get(key) ?? [] }));
}
