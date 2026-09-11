<script lang="ts">
	import { Plus, Trash, X } from '@lucide/svelte';
	import { api, ApiError } from '$lib/api';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import {
		buildRule,
		FREQUENCIES,
		parseRule,
		weekdayName,
		WEEKDAYS,
		type RecurrenceForm,
		type Weekday
	} from '$lib/recurrence';
	import { areas } from '$lib/stores/areas.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import { parseTags } from '$lib/tags';
	import { deleteTask } from '$lib/tasks.svelte';
	import type { Priority, Task } from '$lib/types';
	import Dialog from './Dialog.svelte';

	interface Item {
		key: string;
		id?: string;
		text: string;
		done: boolean;
	}

	interface Form {
		title: string;
		area_id: string;
		due_date: string;
		due_time: string;
		priority: Priority;
		tags: string;
		notes: string;
		recurrence: RecurrenceForm;
		checklist: Item[];
	}

	const PRIORITIES: Priority[] = [0, 1, 2, 3];
	const uid = $props.id();
	let open = $state(false);
	let task = $state<Task | null>(null);
	let form = $state<Form | null>(null);
	let newItem = $state('');
	let saving = $state(false);
	let confirmDelete = $state(false);
	let error = $state<string | null>(null);
	let showPreview = $state(false);
	let keySequence = 0;

	function message(err: unknown): string {
		return err instanceof ApiError ? err.message : t('error.generic');
	}

	function toForm(source: Task): Form {
		return {
			title: source.title,
			area_id: source.area_id,
			due_date: source.due_date ?? '',
			due_time: source.due_time?.slice(0, 5) ?? '',
			priority: source.priority,
			tags: source.tags.join(' '),
			notes: source.notes,
			recurrence: parseRule(source.recurrence),
			checklist: source.checklist.map((item) => ({ ...item, key: `k${keySequence++}` }))
		};
	}

	async function load(id: string) {
		try {
			const loaded = await api<Task>(`/tasks/${id}`);
			if (ui.editTaskId !== id) return;
			task = loaded;
			form = toForm(loaded);
			newItem = '';
			confirmDelete = false;
			error = null;
			showPreview = false;
			open = true;
		} catch (err) {
			toasts.error(message(err));
			ui.editTaskId = null;
		}
	}

	$effect(() => {
		const id = ui.editTaskId;
		if (id) void load(id);
	});

	async function save(event?: Event) {
		event?.preventDefault();
		if (!task || !form || saving) return;
		if (!form.title.trim()) {
			error = t('task.titleRequired');
			return;
		}
		saving = true;
		error = null;
		const pending = newItem.trim();
		const checklist = [
			...form.checklist,
			...(pending ? [{ key: '', text: pending, done: false }] : [])
		]
			.filter((item) => item.text.trim())
			.map((item) => ({ id: item.id, text: item.text.trim(), done: item.done }));
		try {
			await api<Task>(`/tasks/${task.id}`, {
				method: 'PATCH',
				body: {
					title: form.title.trim(),
					area_id: form.area_id,
					due_date: form.due_date || null,
					due_time: form.due_date && form.due_time ? form.due_time : null,
					priority: form.priority,
					tags: parseTags(form.tags),
					notes: form.notes,
					recurrence: buildRule(form.recurrence),
					checklist
				}
			});
			ui.changed();
			void areas.refresh();
			toasts.show(t('task.saved'));
			open = false;
		} catch (err) {
			error = message(err);
		} finally {
			saving = false;
		}
	}

	async function remove() {
		if (!task) return;
		if (!confirmDelete) {
			confirmDelete = true;
			return;
		}
		if (await deleteTask(task)) open = false;
	}

	function addItem() {
		const text = newItem.trim();
		if (!text || !form) return;
		form.checklist.push({ key: `k${keySequence++}`, text, done: false });
		newItem = '';
	}

	function removeItem(key: string) {
		if (form) form.checklist = form.checklist.filter((item) => item.key !== key);
	}

	function toggleWeekday(day: Weekday) {
		if (!form) return;
		const days = form.recurrence.byday;
		form.recurrence.byday = days.includes(day) ? days.filter((d) => d !== day) : [...days, day];
	}

	function onKeydown(event: KeyboardEvent) {
		if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
			event.preventDefault();
			void save();
		}
	}

	function onClose() {
		ui.editTaskId = null;
		task = null;
		form = null;
	}
</script>

