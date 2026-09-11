<script lang="ts">
	let { title, subtitle }: { title: string; subtitle?: string } = $props();
</script>

<svelte:head><title>{title} · ToDoch</title></svelte:head>

<header class="mb-5">
	<h1 tabindex="-1" class="text-2xl font-semibold tracking-tight focus:outline-none">{title}</h1>
	{#if subtitle}<p class="mt-0.5 text-sm text-muted">{subtitle}</p>{/if}
</header>
