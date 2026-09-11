<script lang="ts">
	import { ChevronRight } from '@lucide/svelte';
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n/index.svelte';

	let {
		title,
		count,
		href,
		tone = 'default',
		children
	}: {
		title: string;
		count?: number;
		href?: string;
		tone?: 'default' | 'danger';
		children: Snippet;
	} = $props();

	const uid = $props.id();
</script>

<section
	aria-labelledby="{uid}-title"
	class="flex flex-col rounded-xl border bg-raised p-4 {tone === 'danger'
		? 'border-danger/40'
		: 'border-line'}"
>
	<header class="mb-2 flex items-center justify-between gap-2">
		<h2
			id="{uid}-title"
			class="flex items-center gap-2 text-sm font-semibold {tone === 'danger' ? 'text-danger' : ''}"
		>
			{title}
			{#if count !== undefined}
				<span class="rounded-full bg-surface-2 px-2 text-xs font-medium text-muted">{count}</span>
			{/if}
		</h2>
		{#if href}
			<a {href} class="inline-flex items-center text-xs text-muted hover:text-fg">
				{t('dash.showAll')}<ChevronRight size={14} aria-hidden="true" />
			</a>
		{/if}
	</header>
	{@render children()}
</section>
