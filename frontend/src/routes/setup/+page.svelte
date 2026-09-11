<script lang="ts">
	import { onMount } from 'svelte';
	import { goto, replaceState } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import Logo from '$lib/components/Logo.svelte';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { session } from '$lib/stores/session.svelte';
	import type { Locale, User } from '$lib/types';

	const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Berlin';
	const zones = Array.from(new Set([browserZone, ...Intl.supportedValuesOf('timeZone')])).sort();

	let code = $state('');
	let name = $state('');
	let email = $state('');
	let password = $state('');
	let password2 = $state('');
	let timezone = $state(browserZone);
	let locale = $state<Locale>(navigator.language.toLowerCase().startsWith('en') ? 'en' : 'de');
	let error = $state<string | null>(null);
	let busy = $state(false);

	$effect(() => {
		i18n.locale = locale;
	});

	// Der Installer zeigt einen Link wie /setup#code=… – der Fragment-Teil erreicht nie den
	// Server und steht deshalb auch in keinem Log.
	function readCodeFromHash() {
		const fromHash = new URLSearchParams(location.hash.slice(1)).get('code');
		if (fromHash) {
			code = fromHash;
			replaceState(location.pathname, {});
		}
	}

	onMount(readCodeFromHash);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (password !== password2) {
			error = t('setup.mismatch');
			return;
		}
		busy = true;
		error = null;
		try {
			const user = await api<User>('/setup', {
				method: 'POST',
				body: { setup_token: code.trim(), email, display_name: name, password, timezone, locale }
			});
			session.setUser(user);
			await goto('/', { replaceState: true });
		} catch (err) {
			error = err instanceof ApiError ? err.message : t('error.generic');
		} finally {
			busy = false;
		}
	}
</script>

<svelte:window onhashchange={readCodeFromHash} />

<svelte:head><title>{t('setup.title')} · Todoch</title></svelte:head>

<main id="main" class="grid min-h-dvh place-items-center px-4 py-10">
	<form class="w-full max-w-md" onsubmit={submit}>
		<p class="mb-4 flex items-center gap-2 text-sm font-semibold tracking-tight">
			<Logo size={28} />Todoch
		</p>
		<h1 class="mb-2 text-2xl font-semibold tracking-tight">{t('setup.title')}</h1>
		<p class="mb-6 text-sm text-muted">{t('setup.intro')}</p>
		{#if error}<p role="alert" class="mb-4 text-sm text-danger">{error}</p>{/if}
		<div class="flex flex-col gap-4">
			<div>
				<label class="label" for="code">{t('setup.code')}</label>
				<input id="code" class="input font-mono" autocomplete="off" required bind:value={code} />
			</div>
			<div>
				<label class="label" for="name">{t('setup.name')}</label>
				<input
					id="name"
					class="input"
					autocomplete="name"
					required
					maxlength="100"
					bind:value={name}
				/>
			</div>
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
					autocomplete="new-password"
					minlength="12"
					maxlength="256"
					required
					aria-describedby="password-hint"
					bind:value={password}
				/>
				<p id="password-hint" class="mt-1 text-xs text-muted">{t('setup.passwordHint')}</p>
			</div>
			<div>
				<label class="label" for="password2">{t('setup.password2')}</label>
				<input
					id="password2"
					type="password"
					class="input"
					autocomplete="new-password"
					required
					bind:value={password2}
				/>
			</div>
			<div class="grid gap-4 sm:grid-cols-2">
				<div>
					<label class="label" for="timezone">{t('setup.timezone')}</label>
					<select id="timezone" class="input" bind:value={timezone}>
						{#each zones as zone (zone)}<option value={zone}>{zone}</option>{/each}
					</select>
				</div>
				<div>
					<label class="label" for="locale">{t('setup.language')}</label>
					<select id="locale" class="input" bind:value={locale}>
						<option value="de">Deutsch</option>
						<option value="en">English</option>
					</select>
				</div>
			</div>
			<button type="submit" class="btn btn-primary mt-2 w-full" disabled={busy}>
				{t('setup.submit')}
			</button>
		</div>
	</form>
</main>
