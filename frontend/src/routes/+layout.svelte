<script lang="ts">
	import '../app.css';
	import { onMount, type Snippet } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import Toasts from '$lib/components/Toasts.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { session } from '$lib/stores/session.svelte';

	let { children }: { children: Snippet } = $props();

	const PUBLIC = ['/login', '/setup'];

	onMount(() => {
		void session.init();
	});

	// Weiterleitung je nach Zustand: Einrichtung, Anmeldung oder App.
	$effect(() => {
		const path = page.url.pathname;
		const status = session.status;
		if (status === 'setup' && path !== '/setup') void goto('/setup', { replaceState: true });
		else if (status === 'anonymous' && path !== '/login')
			void goto('/login', { replaceState: true });
		else if (status === 'ready' && PUBLIC.includes(path)) void goto('/', { replaceState: true });
	});

	const showPage = $derived(
		(session.status === 'ready' && !PUBLIC.includes(page.url.pathname)) ||
			(session.status === 'setup' && page.url.pathname === '/setup') ||
			(session.status === 'anonymous' && page.url.pathname === '/login')
	);
</script>

<a
	href="#main"
	class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-raised focus:px-3 focus:py-2"
>
	{t('app.skip')}
</a>

{#if session.status === 'loading'}
	<p class="grid min-h-dvh place-items-center text-sm text-muted" role="status">
		{t('app.loading')}
	</p>
{:else if session.status === 'error'}
	<div class="grid min-h-dvh place-items-center px-4">
		<div class="text-center">
			<p>{t('app.error')}</p>
			<button type="button" class="btn mt-3" onclick={() => session.init()}>{t('app.retry')}</button
			>
		</div>
	</div>
{:else if showPage}
	{@render children()}
{/if}

<Toasts />
