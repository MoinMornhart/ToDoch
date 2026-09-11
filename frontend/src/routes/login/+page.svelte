<script lang="ts">
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api';
	import Logo from '$lib/components/Logo.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { session } from '$lib/stores/session.svelte';

	let email = $state('');
	let password = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		busy = true;
		error = null;
		try {
			await session.login(email, password);
			password = '';
			await goto('/today', { replaceState: true });
		} catch (err) {
			error = err instanceof ApiError ? err.message : t('error.generic');
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>{t('login.title')} · Todoch</title></svelte:head>

<main id="main" class="grid min-h-dvh place-items-center px-4">
	<form class="w-full max-w-sm" onsubmit={submit}>
		<p class="mb-4 flex items-center gap-2 text-sm font-semibold tracking-tight">
			<Logo size={28} />Todoch
		</p>
		<h1 class="mb-6 text-2xl font-semibold tracking-tight">{t('login.title')}</h1>
		{#if error}<p role="alert" class="mb-4 text-sm text-danger">{error}</p>{/if}
		<div class="flex flex-col gap-4">
			<div>
				<label class="label" for="email">{t('login.email')}</label>
				<input
					id="email"
					type="email"
					class="input"
					autocomplete="username"
					required
					bind:value={email}
				/>
			</div>
			<div>
				<label class="label" for="password">{t('login.password')}</label>
				<input
					id="password"
					type="password"
					class="input"
					autocomplete="current-password"
					required
					bind:value={password}
				/>
			</div>
			<button type="submit" class="btn btn-primary mt-2 w-full" disabled={busy}>
				{t('login.submit')}
			</button>
		</div>
	</form>
</main>
