<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import QuickAdd from '$lib/components/QuickAdd.svelte';
	import TaskList from '$lib/components/TaskList.svelte';
	import { formatDay, todayIn } from '$lib/dates';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { dayLabels } from '$lib/labels';
	import { session } from '$lib/stores/session.svelte';
	import { groupByDate, taskQuery } from '$lib/tasks.svelte';
	import type { TaskSection } from '$lib/types';

	const query = taskQuery(() => ({ view: 'open' }));
	const today = $derived(todayIn(session.user?.timezone ?? 'UTC'));

	function title(key: string): string {
		if (key === 'overdue') return t('date.overdue');
		if (key === 'none') return t('date.none');
		return formatDay(key, today, i18n.locale, dayLabels());
	}

	const sections = $derived(
		groupByDate(query.tasks, today).map((group): TaskSection => ({
			key: group.key,
			title: title(group.key),
			href: group.key.length === 10 ? `/day/${group.key}` : undefined,
			tasks: group.tasks
		}))
	);
</script>

<PageHeader title={t('nav.open')} />
<QuickAdd />
<TaskList
	{sections}
	{today}
	emptyText={t('empty.open')}
	loading={query.loading}
	error={query.error}
/>
