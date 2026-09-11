<script lang="ts">
	import { KeyRound } from '@lucide/svelte';
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import Logo from '$lib/components/Logo.svelte';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { signInWithPasskey } from '$lib/passkeys';
	import { session } from '$lib/stores/session.svelte';
	import type { User } from '$lib/types';
	import { autofillSupported, isCancelled, passkeysSupported } from '$lib/webauthn';

	const LANGUAGES = [
		['de', 'Deutsch'],
		['en', 'English']
	] as const;

	let email = $state('');
	let password = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);
	let supported = $state(false);
	let autofill: AbortController | null = null;
	let pendingAutofill: Promise<unknown> | null = null;

	// Autofill und Knopf können beide zum Ziel führen – nur die erste Anmeldung zählt
	let finished = false;

	async function done(user: User) {
		if (finished) return;
		finished = true;
		session.signedIn(user);
		password = '';
		await goto('/', { replaceState: true });
	}

	function message(err: unknown): string {
		return err instanceof ApiError ? err.message : t('error.generic');
	}

	onMount(async () => {
		supported = passkeysSupported();
		if (!(await autofillSupported())) return;
		// Passkeys erscheinen im Autofill des E-Mail-Felds – ohne extra Klick
		autofill = new AbortController();
		pendingAutofill = signInWithPasskey({ signal: autofill.signal, conditional: true })
			.then((user) => (user ? done(user) : undefined))
			.catch((err: unknown) => {
				if (!isCancelled(err)) error = message(err);
			});
	});

	onDestroy(() => autofill?.abort());

	async function stopAutofill() {
		autofill?.abort();
		autofill = null;
		await pendingAutofill;
		pendingAutofill = null;
	}

	async function withPasskey() {
		busy = true;
		error = null;
		try {
			await stopAutofill();
			if (finished) return; // schon über den Autofill angemeldet
			const user = await signInWithPasskey();
			if (user) await done(user);
		} catch (err) {
			error = isCancelled(err) ? t('login.passkeyCancelled') : message(err);
		} finally {
			busy = false;
		}
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		busy = true;
		error = null;
		try {
			await stopAutofill();
			const token = await session.login(email, password);
			password = '';
			if (token) {
				// Zwei-Faktor: jetzt noch der Code aus der App
				mfaToken = token;
				code = '';
				return;
			}
			await goto('/', { replaceState: true });
		} catch (err) {
			error = message(err);
		} finally {
			busy = false;
		}
	}

	let mfaToken = $state<string | null>(null);
	let code = $state('');

	async function submitCode(event: SubmitEvent) {
		event.preventDefault();
		if (!mfaToken) return;
		busy = true;
		error = null;
		try {
			const user = await api<User>('/auth/login/totp', {
				method: 'POST',
				body: { mfa_token: mfaToken, code: code.trim() }
			});
			await done(user);
		} catch (err) {
			error = message(err);
			code = '';
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>{t('login.title')} · ToDoch</title></svelte:head>

<main id="main" class="grid min-h-dvh place-items-center px-4">
	<div class="w-full max-w-sm">
		<p class="mb-4 flex items-center gap-2 text-sm font-semibold tracking-tight">
			<Logo size={28} />ToDoch
		</p>
		<h1 class="mb-6 text-2xl font-semibold tracking-tight">{t('login.title')}</h1>
		{#if error}<p role="alert" class="mb-4 text-sm text-danger">{error}</p>{/if}
		{#if mfaToken}
			<form class="flex flex-col gap-4" onsubmit={submitCode}>
				<div>
					<label class="label" for="code">{t('login.codeTitle')}</label>
					<input
						id="code"
						class="input text-center font-mono text-lg tracking-widest"
						autocomplete="one-time-code"
						maxlength="20"
						required
						bind:value={code}
					/>
					<p class="mt-1 text-xs text-muted">{t('login.codeHint')}</p>
				</div>
				<button type="submit" class="btn btn-primary w-full" disabled={busy}>
					{t('login.verify')}
				</button>
				<button type="button" class="btn btn-ghost" onclick={() => (mfaToken = null)}>
					{t('login.back')}
				</button>
			</form>
		{:else}
			{#if supported}
				<button type="button" class="btn btn-primary w-full" disabled={busy} onclick={withPasskey}>
					<KeyRound size={16} aria-hidden="true" />{t('login.passkey')}
				</button>
				<p class="my-5 flex items-center gap-3 text-xs text-muted">
					<span class="h-px flex-1 bg-line"></span>{t('login.or')}<span class="h-px flex-1 bg-line"
					></span>
				</p>
			{/if}
			<form class="flex flex-col gap-4" onsubmit={submit}>
				<div>
					<label class="label" for="email">{t('login.email')}</label>
					<input
						id="email"
						type="email"
						class="input"
						autocomplete="username webauthn"
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
				<button
					type="submit"
					class="btn mt-2 w-full {supported ? '' : 'btn-primary'}"
					disabled={busy}
				>
					{t('login.submit')}
				</button>
			</form>
		{/if}
		<div
			class="mt-8 flex justify-center gap-1 text-xs"
			role="group"
			aria-label={t('login.language')}
		>
			{#each LANGUAGES as [code, label] (code)}
				<button
					type="button"
					lang={code}
					class="rounded-md px-2 py-1 {i18n.locale === code
						? 'bg-surface-2 font-medium text-fg'
						: 'text-muted hover:text-fg'}"
					aria-pressed={i18n.locale === code}
					onclick={() => (i18n.locale = code)}
				>
					{label}
				</button>
			{/each}
		</div>
	</div>
</main>
