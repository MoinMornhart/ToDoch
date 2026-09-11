<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import TaskList from '$lib/components/TaskList.svelte';
	import { todayIn } from '$lib/dates';
	import { t } from '$lib/i18n/index.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { taskQuery } from '$lib/tasks.svelte';

	const query = taskQuery(() => ({ view: 'done' }));
	const today = $derived(todayIn(session.user?.timezone ?? 'UTC'));
	const sections = $derived([{ key: 'done', tasks: query.tasks }]);
</script>

<PageHeader title={t('nav.done')} />
<TaskList
	{sections}
	{today}
	emptyText={t('empty.done')}
	loading={query.loading}
	error={query.error}
/>
