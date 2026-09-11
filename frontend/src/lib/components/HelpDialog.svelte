<script lang="ts">
	import { t, type MessageKey } from '$lib/i18n/index.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import Dialog from './Dialog.svelte';

	const rows: [string[], MessageKey][] = [
		[['n'], 'help.new'],
		[['/'], 'help.search'],
		[['j'], 'help.next'],
		[['k'], 'help.prev'],
		[['x'], 'help.toggle'],
		[['e'], 'help.edit'],
		[['?'], 'help.help'],
		[['Esc'], 'help.close'],
		[['Strg', 'Enter'], 'help.save'],
		[['c'], 'help.newEvent'],
		[['←', '→'], 'help.calNav'],
		[['m', 'w', 'd', 'a'], 'help.calViews']
	];
</script>

<Dialog bind:open={ui.helpOpen} title={t('help.title')}>
	<dl class="grid grid-cols-[auto_1fr] items-center gap-x-5 gap-y-2.5 text-sm">
		{#each rows as [keys, label] (label)}
			<dt class="flex gap-1">
				{#each keys as key (key)}<kbd>{key}</kbd>{/each}
			</dt>
			<dd>{t(label)}</dd>
		{/each}
	</dl>
</Dialog>
