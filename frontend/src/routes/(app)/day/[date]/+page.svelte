<script lang="ts">
	import { page } from '$app/state';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import QuickAdd from '$lib/components/QuickAdd.svelte';
	import TaskList from '$lib/components/TaskList.svelte';
	import { formatDay, formatLongDate, isValidIsoDate, todayIn } from '$lib/dates';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { dayLabels } from '$lib/labels';
	import { session } from '$lib/stores/session.svelte';
	import { taskQuery } from '$lib/tasks.svelte';

	const date = $derived(page.params.date ?? '');
	const valid = $derived(isValidIsoDate(date));
	const today = $derived(todayIn(session.user?.timezone ?? 'UTC'));
	const query = taskQuery(() => ({ day: valid ? date : today }));
	const sections = $derived([{ key: date, tasks: query.tasks }]);
</script>

{#if valid}
	<PageHeader
		title={formatDay(date, today, i18n.locale, dayLabels())}
		subtitle={formatLongDate(date, i18n.locale)}
	/>
	<QuickAdd />
	<TaskList
		{sections}
		{today}
		emptyText={t('empty.day')}
		loading={query.loading}
		error={query.error}
	/>
{:else}
	<p class="text-sm text-danger" role="alert">{t('error.generic')}</p>
{/if}
