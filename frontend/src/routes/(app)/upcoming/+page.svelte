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

	const query = taskQuery(() => ({ view: 'upcoming' }));
	const today = $derived(todayIn(session.user?.timezone ?? 'UTC'));

	const sections = $derived(
		groupByDate(query.tasks, today).map((group): TaskSection => ({
			key: group.key,
			title: formatDay(group.key, today, i18n.locale, dayLabels()),
			href: `/day/${group.key}`,
			tasks: group.tasks
		}))
	);
</script>

<PageHeader title={t('nav.upcoming')} />
<QuickAdd />
<TaskList
	{sections}
	{today}
	emptyText={t('empty.upcoming')}
	loading={query.loading}
	error={query.error}
/>
