<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import QuickAdd from '$lib/components/QuickAdd.svelte';
	import TaskList from '$lib/components/TaskList.svelte';
	import { formatLongDate, todayIn } from '$lib/dates';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { taskQuery } from '$lib/tasks.svelte';
	import type { TaskSection } from '$lib/types';

	const query = taskQuery(() => ({ view: 'today' }));
	const today = $derived(todayIn(session.user?.timezone ?? 'UTC'));

	const sections = $derived.by((): TaskSection[] => {
		const overdue = query.tasks.filter((task) => task.due_date !== null && task.due_date < today);
		const due = query.tasks.filter((task) => !(task.due_date !== null && task.due_date < today));
		return [
			{ key: 'overdue', title: t('date.overdue'), tasks: overdue },
			{ key: 'today', title: overdue.length ? t('date.today') : undefined, tasks: due }
		];
	});
</script>

<PageHeader title={t('nav.today')} subtitle={formatLongDate(today, i18n.locale)} />
<QuickAdd />
<TaskList
	{sections}
	{today}
	emptyText={t('empty.today')}
	loading={query.loading}
	error={query.error}
/>
