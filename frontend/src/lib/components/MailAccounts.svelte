<script lang="ts">
	import { LogIn, MailPlus, RefreshCw, Trash, TriangleAlert } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import {
		guessImap,
		type MailAccountInfo,
		type MailSecurity,
		type OAuthProvider,
		type OAuthProviders
	} from '$lib/mail';
	import { session } from '$lib/stores/session.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';

	let {
		accounts,
		onchange
	}: { accounts: MailAccountInfo[]; onchange: () => void | Promise<void> } = $props();
	const uid = $props.id();

	let email = $state('');
	let password = $state('');
	let host = $state('');
	let port = $state(993);
	let security = $state<MailSecurity>('ssl');
	let username = $state('');
	let hostEdited = $state(false);
	let busy = $state(false);
	let syncing = $state<string | null>(null);
	let confirmId = $state<string | null>(null);
	const guess = $derived(guessImap(email));
	let providers = $state<OAuthProviders>({ google: false, microsoft: false });
	let connecting = $state<OAuthProvider | null>(null);
	const quick = $derived(providers.google || providers.microsoft);

	onMount(async () => {
		try {
			providers = await api<OAuthProviders>('/mail/oauth/providers');
		} catch {
			// ohne Schnellverbindung weiter – das Formular funktioniert immer
		}
	});

	/** Zur Anmeldeseite von Google bzw. Microsoft – zurück geht es nach /mail. */
	async function connect(provider: OAuthProvider) {
		connecting = provider;
		try {
			const { url } = await api<{ url: string }>(`/mail/oauth/${provider}/start`, {
				method: 'POST'
			});
			window.location.assign(url);
		} catch (error) {
			report(error);
			connecting = null;
		}
	}

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	function formatDate(value: string): string {
		return new Intl.DateTimeFormat(i18n.locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
			new Date(value)
		);
	}

	/** Servereinstellungen aus der Adresse vorschlagen, solange sie niemand von Hand geändert hat. */
	function emailChanged(event: Event & { currentTarget: HTMLInputElement }) {
		const found = guessImap(event.currentTarget.value);
		if (found && !hostEdited) {
			host = found.host;
			port = found.port;
			security = found.security;
		}
	}

	async function add(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;
		busy = true;
		try {
			const created = await api<MailAccountInfo>('/mail/accounts', {
				method: 'POST',
				body: {
					email: email.trim(),
					password,
					imap_host: host.trim(),
					imap_port: port,
					security,
					username: username.trim() || undefined
				}
			});
			email = '';
			password = '';
			host = '';
			username = '';
			port = 993;
			security = 'ssl';
			hostEdited = false;
			toasts.show(t('mail.accountAdded', { count: created.message_count }));
			await onchange();
		} catch (error) {
			report(error);
		} finally {
			busy = false;
		}
	}

	async function sync(account: MailAccountInfo) {
		syncing = account.id;
		try {
			const result = await api<MailAccountInfo>(`/mail/accounts/${account.id}/sync`, {
				method: 'POST'
			});
			if (result.last_error) toasts.error(result.last_error);
			else toasts.show(t('mail.synced'));
			await onchange();
		} catch (error) {
			report(error);
		} finally {
			syncing = null;
		}
	}

	async function remove(account: MailAccountInfo) {
		if (confirmId !== account.id) {
			confirmId = account.id;
			return;
		}
		try {
			await api(`/mail/accounts/${account.id}`, { method: 'DELETE' });
			confirmId = null;
			toasts.show(t('mail.removed'));
			await onchange();
		} catch (error) {
			report(error);
		}
	}
</script>

