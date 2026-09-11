<script lang="ts">
	import { t } from '$lib/i18n/index.svelte';
	import { areas } from '$lib/stores/areas.svelte';

	const uid = $props.id();
</script>

<div class="flex items-center gap-2">
	<span
		class="size-2.5 shrink-0 rounded-full bg-muted"
		style:background-color={areas.current?.color}
		aria-hidden="true"
	></span>
	<label for="{uid}-area" class="sr-only">{t('area.switch')}</label>
	<select
		id="{uid}-area"
		value={areas.selected}
		onchange={(event) => areas.select(event.currentTarget.value)}
		class="rounded-md border border-line bg-raised py-1 pr-7 pl-2 text-sm"
	>
		<option value="all">{t('area.all')}</option>
		{#each areas.list as area (area.id)}
			<option value={area.id}>{area.name}</option>
		{/each}
	</select>
</div>