<Dialog bind:open title={t('task.edit')} size="lg" onclose={onClose}>
	{#if form && task}
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<form class="flex flex-col gap-4" onsubmit={save} onkeydown={onKeydown}>
			{#if error}<p role="alert" class="text-sm text-danger">{error}</p>{/if}

			<div>
				<label class="label" for="{uid}-title">{t('task.title')}</label>
				<input id="{uid}-title" class="input" bind:value={form.title} maxlength="300" required />
			</div>

			<div class="grid gap-4 sm:grid-cols-3">
				<div>
					<label class="label" for="{uid}-area">{t('task.area')}</label>
					<select id="{uid}-area" class="input" bind:value={form.area_id}>
						{#each areas.list as area (area.id)}
							<option value={area.id}>{area.name}</option>
						{/each}
					</select>
				</div>
				<div>
					<label class="label" for="{uid}-due">{t('task.due')}</label>
					<input id="{uid}-due" type="date" class="input" bind:value={form.due_date} />
				</div>
				<div>
					<label class="label" for="{uid}-time">{t('task.time')}</label>
					<input
						id="{uid}-time"
						type="time"
						class="input"
						bind:value={form.due_time}
						disabled={!form.due_date}
					/>
				</div>
			</div>

			<fieldset>
				<legend class="label">{t('task.priority')}</legend>
				<div class="flex flex-wrap gap-1.5">
					{#each PRIORITIES as priority (priority)}
						<label class="cursor-pointer">
							<input
								type="radio"
								name="{uid}-priority"
								value={priority}
								bind:group={form.priority}
								class="peer sr-only"
							/>
							<span
								class="btn px-3 py-1 peer-checked:border-accent peer-checked:text-accent peer-focus-visible:outline-2 peer-focus-visible:outline-accent"
							>
								{t(`priority.${priority}`)}
							</span>
						</label>
					{/each}
				</div>
			</fieldset>

			<fieldset>
				<legend class="label">{t('task.recurrence')}</legend>
				<div class="flex flex-wrap items-center gap-3">
					<select
						aria-label={t('task.recurrence')}
						class="input w-auto"
						bind:value={form.recurrence.freq}
					>
						<option value="NONE">{t('rec.none')}</option>
						{#each FREQUENCIES as freq (freq)}
							<option value={freq}>{t(`rec.${freq}`)}</option>
						{/each}
					</select>
					{#if form.recurrence.freq !== 'NONE'}
						<label class="flex items-center gap-2 text-sm">
							{t('rec.every')}
							<input
								type="number"
								min="1"
								max="365"
								class="input w-20"
								bind:value={form.recurrence.interval}
							/>
							{t(`rec.unit.${form.recurrence.freq}`)}
						</label>
						<label class="flex items-center gap-2 text-sm">
							{t('rec.until')}
							<input type="date" class="input w-auto" bind:value={form.recurrence.until} />
						</label>
					{/if}
				</div>
				{#if form.recurrence.freq === 'WEEKLY'}
					<div class="mt-2 flex flex-wrap gap-1" role="group" aria-label={t('rec.weekdays')}>
						{#each WEEKDAYS as day (day)}
							<button
								type="button"
								class="btn px-2.5 py-1 {form.recurrence.byday.includes(day)
									? 'border-accent text-accent'
									: ''}"
								aria-pressed={form.recurrence.byday.includes(day)}
								onclick={() => toggleWeekday(day)}
							>
								{weekdayName(day, i18n.locale)}
							</button>
						{/each}
					</div>
				{/if}
			</fieldset>

			<div>
				<label class="label" for="{uid}-tags">{t('task.tags')}</label>
				<input
					id="{uid}-tags"
					class="input"
					bind:value={form.tags}
					aria-describedby="{uid}-tags-hint"
					autocomplete="off"
				/>
				<p id="{uid}-tags-hint" class="mt-1 text-xs text-muted">{t('task.tagsHint')}</p>
			</div>

			<fieldset>
				<legend class="label">{t('task.checklist')}</legend>
				<ul class="flex flex-col gap-1">
					{#each form.checklist as item (item.key)}
						<li class="flex items-center gap-2">
							<input
								type="checkbox"
								bind:checked={item.done}
								aria-label={item.text}
								class="size-4 shrink-0 accent-accent"
							/>
							<input
								class="input py-1"
								bind:value={item.text}
								aria-label={t('task.checklist')}
								maxlength="300"
							/>
							<button
								type="button"
								class="icon-btn shrink-0"
								aria-label={t('task.checklistRemove')}
								onclick={() => removeItem(item.key)}
							>
								<X size={16} aria-hidden="true" />
							</button>
						</li>
					{/each}
				</ul>
				<div class="mt-1 flex items-center gap-2">
					<input
						class="input py-1"
						bind:value={newItem}
						placeholder={t('task.checklistAdd')}
						aria-label={t('task.checklistAdd')}
						maxlength="300"
						onkeydown={(event) => {
							if (event.key === 'Enter' && !event.ctrlKey && !event.metaKey) {
								event.preventDefault();
								addItem();
							}
						}}
					/>
					<button
						type="button"
						class="icon-btn shrink-0"
						aria-label={t('task.checklistAdd')}
						onclick={addItem}
					>
						<Plus size={16} aria-hidden="true" />
					</button>
				</div>
			</fieldset>

			<div>
				<div class="flex items-center justify-between">
					<label class="label" for="{uid}-notes">{t('task.notes')}</label>
					{#if task.notes_html}
						<button
							type="button"
							class="text-xs text-accent"
							aria-pressed={showPreview}
							onclick={() => (showPreview = !showPreview)}
						>
							{t('task.preview')}
						</button>
					{/if}
				</div>
				{#if showPreview}
					<!-- Serverseitig per Allowlist bereinigtes HTML -->
					<div class="prose-notes rounded-lg border border-line p-3 text-sm">
						{@html task.notes_html}
					</div>
				{:else}
					<textarea
						id="{uid}-notes"
						class="input min-h-28"
						bind:value={form.notes}
						maxlength="50000"
						aria-describedby="{uid}-notes-hint"></textarea>
				{/if}
				<p id="{uid}-notes-hint" class="mt-1 text-xs text-muted">{t('task.notesHint')}</p>
			</div>

			<div class="flex items-center justify-between gap-2 border-t border-line pt-4">
				<button type="button" class="btn btn-ghost btn-danger" onclick={remove}>
					<Trash size={16} aria-hidden="true" />
					{confirmDelete ? t('task.deleteConfirm') : t('task.delete')}
				</button>
				<div class="flex gap-2">
					<button type="button" class="btn" onclick={() => (open = false)}
						>{t('task.cancel')}</button
					>
					<button type="submit" class="btn btn-primary" disabled={saving}>{t('task.save')}</button>
				</div>
			</div>
		</form>
	{/if}
</Dialog>
