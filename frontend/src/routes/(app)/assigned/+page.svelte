<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import TaskList from '$lib/components/TaskList.svelte';
	import { todayIn } from '$lib/dates';
	import { t } from '$lib/i18n/index.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { taskQuery } from '$lib/tasks.svelte';

	/** Aufgaben aus geteilten Bereichen, für die du zuständig bist. */
	const query = taskQuery(() => ({ view: 'open', assigned: 'me' }));
	const today = $derived(todayIn(session.user?.timezone ?? 'UTC'));
	const sections = $derived([{ key: 'assigned', tasks: query.tasks }]);
</script>

<PageHeader title={t('nav.assigned')} />
<TaskList
	{sections}
	{today}
	emptyText={t('empty.assigned')}
	loading={query.loading}
	error={query.error}
/>