<section aria-labelledby="{uid}-title">
	<h2 id="{uid}-title" class="mb-3 text-base font-semibold">{t('mail.accounts')}</h2>

	{#if accounts.length}
		<ul class="mb-4 flex flex-col divide-y divide-line rounded-xl border border-line bg-raised">
			{#each accounts as account (account.id)}
				<li class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
					<div class="min-w-0">
						<p class="font-medium">
							{account.name}
							<span class="font-normal text-muted">· {account.host}</span>
						</p>
						<p class="text-xs text-muted">
							{t('mail.messages', { count: account.message_count })}
							{#if account.last_success_at}
								· {t('mail.lastSync', { date: formatDate(account.last_success_at) })}
							{/if}
						</p>
						{#if account.last_error}
							<p class="mt-1 flex items-center gap-1 text-xs text-danger" role="alert">
								<TriangleAlert size={12} aria-hidden="true" />{account.last_error}
							</p>
						{/if}
					</div>
					<div class="flex flex-wrap items-center gap-1">
						<button
							type="button"
							class="btn btn-ghost"
							disabled={syncing === account.id}
							onclick={() => sync(account)}
						>
							<RefreshCw size={14} aria-hidden="true" />{t('mail.syncNow')}
						</button>
						<button
							type="button"
							class="btn btn-ghost btn-danger"
							aria-label="{t('mail.remove')}: {account.name}"
							onclick={() => remove(account)}
						>
							<Trash size={14} aria-hidden="true" />
							{confirmId === account.id ? t('mail.removeConfirm') : t('mail.remove')}
						</button>
					</div>
				</li>
			{/each}
		</ul>
	{/if}

	{#if quick}
		<p class="mb-2 text-sm">{t('mail.quickConnect')}</p>
		<div class="mb-5 flex flex-wrap gap-2">
			{#if providers.google}
				<button
					type="button"
					class="btn btn-primary"
					disabled={connecting !== null}
					onclick={() => connect('google')}
				>
					<LogIn size={16} aria-hidden="true" />{t('mail.connectGoogle')}
				</button>
			{/if}
			{#if providers.microsoft}
				<button
					type="button"
					class="btn btn-primary"
					disabled={connecting !== null}
					onclick={() => connect('microsoft')}
				>
					<LogIn size={16} aria-hidden="true" />{t('mail.connectMicrosoft')}
				</button>
			{/if}
		</div>
		<p class="mb-2 text-sm text-muted">{t('mail.orManual')}</p>
	{:else if session.user?.is_admin}
		<p class="mb-4 rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">
			{t('mail.oauthMissing')}
		</p>
	{/if}

	<form class="grid gap-3 sm:grid-cols-2" onsubmit={add}>
		<div>
			<label class="label" for="{uid}-email">{t('mail.email')}</label>
			<input
				id="{uid}-email"
				class="input"
				type="email"
				required
				maxlength="320"
				autocomplete="off"
				bind:value={email}
				oninput={emailChanged}
			/>
		</div>
		<div>
			<label class="label" for="{uid}-password">{t('mail.password')}</label>
			<input
				id="{uid}-password"
				class="input"
				type="password"
				required
				maxlength="500"
				autocomplete="new-password"
				bind:value={password}
			/>
			<p class="mt-1 text-xs text-muted">{t('mail.passwordHint')}</p>
		</div>
		{#if guess?.hint === 'app'}
			<p class="rounded-lg bg-surface-2 px-3 py-2 text-sm sm:col-span-2">
				{t('mail.hintAppPassword')}
			</p>
		{:else if guess?.hint === 'oauth'}
			<p class="rounded-lg bg-surface-2 px-3 py-2 text-sm sm:col-span-2">{t('mail.hintOAuth')}</p>
		{/if}
		<div>
			<label class="label" for="{uid}-host">{t('mail.server')}</label>
			<input
				id="{uid}-host"
				class="input font-mono text-xs"
				required
				maxlength="255"
				autocomplete="off"
				placeholder="imap.example.org"
				bind:value={host}
				oninput={() => (hostEdited = true)}
			/>
		</div>
		<div class="grid grid-cols-2 gap-3">
			<div>
				<label class="label" for="{uid}-port">{t('mail.port')}</label>
				<input
					id="{uid}-port"
					class="input"
					type="number"
					min="1"
					max="65535"
					required
					bind:value={port}
				/>
			</div>
			<div>
				<label class="label" for="{uid}-security">{t('mail.security')}</label>
				<select
					id="{uid}-security"
					class="input"
					bind:value={security}
					onchange={(event) => (port = event.currentTarget.value === 'ssl' ? 993 : 143)}
				>
					<option value="ssl">SSL/TLS</option>
					<option value="starttls">STARTTLS</option>
				</select>
			</div>
		</div>
		<div class="sm:col-span-2">
			<label class="label" for="{uid}-username">{t('mail.username')}</label>
			<input
				id="{uid}-username"
				class="input"
				maxlength="320"
				autocomplete="off"
				bind:value={username}
			/>
		</div>
		<div>
			<button type="submit" class="btn btn-primary" disabled={busy}>
				<MailPlus size={16} aria-hidden="true" />{busy ? t('mail.adding') : t('mail.add')}
			</button>
		</div>
	</form>
</section>
