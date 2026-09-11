<script lang="ts">
	import { CalendarDays, Clock, Flag, Plus, Repeat, Tag, TriangleAlert } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { formatDay, formatTime, todayIn } from '$lib/dates';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { dayLabels, ruleLabels } from '$lib/labels';
	import { describeRule } from '$lib/recurrence';
	import { areas } from '$lib/stores/areas.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import type { QuickAddPreview, Task } from '$lib/types';
	import AreaIcon from './AreaIcon.svelte';

	const uid = $props.id();
	let text = $state('');
	let preview = $state<QuickAddPreview | null>(null);
	let busy = $state(false);
	let input: HTMLInputElement | undefined = $state();
	let timer: ReturnType<typeof setTimeout> | undefined;
	let sequence = 0;

	const today = $derived(todayIn(session.user?.timezone ?? 'UTC'));
	const previewArea = $derived(preview?.area_id ? areas.byId(preview.area_id) : undefined);

	// Auf schmalen Bildschirmen ein kurzer Platzhalter statt abgeschnittenem Beispiel.
	let narrow = $state(false);

	onMount(() => {
		ui.quickAddMounted = true;
		const media = matchMedia('(max-width: 640px)');
		narrow = media.matches;
		const onChange = (event: MediaQueryListEvent) => (narrow = event.matches);
		media.addEventListener('change', onChange);
		return () => {
			media.removeEventListener('change', onChange);
			ui.quickAddMounted = false;
			clearTimeout(timer);
		};
	});

	$effect(() => {
		if (ui.quickAddPending && input) {
			input.focus();
			ui.quickAddPending = false;
		}
	});

	function schedulePreview() {
		clearTimeout(timer);
		const value = text.trim();
		const mine = ++sequence;
		if (!value) {
			preview = null;
			return;
		}
		timer = setTimeout(async () => {
			try {
				const result = await api<QuickAddPreview>('/tasks/quick/preview', {
					method: 'POST',
					body: { text: value, area_id: areas.filterId }
				});
				if (mine === sequence) preview = result;
			} catch {
				// Die Vorschau ist nur eine Hilfe – Fehler hier nicht melden.
			}
		}, 200);
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		const value = text.trim();
		if (!value || busy) return;
		busy = true;
		const warning =
			preview?.area_unknown && preview.area_name
				? t('quick.unknownArea', {
						name: value.match(/@(\S+)/)?.[1] ?? '',
						fallback: preview.area_name
					})
				: null;
		try {
			await api<Task>('/tasks/quick', {
				method: 'POST',
				body: { text: value, area_id: areas.filterId }
			});
			sequence++;
			text = '';
			preview = null;
			ui.changed();
			void areas.refresh();
			toasts.show(warning ?? t('quick.created'));
		} catch (error) {
			toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
		} finally {
			busy = false;
		}
	}

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			text = '';
			preview = null;
			input?.blur();
		}
	}
</script>

<form class="mb-2" onsubmit={submit}>
	<label for="{uid}-input" class="sr-only">{t('quick.label')}</label>
	<div
		class="flex items-center gap-2 rounded-xl border border-line bg-raised px-3 focus-within:border-accent"
	>
		<Plus size={18} class="shrink-0 text-muted" aria-hidden="true" />
		<input
			id="{uid}-input"
			bind:this={input}
			bind:value={text}
			oninput={schedulePreview}
			onkeydown={onKeydown}
			placeholder={narrow ? t('quick.placeholderShort') : t('quick.placeholder')}
			class="h-11 w-full bg-transparent text-[15px] outline-none placeholder:text-muted"
			autocomplete="off"
			enterkeyhint="done"
			maxlength="500"
			disabled={busy}
		/>
	</div>
	{#if preview && text.trim()}
		<ul class="mt-2 flex flex-wrap gap-1.5 px-1 text-xs" data-testid="quick-preview">
			<li class="chip font-medium">{preview.title}</li>
			{#if preview.due_date}
				<li class="chip">
					<CalendarDays size={12} aria-hidden="true" />
					{formatDay(preview.due_date, today, i18n.locale, dayLabels())}
				</li>
			{/if}
			{#if preview.due_time}
				<li class="chip"><Clock size={12} aria-hidden="true" />{formatTime(preview.due_time)}</li>
			{/if}
			{#if preview.recurrence}
				<li class="chip">
					<Repeat size={12} aria-hidden="true" />
					{describeRule(preview.recurrence, i18n.locale, ruleLabels())}
				</li>
			{/if}
			{#if preview.priority > 0}
				<li class="chip">
					<Flag size={12} aria-hidden="true" />{t(`priority.${preview.priority}`)}
				</li>
			{/if}
			{#each preview.tags as tag (tag)}
				<li class="chip"><Tag size={12} aria-hidden="true" />{tag}</li>
			{/each}
			{#if previewArea}
				<li class="chip">
					<AreaIcon name={previewArea.icon} size={12} />
					{previewArea.name}
					{#if preview.area_unknown}<TriangleAlert
							size={12}
							class="text-warn"
							aria-hidden="true"
						/>{/if}
				</li>
			{/if}
		</ul>
	{/if}
</form>
